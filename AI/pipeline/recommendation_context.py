"""Deterministic context extraction for multi-turn movie recommendations."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


GENRES = (
    "액션", "로맨스", "공포", "코미디", "스릴러", "SF", "판타지",
    "애니메이션", "다큐멘터리", "드라마", "범죄", "전쟁", "역사",
    "미스터리", "뮤지컬",
)
_GENRE_ALT = "|".join(map(re.escape, GENRES))
_MOVIE_CONTEXT = re.compile(
    r"영화|추천|뭐\s*볼|볼만한|장르|감독|배우|개봉|평점|"
    + _GENRE_ALT,
    re.IGNORECASE,
)
_FOLLOWUP = re.compile(
    r"너무\s*(?:무겁|무거|어둡|어두|우울|슬프|슬퍼|무섭|무서|잔인|폭력적|길|오래됐)|"
    r"(?:좀\s*)?더\s*(?:밝|가볍|가벼|유쾌|최신|최근|짧|재밌)|"
    r"다른\s*(?:거|것|걸|건|게|영화|작품)(?:도|은|는|을|이|가)?|"
    r"또\s*(?:보여|알려|추천|골라)|추가로\s*(?:보여|알려|추천|골라)|"
    r"별로|마음에\s*안|싫어|싫다|말고|빼줘|제외|"
    r"(?:조건|장르|언어|연도).{0,20}(?:유지|바꿔|변경|완화|없애|취소)|"
    r"\d{4}\s*년?\s*(?:이후|이전|부터|까지|이상|이하)?\s*만|"
    r"평점\s*\d+(?:\.\d+)?\s*(?:점|이상|이하)?\s*만?|"
    r"(?:한국어|영어|일본어|중국어|프랑스어)\s*(?:영화|작품)?\s*만",
    re.IGNORECASE,
)
_NEGATED_GENRE = re.compile(
    rf"({_GENRE_ALT})(?:물)?(?:는|은|이|가|를|을|만|도)?\s*(?:싫|말고|빼|제외)",
    re.IGNORECASE,
)
_COORDINATED_NEGATED_GENRES = re.compile(
    rf"({_GENRE_ALT})(?:와|과|,)\s*({_GENRE_ALT})(?:물)?(?:는|은|이|가|를|을|만)?\s*(?:싫|말고|빼|제외)",
    re.IGNORECASE,
)
_COLLOQUIAL_HORROR_NEGATION = re.compile(
    r"(?:무서운|무서운\s*거|무서운\s*건|귀신(?:물)?|호러|공포).{0,12}(?:ㄴㄴ|싫|말고|빼|제외|절대\s*안)",
    re.IGNORECASE,
)
_QUOTED_TITLE = re.compile(r"['‘’\"“”]([^'‘’\"“”]{1,80})['‘’\"“”]")
_TITLE_RECALL = re.compile(r"(?:영화|제목).{0,12}(?:뭐였|뭐였지|알려)|뭐였지", re.IGNORECASE)
_OVERVIEW_REQUEST = re.compile(r"줄거리|내용|무슨\s*내용", re.IGNORECASE)
_LIGHT_COMPARISON = re.compile(r"(?:더\s*)?(?:가볍|가벼|편하|유쾌|밝)", re.IGNORECASE)
_REMAINDER_COMPARISON = re.compile(r"말고.{0,20}(?:나머지|둘\s*중|것\s*중|거\s*중)", re.IGNORECASE)
_ORDINALS = (
    (re.compile(r"첫\s*번째|1\s*번째|첫째"), 0),
    (re.compile(r"두\s*번째|2\s*번째|둘째"), 1),
    (re.compile(r"세\s*번째|3\s*번째|셋째"), 2),
)
_REQUESTED_COUNT = re.compile(
    r"(?:딱\s*)?(한|두|세|네|다섯|[1-5])\s*(?:편|개)(?:만|만\s*추천)?",
    re.IGNORECASE,
)
_COUNT_VALUES = {"한": 1, "두": 2, "세": 3, "네": 4, "다섯": 5}
_FULL_PREFERENCE_RESET = re.compile(
    r"(?:조건은?\s*(?:전부\s*)?취소|그\s*추천은?\s*(?:됐|그만)|이번엔|새로\s*(?:골라|추천))",
    re.IGNORECASE,
)
_YEAR_RELEASE = re.compile(r"연도\s*(?:제한|조건)(?:만)?\s*(?:없애|빼|취소)", re.IGNORECASE)
_YEAR_OVERRIDE = re.compile(r"연도(?:만|를)\s*\d{4}", re.IGNORECASE)
_YEAR_EXPRESSION = re.compile(
    r"\d{4}\s*년?\s*(?:이후|이전|부터|까지|이상|이하)?|\d{4}\s*[-~]\s*\d{4}"
)
_LANGUAGE_OVERRIDE = re.compile(r"언어(?:만|를)\s*(?:한국어|영어|일본어|중국어|프랑스어)", re.IGNORECASE)
_LANGUAGE_EXPRESSION = re.compile(r"(?:한국어|영어|일본어|중국어|프랑스어|한국|일본|중국|프랑스)\s*(?:영화|작품)?")


@dataclass
class RecommendationContext:
    search_message: str
    is_followup: bool = False
    excluded_genres: list[str] = field(default_factory=list)
    excluded_titles: list[str] = field(default_factory=list)


def requested_movie_count(message: str) -> int | None:
    match = _REQUESTED_COUNT.search(message or "")
    if not match:
        return None
    token = match.group(1)
    return _COUNT_VALUES.get(token, int(token) if token.isdigit() else None)


def _latest_structured_movies(history: list[dict] | None) -> list[dict]:
    for item in reversed(history or []):
        if item.get("role") != "assistant":
            continue
        raw_movies = item.get("recommended_movies") or item.get("movies") or []
        movies = [movie for movie in raw_movies if isinstance(movie, dict) and movie.get("title")]
        if movies:
            return movies
    return []


def _mentioned_ordinal(message: str) -> int | None:
    for pattern, index in _ORDINALS:
        if pattern.search(message):
            return index
    if re.search(r"마지막", message):
        return -1
    return None


def _genre_names(movie: dict) -> list[str]:
    raw = movie.get("genres_list") or movie.get("genres") or []
    if isinstance(raw, str):
        return [part.strip() for part in raw.split(",") if part.strip()]
    if isinstance(raw, list):
        return [str(part).strip() for part in raw if str(part).strip()]
    return []


def _lightness_score(movie: dict) -> int:
    scores = {
        "코미디": 4,
        "가족": 3,
        "애니메이션": 3,
        "음악": 2,
        "모험": 1,
        "로맨스": 1,
        "공포": -2,
        "스릴러": -1,
        "범죄": -1,
        "전쟁": -2,
    }
    return sum(scores.get(genre, 0) for genre in _genre_names(movie))


def build_card_followup_reply(
    user_message: str,
    history: list[dict] | None,
) -> tuple[str, list[dict]] | None:
    """Answer narrow card references using only the latest structured metadata."""
    movies = _latest_structured_movies(history)
    if not movies:
        return None

    ordinal = _mentioned_ordinal(user_message)
    if (
        ordinal is not None
        and _REMAINDER_COMPARISON.search(user_message)
        and _LIGHT_COMPARISON.search(user_message)
    ):
        excluded_index = ordinal if ordinal >= 0 else len(movies) - 1
        candidates = [movie for index, movie in enumerate(movies) if index != excluded_index]
        if len(candidates) < 2:
            return None
        ranked = sorted(candidates, key=_lightness_score, reverse=True)
        if _lightness_score(ranked[0]) == _lightness_score(ranked[1]):
            titles = "와 ".join(f"‘{movie['title']}’" for movie in ranked[:2])
            return f"장르 정보만으로는 {titles} 중 어느 쪽이 더 가벼운지 구분하기 어려워.", []
        selected = ranked[0]
        genres = _genre_names(selected)
        genre_text = " · ".join(genres[:2]) or "등록된 장르"
        return (
            f"장르 정보만 보면 ‘{selected['title']}’이 더 가벼운 쪽이야. "
            f"{genre_text} 장르로 표시되어 있어.",
            [selected],
        )

    if ordinal is None:
        return None
    selected_index = ordinal if ordinal >= 0 else len(movies) - 1
    if selected_index >= len(movies):
        return None
    selected = movies[selected_index]
    title = str(selected.get("title") or "").strip()
    if _OVERVIEW_REQUEST.search(user_message):
        overview = str(selected.get("overview") or "").strip()
        if overview:
            return f"‘{title}’의 등록된 줄거리는 이래. {overview}", [selected]
        return f"‘{title}’의 줄거리 정보는 현재 카드에 없어.", [selected]
    if _TITLE_RECALL.search(user_message):
        return f"{selected_index + 1}번째 영화는 ‘{title}’이야.", [selected]
    return None


def _recent_movie_request(history: list[dict] | None) -> str:
    for item in reversed(history or []):
        if item.get("role") != "user":
            continue
        content = str(item.get("content") or "").strip()
        if _MOVIE_CONTEXT.search(content):
            return content
    return ""


def _has_structured_recommendations(history: list[dict] | None) -> bool:
    """Return true only when the conversation actually contains movie cards."""
    return any(
        item.get("role") == "assistant"
        and bool(item.get("recommended_movies") or item.get("movies"))
        for item in history or []
    )


def _request_before_latest_movie_cards(history: list[dict] | None) -> str:
    """Recover the user request that produced the latest structured movie cards."""
    items = list(history or [])
    for assistant_index in range(len(items) - 1, -1, -1):
        item = items[assistant_index]
        if item.get("role") != "assistant" or not (
            item.get("recommended_movies") or item.get("movies")
        ):
            continue
        for user_index in range(assistant_index - 1, -1, -1):
            user_item = items[user_index]
            if user_item.get("role") == "user":
                return str(user_item.get("content") or "").strip()
    return ""


def _recommendation_thread_request(history: list[dict] | None) -> str:
    """Rebuild the active recommendation request, including chained refinements."""
    items = list(history or [])
    root_index = None
    for index in range(len(items) - 1, -1, -1):
        item = items[index]
        if item.get("role") != "user":
            continue
        content = str(item.get("content") or "").strip()
        if _MOVIE_CONTEXT.search(content) and not _FOLLOWUP.search(content):
            root_index = index
            break
    if root_index is None:
        return _recent_movie_request(history) or _request_before_latest_movie_cards(history)

    messages = [str(items[root_index].get("content") or "").strip()]
    for item in items[root_index + 1:]:
        if item.get("role") != "user":
            continue
        content = str(item.get("content") or "").strip()
        if content and _FOLLOWUP.search(content):
            messages.append(content)
    return " ".join(messages)


def is_movie_recommendation_followup(user_message: str, history: list[dict] | None) -> bool:
    return bool(
        _FOLLOWUP.search(user_message)
        and (_recent_movie_request(history) or _has_structured_recommendations(history))
    )


def _previous_titles(history: list[dict] | None) -> list[str]:
    titles = []
    for item in reversed(history or []):
        if item.get("role") != "assistant":
            continue
        for movie in item.get("recommended_movies") or item.get("movies") or []:
            title = str(movie.get("title") or "").strip() if isinstance(movie, dict) else ""
            if title and title not in titles:
                titles.append(title)
        for title in _QUOTED_TITLE.findall(str(item.get("content") or "")):
            title = title.strip()
            if title and title not in titles:
                titles.append(title)
        if titles:
            break
    return titles


def build_recommendation_context(
    user_message: str,
    history: list[dict] | None,
) -> RecommendationContext:
    excluded_genres = []
    for match in _COORDINATED_NEGATED_GENRES.finditer(user_message):
        for genre in match.groups():
            if genre not in excluded_genres:
                excluded_genres.append(genre)
    for match in _NEGATED_GENRE.finditer(user_message):
        genre = match.group(1)
        if genre not in excluded_genres:
            excluded_genres.append(genre)
    compound_negation = re.search(rf"({_GENRE_ALT})\s+({_GENRE_ALT})\s*말고", user_message)
    if compound_negation:
        first, second = compound_negation.groups()
        if second in excluded_genres:
            excluded_genres.remove(second)
        if first not in excluded_genres:
            excluded_genres.append(first)
    for match in re.finditer(rf"({_GENRE_ALT})도\s*({_GENRE_ALT})도\s*없", user_message):
        for genre in match.groups():
            if genre not in excluded_genres:
                excluded_genres.append(genre)
    for match in re.finditer(rf"({_GENRE_ALT})만\s*아니면", user_message):
        genre = match.group(1)
        if genre not in excluded_genres:
            excluded_genres.append(genre)
    for match in re.finditer(rf"({_GENRE_ALT})\s*장르\s*조건만\s*(?:빼|제외|취소)", user_message):
        genre = match.group(1)
        if genre not in excluded_genres:
            excluded_genres.append(genre)
    for match in re.finditer(rf"({_GENRE_ALT}).{{0,8}}싫어하는\s*건\s*아니", user_message):
        genre = match.group(1)
        if genre in excluded_genres:
            excluded_genres.remove(genre)
    if re.search(r"공포\s*영화는?\s*맞", user_message) and "공포" in excluded_genres:
        excluded_genres.remove("공포")
    if re.search(r"액션\s*코미디.{0,12}괜찮", user_message) and "액션" in excluded_genres:
        excluded_genres.remove("액션")
    horror_is_explicitly_allowed = bool(
        re.search(r"공포.{0,10}싫어하는\s*건\s*아니", user_message)
        or re.search(r"공포\s*영화는?\s*맞", user_message)
    )
    if (
        _COLLOQUIAL_HORROR_NEGATION.search(user_message)
        and not horror_is_explicitly_allowed
        and "공포" not in excluded_genres
    ):
        excluded_genres.append("공포")

    previous_request = _recommendation_thread_request(history)
    followup = bool(previous_request and _FOLLOWUP.search(user_message))
    if not followup:
        return RecommendationContext(
            search_message=user_message,
            excluded_genres=excluded_genres,
        )

    if _FULL_PREFERENCE_RESET.search(user_message):
        search_message = user_message
    else:
        if _YEAR_RELEASE.search(user_message) or _YEAR_OVERRIDE.search(user_message):
            previous_request = _YEAR_EXPRESSION.sub("", previous_request)
        if _LANGUAGE_OVERRIDE.search(user_message):
            previous_request = _LANGUAGE_EXPRESSION.sub("", previous_request)
        search_message = f"{previous_request} {user_message}"

    return RecommendationContext(
        search_message=search_message,
        is_followup=True,
        excluded_genres=excluded_genres,
        excluded_titles=_previous_titles(history),
    )
