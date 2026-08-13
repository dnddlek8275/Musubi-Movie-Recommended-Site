from collections import defaultdict
from datetime import datetime, timedelta
from math import log1p
import random
from zoneinfo import ZoneInfo

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session

from app.ai_client.recommend import request_recommend_today_movie
from app.models.daily_ai_recommendation import DailyAiRecommendation, DailyAiRecommendationMovie
from app.models.interactions import MovieRating, MovieWishlist, UserMovieInteraction
from app.models.movies import Movie, MovieGenreWeight, MovieStats
from app.models.users import User
from app.services.movies.overview_utils import shorten_text
from app.services.movies.genre_relevance import (
    GENRE_RELEVANCE_MINIMUM,
    genre_relevance_score,
    load_genre_weight_map,
    weighted_genre_similarity,
)
from app.services.preference_service import (
    canonicalize_keyword,
    get_combined_user_preference_signals,
    keyword_aliases_for,
)

# 추천 흐름
# 배우 한 명의 폭넓은 필모그래피가 추천 목록을 과도하게 확장하지 않도록
# 배우 일치는 장르·키워드를 보조하는 신호로만 사용한다.
PREFERENCE_WEIGHT = {"genre": 3.5, "actor": 0.5, "director": 0.7, "keyword": 2.5}
GUEST_PREFERENCE_WEIGHT = {"genre": 4.0, "actor": 2.0, "keyword": 6.0}
INTEREST_ACTION_WEIGHT = {"view": 0.1, "search_click": 1.5, "like": 3.0}
CONTENT_SIMILARITY_WEIGHTS = {
    "genre": 0.30,
    "keyword": 0.25,
    "cast": 0.15,
    "director": 0.10,
    "locale": 0.08,
    "release": 0.05,
    "runtime": 0.02,
    "rating": 0.05,
}
CONTENT_SIMILARITY_MINIMUM = 0.25
CONTENT_MINIMUM_VOTES = 300
CONTENT_DUPLICATE_GENRE_PENALTY = 0.03
CONTENT_CANDIDATE_POOL_LIMIT = 400
INTERACTED_RECOMMENDATION_MAX_SHARE = 0.33
PREFERENCE_SCORE_SATURATION = 3.0
BEHAVIOR_HALF_LIFE_DAYS = 30.0
DAILY_RECOMMENDATION_GENRES = [
    "액션", "드라마", "코미디", "로맨스", "스릴러",
    "공포", "SF", "판타지", "범죄", "애니메이션",
]

# PREFERENCE_SCORE = {
#     "view": 0.5,
#     "search_click": 0.8,
#     "like": 2.0,
# }

# db 영화 출력
def db_movies_to_response(daily_movies):
    result = []

    for item in sorted(daily_movies, key=lambda row: row.display_order):
        movie = item.movie

        result.append({
            "movie_id": movie.id,
            "tmdb_id": movie.tmdb_id,
            "title": movie.title,
            "year": movie.year,
            "release_date": movie.release_date.isoformat() if movie.release_date else None,
            "genres": ", ".join(movie.genres or []),
            "director": movie.director,
            "cast": ", ".join(movie.cast or []),
            "vote_average": movie.vote_average,
            "overview": shorten_text(movie.overview),
            "poster_url": movie.poster_path,
        })

    return result

# 오늘의 ai 영화 추천
async def get_recommend_today_movie_result(db : Session) :
    # 오늘 추천 DB가 있으면 바로 반환
    today = datetime.now(ZoneInfo("Asia/Seoul")).date()
    daily = db.scalar(
        select(DailyAiRecommendation)
        .where(DailyAiRecommendation.recommend_date == today)
    )
    
    if daily:
        return daily.answer, db_movies_to_response(daily.movies)

    genre = random.choice(DAILY_RECOMMENDATION_GENRES)
    movies = select_daily_genre_movies(db, genre, limit=3)
    if len(movies) < 3:
        raise ValueError(f"{genre} 핵심 장르 영화가 3편 미만입니다.")
    ai_recommend_result = await request_recommend_today_movie(genre, movies)
    answer = ai_recommend_result.get("answer")
    if not answer:
        raise ValueError("AI 추천 문구가 비어 있습니다.")

    daily = save_daily_ai_recommendation(db, today, answer, movies)

    return answer, db_movies_to_response(daily.movies)


def select_daily_genre_movies(
    db: Session,
    genre: str,
    limit: int = 3,
) -> list[dict]:
    """DB에서 핵심 장르 관련도와 품질을 검증한 일일 추천 영화를 고른다."""
    today = datetime.now(ZoneInfo("Asia/Seoul")).date()
    normalized_genre = genre.strip().casefold()
    rows = db.execute(
        select(Movie, MovieStats, MovieGenreWeight.weight)
        .join(
            MovieGenreWeight,
            (MovieGenreWeight.movie_id == Movie.id)
            & (MovieGenreWeight.genre == normalized_genre),
        )
        .outerjoin(MovieStats, MovieStats.movie_id == Movie.id)
        .where(
            MovieGenreWeight.weight >= GENRE_RELEVANCE_MINIMUM,
            Movie.poster_path.is_not(None),
            func.btrim(Movie.poster_path) != "",
            Movie.vote_count >= CONTENT_MINIMUM_VOTES,
            (Movie.release_date.is_(None)) | (Movie.release_date <= today),
        )
        .order_by(
            MovieGenreWeight.weight.desc(),
            Movie.vote_count.desc().nulls_last(),
            Movie.vote_average.desc().nulls_last(),
        )
        .limit(max(limit * 20, 60))
    ).all()
    ranked = sorted(
        rows,
        key=lambda row: (
            (
                2.0
                if row[0].genres
                and row[0].genres[0].strip().casefold() == normalized_genre
                else 0.0
            )
            + float(row[2] or 0) * 4
            + default_score(row[0], row[1]),
            row[0].vote_count or 0,
        ),
        reverse=True,
    )[:limit]
    return [
        {
            "movie_id": movie.id,
            "tmdb_id": movie.tmdb_id,
            "title": movie.title,
            "year": movie.year,
            "release_date": movie.release_date,
            "genres": movie.genres or [],
            "overview": shorten_text(movie.overview),
            "poster_path": movie.poster_path,
            "genre_weight": round(float(weight or 0), 3),
        }
        for movie, _, weight in ranked
    ]

# 사용자 영화 추천 - 기본 추천 기반
def get_user_recommend_movies_result(
        db : Session,
        user_id : int,
        limit : int = 12,
):
    base_movies = get_recommend_movies_result(db, limit=max(limit * 3, 30))
    preferences = [
        preference for preference in get_combined_user_preference_signals(db, user_id)
        if preference.preference_type in PREFERENCE_WEIGHT and abs(preference.score or 0) > 1e-9
    ]
    context = build_behavior_context(db, user_id)
    if not preferences and not context["movie_interest"]:
        return base_movies[:limit]

    top_values: dict[str, list[str]] = defaultdict(list)
    for preference in preferences:
        if preference.score <= 0:
            continue
        if len(top_values[preference.preference_type]) < 30:
            top_values[preference.preference_type].append(preference.preference_value)

    match_filters = []
    if top_values["genre"]:
        match_filters.append(Movie.id.in_(
            select(MovieGenreWeight.movie_id).where(
                MovieGenreWeight.genre.in_(top_values["genre"]),
                MovieGenreWeight.weight >= GENRE_RELEVANCE_MINIMUM,
            )
        ))
    if top_values["actor"]:
        match_filters.append(Movie.cast.op("&&")(top_values["actor"]))
    if top_values["director"]:
        match_filters.append(or_(*[
            func.lower(Movie.director).contains(value.strip().casefold())
            for value in top_values["director"]
            if value.strip()
        ]))
    if top_values["keyword"]:
        keyword_candidates = list(dict.fromkeys(
            alias
            for value in top_values["keyword"]
            for alias in keyword_aliases_for(value)
        ))
        match_filters.append(Movie.keywords.op("&&")(keyword_candidates))
    if context["countries"]:
        match_filters.append(Movie.production_countries.op("&&")(list(context["countries"])))
    if context["movie_interest"]:
        match_filters.append(Movie.id.in_(list(context["movie_interest"])))

    today = datetime.now(ZoneInfo("Asia/Seoul")).date()
    # 초기화는 학습 효과만 끄며, 현재 좋아요 상태와 추천 제외 정책은 유지한다.
    liked_movie_ids = set(db.scalars(
        select(UserMovieInteraction.movie_id).where(
            UserMovieInteraction.user_id == user_id,
            UserMovieInteraction.action_type == "like",
        )
    ).all())
    excluded_movie_ids = (
        liked_movie_ids
        | context["wishlisted_movie_ids"]
        | context["disliked_movie_ids"]
    )
    query = (
        select(Movie, MovieStats)
        .outerjoin(MovieStats, MovieStats.movie_id == Movie.id)
        .where(Movie.poster_path.is_not(None))
        .where((Movie.release_date.is_(None)) | (Movie.release_date <= today))
        .where(~Movie.id.in_(excluded_movie_ids) if excluded_movie_ids else True)
        .order_by(
            case(
                (Movie.id.in_(list(context["movie_interest"])), 1),
                else_=0,
            ).desc(),
            Movie.vote_count.desc().nulls_last(),
            Movie.id.desc(),
        )
        .limit(max(limit * 25, 300))
    )
    if match_filters:
        query = query.where(or_(*match_filters))
    candidates = db.execute(query).all()
    stored_genre_weights = load_genre_weight_map(
        db, [movie.id for movie, _ in candidates]
    )
    global_average = db.scalar(
        select(func.avg(Movie.vote_average)).where(Movie.vote_count >= 50)
    ) or 6.0
    preferences_by_type = {
        preference_type: {
            preference.preference_value.strip().casefold(): preference
            for preference in preferences
            if preference.preference_type == preference_type
            and preference.preference_value.strip()
        }
        for preference_type in PREFERENCE_WEIGHT
    }

    scored = []
    for movie, stats in candidates:
        matched = []
        axis_score = 0.0
        for preference_type, axis_weight in PREFERENCE_WEIGHT.items():
            movie_values = get_movie_preference_values(
                movie, preference_type, stored_genre_weights
            )
            preference_lookup = preferences_by_type[preference_type]
            matches = [
                preference_lookup[value]
                for value in movie_values
                if value in preference_lookup
            ]
            if not matches:
                continue
            normalized_matches = sorted(
                (
                    (
                        preference_confidence(preference)
                        * (
                            get_genre_weight(
                                movie,
                                preference.preference_value,
                                stored_genre_weights,
                            )
                            if preference_type == "genre"
                            else 1.0
                        ),
                        preference,
                    )
                    for preference in matches
                ),
                key=lambda item: item[0],
            )[-3:]
            axis_score += axis_weight * sum(value for value, _ in normalized_matches) / len(normalized_matches)
            matched.extend(
                (value * axis_weight, f"{preference_type}:{preference.preference_value}")
                for value, preference in normalized_matches
            )

        country_score = max(
            (context["countries"].get(code, 0.0) for code in movie.production_countries or []),
            default=0.0,
        )
        language_score = context["languages"].get(movie.language, 0.0) if movie.language else 0.0
        context_score = min(country_score + language_score, 1.0)
        release_score = (
            release_similarity_score(movie, context["average_year"])
            * context["year_confidence"]
        )
        interaction_kind = context["interaction_kind"].get(movie.id)
        interaction_bonus_cap = {"like": 1.2, "wishlist": 0.8, "search_click": 0.6, "view": 0.15}.get(
            interaction_kind, 0.0
        )
        interest_bonus = min(
            context["movie_interest"].get(movie.id, 0.0) * 0.35,
            interaction_bonus_cap,
        )
        quality_score = bayesian_rating(movie, float(global_average), minimum_votes=100) / 10
        score = axis_score + context_score + (release_score * 0.5) + quality_score + interest_bonus
        matched.sort(key=lambda item: item[0], reverse=True)
        matched_labels = [label for _, label in matched]
        reason = (
            "최근 관심을 보인 영화"
            if interest_bonus > 0
            else build_user_recommend_reason(matched_labels)
        )
        scored.append({
            "movie_id": movie.id,
            "title": movie.title,
            "year": movie.year,
            "release_date": movie.release_date,
            "poster_path": movie.poster_path,
            "genres": movie.genres or [],
            "production_countries": movie.production_countries or [],
            "vote_average": movie.vote_average,
            "vote_count": movie.vote_count,
            "recommendation_score": round(score, 3),
            "reason": reason,
            "matched_preferences": matched_labels,
            "_pinned_interest": context["strong_interest"].get(movie.id, 0.0),
            "_interaction_kind": interaction_kind,
            "_is_interacted": movie.id in context["interacted_movie_ids"],
            "_genre_profile": {
                genre.casefold(): get_genre_weight(
                    movie, genre, stored_genre_weights
                )
                for genre in (movie.genres or [])
            },
        })

    return diversify_recommendations(scored, limit) or base_movies[:limit]


def build_behavior_context(db: Session, user_id: int) -> dict:
    """최근 1년 행동에서 국가·언어·개봉 시기와 직접 관심 영화를 계산한다."""
    now = datetime.now(ZoneInfo("Asia/Seoul"))
    cutoff = now - timedelta(days=365)
    user = db.get(User, user_id)
    if user and user.preference_learning_reset_at:
        cutoff = max(cutoff, user.preference_learning_reset_at)
    interaction_query = (
        select(UserMovieInteraction, Movie)
        .join(Movie, Movie.id == UserMovieInteraction.movie_id)
        .where(UserMovieInteraction.user_id == user_id, UserMovieInteraction.created_at >= cutoff)
        .order_by(UserMovieInteraction.created_at.desc())
    )
    rows = db.execute(interaction_query).all()
    seen = set()
    countries: dict[str, float] = defaultdict(float)
    languages: dict[str, float] = defaultdict(float)
    movie_interest: dict[int, float] = defaultdict(float)
    strong_interest: dict[int, float] = defaultdict(float)
    interaction_kind: dict[int, str] = {}
    interacted_movie_ids: set[int] = set()
    year_total = year_weight = 0.0
    for interaction, movie in rows:
        day = interaction.created_at.date() if interaction.created_at else None
        key = (movie.id, interaction.action_type, day)
        if key in seen:
            continue
        seen.add(key)
        age_days = max((now - interaction.created_at).total_seconds() / 86_400, 0.0)
        decay = 0.5 ** (age_days / BEHAVIOR_HALF_LIFE_DAYS)
        weight = INTEREST_ACTION_WEIGHT.get(interaction.action_type, 0.0) * decay
        if not weight:
            continue
        movie_interest[movie.id] += weight
        interacted_movie_ids.add(movie.id)
        current_kind = interaction_kind.get(movie.id)
        priority = {"view": 1, "search_click": 2, "like": 3}
        if current_kind is None or priority[interaction.action_type] > priority[current_kind]:
            interaction_kind[movie.id] = interaction.action_type
        if interaction.action_type in {"search_click", "like"}:
            strong_interest[movie.id] += weight
        country_values = movie.production_countries or []
        for country in country_values:
            countries[country] += weight / len(country_values)
        if movie.language:
            languages[movie.language] += weight
        movie_year = movie.release_date.year if movie.release_date else movie.year
        if movie_year:
            year_total += movie_year * weight
            year_weight += weight

    wishlist_query = (
        select(MovieWishlist, Movie)
        .join(Movie, Movie.id == MovieWishlist.movie_id)
        .where(MovieWishlist.user_id == user_id, MovieWishlist.created_at >= cutoff)
    )
    wishlisted_movie_ids: set[int] = set()
    for wishlist, movie in db.execute(wishlist_query).all():
        age_days = max((now - wishlist.created_at).total_seconds() / 86_400, 0.0)
        weight = 2.0 * (0.5 ** (age_days / BEHAVIOR_HALF_LIFE_DAYS))
        movie_interest[movie.id] += weight
        strong_interest[movie.id] += weight
        interacted_movie_ids.add(movie.id)
        wishlisted_movie_ids.add(movie.id)
        interaction_kind.setdefault(movie.id, "wishlist")

    rating_query = (
        select(MovieRating)
        .where(MovieRating.user_id == user_id, MovieRating.updated_at >= cutoff)
    )
    disliked_movie_ids = {
        rating.movie_id for rating in db.scalars(rating_query).all()
        if float(rating.score) <= 2.0
    }

    def normalize(values):
        # 보조 취향도 상대 최고점이 아니라 절대 행동량에 따라 점차 포화시킨다.
        return {
            key: value / (value + PREFERENCE_SCORE_SATURATION)
            for key, value in values.items()
            if value > 0
        }

    return {
        "countries": normalize(countries),
        "languages": normalize(languages),
        "movie_interest": dict(movie_interest),
        "strong_interest": dict(strong_interest),
        "interaction_kind": interaction_kind,
        "interacted_movie_ids": interacted_movie_ids,
        "wishlisted_movie_ids": wishlisted_movie_ids,
        "disliked_movie_ids": disliked_movie_ids,
        "average_year": year_total / year_weight if year_weight else None,
        "year_confidence": year_weight / (year_weight + PREFERENCE_SCORE_SATURATION) if year_weight else 0.0,
    }


def preference_confidence(preference) -> float:
    """상대 최고점 대신 절대 점수에 포화 함수를 적용한다."""
    behavior_score = float(getattr(preference, "behavior_score", preference.score) or 0.0)
    behavior_confidence = behavior_score / (abs(behavior_score) + PREFERENCE_SCORE_SATURATION)
    if not getattr(preference, "explicit", False):
        return behavior_confidence
    # 직접 선택은 강한 신호로 유지하되 이후 행동이 최대 25% 범위에서 보정한다.
    return max(min(0.75 + (0.25 * behavior_confidence), 1.0), 0.5)


def bayesian_rating(movie: Movie, global_average: float = 6.0, minimum_votes: int = 100) -> float:
    rating = movie.vote_average or global_average
    votes = max(movie.vote_count or 0, 0)
    return (votes / (votes + minimum_votes)) * rating + (minimum_votes / (votes + minimum_votes)) * global_average


def _normalized_values(values) -> set[str]:
    return {
        str(value).strip().casefold()
        for value in (values or [])
        if str(value).strip()
    }


def _jaccard_similarity(left, right) -> float | None:
    left_values = _normalized_values(left)
    right_values = _normalized_values(right)
    if not left_values or not right_values:
        return None
    return len(left_values & right_values) / len(left_values | right_values)


def _exact_similarity(left, right) -> float | None:
    left_value = str(left or "").strip().casefold()
    right_value = str(right or "").strip().casefold()
    if not left_value or not right_value:
        return None
    return 1.0 if left_value == right_value else 0.0


def _release_similarity(source: Movie, candidate: Movie) -> float | None:
    source_year = source.release_date.year if source.release_date else source.year
    candidate_year = candidate.release_date.year if candidate.release_date else candidate.year
    if source_year is None or candidate_year is None:
        return None
    return 1.0 / (1.0 + abs(source_year - candidate_year) / 5.0)


def _runtime_similarity(source: Movie, candidate: Movie) -> float | None:
    if not source.runtime or not candidate.runtime:
        return None
    return 1.0 / (1.0 + abs(source.runtime - candidate.runtime) / 30.0)


def _locale_similarity(source: Movie, candidate: Movie) -> float | None:
    values = [
        value
        for value in (
            _jaccard_similarity(source.production_countries, candidate.production_countries),
            _exact_similarity(source.language, candidate.language),
        )
        if value is not None
    ]
    return sum(values) / len(values) if values else None


def calculate_content_similarity(source: Movie, candidate: Movie, global_average: float) -> tuple[float, dict[str, float]]:
    components = {
        "genre": weighted_genre_similarity(source, candidate),
        "keyword": _jaccard_similarity(source.keywords, candidate.keywords),
        "cast": _jaccard_similarity(source.cast, candidate.cast),
        "director": _exact_similarity(source.director, candidate.director),
        "locale": _locale_similarity(source, candidate),
        "release": _release_similarity(source, candidate),
        "runtime": _runtime_similarity(source, candidate),
        "rating": (
            bayesian_rating(candidate, global_average, minimum_votes=100) / 10.0
            if (candidate.vote_average or 0) > 0
            and (candidate.vote_count or 0) >= CONTENT_MINIMUM_VOTES
            else None
        ),
    }
    available = {
        name: value
        for name, value in components.items()
        if value is not None
    }
    if not available:
        return 0.0, {}
    score = sum(
        CONTENT_SIMILARITY_WEIGHTS[name] * value
        for name, value in available.items()
    )
    return score, available


def _shared_content(source: Movie, candidate: Movie) -> dict:
    shared_genres = {
        genre.casefold()
        for genre in (source.genres or [])
        if genre_relevance_score(source, genre) >= GENRE_RELEVANCE_MINIMUM
    } & {
        genre.casefold()
        for genre in (candidate.genres or [])
        if genre_relevance_score(candidate, genre) >= GENRE_RELEVANCE_MINIMUM
    }
    shared_keywords = _normalized_values(source.keywords) & _normalized_values(candidate.keywords)
    shared_cast = _normalized_values(source.cast) & _normalized_values(candidate.cast)
    same_director = _exact_similarity(source.director, candidate.director) == 1.0
    shared_superhero_keywords = {
        keyword
        for keyword in shared_keywords
        if "슈퍼히어로" in keyword or "superhero" in keyword or "super hero" in keyword
    }
    return {
        "genre_count": len(shared_genres),
        "keyword_count": len(shared_keywords),
        "cast_count": len(shared_cast),
        "same_director": same_director,
        "strong_relation": bool(same_director or shared_cast or shared_superhero_keywords),
    }


def qualifies_content_candidate(source: Movie, candidate: Movie) -> tuple[bool, dict]:
    shared = _shared_content(source, candidate)
    has_content_match = (
        shared["genre_count"] >= 2
        or shared["keyword_count"] >= 1
        or shared["cast_count"] >= 1
        or shared["same_director"]
    )
    has_enough_votes = (candidate.vote_count or 0) >= CONTENT_MINIMUM_VOTES
    return has_content_match and (has_enough_votes or shared["strong_relation"]), shared


def rank_content_recommendations(candidates: list[dict], limit: int) -> list[dict]:
    remaining = sorted(candidates, key=lambda item: item["similarity_score"], reverse=True)
    selected: list[dict] = []
    while remaining and len(selected) < limit:
        def adjusted_score(item: dict) -> float:
            item_genres = _normalized_values(item.get("genres"))
            duplicate_similarity = max(
                (
                    len(item_genres & _normalized_values(chosen.get("genres")))
                    / max(len(item_genres | _normalized_values(chosen.get("genres"))), 1)
                    for chosen in selected
                ),
                default=0.0,
            )
            return item["similarity_score"] - CONTENT_DUPLICATE_GENRE_PENALTY * duplicate_similarity

        chosen = max(remaining, key=adjusted_score)
        selected.append(chosen)
        remaining.remove(chosen)
    return selected


def get_similar_movies_result(
    db: Session,
    movie_id: int,
    limit: int = 6,
    user_id: int | None = None,
) -> list[dict] | None:
    source = db.scalar(select(Movie).where(Movie.id == movie_id))
    if source is None:
        return None

    match_filters = []
    source_genres = [
        genre for genre in (source.genres or [])
        if genre_relevance_score(source, genre) >= GENRE_RELEVANCE_MINIMUM
    ]
    if source_genres:
        match_filters.append(Movie.id.in_(
            select(MovieGenreWeight.movie_id).where(
                MovieGenreWeight.genre.in_(source_genres),
                MovieGenreWeight.weight >= GENRE_RELEVANCE_MINIMUM,
            )
        ))
    if source.keywords:
        match_filters.append(Movie.keywords.op("&&")(source.keywords))
    if source.cast:
        match_filters.append(Movie.cast.op("&&")(source.cast))
    if source.director and source.director.strip():
        match_filters.append(func.lower(Movie.director) == source.director.strip().lower())
    if not match_filters:
        return []

    strong_relation_filters = []
    if source.cast:
        strong_relation_filters.append(Movie.cast.op("&&")(source.cast))
    if source.director and source.director.strip():
        strong_relation_filters.append(
            func.lower(Movie.director) == source.director.strip().lower()
        )
    superhero_keywords = [
        keyword
        for keyword in (source.keywords or [])
        if "슈퍼히어로" in keyword.casefold()
        or "superhero" in keyword.casefold()
        or "super hero" in keyword.casefold()
    ]
    if superhero_keywords:
        strong_relation_filters.append(Movie.keywords.op("&&")(superhero_keywords))

    vote_filter = Movie.vote_count >= CONTENT_MINIMUM_VOTES
    if strong_relation_filters:
        vote_filter = or_(vote_filter, *strong_relation_filters)

    today = datetime.now(ZoneInfo("Asia/Seoul")).date()
    liked_movie_ids = set()
    if user_id is not None:
        liked_movie_ids = set(db.scalars(
            select(UserMovieInteraction.movie_id).where(
                UserMovieInteraction.user_id == user_id,
                UserMovieInteraction.action_type == "like",
            )
        ).all())
    candidates = db.scalars(
        select(Movie)
        .where(Movie.id != movie_id)
        .where(~Movie.id.in_(liked_movie_ids) if liked_movie_ids else True)
        .where(Movie.poster_path.is_not(None), func.btrim(Movie.poster_path) != "")
        .where(
            or_(
                Movie.release_date <= today,
                and_(Movie.release_date.is_(None), Movie.year.is_not(None), Movie.year <= today.year),
            )
        )
        .where(or_(*match_filters))
        .where(vote_filter)
        # 전체 영화 행을 Python으로 가져와 점수 계산하던 병목을 제한한다.
        # 충분한 후보 다양성을 유지하면서 우선 검토할 고신뢰 후보만 읽는다.
        .order_by(Movie.vote_count.desc().nullslast(), Movie.vote_average.desc().nullslast(), Movie.id.asc())
        .limit(CONTENT_CANDIDATE_POOL_LIMIT)
    ).all()

    global_average = float(
        db.scalar(select(func.avg(Movie.vote_average)).where(Movie.vote_count >= 50)) or 6.0
    )
    scored = []
    for candidate in candidates:
        is_candidate, shared = qualifies_content_candidate(source, candidate)
        if not is_candidate:
            continue
        content_score, components = calculate_content_similarity(source, candidate, global_average)
        if content_score < CONTENT_SIMILARITY_MINIMUM:
            continue
        scored.append({
            "movie_id": candidate.id,
            "title": candidate.title,
            "year": candidate.year,
            "release_date": candidate.release_date,
            "poster_path": candidate.poster_path,
            "genres": candidate.genres or [],
            "vote_average": candidate.vote_average,
            "vote_count": candidate.vote_count,
            "similarity_score": round(content_score, 4),
            "similarity_components": {
                name: round(value, 4)
                for name, value in components.items()
            },
        })

    return rank_content_recommendations(scored, min(limit, 6))


def release_similarity_score(movie: Movie, preferred_year: float | None) -> float:
    movie_year = movie.release_date.year if movie.release_date else movie.year
    if preferred_year is None or movie_year is None:
        return 0.0
    return max(0.0, 1.0 - abs(movie_year - preferred_year) / 10.0)


def diversify_recommendations(candidates: list[dict], limit: int) -> list[dict]:
    """좋아한 작품은 유지하되 행동 작품 독점과 동일 장르 반복을 제한한다."""
    remaining = sorted(candidates, key=lambda item: item["recommendation_score"], reverse=True)
    selected: list[dict] = []
    interacted_limit = max(1, round(limit * INTERACTED_RECOMMENDATION_MAX_SHARE))
    interacted_count = 0

    def profile_similarity(left: dict, right: dict) -> float:
        keys = set(left) | set(right)
        if not keys:
            return 0.0
        denominator = sum(max(left.get(key, 0.0), right.get(key, 0.0)) for key in keys)
        if not denominator:
            return 0.0
        return sum(min(left.get(key, 0.0), right.get(key, 0.0)) for key in keys) / denominator

    def genre_profile(item: dict) -> dict[str, float]:
        stored = item.get("_genre_profile")
        if stored:
            return stored
        return {
            str(genre).strip().casefold(): 1.0
            for genre in (item.get("genres") or [])
            if str(genre).strip()
        }

    while remaining and len(selected) < limit:
        eligible = [
            item for item in remaining
            if not item.get("_is_interacted") or interacted_count < interacted_limit
        ]
        if not eligible:
            eligible = remaining

        def adjusted(item):
            similarity = max(
                (
                    profile_similarity(
                        genre_profile(item),
                        genre_profile(chosen),
                    )
                    for chosen in selected
                ),
                default=0.0,
            )
            interaction_priority = {"like": 0.35, "search_click": 0.1, "view": 0.0}.get(
                item.get("_interaction_kind"), 0.0
            )
            return item["recommendation_score"] + interaction_priority - (similarity * 0.6)

        best = max(eligible, key=adjusted)
        selected.append(best)
        remaining.remove(best)
        if best.get("_is_interacted"):
            interacted_count += 1
    for item in selected:
        item.pop("_pinned_interest", None)
        item.pop("_interaction_kind", None)
        item.pop("_is_interacted", None)
        item.pop("_genre_profile", None)
    return selected


def get_guest_recommend_movies_result(
        db: Session,
        genres: list[str],
        actors: list[str],
        keywords: list[str],
        limit: int = 12,
):
    """서버 계정이 없는 비회원의 명시적 취향으로 현재 요청만 개인화한다."""
    normalized_preferences = {
        "genre": [value.strip() for value in genres if isinstance(value, str) and value.strip()],
        "actor": [value.strip() for value in actors if isinstance(value, str) and value.strip()],
        "keyword": list(dict.fromkeys(
            canonicalize_keyword(value)
            for value in keywords
            if isinstance(value, str) and value.strip()
        )),
    }

    match_filters = []
    match_priority_parts = []
    if normalized_preferences["genre"]:
        genre_match = Movie.id.in_(
            select(MovieGenreWeight.movie_id).where(
                MovieGenreWeight.genre.in_(normalized_preferences["genre"]),
                MovieGenreWeight.weight >= GENRE_RELEVANCE_MINIMUM,
            )
        )
        match_filters.append(genre_match)
        match_priority_parts.append(
            case((genre_match, GUEST_PREFERENCE_WEIGHT["genre"]), else_=0)
        )
    if normalized_preferences["actor"]:
        actor_match = Movie.cast.op("&&")(normalized_preferences["actor"])
        match_filters.append(actor_match)
        match_priority_parts.append(
            case((actor_match, GUEST_PREFERENCE_WEIGHT["actor"]), else_=0)
        )
    if normalized_preferences["keyword"]:
        keyword_candidates = list(dict.fromkeys(
            alias
            for value in normalized_preferences["keyword"]
            for alias in keyword_aliases_for(value)
        ))
        keyword_match = Movie.keywords.op("&&")(keyword_candidates)
        match_filters.append(keyword_match)
        match_priority_parts.append(
            case((keyword_match, GUEST_PREFERENCE_WEIGHT["keyword"]), else_=0)
        )

    if not match_filters:
        return get_recommend_movies_result(db, limit)

    match_priority = sum(match_priority_parts)
    candidate_limit = max(limit * 20, 120)
    candidate_query = (
        select(Movie, MovieStats)
        .outerjoin(MovieStats, MovieStats.movie_id == Movie.id)
        .where(Movie.poster_path.is_not(None))
        .where(
            (Movie.release_date.is_(None))
            | (Movie.release_date <= datetime.now(ZoneInfo("Asia/Seoul")).date())
        )
        .where(or_(*match_filters))
        .order_by(
            match_priority.desc(),
            func.coalesce(MovieStats.ranking_score, 0).desc(),
            Movie.vote_count.desc().nulls_last(),
            Movie.vote_average.desc().nulls_last(),
            Movie.id.desc(),
        )
        .limit(candidate_limit)
    )

    candidate_rows = db.execute(candidate_query).all()
    stored_genre_weights = load_genre_weight_map(
        db, [movie.id for movie, _ in candidate_rows]
    )
    result = []
    for movie, stats in candidate_rows:
        base_score = default_score(movie, stats)
        preference_score = 0.0
        matched = []

        for preference_type, values in normalized_preferences.items():
            movie_values = get_movie_preference_values(
                movie, preference_type, stored_genre_weights
            )
            for value in values:
                if value.casefold() not in movie_values:
                    continue
                contribution = GUEST_PREFERENCE_WEIGHT.get(preference_type, 0.0)
                if preference_type == "genre":
                    contribution *= get_genre_weight(
                        movie,
                        value,
                        stored_genre_weights,
                    )
                preference_score += contribution
                matched.append((contribution, f"{preference_type}:{value}"))

        matched.sort(key=lambda item: item[0], reverse=True)
        matched_labels = [label for _, label in matched]
        result.append({
            "movie_id": movie.id,
            "title": movie.title,
            "year": movie.year,
            "release_date": movie.release_date,
            "poster_path": movie.poster_path,
            "genres": movie.genres or [],
            "vote_average": movie.vote_average,
            "recommendation_score": round(preference_score + base_score, 3),
            "preference_match_score": preference_score,
            "reason": build_user_recommend_reason(matched_labels),
            "matched_preferences": matched_labels,
        })

    result.sort(
        key=lambda item: (
            item["preference_match_score"],
            item["recommendation_score"],
        ),
        reverse=True,
    )
    return result[:limit] if result else get_recommend_movies_result(db, limit)
    


# 기본 영화 추천 - 메인 페이지에 보여줄 기본 추천 목록
def get_recommend_movies_result(db : Session, limit : int = 12,):

    candidate_limit = max(limit * 4, 40)

    recommend_result = (
        select(Movie, MovieStats)
        # 통계에 없는 영화도 포함
        .outerjoin(MovieStats, MovieStats.movie_id == Movie.id)
        # 포스터 없는 경우 추천 안함
        .where(Movie.poster_path.is_not(None))
        .where(
            (Movie.release_date.is_(None))
            | (Movie.release_date <= datetime.now(ZoneInfo("Asia/Seoul")).date())
        )
        .order_by(
            func.coalesce(MovieStats.ranking_score, 0).desc(),
            Movie.vote_count.desc().nulls_last(),
            Movie.vote_average.desc().nulls_last(),
            Movie.id.desc(),
        )
        .limit(candidate_limit)
    )

    result_movies = []

    for movie, stats in db.execute(recommend_result).all():
        # 랭킹, 평점, 투표수, 등록 최신성 함께 반영
        score = default_score(movie, stats)

        result_movies.append(
            {
                "movie_id" : movie.id,
                "title" : movie.title,
                "year" : movie.year,
                "release_date" : movie.release_date,
                "poster_path" : movie.poster_path,
                "genres" : movie.genres or [],
                "vote_average" : movie.vote_average,
                "recommendation_score" : round(score, 3),
                "reason" : build_default_reason(movie, stats),
            }
        )

    # 직접 계산한 추천 점수 기준으로 다시 정령 - 실시간 랭킹이랑 안겹침
    result_movies.sort(key=lambda item:item["recommendation_score"], reverse=True)

    return result_movies[:limit]

# 기본 영화 - 추천 이유 생성
def build_default_reason(movie: Movie, stats : MovieStats | None):
    
    if stats and stats.ranking_score > 0:
        return "최근 조회수 높은 영화 추천"
    if movie.vote_average and movie.vote_average >=7:
        return "평점 높은 영화 추천"
    if movie.vote_count and movie.vote_count>=1000:
        return "인기 있는 영화 추천"
    return "가볍게 둘러보기 좋은 영화 추천"

# 사용자 기반 - 추천 이유 생성
def build_user_recommend_reason(matched : list[str]):
    if not matched:
        return "인기와 평점 기준으로 추천"
    
    # 가장 먼저 매칭된 취향을 대표 추천 이유로 사용
    preference_type, value = matched[0].split(":", 1)

    label = {
        "genre": "좋아하는 장르",
        "actor": "관심 있는 배우",
        "director": "선호하는 감독",
        "keyword": "관심 키워드",
        "language": "선호 언어",
        "character": "좋아하는 캐릭터",
    }.get(preference_type, "취향")

    return f"{label} '{value}'와 잘 맞는 영화"

# 점수 반영
def default_score(movie : Movie, stats : MovieStats | None) :
    # 소수 사용자의 반복 행동과 소수 투표 10점이 추천을 독점하지 않도록
    # 서비스 랭킹은 로그로 완화하고 TMDB 평점은 베이지안 보정을 적용한다.
    ranking_score = log1p(max(stats.ranking_score if stats else 0, 0)) * 0.2
    vote_score = bayesian_rating(movie, global_average=6.0, minimum_votes=100) * 0.8
    vote_count_score = log1p(movie.vote_count or 0) * 0.15

    # 최신성
    recent_score = calculate_release_date_recency_score(movie)
    
    return ranking_score + vote_score + vote_count_score + recent_score

# 최신 점수 반영
def calculate_release_date_recency_score(movie: Movie, today=None) -> float:
    """실제 개봉일 기준 최신성 점수(개봉 후 1년 동안 최대 0.5점)를 계산한다."""
    if movie.release_date is None:
        return 0.0

    today = today or datetime.now(ZoneInfo("Asia/Seoul")).date()
    days_since_release = (today - movie.release_date).days

    # 미래 개봉작 또는 개봉 후 1년이 지난 작품에는 최신 가산점을 주지 않는다.
    if days_since_release < 0 or days_since_release >= 365:
        return 0.0

    return (1 - (days_since_release / 365)) * 0.5


def save_daily_ai_recommendation(
        db : Session,
        recommend_date,
        answer : str,
        movies : list[dict],
) -> DailyAiRecommendation:
    daily = DailyAiRecommendation(
        recommend_date = recommend_date, 
        answer = answer
    )

    db.add(daily)
    # 임시 저장 daily.id 반환하기 위해
    db.flush()

    display_order = 1
    for movie in movies[:3]:
        raw_tmdb_id = movie.get("tmdb_id")
        if not raw_tmdb_id:
            continue
        tmdb_id = int(raw_tmdb_id)
        db_movie = db.scalar(select(Movie).where(Movie.tmdb_id == tmdb_id))

        if db_movie is None:
            continue

        daily_movie = DailyAiRecommendationMovie(
            daily_recommendation_id = daily.id,
            movie_id = db_movie.id,
            display_order = display_order
        )

        db.add(daily_movie)
        display_order += 1

    if display_order <= 3:
        raise ValueError("검증된 일일 추천 영화를 3편 모두 저장하지 못했습니다.")
    db.flush()
    db.commit()
    db.refresh(daily)

    return daily
# 영화 취향값 가져오는 함수
def get_movie_preference_values(
        movie,
        preference_type : str,
        stored_genre_weights: dict[tuple[int, str], float] | None = None,
):
    if preference_type == "genre":
        values = [
            genre for genre in (movie.genres or [])
            if get_genre_weight(movie, genre, stored_genre_weights)
            >= GENRE_RELEVANCE_MINIMUM
        ]
    elif preference_type == "actor":
        values = movie.cast or []
    elif preference_type == "director":
        values = [
            value.strip()
            for value in str(movie.director or "").split(",")
            if value.strip()
        ]
    elif preference_type == "keyword":
        values = [canonicalize_keyword(value) for value in (movie.keywords or [])]
    elif preference_type == "language":
        values = [movie.language] if movie.language else []
    else:
        values = []

    return {
        value.strip().casefold() # 문자열 앞뒤 공백 제거, 대소문자 차지 없애서 비교하기 쉽게 만드는 형태
        for value in values
        if isinstance(value, str) and value.strip()
    }


def get_genre_weight(
    movie,
    genre: str,
    stored_genre_weights: dict[tuple[int, str], float] | None = None,
) -> float:
    key = (movie.id, genre.strip().casefold())
    if stored_genre_weights is not None and key in stored_genre_weights:
        return stored_genre_weights[key]
    return genre_relevance_score(movie, genre)
