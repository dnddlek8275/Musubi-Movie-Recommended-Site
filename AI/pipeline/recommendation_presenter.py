"""Grounded roles, diversity selection, and reasons for movie recommendations."""

from __future__ import annotations

import json
import re

from pipeline.topic_grounding import build_topic_reason
from rag.movie_quality import is_child_safe_certification


ROLE_LABELS = (
    "가장 잘 맞는 선택",
    "다른 결의 대안",
    "취향 확장 선택",
)

_LIGHT_QUERY = re.compile(
    r"가볍|유쾌|웃긴|재밌|부담\s*없이|편하게|힐링|기분\s*전환|우울할\s*때"
)
_DATE_QUERY = re.compile(r"데이트|연인|커플")
_FAMILY_COMFORT_QUERY = re.compile(
    r"(?:부모님|가족).{0,30}(?:민망|잔인하지|폭력적이지|편하게\s*같이)|"
    r"(?:민망|잔인하지|폭력적이지).{0,30}(?:부모님|가족)"
)
_GROUP_COMPROMISE_QUERY = re.compile(
    r"(?:한\s*명은|나는|친구).{0,100}(?:다\s*같이|모두|넷\s*다|덜\s*불만|취향.{0,12}(?:맞|절충))"
)
_VIOLENCE_AVERSION_QUERY = re.compile(
    r"잔인(?:한|한\s*걸|한\s*건|함).{0,12}(?:못\s*봐|싫|피하)|폭력적.{0,12}(?:못\s*봐|싫|피하)"
)
_GENTLE_SUSPENSE_QUERY = re.compile(
    r"(?:긴장감(?:은|이)?\s*(?:조금|살짝)|살짝\s*(?:쫄깃|긴장)|가볍게\s*쫄깃)|"
    r"(?:쫄깃|긴장감).{0,24}(?:안\s*무서|무섭지)|"
    r"(?:안\s*무서|무섭지).{0,24}(?:쫄깃|긴장감)"
)
_BRIGHT_ROMANCE_QUERY = re.compile(
    r"(?:밝|유쾌|설레).*?(?:데이트|로맨스|멜로)|"
    r"(?:데이트|로맨스|멜로).*?(?:밝|유쾌|설레)"
)
_KIDS_QUERY = re.compile(
    r"아이와|아이랑|어린이|자녀와|온\s*가족|"
    r"유치원생|미취학|초등생|초등학생|아동|(?:어린|어린이|초등생|초등학생)\s*조카|조카(?:랑|와|하고)"
)
_TOUCHING_QUERY = re.compile(r"감동|뭉클|눈물|마음\s*따뜻")
_DISCUSSION_QUERY = re.compile(r"얘기할\s*거리|생각할\s*거리|토론할\s*거리|곱씹|철학적")
_FEELGOOD_QUERY = re.compile(
    r"보고\s*나면\s*기분(?:이)?\s*(?:좋|나아)|기분\s*좋아지는|행복해지는|"
    r"다시\s*용기|용기\s*나는|자신감(?:을|이)?\s*(?:되찾|생기|높)|힘이?\s*나는"
)
_AVOID_SAD_QUERY = re.compile(r"(?:슬픈|슬프|슬퍼).*?(?:싫|말고|빼|제외)")
_ADULT_ANIMATION_QUERY = re.compile(r"(?:어른|성인).*?(?:유치하지\s*않|애니)")
_DISCUSSION_REASON_TERMS = re.compile(r"기술|인간|사회|정체성|관계|선택|미래|삶|윤리|갈등")
_BRIGHT_REASON_TERMS = re.compile(r"밝고\s*경쾌|유쾌|희망|꿈|새\s*출발|다시\s*시작|사랑|음악")
_MATURE_REASON_TERMS = re.compile(r"사회|정체성|관계|가족|갈등|편견|책임|인간|삶|죽음|상실|범죄|정치")
_QUOTED_PHRASE = re.compile(
    r"[‘“]([^’”\n]{1,100})[’”]|\"([^\"\n]{1,100})\"|(?<!\w)'([^'\n]{1,100})'(?!\w)"
)
_MARKDOWN_ARTIFACT = re.compile(r"(?:\*\*|__|^\s*#{1,6}\s|^\s*[-*]\s)", re.MULTILINE)
_FACT_CLAIM_TERMS = re.compile(
    r"액션|모험|SF|판타지|애니메이션|다큐멘터리|드라마|로맨스|코미디|"
    r"공포|호러|스릴러|스릴|범죄|전쟁|역사|미스터리|뮤지컬|음악|가족|"
    r"긴장감|속도감|반전|실화|실제\s*사건|영상미|감동|뭉클|따뜻|힐링|"
    r"유쾌|웃음|웃긴|잔잔|잔인|무서|통쾌|성장|우정|사랑"
)
_GENRE_CLAIM_TERMS = re.compile(
    r"(?P<genre>액션|모험|SF|판타지|애니메이션|다큐멘터리|드라마|로맨스|코미디|"
    r"공포|호러|스릴러|범죄|전쟁|역사|미스터리|뮤지컬|음악|가족)"
    r"\s*(?:장르|영화|작품)"
)
_NUMERIC_FACT_CLAIM = re.compile(r"\d+(?:\.\d+)?\s*(?:년|점|분|위)")


def _korean_object_particle(value: str) -> str:
    """Return 을/를 for a Korean label, defaulting safely for Latin labels."""
    text = str(value or "").strip()
    if not text:
        return "를"
    last = ord(text[-1])
    if 0xAC00 <= last <= 0xD7A3:
        return "을" if (last - 0xAC00) % 28 else "를"
    return "를"


def _join_korean_nouns(values: list[str]) -> str:
    """Join one or two quoted labels with the correct 와/과 particle."""
    quoted = [f"‘{str(value).strip()}’" for value in values if str(value).strip()]
    if len(quoted) < 2:
        return "".join(quoted)
    last = ord(str(values[0]).strip()[-1])
    particle = "과" if 0xAC00 <= last <= 0xD7A3 and (last - 0xAC00) % 28 else "와"
    return f"{quoted[0]}{particle} {quoted[1]}"


def _genres(movie: dict) -> list[str]:
    raw = movie.get("genres_list") or movie.get("genres") or []
    if isinstance(raw, str):
        if raw.lstrip().startswith("["):
            try:
                raw = json.loads(raw)
            except (TypeError, ValueError, json.JSONDecodeError):
                raw = raw.split(",")
        else:
            raw = raw.split(",")
    return [str(value).strip() for value in raw if str(value).strip()]


def filter_movies_by_requested_genre(
    candidates: list[dict],
    requested_genre: str | None,
) -> list[dict]:
    """Keep only cards whose structured genre exactly matches the request.

    Milvus applies the genre expression during retrieval, but this second guard is
    deliberately kept at the presentation boundary. It prevents a relaxed retry,
    stale vector metadata, or a malformed genre field from leaking a different
    genre into the cards shown to the user.
    """
    genre = str(requested_genre or "").strip().casefold()
    if not genre:
        return [dict(movie) for movie in candidates]
    return [
        dict(movie)
        for movie in candidates
        if genre in {value.casefold() for value in _genres(movie)}
    ]


def _cast(movie: dict) -> set[str]:
    raw = movie.get("cast") or []
    if isinstance(raw, str):
        raw = raw.split(",")
    return {str(value).strip() for value in raw if str(value).strip()}


def _deduplicate_candidates(candidates: list[dict]) -> list[dict]:
    """Keep the highest-ranked card for each display title."""
    unique: list[dict] = []
    seen_titles: set[str] = set()
    for movie in candidates:
        title = re.sub(r"\s+", " ", str(movie.get("title") or "")).strip().casefold()
        if title and title in seen_titles:
            continue
        if title:
            seen_titles.add(title)
        unique.append(movie)
    return unique


def _similarity(left: dict, right: dict, requested_genre: str | None) -> float:
    left_genres = set(_genres(left))
    right_genres = set(_genres(right))
    if requested_genre:
        left_genres.discard(requested_genre)
        right_genres.discard(requested_genre)
    union = left_genres | right_genres
    genre_similarity = len(left_genres & right_genres) / len(union) if union else 0.0

    same_director = bool(
        str(left.get("director") or "").strip()
        and str(left.get("director") or "").strip() == str(right.get("director") or "").strip()
    )
    cast_overlap = bool(_cast(left) & _cast(right))
    left_year = int(left.get("year") or 0)
    right_year = int(right.get("year") or 0)
    same_decade = bool(left_year and right_year and left_year // 10 == right_year // 10)

    return min(
        1.0,
        0.55 * genre_similarity
        + 0.20 * float(same_director)
        + 0.15 * float(cast_overlap)
        + 0.10 * float(same_decade),
    )


def select_diverse_movies(
    candidates: list[dict],
    limit: int,
    requested_genre: str | None = None,
) -> list[dict]:
    """Keep the best result first, then reduce metadata redundancy."""
    if len(candidates) <= limit:
        return [dict(movie) for movie in candidates]
    # A vague request has no stable axis for "diversity". Pushing genres apart in
    # that case creates incoherent sets (for example horror + romance + animation).
    # Preserve semantic rank until the user names a genre or another constraint.
    if not requested_genre:
        return [dict(movie) for movie in candidates[:limit]]

    selected_indexes = [0]
    while len(selected_indexes) < limit:
        best_index = None
        best_score = float("-inf")
        for index, movie in enumerate(candidates):
            if index in selected_indexes:
                continue
            relevance = 1.0 - 0.35 * (index / max(len(candidates) - 1, 1))
            redundancy = max(
                _similarity(movie, candidates[selected], requested_genre)
                for selected in selected_indexes
            )
            score = relevance - 0.28 * redundancy
            if score > best_score:
                best_index = index
                best_score = score
        if best_index is None:
            break
        selected_indexes.append(best_index)
    return [dict(candidates[index]) for index in selected_indexes]


def _alternative_reason(movie: dict, primary: dict, role_index: int) -> str | None:
    movie_genres = _genres(movie)
    primary_genres = set(_genres(primary))
    distinct_genres = [genre for genre in movie_genres if genre not in primary_genres]
    release_date = str(movie.get("release_date") or "").strip()
    year = int(movie.get("year") or 0)
    primary_year = int(primary.get("year") or 0)
    rating = float(movie.get("vote_average") or 0.0)

    if distinct_genres:
        return f"{distinct_genres[0]} 요소가 더해져 첫 번째 영화와는 다른 분위기로 볼 수 있어요."
    if year and primary_year and abs(year - primary_year) >= 10:
        return f"{year}년 작품이라 첫 번째 영화와는 다른 시기의 분위기를 느낄 수 있어요."
    if role_index >= 2 and rating >= 7.0:
        return f"TMDB 평점 {rating:.1f}점으로, 조금 다른 선택지를 찾을 때 살펴볼 만해요."
    if release_date:
        return f"{release_date} 개봉작으로 첫 번째 영화와 함께 비교해 볼 만해요."
    return None


def _reason(
    movie: dict,
    user_message: str,
    filters: dict,
    role_index: int = 0,
    primary: dict | None = None,
) -> str:
    genres = _genres(movie)
    genre_set = set(genres)
    requested_genre = str(filters.get("genre") or "").strip()
    actor = str(filters.get("actor") or "").strip()
    director = str(filters.get("director") or "").strip()
    release_date = str(movie.get("release_date") or "").strip()
    rating = float(movie.get("vote_average") or 0.0)
    runtime = int(movie.get("runtime") or 0)
    runtime_max = int(filters.get("runtime_max") or 0)
    audience_count = int(movie.get("audience_count") or 0)
    audience_min = int(filters.get("audience_min") or 0)
    production_country = str(filters.get("production_country") or "").strip()
    language = str(filters.get("language") or "").strip()

    topic_reason = build_topic_reason(movie, filters.get("topic"))
    if topic_reason:
        return topic_reason

    if runtime_max and runtime:
        genre_text = f" {' · '.join(genres[:2])} 장르 작품" if genres else " 작품"
        return f"상영시간이 {runtime}분으로 {runtime_max}분 이하 조건을 만족하는{genre_text}이에요."

    if audience_min and audience_count:
        return f"누적 관객 수 {audience_count:,}명으로 요청한 {audience_min:,}명 이상 조건을 만족해요."

    if production_country and language:
        country_label = {"KR": "한국", "US": "미국", "FR": "프랑스", "JP": "일본", "CN": "중국", "GB": "영국"}.get(
            production_country, production_country
        )
        language_label = {"ko": "한국어", "en": "영어", "fr": "프랑스어", "ja": "일본어", "zh": "중국어"}.get(
            language, language
        )
        return f"제작 국가 {country_label}와 언어 {language_label} 정보가 요청 조건에 맞는 작품이에요."

    if filters.get("release_date_from") and filters.get("release_date_to") and release_date:
        return (
            f"{release_date} 개봉작으로 요청한 {filters['release_date_from']}부터 "
            f"{filters['release_date_to']}까지의 범위에 들어요."
        )

    overview = str(movie.get("overview") or "")
    if _GENTLE_SUSPENSE_QUERY.search(user_message):
        matched = [genre for genre in ("미스터리", "코미디", "모험", "범죄", "스릴러") if genre in genre_set]
        if matched:
            return f"{' · '.join(matched[:2])} 장르라 공포를 피하면서 가볍게 긴장감을 즐기기 좋은 선택이에요."
    if _FAMILY_COMFORT_QUERY.search(user_message):
        matched = [genre for genre in ("가족", "코미디", "드라마", "음악") if genre in genre_set]
        if matched:
            return f"{' · '.join(matched[:2])} 장르 정보를 근거로 부모님과 함께 보기 편한 쪽으로 고른 작품이에요."
    if _GROUP_COMPROMISE_QUERY.search(user_message):
        requested = [genre for genre in ("액션", "코미디", "미스터리", "로맨스", "SF", "판타지", "모험", "드라마") if genre in user_message]
        matched = [genre for genre in requested if genre in genre_set]
        if matched:
            return f"요청에 나온 취향 중 {' · '.join(matched)} 장르가 확인돼 여러 사람의 공통분모가 큰 선택이에요."
    if _DISCUSSION_QUERY.search(user_message):
        terms = list(dict.fromkeys(_DISCUSSION_REASON_TERMS.findall(overview)))[:2]
        if terms:
            return f"줄거리에서 {' · '.join(terms)} 문제를 다뤄 보고 나서 이야기할 근거가 있는 작품이에요."
        if genre_set & {"드라마", "미스터리", "SF"}:
            return f"{' · '.join(genres[:2])} 장르를 바탕으로 해석하고 이야기할 여지가 있는 작품이에요."
    if _ADULT_ANIMATION_QUERY.search(user_message):
        terms = list(dict.fromkeys(_MATURE_REASON_TERMS.findall(overview)))[:2]
        certification = str(movie.get("certification") or "").strip()
        if terms:
            return f"줄거리에서 {' · '.join(terms)} 주제를 다뤄 성인도 깊이 있게 볼 수 있는 애니메이션이에요."
        if certification and certification.upper() not in {"ALL", "G", "PG"}:
            return f"{certification} 등급과 {' · '.join(genres[:2])} 장르가 확인된 성인 취향 애니메이션이에요."
    if _AVOID_SAD_QUERY.search(user_message) or _BRIGHT_ROMANCE_QUERY.search(user_message):
        terms = list(dict.fromkeys(_BRIGHT_REASON_TERMS.findall(overview)))[:2]
        if role_index > 0 and primary:
            alternative = _alternative_reason(movie, primary, role_index)
            if alternative:
                return alternative
        if terms:
            if _BRIGHT_ROMANCE_QUERY.search(user_message):
                return f"줄거리의 {' · '.join(terms)} 흐름을 근거로 밝은 데이트 분위기에 맞춰 골랐어요."
            return f"줄거리의 {' · '.join(terms)} 흐름을 근거로 너무 슬프지 않은 선택으로 골랐어요."
        if "코미디" in genre_set:
            return "코미디 장르를 포함해 너무 슬픈 분위기를 피하고 싶다는 요청에 가까운 작품이에요."
    if _FEELGOOD_QUERY.search(user_message):
        terms = list(dict.fromkeys(_BRIGHT_REASON_TERMS.findall(overview)))[:2]
        if terms:
            return f"줄거리의 {' · '.join(terms)} 요소가 보고 난 뒤 기분 좋은 분위기와 잘 맞아요."
        matched = [genre for genre in ("코미디", "음악", "가족", "모험") if genre in genre_set]
        if matched:
            return f"{' · '.join(matched[:2])} 장르라 기분 좋게 볼 작품을 찾는 요청에 잘 맞아요."

    # A plain fun/light request needs its mood evidence on every card. Without
    # this branch, alternative cards fall through to a generic diversity reason
    # (for example, "모험 요소") even when their verified comedy genre is the
    # actual reason they satisfy the request.
    if _LIGHT_QUERY.search(user_message) and genre_set & {"코미디", "가족", "애니메이션", "모험"}:
        matched = [genre for genre in ("코미디", "가족", "애니메이션", "모험") if genre in genre_set]
        return f"{' · '.join(matched[:2])} 장르라 가볍게 보기 좋은 선택이에요."

    if role_index > 0 and primary:
        alternative = _alternative_reason(movie, primary, role_index)
        if alternative:
            return alternative

    if actor and actor in str(movie.get("cast") or ""):
        return f"요청하신 배우 {actor}의 출연 정보가 확인된 작품이에요."
    if director and director in str(movie.get("director") or ""):
        return f"요청하신 {director} 감독의 작품이에요."
    if filters.get("sort_latest") and release_date:
        return f"{release_date} 개봉작이라 최신 영화를 찾는 조건에 잘 맞아요."
    if _KIDS_QUERY.search(user_message):
        certification = str(movie.get("certification") or "").strip()
        if certification in {"ALL", "전체관람가", "G", "PG"}:
            return f"{certification} 등급이 확인된 {' · '.join(genres[:2])} 장르 작품이에요."
    if _DATE_QUERY.search(user_message) and genre_set & {"로맨스", "코미디"}:
        matched = [genre for genre in ("로맨스", "코미디") if genre in genre_set]
        return f"{' · '.join(matched)} 장르라 데이트 분위기에 맞춰 고른 작품이에요."
    if _TOUCHING_QUERY.search(user_message) and genre_set & {"드라마", "가족", "애니메이션", "로맨스"}:
        matched = [genre for genre in ("드라마", "가족", "애니메이션", "로맨스") if genre in genre_set]
        return f"{' · '.join(matched[:2])} 장르를 바탕으로 감동적인 분위기에 맞춰 고른 작품이에요."

    if requested_genre and requested_genre in genre_set:
        if rating >= 7.0:
            return f"요청하신 {requested_genre} 장르이면서 TMDB 평점이 {rating:.1f}점인 작품이에요."
        related_genres = [genre for genre in genres if genre != requested_genre]
        if related_genres:
            return (
                f"{requested_genre}에 {' · '.join(related_genres[:2])} 요소가 더해진 작품이에요."
            )
        object_particle = _korean_object_particle(requested_genre)
        if release_date:
            return (
                f"{release_date} 개봉작으로, {requested_genre}{object_particle} "
                "찾을 때 살펴볼 만해요."
            )
        return (
            f"{requested_genre}{object_particle} 중심으로 찾을 때 "
            "먼저 살펴볼 만한 작품이에요."
        )
    if genres:
        return f"{' · '.join(genres[:2])} 장르 정보를 기준으로 요청과 가까운 작품을 골랐어요."
    if rating >= 7.0:
        return f"TMDB 평점이 {rating:.1f}점으로 확인된 작품이에요."
    return "검색 결과에서 요청과의 관련도가 높았던 작품이에요."


def prepare_recommendations(
    candidates: list[dict],
    user_message: str,
    filters: dict,
    limit: int = 3,
) -> list[dict]:
    def matches_hard_filters(movie: dict) -> bool:
        genre_set = set(_genres(movie))
        required_genres = set(filters.get("required_genres") or [])
        requested_genre = str(filters.get("genre") or "").strip()
        if requested_genre:
            required_genres.add(requested_genre)
        if required_genres and not required_genres.issubset(genre_set):
            return False
        actor = str(filters.get("actor") or "").strip()
        if actor and actor not in str(movie.get("cast") or ""):
            return False
        director = str(filters.get("director") or "").strip()
        if director and director not in str(movie.get("director") or ""):
            return False
        language = str(filters.get("language") or "").strip().lower()
        if language and str(movie.get("language") or "").strip().lower() != language:
            return False
        countries_raw = movie.get("production_countries") or []
        countries = (
            {part.strip().upper() for part in re.split(r"[,/|]", countries_raw) if part.strip()}
            if isinstance(countries_raw, str)
            else {str(part).strip().upper() for part in countries_raw if str(part).strip()}
        )
        country = str(filters.get("production_country") or "").strip().upper()
        if country and country not in countries:
            return False
        year = int(movie.get("year") or 0)
        if filters.get("year_from") is not None and year < int(filters["year_from"]):
            return False
        if filters.get("year_to") is not None and year > int(filters["year_to"]):
            return False
        release_date = str(movie.get("release_date") or "").strip()
        if filters.get("release_date_from") and (not release_date or release_date < filters["release_date_from"]):
            return False
        if filters.get("release_date_to") and (not release_date or release_date > filters["release_date_to"]):
            return False
        rating = float(movie.get("vote_average") or 0.0)
        if filters.get("min_rating") is not None and rating < float(filters["min_rating"]):
            return False
        runtime = int(movie.get("runtime") or 0)
        if filters.get("runtime_max") is not None and (
            runtime <= 0 or runtime > int(filters["runtime_max"])
        ):
            return False
        audience_count = int(movie.get("audience_count") or 0)
        if filters.get("audience_min") is not None and audience_count < int(filters["audience_min"]):
            return False
        return True

    candidates = [movie for movie in candidates if matches_hard_filters(movie)]
    if _VIOLENCE_AVERSION_QUERY.search(user_message):
        adult_certifications = {"R", "NC-17", "18", "청소년관람불가"}
        candidates = [
            movie for movie in candidates
            if re.sub(r"\s+", "", str(movie.get("certification") or "")).upper()
            not in adult_certifications
        ]
    if _KIDS_QUERY.search(user_message):
        candidates = [movie for movie in candidates if is_child_safe_certification(movie)]
    candidates = _deduplicate_candidates(candidates)
    if filters.get("sort_latest"):
        selected = [dict(movie) for movie in candidates[:limit]]
    else:
        selected = select_diverse_movies(candidates, limit, filters.get("genre"))

    prepared = []
    for index, movie in enumerate(selected):
        movie["recommendation_role"] = ROLE_LABELS[min(index, len(ROLE_LABELS) - 1)]
        movie["recommendation_reason"] = _reason(
            movie,
            user_message,
            filters,
            role_index=index,
            primary=selected[0] if selected else None,
        )
        prepared.append(movie)
    return prepared


def _alternative_description(movie: dict, primary: dict) -> str:
    movie_genres = _genres(movie)
    primary_genres = set(_genres(primary))
    distinct_genres = [genre for genre in movie_genres if genre not in primary_genres]
    title = str(movie.get("title") or "").strip()
    year = int(movie.get("year") or 0)
    rating = float(movie.get("vote_average") or 0.0)

    if distinct_genres:
        return f"{distinct_genres[0]} 요소가 있는 ‘{title}’"
    if year:
        return f"{year}년 작품인 ‘{title}’"
    if rating >= 7.0:
        return f"TMDB 평점 {rating:.1f}점의 ‘{title}’"
    return f"‘{title}’"


def build_grounded_answer(movies: list[dict]) -> str:
    if not movies:
        return "조건에 맞는 영화를 찾지 못했어요. 다른 분위기나 장르를 알려주시겠어요?"

    primary = movies[0]
    lines = [
        f"먼저 ‘{primary.get('title', '')}’부터 추천해요.",
        str(primary.get("recommendation_reason") or "").strip(),
    ]
    alternatives = movies[1:3]
    if alternatives:
        descriptions = [_alternative_description(movie, primary) for movie in alternatives]
        lines.append(f"조금 다른 선택으로는 {', '.join(descriptions)}도 있어요.")
    lines.append("이 중에 끌리는 영화가 있나요?")
    return "\n\n".join(line for line in lines if line)


def _casualize_reason(reason: str) -> str:
    """Convert our own verified polite reason to a restrained casual ending."""
    text = str(reason or "").strip()
    replacements = (
        ("작품이에요.", "작품이야."),
        ("선택이에요.", "선택이야."),
        ("골랐어요.", "골랐어."),
        ("볼 만해요.", "볼 만해."),
        ("좋아요.", "좋아."),
        ("맞아요.", "맞아."),
        ("있어요.", "있어."),
        ("예요.", "야."),
        ("이에요.", "이야."),
    )
    for old, new in replacements:
        if text.endswith(old):
            return text[:-len(old)] + new
    return text


def build_character_grounded_answer(movies: list[dict], character_name: str) -> str:
    """Build a deterministic, card-safe fallback with a restrained character tone."""
    if not movies:
        return build_grounded_answer(movies)

    # Local import avoids coupling the general presenter to character prompting.
    from pipeline.tone_presets import get_tone_preset_name

    primary = str(movies[0].get("title") or "").strip()
    alternatives = [
        str(movie.get("title") or "").strip()
        for movie in movies[1:3]
        if str(movie.get("title") or "").strip()
    ]
    quoted_alternatives = _join_korean_nouns(alternatives)
    reason = str(movies[0].get("recommendation_reason") or "").strip()
    casual_reason = _casualize_reason(reason)
    preset = get_tone_preset_name(character_name)

    if character_name == "화림":
        genres = _genres(movies[0])
        genre_line = (
            f"{' · '.join(genres[:2])} 쪽 기운이 또렷해서 네가 찾는 흐름에 맞아."
            if genres
            else casual_reason
        )
        lines = [f"낌새부터 다른 건 ‘{primary}’야.", genre_line]
        if quoted_alternatives:
            lines.append(f"{quoted_alternatives}도 같이 판에 올려둘 만해.")
        lines.append("어느 쪽 낌새가 더 당겨?")
    elif preset == "direct_grounded":
        lines = [f"오늘은 ‘{primary}’부터 봐.", casual_reason]
        if quoted_alternatives:
            lines.append(f"{quoted_alternatives}도 같이 봐둘 만해.")
        lines.append("이 중 뭐가 당겨?")
    elif preset == "terse_reserved":
        lines = [f"‘{primary}’부터 봐.", casual_reason]
        if quoted_alternatives:
            lines.append(f"다른 선택은 {quoted_alternatives}.")
    elif preset == "cold_calculating":
        lines = [f"우선 ‘{primary}’, 이걸 고르지.", casual_reason]
        if quoted_alternatives:
            lines.append(f"{quoted_alternatives}도 선택지로 남겨두지.")
        lines.append("뭘 고를 거지?")
    elif preset == "witty_intellectual":
        lines = [f"첫 카드는 ‘{primary}’야.", casual_reason]
        if quoted_alternatives:
            lines.append(f"{quoted_alternatives}도 후보로 챙겼어.")
        lines.append("이 중 하나쯤은 취향을 맞히겠지?")
    elif preset == "playful_social":
        lines = [f"오늘 첫 픽은 ‘{primary}’!", casual_reason]
        if quoted_alternatives:
            lines.append(f"{quoted_alternatives}도 같이 챙겼어.")
        lines.append("뭐부터 볼래?")
    elif preset == "warm_supportive":
        lines = [f"먼저 ‘{primary}’부터 추천할게요.", reason]
        if quoted_alternatives:
            lines.append(f"{quoted_alternatives}도 함께 골라봤어요.")
        lines.append("어떤 영화가 끌리세요?")
    elif preset == "logical_reflective":
        lines = [f"우선순위는 ‘{primary}’예요.", reason]
        if quoted_alternatives:
            lines.append(f"대안은 {quoted_alternatives}예요.")
        lines.append("어느 쪽이 더 맞나요?")
    elif preset == "dignified_guiding":
        lines = [f"먼저 권할 작품은 ‘{primary}’입니다.", reason]
        if quoted_alternatives:
            lines.append(f"{quoted_alternatives}도 좋은 선택지가 되겠군요.")
        lines.append("어느 작품을 택하시겠습니까?")
    elif preset == "distinctive_voice":
        lines = [f"먼저 눈에 들어오는 건 ‘{primary}’야.", casual_reason]
        if quoted_alternatives:
            lines.append(f"{quoted_alternatives}도 그냥 지나치긴 아까워.")
        lines.append("넌 뭐가 끌려?")
    else:
        return build_grounded_answer(movies)

    return "\n\n".join(line for line in lines if line)


def is_safe_general_recommendation(text: str, movies: list[dict]) -> bool:
    """Accept only concise answers grounded in the exact recommendation cards."""
    answer = str(text or "").strip()
    allowed_titles = {
        str(movie.get("title") or "").strip()
        for movie in movies
        if str(movie.get("title") or "").strip()
    }
    if not answer or not allowed_titles or len(answer) > 800:
        return False
    if _MARKDOWN_ARTIFACT.search(answer):
        return False
    if any(label in answer for label in ROLE_LABELS):
        return False
    if any(title not in answer for title in allowed_titles):
        return False

    for match in _QUOTED_PHRASE.finditer(answer):
        phrase = next((group for group in match.groups() if group is not None), "").strip()
        if phrase and phrase not in allowed_titles:
            return False
    return True


def _movie_evidence_text(movie: dict) -> str:
    fields = (
        "title", "overview", "genres", "genres_list", "director", "cast",
        "keywords", "year", "release_date", "runtime", "production_countries",
        "certification", "language", "vote_average", "audience_count",
        "recommendation_reason",
    )
    values: list[str] = []
    for field in fields:
        value = movie.get(field)
        if isinstance(value, (list, tuple, set)):
            values.extend(str(item) for item in value)
        elif value not in (None, ""):
            values.append(str(value))
    return " ".join(values).casefold()


def is_fact_grounded_recommendation(
    text: str,
    movies: list[dict],
    user_message: str = "",
) -> bool:
    """Reject movie claims that are absent from the referenced cards and request."""
    if not is_safe_general_recommendation(text, movies):
        return False

    request_evidence = str(user_message or "").casefold()
    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?:\n+|(?<=[.!?。])\s+)", str(text or ""))
        if sentence.strip()
    ]
    for sentence in sentences:
        referenced = [
            movie for movie in movies
            if str(movie.get("title") or "").strip()
            and str(movie.get("title") or "").strip() in sentence
        ]
        evidence_movies = referenced or movies
        evidence = " ".join(
            [request_evidence, *(_movie_evidence_text(movie) for movie in evidence_movies)]
        )

        # A genre claim without a named title describes the displayed set as a
        # whole (for example, "액션 영화 어때?"). Every card must therefore
        # carry that structured genre, not just one card in a mixed result.
        if not referenced:
            for match in _GENRE_CLAIM_TERMS.finditer(sentence):
                claim = match.group("genre")
                accepted = {claim}
                if claim == "호러":
                    accepted.add("공포")
                elif claim == "공포":
                    accepted.add("호러")
                if not all(accepted & set(_genres(movie)) for movie in movies):
                    return False

        for match in _FACT_CLAIM_TERMS.finditer(sentence):
            claim = re.sub(r"\s+", "", match.group(0).casefold())
            compact_evidence = re.sub(r"\s+", "", evidence)
            aliases = {
                "호러": ("호러", "공포"),
                "스릴": ("스릴", "스릴러"),
                "실제사건": ("실제사건", "실화"),
                "웃긴": ("웃긴", "코미디", "유쾌"),
                "웃음": ("웃음", "코미디", "유쾌"),
                "무서": ("무서", "공포", "호러"),
            }.get(claim, (claim,))
            if not any(alias in compact_evidence for alias in aliases):
                return False

        compact_evidence = re.sub(r"\s+", "", evidence)
        for match in _NUMERIC_FACT_CLAIM.finditer(sentence):
            claim = re.sub(r"\s+", "", match.group(0))
            if claim not in compact_evidence:
                return False
    return True
