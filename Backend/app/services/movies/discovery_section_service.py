from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.interactions import UserMovieInteraction
from app.models.movies import Movie, MovieGenreWeight, MovieStats
from app.services.movies.box_office_service import latest_box_office_rows
from app.services.movies.genre_relevance import GENRE_RELEVANCE_MINIMUM
from app.services.movies.recommendation_service import (
    get_guest_recommend_movies_result,
    get_user_recommend_movies_result,
)
from app.services.preference_service import (
    canonicalize_keyword,
    get_combined_user_preference_signals,
    keyword_aliases_for,
)


SECTION_LIMIT = 25
RANDOM_MINIMUM_VOTES = 300

# MovieChart 박스오피스(2026-08-05 조회, 영화진흥위원회 제공) 순서 중
# 제목과 연도·개봉 정보로 현재 movies DB에서 확인된 작품만 유지한다.
# 첫 번째 값은 원본 순위이며 화면 순위는 누락 작품을 제외한 뒤 1부터 다시 매긴다.
CURRENT_BOX_OFFICE = [
    (1, 196),   # 스파이더맨: 브랜드 뉴 데이
    (2, 969),   # 호프
    (3, 168),   # 미니언즈 & 몬스터즈
    (4, 161),   # 토이 스토리 5
    (5, 750),   # 모아나 (2026)
    (6, 451),   # 다윗
    (9, 203),   # 오디세이
    (14, 427),  # 마티 슈프림
    (19, 314),  # 호컴
    (20, 379),  # 군체
]


def _movie_payload(movie: Movie, *, rank: int | None = None) -> dict:
    return {
        "movie_id": movie.id,
        "title": movie.title,
        "poster_path": movie.poster_path,
        "genres": movie.genres or [],
        "vote_average": movie.vote_average,
        "vote_count": movie.vote_count,
        "year": movie.year,
        "release_date": movie.release_date,
        "rank": rank,
    }


def _released_display_filter():
    today = datetime.now(ZoneInfo("Asia/Seoul")).date()
    return (
        Movie.poster_path.is_not(None),
        func.btrim(Movie.poster_path) != "",
        or_(
            Movie.release_date <= today,
            Movie.release_date.is_(None),
        ),
    )


def _popular_order():
    return (
        func.coalesce(MovieStats.ranking_score, 0).desc(),
        func.coalesce(MovieStats.view_count, 0).desc(),
        func.coalesce(MovieStats.like_count, 0).desc(),
        func.coalesce(MovieStats.search_click_count, 0).desc(),
        Movie.vote_count.desc().nulls_last(),
        Movie.vote_average.desc().nulls_last(),
        Movie.id.desc(),
    )


def _movies_for_preference(
    db: Session,
    preference_type: str,
    values: list[str],
    limit: int,
    exclude_movie_ids: set[int] | None = None,
) -> list[dict]:
    normalized = list(dict.fromkeys(value.strip() for value in values if value and value.strip()))
    if preference_type == "keyword":
        normalized = list(dict.fromkeys(
            alias
            for value in normalized
            for alias in keyword_aliases_for(value)
        ))
    if not normalized:
        return []

    column = {
        "genre": Movie.genres,
        "actor": Movie.cast,
        "keyword": Movie.keywords,
    }.get(preference_type)
    if column is None:
        return []

    statement = (
        select(Movie)
        .outerjoin(MovieStats, MovieStats.movie_id == Movie.id)
        .where(*_released_display_filter())
        .where(column.op("&&")(normalized))
    )
    if exclude_movie_ids:
        statement = statement.where(~Movie.id.in_(exclude_movie_ids))
    if preference_type == "genre":
        genre_weight = (
            select(func.max(MovieGenreWeight.weight))
            .where(
                MovieGenreWeight.movie_id == Movie.id,
                MovieGenreWeight.genre.in_(normalized),
            )
            .correlate(Movie)
            .scalar_subquery()
        )
        statement = statement.where(
            func.coalesce(genre_weight, 0.0) >= GENRE_RELEVANCE_MINIMUM
        ).order_by(genre_weight.desc(), *_popular_order())
    else:
        statement = statement.order_by(*_popular_order())

    movies = db.scalars(statement.limit(limit)).all()
    return [_movie_payload(movie) for movie in movies]


def _preference_items(db: Session, user_id: int | None, guest_preferences) -> list[dict]:
    if user_id is not None:
        return [
            {
                "type": item.preference_type,
                "value": item.preference_value,
                "score": float(item.score or 0),
            }
            for item in get_combined_user_preference_signals(db, user_id)
            if item.preference_type in {"genre", "actor", "keyword"}
            and item.preference_value
            and (item.score or 0) > 0
        ]

    if guest_preferences is None:
        return []
    ordered = []
    for preference_type, values in (
        ("genre", guest_preferences.genres),
        ("keyword", guest_preferences.keywords),
        ("actor", guest_preferences.actors),
    ):
        for value in values:
            if value and value.strip():
                normalized_value = (
                    canonicalize_keyword(value)
                    if preference_type == "keyword"
                    else value.strip()
                )
                ordered.append({"type": preference_type, "value": normalized_value, "score": 1.0})
    return ordered


def _box_office_section(db: Session) -> dict:
    daily_rows = latest_box_office_rows(db)
    if daily_rows:
        display_rows = [
            row
            for row in daily_rows
            if row.movie is not None
            and row.movie.poster_path is not None
            and row.movie.poster_path.strip()
        ]
        movies = [
            _movie_payload(row.movie, rank=display_rank)
            for display_rank, row in enumerate(display_rows, start=1)
        ]
        return {
            "key": "box-office",
            "title": "박스오피스 순위",
            "box_office_date": daily_rows[0].box_office_date,
            "movies": movies,
        }

    source_rank_by_id = {movie_id: rank for rank, movie_id in CURRENT_BOX_OFFICE}
    movies_by_id = {
        movie.id: movie
        for movie in db.scalars(
            select(Movie).where(
                Movie.id.in_(source_rank_by_id),
                Movie.poster_path.is_not(None),
                func.btrim(Movie.poster_path) != "",
            )
        ).all()
    }
    matched_box_office = [
        (source_rank, movie_id)
        for source_rank, movie_id in CURRENT_BOX_OFFICE
        if movie_id in movies_by_id
    ]
    movies = [
        _movie_payload(movies_by_id[movie_id], rank=display_rank)
        for display_rank, (_, movie_id) in enumerate(matched_box_office, start=1)
    ]
    return {
        "key": "box-office",
        "title": "박스오피스 순위",
        "box_office_date": None,
        "movies": movies,
    }


def _recent_likes_section(db: Session, user_id: int | None, limit: int) -> dict:
    movies = []
    if user_id is not None:
        latest_liked_at = func.max(UserMovieInteraction.created_at).label(
            "latest_liked_at"
        )
        rows = db.execute(
            select(Movie, latest_liked_at)
            .join(UserMovieInteraction, UserMovieInteraction.movie_id == Movie.id)
            .where(
                UserMovieInteraction.user_id == user_id,
                UserMovieInteraction.action_type == "like",
                *_released_display_filter(),
            )
            .group_by(Movie.id)
            .order_by(latest_liked_at.desc(), Movie.id.desc())
            .limit(limit)
        ).all()
        movies = [dict(_movie_payload(movie), liked_at=liked_at) for movie, liked_at in rows]
    return {
        "key": "recent-likes",
        "title": "최근 좋아요한 영화",
        "movies": movies,
    }


def _site_popular_section(
    db: Session,
    limit: int,
    exclude_movie_ids: set[int] | None = None,
) -> dict:
    active = or_(
        MovieStats.view_count > 0,
        MovieStats.search_click_count > 0,
        MovieStats.like_count > 0,
        MovieStats.ranking_score > 0,
    )
    statement = (
        select(Movie)
        .join(MovieStats, MovieStats.movie_id == Movie.id)
        .where(*_released_display_filter(), active)
        .order_by(*_popular_order())
    )
    if exclude_movie_ids:
        statement = statement.where(~Movie.id.in_(exclude_movie_ids))
    movies = db.scalars(statement.limit(limit)).all()
    return {
        "key": "site-popular",
        "title": "Musubi 전체 인기 영화",
        "movies": [_movie_payload(movie) for movie in movies],
    }


def _random_section(
    db: Session,
    limit: int,
    exclude_movie_ids: set[int] | None = None,
) -> dict:
    statement = (
        select(Movie)
        .where(*_released_display_filter(), Movie.vote_count >= RANDOM_MINIMUM_VOTES)
        .order_by(func.random())
    )
    if exclude_movie_ids:
        statement = statement.where(~Movie.id.in_(exclude_movie_ids))
    movies = db.scalars(statement.limit(limit)).all()
    return {
        "key": "random-picks",
        "title": "우연히 만난 영화가 인생 영화가 될지도 몰라요",
        "movies": [_movie_payload(movie) for movie in movies],
    }


def get_discovery_sections_result(
    db: Session,
    user_id: int | None,
    guest_preferences=None,
    limit: int = SECTION_LIMIT,
) -> list[dict]:
    limit = min(max(limit, 1), SECTION_LIMIT)
    preferences = _preference_items(db, user_id, guest_preferences)
    liked_movie_ids: set[int] = set()
    if user_id is not None:
        liked_movie_ids = set(db.scalars(
            select(UserMovieInteraction.movie_id).where(
                UserMovieInteraction.user_id == user_id,
                UserMovieInteraction.action_type == "like",
            )
        ).all())

    personalized_movies = []
    if user_id is not None:
        personalized_movies = get_user_recommend_movies_result(db, user_id, min(limit, 12))
    elif guest_preferences is not None:
        personalized_movies = get_guest_recommend_movies_result(
            db,
            guest_preferences.genres,
            guest_preferences.actors,
            guest_preferences.keywords,
            min(limit, 12),
        )
    sections = [_box_office_section(db)]
    if personalized_movies:
        sections.append({
            "key": "for-you",
            "title": "개인화 추천",
            "movies": personalized_movies,
        })
    sections.append(_recent_likes_section(db, user_id, limit))

    for index, preference in enumerate(preferences[:3], start=1):
        sections.append({
            "key": f"preference-{index}",
            "title": f"{index}순위 취향 · {preference['value']}",
            "preference_type": preference["type"],
            "preference_value": preference["value"],
            "movies": _movies_for_preference(
                db,
                preference["type"],
                [preference["value"]],
                limit,
                liked_movie_ids,
            ),
        })

    actor_values = [item["value"] for item in preferences if item["type"] == "actor"]
    sections.extend([
        {
            "key": "preferred-actors",
            "title": "선호 배우 영화",
            "movies": _movies_for_preference(
                db, "actor", actor_values, limit, liked_movie_ids
            ),
        },
        _site_popular_section(db, limit, liked_movie_ids),
        _random_section(db, limit, liked_movie_ids),
    ])
    return sections
