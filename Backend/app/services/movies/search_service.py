import re

from sqlalchemy import and_, case, func, literal, or_, select
from sqlalchemy.orm import Session

from app.models.actors import Actor, MovieActor
from app.models.movies import Movie, MovieGenre, MovieGenreWeight
from app.models.users import User
from app.services.actor_name_policy import actor_display_name
from app.services.movies.genre_relevance import (
    GENRE_KEYWORD_SIGNALS,
    GENRE_RELEVANCE_MINIMUM,
    genre_relevance_score,
)


COUNTRY_ALIASES = {
    "한국": "KR", "대한민국": "KR", "일본": "JP", "미국": "US", "영국": "GB",
    "프랑스": "FR", "중국": "CN", "홍콩": "HK", "대만": "TW", "캐나다": "CA",
    "독일": "DE", "이탈리아": "IT", "스페인": "ES",
}
ROMANCE_RELATED_TERMS = (
    "로맨스", "연애", "첫사랑", "사랑", "결혼", "이별", "연인",
    "romance", "love", "first love", "dating", "wedding", "marriage", "breakup",
)
ROMANCE_NEGATIVE_TERMS = ("액션", "전쟁", "범죄", "action", "war", "crime")
SEARCH_STOP_WORDS = {"영화", "작품", "관련", "추천", "같은", "비슷한"}

# DB 컬럼/SQL 표현식을 검색용으로 정규화
# lower: 대소문자 차이 제거
# coalesce: NULL 값을 빈 문자열로 처리
# regexp_replace: 모든 공백 제거
def normalize_search_expr(column):
    return func.regexp_replace(func.lower(func.coalesce(column, "")), r"\s+", "", "g")


def search_suggestions_result(
        db: Session,
        search_keyword: str,
        limit: int = 8,
):
    """Return distinct, prefix-matched terms from the same metadata used by movie search."""
    keyword = (search_keyword or "").strip()
    normalized_keyword = re.sub(r"\s+", "", keyword.lower())
    if not normalized_keyword:
        return {"state": "success", "message": "검색어 자동완성", "data": []}

    prefix_pattern = f"{normalized_keyword}%"
    per_source_limit = max(limit * 2, 12)

    title_value = normalize_search_expr(Movie.title)
    title_completion_score = (
        func.ln(func.max(func.coalesce(Movie.vote_count, 0)) + 1)
        - (func.char_length(title_value) - len(normalized_keyword)) * 0.45
    )
    title_rows = db.execute(
        select(Movie.title)
        .where(title_value.ilike(prefix_pattern))
        .group_by(Movie.title)
        .order_by(
            case((title_value == normalized_keyword, 0), else_=1),
            title_completion_score.desc(),
            Movie.title.asc(),
        )
        .limit(per_source_limit)
    ).scalars().all()

    suggestions = []
    seen = set()

    def add_suggestions(source, values):
        for value in values:
            text = str(value or "").strip()
            normalized_text = re.sub(r"\s+", "", text.lower())
            if not text or normalized_text in seen:
                continue
            seen.add(normalized_text)
            suggestions.append({"text": text, "type": source})
            if len(suggestions) >= limit:
                return True
        return False

    if add_suggestions("영화", title_rows):
        return {"state": "success", "message": "검색어 자동완성", "data": suggestions}

    actor_rows = db.execute(
        select(Actor.name)
        .where(normalize_search_expr(Actor.name).ilike(prefix_pattern))
        .order_by(Actor.name.asc())
        .limit(per_source_limit)
    ).scalars().all()

    director_rows = db.execute(
        select(Movie.director)
        .where(
            Movie.director.is_not(None),
            normalize_search_expr(Movie.director).ilike(prefix_pattern),
        )
        .distinct()
        .order_by(Movie.director.asc())
        .limit(per_source_limit)
    ).scalars().all()
    if add_suggestions("감독", director_rows):
        return {"state": "success", "message": "검색어 자동완성", "data": suggestions}
    if add_suggestions("배우", actor_rows):
        return {"state": "success", "message": "검색어 자동완성", "data": suggestions}

    genre_rows = db.execute(
        select(MovieGenre.genre)
        .where(normalize_search_expr(MovieGenre.genre).ilike(prefix_pattern))
        .distinct()
        .order_by(MovieGenre.genre.asc())
        .limit(per_source_limit)
    ).scalars().all()
    if add_suggestions("장르", genre_rows):
        return {"state": "success", "message": "검색어 자동완성", "data": suggestions}

    keyword_values = (
        select(func.unnest(Movie.keywords).label("value"))
        .where(Movie.keywords.is_not(None))
        .subquery()
    )
    keyword_rows = db.execute(
        select(keyword_values.c.value)
        .where(normalize_search_expr(keyword_values.c.value).ilike(prefix_pattern))
        .distinct()
        .order_by(keyword_values.c.value.asc())
        .limit(per_source_limit)
    ).scalars().all()
    add_suggestions("키워드", keyword_rows)

    return {
        "state": "success",
        "message": "검색어 자동완성",
        "data": suggestions,
    }

# 영화 검색 기능 구현
def _normalized_text(value) -> str:
    return re.sub(r"\s+", "", str(value or "").strip().casefold())


def _recent_movie_rows(
        db: Session,
        condition,
        limit: int,
        page: int = 1,
        excluded_ids: set[int] | None = None,
):
    statement = select(Movie).where(condition)
    excluded_ids = excluded_ids or set()
    if excluded_ids:
        statement = statement.where(Movie.id.not_in(excluded_ids))
    offset = 0 if excluded_ids else (max(page, 1) - 1) * limit
    rows = db.scalars(
        statement
        .order_by(
            Movie.release_date.desc().nullslast(),
            Movie.year.desc().nullslast(),
            func.coalesce(Movie.vote_count, 0).desc(),
            Movie.title.asc(),
        )
        .offset(offset)
        .limit(limit + 1)
    ).all()
    return rows[:limit], len(rows) > limit


def search_movie_sections_result(
        db: Session,
        search_keyword: str,
        limit: int = 20,
        search_type: str | None = None,
        category: str | None = None,
        page: int = 1,
        exclude_ids: list[int] | None = None,
):
    """검색 필드별 영화 섹션을 최신 개봉일순으로 반환한다."""
    raw_keyword = (search_keyword or "").strip()
    if not raw_keyword:
        return {"state": "failure", "message": "검색어를 입력해주세요."}

    normalized_query = _normalized_text(raw_keyword)
    if not normalized_query:
        return {"state": "failure", "message": "검색어를 입력해주세요."}

    pattern = f"%{normalized_query}%"
    title_expr = normalize_search_expr(Movie.title)
    director_expr = normalize_search_expr(Movie.director)
    overview_expr = normalize_search_expr(Movie.overview)
    actor_name_expr = normalize_search_expr(Actor.name)
    actor_korean_name_expr = normalize_search_expr(Actor.korean_name)
    actor_original_name_expr = normalize_search_expr(Actor.original_name)

    title_condition = title_expr.ilike(pattern)
    title_exact = db.scalar(select(Movie.id).where(title_expr == normalized_query).limit(1)) is not None

    matched_actors = db.scalars(
        select(Actor)
        .where(or_(
            actor_name_expr.ilike(pattern),
            actor_korean_name_expr.ilike(pattern),
            actor_original_name_expr.ilike(pattern),
        ))
        .order_by(
            case((actor_name_expr == normalized_query, 0), else_=1),
            Actor.name.asc(),
            Actor.id.asc(),
        )
    ).all()
    actor_ids = [actor.id for actor in matched_actors]
    actor_condition = (
        Movie.id.in_(select(MovieActor.movie_id).where(MovieActor.actor_id.in_(actor_ids)))
        if actor_ids else None
    )
    actor_exact = any(
        normalized_query in {
            _normalized_text(actor.name),
            _normalized_text(actor.korean_name),
            _normalized_text(actor.original_name),
        }
        for actor in matched_actors
    )

    matched_directors = db.scalars(
        select(Movie.director)
        .where(Movie.director.is_not(None), director_expr.ilike(pattern))
        .distinct()
        .order_by(Movie.director.asc())
    ).all()
    director_condition = director_expr.ilike(pattern) if matched_directors else None
    director_exact = any(_normalized_text(value) == normalized_query for value in matched_directors)

    matched_genres = db.scalars(
        select(MovieGenre.genre)
        .where(normalize_search_expr(MovieGenre.genre).ilike(pattern))
        .distinct()
        .order_by(MovieGenre.genre.asc())
    ).all()
    genre_condition = (
        Movie.id.in_(select(MovieGenre.movie_id).where(MovieGenre.genre.in_(matched_genres)))
        if matched_genres else None
    )
    genre_exact = any(_normalized_text(value) == normalized_query for value in matched_genres)

    keyword_values = (
        select(func.unnest(Movie.keywords).label("value"))
        .where(Movie.keywords.is_not(None))
        .subquery()
    )
    matched_keywords = db.scalars(
        select(keyword_values.c.value)
        .where(normalize_search_expr(keyword_values.c.value).ilike(pattern))
        .distinct()
        .order_by(keyword_values.c.value.asc())
    ).all()
    keyword_condition = Movie.keywords.op("&&")(matched_keywords) if matched_keywords else None
    keyword_exact = any(_normalized_text(value) == normalized_query for value in matched_keywords)

    related_condition = overview_expr.ilike(pattern)
    requested_type = {
        "영화": "title", "movie": "title", "title": "title",
        "배우": "actor", "actor": "actor",
        "감독": "director", "director": "director",
        "장르": "genre", "genre": "genre",
        "키워드": "keyword", "keyword": "keyword",
    }.get(str(search_type or "").strip().casefold())
    requested_category = str(category or "").strip().casefold()
    allowed_categories = {"title", "actor", "director", "genre", "keyword", "related"}
    if requested_category and requested_category not in allowed_categories:
        requested_category = ""

    specs = [
        {
            "type": "title", "title": "영화 제목", "condition": title_condition,
            "exact": title_exact, "matches": [raw_keyword],
        },
        {
            "type": "actor", "title": f"{raw_keyword} 출연 영화", "condition": actor_condition,
            "exact": actor_exact,
            "matches": [
                {"id": actor.id, "tmdb_actor_id": actor.tmdb_actor_id, "name": actor_display_name(actor),
                 "profile_path": actor.profile_path}
                for actor in matched_actors
            ],
        },
        {
            "type": "director", "title": f"{raw_keyword} 감독 영화", "condition": director_condition,
            "exact": director_exact, "matches": matched_directors,
        },
        {
            "type": "genre", "title": f"{raw_keyword} 장르 영화", "condition": genre_condition,
            "exact": genre_exact, "matches": matched_genres,
        },
        {
            "type": "keyword", "title": f"{raw_keyword} 키워드 영화", "condition": keyword_condition,
            "exact": keyword_exact, "matches": matched_keywords,
        },
        {
            "type": "related", "title": "관련 영화", "condition": related_condition,
            "exact": False, "matches": [],
        },
    ]
    base_order = {spec["type"]: index for index, spec in enumerate(specs)}
    specs.sort(key=lambda spec: (
        0 if spec["type"] == requested_type else 1,
        0 if spec["exact"] else 1,
        base_order[spec["type"]],
    ))

    if requested_category:
        specs = [spec for spec in specs if spec["type"] == requested_category]

    sections = []
    used_ids: set[int] = set(exclude_ids or [])
    for spec in specs:
        if spec["condition"] is None:
            continue
        movies, has_more = _recent_movie_rows(
            db,
            spec["condition"],
            limit,
            page,
            used_ids,
        )
        if not movies:
            continue
        used_ids.update(movie.id for movie in movies)
        sections.append({
            "key": f"search-{spec['type']}",
            "type": spec["type"],
            "title": spec["title"],
            "matches": spec["matches"],
            "movies": [get_movie_result(movie) for movie in movies],
            "page": page,
            "has_more": has_more,
        })

    if not sections:
        return {"state": "failure", "message": "관련 영화 정보가 없습니다.", "data": {"sections": []}}
    return {
        "state": "success",
        "message": "카테고리별 검색 성공",
        "data": {"query": raw_keyword, "sections": sections},
    }


def search_movies_result(
        db: Session,
        search_keyword: str,
        page: int = 1,
        limit: int = 80,
        search_type: str | None = None,
        user_id: int | None = None,
):
    raw_keyword = (search_keyword or "").strip()
    if not raw_keyword:
        return {"state": "failure", "message": "검색어를 입력해주세요."}

    query = raw_keyword.casefold()
    normalized_query = _normalized_text(query)
    type_aliases = {
        "영화": "movie", "movie": "movie", "장르": "genre", "genre": "genre",
        "배우": "actor", "actor": "actor", "키워드": "keyword", "keyword": "keyword",
        "감독": "director", "director": "director",
    }
    requested_type = type_aliases.get(str(search_type or "").strip().casefold())

    all_genres = db.scalars(select(MovieGenre.genre).distinct()).all()
    matched_genres = sorted(
        {
            genre for genre in all_genres
            if genre and _normalized_text(genre) in normalized_query
        },
        key=len,
        reverse=True,
    )
    exact_genre = next(
        (genre for genre in matched_genres if _normalized_text(genre) == normalized_query),
        None,
    )
    exact_actor = db.scalar(
        select(Actor).where(or_(
            normalize_search_expr(Actor.name) == normalized_query,
            normalize_search_expr(Actor.korean_name) == normalized_query,
            normalize_search_expr(Actor.original_name) == normalized_query,
        )).limit(1)
    )
    exact_director = db.scalar(
        select(Movie.director)
        .where(Movie.director.is_not(None), normalize_search_expr(Movie.director) == normalized_query)
        .limit(1)
    )
    keyword_values = (
        select(func.unnest(Movie.keywords).label("value"))
        .where(Movie.keywords.is_not(None))
        .subquery()
    )
    meaningful_tokens = [
        token.casefold() for token in re.findall(r"[0-9a-zA-Z가-힣]+", query)
        if token.casefold() not in SEARCH_STOP_WORDS
    ]
    exact_keyword = db.scalar(
        select(keyword_values.c.value)
        .where(
            normalize_search_expr(keyword_values.c.value).in_(
                list(dict.fromkeys([normalized_query, *map(_normalized_text, meaningful_tokens)]))
            )
        )
        .limit(1)
    )

    similar_match = re.match(r"^(.+?)(?:와|과)?\s*(?:같은|비슷한)\s*영화$", raw_keyword)
    source_movie = None
    if similar_match:
        source_text = _normalized_text(similar_match.group(1))
        source_movie = db.scalar(
            select(Movie)
            .where(normalize_search_expr(Movie.title).ilike(f"%{source_text}%"))
            .order_by(
                case((normalize_search_expr(Movie.title) == source_text, 0), else_=1),
                func.coalesce(Movie.vote_count, 0).desc(),
            )
            .limit(1)
        )

    detected_type = "similar" if source_movie else requested_type
    if detected_type is None:
        if exact_genre:
            detected_type = "genre"
        elif exact_director:
            detected_type = "director"
        elif exact_actor:
            detected_type = "actor"
        elif exact_keyword:
            detected_type = "keyword"
        else:
            detected_type = "mixed"

    country_codes = list(dict.fromkeys(
        code for label, code in COUNTRY_ALIASES.items() if label in query
    ))
    decade_match = re.search(r"((?:19|20)\d0)년대", query)
    year_match = re.search(r"((?:19|20)\d{2})년(?!대)", query)

    semantic_terms = [
        token for token in meaningful_tokens
        if token not in COUNTRY_ALIASES
        and not re.fullmatch(r"(?:19|20)\d{2}년?대?", token)
        and all(_normalized_text(genre) != _normalized_text(token) for genre in matched_genres)
    ]
    if "로맨스" in matched_genres:
        semantic_terms = [*ROMANCE_RELATED_TERMS, *semantic_terms]
    elif matched_genres:
        genre_signals = [
            signal
            for genre in matched_genres
            for signal in GENRE_KEYWORD_SIGNALS.get(genre.casefold(), ())
        ]
        semantic_terms = [*genre_signals, *semantic_terms]
    elif exact_keyword:
        semantic_terms = [str(exact_keyword), *semantic_terms]
    semantic_terms = list(dict.fromkeys(term.casefold() for term in semantic_terms if term))

    title_expr = normalize_search_expr(Movie.title)
    cast_expr = normalize_search_expr(func.array_to_string(Movie.cast, " "))
    director_expr = normalize_search_expr(Movie.director)
    keyword_expr = normalize_search_expr(func.array_to_string(Movie.keywords, " "))
    overview_expr = normalize_search_expr(Movie.overview)
    title_condition = Movie.title.ilike(f"%{query}%")
    semantic_keyword_conditions = []
    semantic_overview_conditions = []
    for term in semantic_terms:
        semantic_keyword_conditions.append(Movie.keywords.any(term))
        semantic_overview_conditions.append(Movie.overview.ilike(f"%{term}%"))
    semantic_conditions = [*semantic_keyword_conditions, *semantic_overview_conditions]

    tagged_genre_condition = (
        Movie.genres.op("&&")(matched_genres)
        if matched_genres else None
    )
    genre_weight = None
    genre_condition = tagged_genre_condition
    if matched_genres:
        genre_weight = (
            select(func.max(MovieGenreWeight.weight))
            .where(
                MovieGenreWeight.movie_id == Movie.id,
                func.lower(MovieGenreWeight.genre).in_([genre.casefold() for genre in matched_genres]),
            )
            .correlate(Movie)
            .scalar_subquery()
        )
        genre_condition = and_(
            tagged_genre_condition,
            func.coalesce(genre_weight, 0.0) >= GENRE_RELEVANCE_MINIMUM,
        )
    candidate_conditions = [title_condition]
    if genre_condition is not None:
        candidate_conditions.append(genre_condition)
    candidate_conditions.extend(semantic_conditions)

    if detected_type == "genre" and genre_condition is not None:
        candidate_filter = genre_condition
    elif detected_type == "actor" and exact_actor:
        candidate_filter = Movie.id.in_(
            select(MovieActor.movie_id).where(MovieActor.actor_id == exact_actor.id)
        )
    elif detected_type == "director" and exact_director:
        candidate_filter = Movie.director == exact_director
    elif detected_type == "keyword" and exact_keyword:
        candidate_filter = or_(Movie.keywords.any(exact_keyword), *semantic_conditions, title_condition)
    elif source_movie:
        similarity_conditions = []
        source_genres = [
            genre for genre in (source_movie.genres or [])
            if genre_relevance_score(source_movie, genre) >= GENRE_RELEVANCE_MINIMUM
        ]
        if source_genres:
            similarity_conditions.append(Movie.id.in_(
                select(MovieGenreWeight.movie_id).where(
                    MovieGenreWeight.genre.in_(source_genres),
                    MovieGenreWeight.weight >= GENRE_RELEVANCE_MINIMUM,
                )
            ))
        if source_movie.keywords:
            similarity_conditions.append(Movie.keywords.op("&&")(source_movie.keywords))
        if source_movie.cast:
            similarity_conditions.append(Movie.cast.op("&&")(source_movie.cast))
        if source_movie.director:
            similarity_conditions.append(Movie.director == source_movie.director)
        candidate_filter = and_(
            Movie.id != source_movie.id,
            or_(*similarity_conditions) if similarity_conditions else Movie.id == -1,
        )
    else:
        generic_pattern = f"%{normalized_query}%"
        candidate_conditions.extend((
            cast_expr.ilike(generic_pattern),
            director_expr.ilike(generic_pattern),
            keyword_expr.ilike(generic_pattern),
            overview_expr.ilike(generic_pattern),
        ))
        candidate_filter = or_(*candidate_conditions)

    structured_filters = []
    if country_codes:
        structured_filters.append(Movie.production_countries.op("&&")(country_codes))
    if decade_match:
        decade = int(decade_match.group(1))
        structured_filters.extend((Movie.year >= decade, Movie.year <= decade + 9))
    elif year_match:
        structured_filters.append(Movie.year == int(year_match.group(1)))
    if structured_filters:
        if genre_condition is not None:
            structured_filters.append(genre_condition)
        candidate_filter = and_(*structured_filters)

    title_exact = title_expr == normalized_query
    keyword_hit_count = sum(
        (case((condition, 1.0), else_=0.0) for condition in semantic_keyword_conditions),
        0.0,
    )
    overview_hit_count = sum(
        (case((condition, 1.0), else_=0.0) for condition in semantic_overview_conditions),
        0.0,
    )
    semantic_keyword_match = (
        or_(*semantic_keyword_conditions) if semantic_keyword_conditions else Movie.keywords.any(query)
    )
    semantic_overview_match = (
        or_(*semantic_overview_conditions) if semantic_overview_conditions else Movie.overview.ilike(f"%{query}%")
    )
    actor_match = cast_expr.ilike(f"%{normalized_query}%")
    director_match = director_expr.ilike(f"%{normalized_query}%")

    primary_genre = (
        and_(
            genre_condition,
            or_(
                func.cardinality(Movie.genres) == 1,
                keyword_hit_count >= 2,
                and_(func.coalesce(genre_weight, 0.0) >= 0.8, func.coalesce(genre_weight, 0.0) < 1.0),
            ),
        )
        if genre_condition is not None
        else None
    )

    source_signal = 0.0
    if source_movie:
        source_genres = [
            genre for genre in (source_movie.genres or [])
            if genre_relevance_score(source_movie, genre) >= GENRE_RELEVANCE_MINIMUM
        ]
        if source_genres:
            source_signal += case((Movie.id.in_(
                select(MovieGenreWeight.movie_id).where(
                    MovieGenreWeight.genre.in_(source_genres),
                    MovieGenreWeight.weight >= GENRE_RELEVANCE_MINIMUM,
                )
            ), 7.0), else_=0.0)
        if source_movie.keywords:
            source_signal += case((Movie.keywords.op("&&")(source_movie.keywords), 6.0), else_=0.0)
        if source_movie.cast:
            source_signal += case((Movie.cast.op("&&")(source_movie.cast), 4.0), else_=0.0)
        if source_movie.director:
            source_signal += case((Movie.director == source_movie.director, 3.0), else_=0.0)

    if source_movie:
        intent_bucket = case((source_signal > 0, 0), else_=9)
        match_score = func.least(source_signal * 3.5, 70.0)
        content_score = func.least(source_signal, 20.0)
    elif detected_type == "actor" and exact_actor:
        intent_bucket = case((actor_match, 0), else_=9)
        match_score = case((actor_match, 70.0), else_=0.0)
        content_score = case((actor_match, 12.0), else_=0.0)
    elif detected_type == "director" and exact_director:
        intent_bucket = case((director_match, 0), else_=9)
        match_score = case((director_match, 70.0), else_=0.0)
        content_score = case((director_match, 12.0), else_=0.0)
    elif detected_type == "keyword" and exact_keyword:
        exact_keyword_match = Movie.keywords.any(exact_keyword)
        intent_bucket = case((exact_keyword_match, 0), (semantic_overview_match, 1), else_=9)
        match_score = case((exact_keyword_match, 70.0), (semantic_overview_match, 46.0), else_=0.0)
        content_score = func.least(keyword_hit_count * 2.0 + func.least(overview_hit_count, 4.0), 20.0)
    elif matched_genres:
        intent_bucket = case(
            (title_exact, 0),
            (title_condition, 1),
            (primary_genre, 2),
            (or_(semantic_keyword_match, semantic_overview_match), 3),
            (genre_condition, 4),
            else_=5,
        )
        match_score = case(
            (title_exact, 70.0),
            (title_condition, 66.0),
            (primary_genre, 58.0),
            (or_(semantic_keyword_match, semantic_overview_match), 52.0),
            (genre_condition, 45.0),
            else_=36.0,
        )
        raw_content_score = (
            case((genre_condition, 3.0), else_=0.0)
            + func.least(keyword_hit_count, 8.0)
            + case((overview_hit_count >= 2, 1.0), else_=0.0)
        )
        if "로맨스" in matched_genres:
            negative_hit_count = sum(
                (
                    case(
                        (Movie.keywords.any(term), 1.0),
                        else_=0.0,
                    )
                    for term in ROMANCE_NEGATIVE_TERMS
                ),
                0.0,
            )
            raw_content_score -= case((negative_hit_count > keyword_hit_count, 1.0), else_=0.0)
        content_score = func.least(func.greatest(raw_content_score, 0.0) / 12.0 * 20.0, 20.0)
    else:
        intent_bucket = case(
            (title_exact, 0),
            (title_condition, 1),
            (or_(actor_match, director_match), 2),
            (semantic_keyword_match, 3),
            else_=4,
        )
        match_score = case(
            (title_exact, 70.0),
            (title_condition, 64.0),
            (or_(actor_match, director_match), 56.0),
            (semantic_keyword_match, 48.0),
            else_=38.0,
        )
        content_score = func.least(keyword_hit_count * 2.0 + func.least(overview_hit_count, 4.0), 20.0)

    vote_confidence = func.least(
        func.ln(func.coalesce(Movie.vote_count, 0) + 1) / func.ln(10_001),
        1.0,
    )
    rating_quality = func.least(func.coalesce(Movie.vote_average, 0) / 10.0, 1.0)
    quality_score = vote_confidence * 4.4 + rating_quality * 3.6
    search_score = (match_score + content_score + quality_score).label("search_score")

    preference_tie = literal(0.0)
    user = db.get(User, user_id) if user_id else None
    if user:
        if user.preferred_genres:
            preference_tie += case((Movie.id.in_(
                select(MovieGenreWeight.movie_id).where(
                    MovieGenreWeight.genre.in_(user.preferred_genres),
                    MovieGenreWeight.weight >= GENRE_RELEVANCE_MINIMUM,
                )
            ), 1.0), else_=0.0)
        if user.preferred_actors:
            preference_tie += case((Movie.cast.op("&&")(user.preferred_actors), 1.0), else_=0.0)
        if user.preferred_keywords:
            preference_tie += case((Movie.keywords.op("&&")(user.preferred_keywords), 1.0), else_=0.0)

    result = db.execute(
        select(Movie, search_score)
        .where(candidate_filter)
        .order_by(
            intent_bucket.asc(),
            search_score.desc(),
            preference_tie.desc(),
            func.coalesce(Movie.vote_count, 0).desc(),
            Movie.title.asc(),
        )
        .offset((page - 1) * limit)
        .limit(limit)
    ).all()
    if not result:
        return {"state": "failure", "message": "관련 영화 정보가 없습니다."}
    return {
        "state": "success",
        "message": "검색 성공",
        "search_type": detected_type,
        "data": [get_movie_result(movie) for movie, _score in result],
    }

# 영화 결과 함수
def get_movie_result(movie):
    return {
        "movie_id" : movie.id,
        "title" : movie.title,
        "genres": movie.genres,
        "keyword" : movie.keywords,
        "cast" : movie.cast,
        "poster_path": movie.poster_path,
        "vote_average" : movie.vote_average,
        "year": movie.year,
        "release_date": movie.release_date,
    }
