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
    r"영화|추천|뭐\s*볼|볼\s*만한|장르|감독|배우|개봉|평점|"
    + _GENRE_ALT,
    re.IGNORECASE,
)
_FOLLOWUP = re.compile(
    r"너무\s*(?:무겁|무거|어둡|어두|우울|슬프|슬퍼|무섭|무서|잔인|폭력적|길|오래됐)|"
    r"(?:좀\s*)?더\s*(?:밝|가볍|가벼|유쾌|최신|최근|짧|재밌)|"
    r"다른\s*(?:거|것|걸|건|게|영화|작품)(?:도|은|는|을|이|가)?|"
    r"또\s*(?:보여|알려|추천|골라)|추가로\s*(?:보여|알려|추천|골라)|"
    r"별로|마음에\s*안|싫어|싫다|말고|빼줘|빼고|제외|조건.{0,20}무시|"
    r"추천.{0,12}왜.{0,8}안\s*해|"
    r"(?:네가|그냥).{0,12}(?:하나|한\s*편|두\s*개|두\s*편)?\s*(?:골라|추천)|"
    r"(?:요즘|근래|최근)\s*(?:거|것|영화|작품)?\s*(?:없어|없나|있어|있나)?|"
    r"(?:나머지\s*)?조건(?:은|을|도)?\s*(?:그대로|유지)|나머지.{0,12}그대로|"
    r"(?:관객|평점|상영\s*시간|연도).{0,16}기준(?:만|을)?\s*.{0,12}(?:낮춰|높여|완화|바꿔)|"
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
_REALTIME_OTT_REQUEST = re.compile(
    r"(?:넷플릭스|티빙|왓챠|웨이브|디즈니\s*플러스|쿠팡\s*플레이|OTT).{0,32}"
    r"(?:지금|현재|오늘|있|바로\s*볼|볼\s*수|제공|스트리밍|내려간)",
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
    (re.compile(r"네\s*번째|4\s*번째|넷째"), 3),
    (re.compile(r"다섯\s*번째|5\s*번째|다섯째"), 4),
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
_PERSON_OVERRIDE = re.compile(
    r"(?P<old>[가-힣A-Za-z·]{2,24})\s*(?:배우|감독)?\s*말고\s*"
    r"(?P<new>[가-힣A-Za-z·]{2,24})(?:\s*(?:배우|감독))?(?:으?로)?\s*"
    r"(?:바꿔|변경|교체)",
    re.IGNORECASE,
)


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


def _directly_mentioned_movie(user_message: str, movies: list[dict]) -> dict | None:
    matches = [
        movie for movie in movies
        if str(movie.get("title") or "").strip()
        and str(movie.get("title") or "").strip() in user_message
    ]
    return max(matches, key=lambda movie: len(str(movie.get("title") or "")), default=None)


def _lightness_score(movie: dict) -> int:
    scores = {
        "코미디": 4,
        "가족": 3,
        "애니메이션": 3,
        "음악": 2,
        "모험": 1,
        "로맨스": 1,
        "드라마": -1,
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

    if is_realtime_ott_request(user_message):
        return (
            "현재 카드에는 실시간 OTT 제공 정보가 없어 한국에서 지금 볼 수 있는지는 확인할 수 없어.",
            [],
        )

    if re.search(r"첫\s*번째.{0,20}두\s*번째.{0,24}감독", user_message):
        compared = movies[:2]
        if len(compared) < 2:
            return "비교할 영화 카드가 두 편보다 적어.", []
        first_director = str(compared[0].get("director") or "").strip()
        second_director = str(compared[1].get("director") or "").strip()
        if not first_director or not second_director:
            return "두 카드에 감독 정보가 모두 있어야 같은 감독인지 비교할 수 있어.", []
        relation = "같은 감독" if first_director == second_director else "서로 다른 감독"
        return (
            f"첫 번째 ‘{compared[0]['title']}’은 {first_director}, 두 번째 ‘{compared[1]['title']}’은 "
            f"{second_director} 감독이라 {relation}이야.",
            compared,
        )

    if re.search(r"주연|조연|특별\s*출연|카메오|출연\s*시간|분량", user_message):
        return (
            "현재 카드에는 출연진 명단만 있고 주연·특별출연 여부나 출연 분량 정보는 없어 정확히 구분할 수 없어.",
            [],
        )

    directly_mentioned = _directly_mentioned_movie(user_message, movies)
    if directly_mentioned:
        title = str(directly_mentioned.get("title") or "").strip()
        direct_fields = (
            (r"감독", "director", "감독"),
            (r"(?:배우|출연진)", "cast", "출연진"),
            (r"(?:개봉\s*연도|몇\s*년|연도)", "year", "개봉 연도"),
        )
        for pattern, field, label in direct_fields:
            if not re.search(pattern, user_message):
                continue
            value = directly_mentioned.get(field)
            if isinstance(value, list):
                value = ", ".join(str(item) for item in value if item)
            value = str(value or "").strip()
            if value:
                suffix = "년" if field == "year" and not value.endswith("년") else ""
                return f"‘{title}’의 카드 등록 {label} 정보는 {value}{suffix}이야.", [directly_mentioned]
            return f"‘{title}’의 {label} 정보는 현재 카드에 없어.", [directly_mentioned]
        if re.search(r"장르", user_message):
            genre_text = " · ".join(_genre_names(directly_mentioned))
            if genre_text:
                return f"‘{title}’은 카드에 {genre_text} 장르로 등록되어 있어.", [directly_mentioned]
            return f"‘{title}’의 장르 정보는 현재 카드에 없어.", [directly_mentioned]

    if re.search(r"(?:왜|이유).{0,16}추천|추천.{0,16}(?:왜|이유)", user_message):
        selected = movies[0]
        title = str(selected.get("title") or "").strip()
        reason = str(selected.get("recommendation_reason") or "").strip()
        if reason:
            return f"‘{title}’은 {reason}", [selected]
        genres = _genre_names(selected)
        if genres:
            return f"‘{title}’은 카드에 {' · '.join(genres[:2])} 장르로 등록되어 있어서 추천됐어.", [selected]
        return f"현재 카드에는 ‘{title}’의 구체적인 추천 근거가 저장되어 있지 않아.", [selected]

    if re.search(r"(?:가장|제일)\s*(?:최근|최신)|(?:최근|최신).{0,8}(?:뭐|어느|어떤)", user_message):
        dated = [(movie, int(movie.get("year") or 0)) for movie in movies if movie.get("year")]
        if not dated:
            return "현재 카드에는 개봉 연도 정보가 없어 최신 작품을 비교할 수 없어.", []
        selected, year = max(dated, key=lambda item: item[1])
        return f"셋 중 가장 최근 작품은 {year}년의 ‘{selected['title']}’이야.", [selected]

    if re.search(r"(?:셋|세\s*편|카드).{0,20}(?:제일|가장).{0,12}(?:가볍|웃기)", user_message):
        ranked = sorted(movies, key=_lightness_score, reverse=True)
        if len(ranked) > 1 and _lightness_score(ranked[0]) == _lightness_score(ranked[1]):
            tied = [movie for movie in ranked if _lightness_score(movie) == _lightness_score(ranked[0])]
            titles = ", ".join(f"‘{movie['title']}’" for movie in tied)
            return f"카드 장르 정보만으로는 {titles} 중 어느 작품이 더 가벼운지 구분하기 어려워.", tied
        selected = ranked[0]
        return f"카드 장르 정보만 보면 ‘{selected['title']}’이 가장 가볍게 웃기 좋은 쪽이야.", [selected]

    if re.search(r"평점.{0,12}(?:제일|가장|높)", user_message):
        rated = [
            (movie, float(movie.get("vote_average")))
            for movie in movies
            if movie.get("vote_average") not in (None, "")
        ]
        if not rated:
            return "현재 카드에는 평점 정보가 없어 어느 작품이 더 높은지 비교할 수 없어.", []
        selected, rating = max(rated, key=lambda item: item[1])
        return f"카드 평점이 가장 높은 작품은 {rating:g}점의 ‘{selected['title']}’이야.", [selected]

    if re.search(r"첫\s*번째.{0,12}두\s*번째.{0,16}평점", user_message):
        compared = movies[:2]
        if len(compared) < 2 or any(movie.get("vote_average") in (None, "") for movie in compared):
            return "첫 번째와 두 번째 카드에 평점 정보가 모두 있어야 비교할 수 있는데, 현재는 그 정보가 없어.", []
        selected = max(compared, key=lambda movie: float(movie["vote_average"]))
        return f"두 카드 중 평점이 높은 작품은 ‘{selected['title']}’이야.", [selected]

    genre_filter = next((genre for genre in GENRES if genre in user_message), None)
    if genre_filter and re.search(r"중.{0,16}(?:인\s*것만|장르)", user_message):
        selected = [movie for movie in movies if genre_filter in _genre_names(movie)]
        if not selected:
            return f"방금 카드 중 {genre_filter} 장르로 등록된 작품은 없어.", []
        titles = ", ".join(f"‘{movie['title']}’" for movie in selected)
        return f"방금 카드 중 {genre_filter} 장르는 {titles}이야.", selected

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
        return f"현재 추천 카드는 {len(movies)}편이라 {selected_index + 1}번째 영화는 없어.", []
    selected = movies[selected_index]
    title = str(selected.get("title") or "").strip()
    if _OVERVIEW_REQUEST.search(user_message):
        overview = str(selected.get("overview") or "").strip()
        if overview:
            return f"‘{title}’의 등록된 줄거리는 이래. {overview}", [selected]
        return f"‘{title}’의 줄거리 정보는 현재 카드에 없어.", [selected]
    if _TITLE_RECALL.search(user_message) and not re.search(
        r"장르|감독|주연|배우|출연|언어|어느\s*나라\s*말",
        user_message,
    ):
        return f"{selected_index + 1}번째 영화는 ‘{title}’이야.", [selected]
    if re.search(r"장르", user_message):
        genre_text = " · ".join(_genre_names(selected))
        if genre_text:
            return f"‘{title}’은 카드에 {genre_text} 장르로 등록되어 있어.", [selected]
        return f"‘{title}’의 장르 정보는 현재 카드에 없어.", [selected]
    metadata_requests = (
        (r"감독", "director", "감독"),
        (r"(?:주연|배우|출연)", "cast", "배우"),
        (r"(?:언어|어느\s*나라\s*말)", "language", "언어"),
    )
    for pattern, field, label in metadata_requests:
        if not re.search(pattern, user_message):
            continue
        value = selected.get(field)
        if isinstance(value, list):
            value = ", ".join(str(item) for item in value if item)
        value = str(value or "").strip()
        if value:
            return f"‘{title}’의 카드 등록 {label} 정보는 {value}야.", [selected]
        return f"‘{title}’의 {label} 정보는 현재 카드에 없어.", [selected]
    return None


def is_realtime_ott_request(user_message: str) -> bool:
    """Whether answering requires current regional streaming-provider data."""
    return bool(_REALTIME_OTT_REQUEST.search(user_message))


def is_card_followup_question(user_message: str, history: list[dict] | None) -> bool:
    movies = _latest_structured_movies(history)
    if not movies:
        return False
    return bool(
        _mentioned_ordinal(user_message) is not None
        or (
            _directly_mentioned_movie(user_message, movies) is not None
            and re.search(r"감독|배우|출연진|개봉\s*연도|몇\s*년|연도|장르", user_message)
        )
        or re.search(r"주연|조연|특별\s*출연|카메오|출연\s*시간|분량", user_message)
        or re.search(
            r"(?:넷플릭스|티빙|왓챠|웨이브|디즈니\s*플러스|쿠팡\s*플레이|OTT).{0,24}"
            r"(?:지금|현재|있|볼\s*수|제공|스트리밍)",
            user_message,
            re.IGNORECASE,
        )
        or re.search(r"(?:왜|이유).{0,16}추천|추천.{0,16}(?:왜|이유)", user_message)
        or re.search(r"(?:셋|세\s*편|카드|방금).{0,20}(?:최근|최신|평점|장르|제목)", user_message)
        or re.search(r"(?:셋|세\s*편|카드).{0,20}(?:제일|가장).{0,12}(?:가볍|웃기)", user_message)
        or re.search(r"평점.{0,12}(?:제일|가장|높)", user_message)
    )


def _recent_movie_request(history: list[dict] | None) -> str:
    items = list(history or [])
    for item in reversed(items):
        if item.get("role") != "user":
            continue
        content = str(item.get("content") or "").strip()
        if _MOVIE_CONTEXT.search(content):
            return content

    # A vague first turn can be clarified by the assistant as a movie offer.
    # Recover the user request immediately before that offer so a response such
    # as "네가 하나 골라줘" remains in the recommendation pipeline.
    for assistant_index in range(len(items) - 1, -1, -1):
        item = items[assistant_index]
        if item.get("role") != "assistant":
            continue
        content = str(item.get("content") or "").strip()
        if not _MOVIE_CONTEXT.search(content):
            continue
        for user_index in range(assistant_index - 1, -1, -1):
            user_item = items[user_index]
            if user_item.get("role") == "user":
                return str(user_item.get("content") or "").strip()
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


def _add_contextual_genre_exclusions(text: str, excluded_genres: list[str]) -> None:
    """Interpret rejection/comfort language before positive genre extraction."""
    complaint = re.search(
        rf"((?:{_GENRE_ALT})(?:[\s·,/]+(?:{_GENRE_ALT}))*)\s*(?:잖아|인데).{{0,100}}"
        r"(?:조건.{0,20}무시|원한.{0,12}아니|왜.{0,20}(?:추천|나와)|빼)",
        text,
        re.IGNORECASE,
    )
    if complaint:
        for genre in re.findall(_GENRE_ALT, complaint.group(1), re.IGNORECASE):
            if genre not in excluded_genres:
                excluded_genres.append(genre)

    if re.search(r"잔인(?:한|한\s*걸|한\s*건|함).{0,12}(?:못\s*봐|싫|피하)|폭력적.{0,12}(?:못\s*봐|싫|피하)", text):
        for genre in ("공포", "전쟁"):
            if genre not in excluded_genres:
                excluded_genres.append(genre)

    if re.search(r"편하게\s*웃|머리\s*비우고\s*웃|웃기기만", text):
        for genre in ("공포", "스릴러"):
            explicitly_requested = re.search(
                rf"{genre}.{{0,24}}(?:추천|골라|보고\s*싶|볼\s*(?:래|거|영화)|원해)",
                text,
            )
            if not explicitly_requested and genre not in excluded_genres:
                excluded_genres.append(genre)

    if re.search(
        r"(?:부모님|가족).{0,30}(?:잔인하지|폭력적이지)|"
        r"(?:잔인하지|폭력적이지).{0,30}(?:부모님|가족)",
        text,
    ):
        for genre in ("공포", "전쟁", "범죄", "스릴러"):
            if genre not in excluded_genres:
                excluded_genres.append(genre)


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
        _add_contextual_genre_exclusions(user_message, excluded_genres)
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
        person_override = _PERSON_OVERRIDE.search(user_message)
        if person_override:
            old_person = person_override.group("old")
            previous_request = re.sub(
                rf"{re.escape(old_person)}(?:\s*(?:배우|감독))?",
                "",
                previous_request,
            )
        search_message = f"{previous_request} {user_message}"

    _add_contextual_genre_exclusions(search_message, excluded_genres)
    if (
        _COLLOQUIAL_HORROR_NEGATION.search(search_message)
        and not horror_is_explicitly_allowed
        and "공포" not in excluded_genres
    ):
        excluded_genres.append("공포")

    return RecommendationContext(
        search_message=search_message,
        is_followup=True,
        excluded_genres=excluded_genres,
        excluded_titles=_previous_titles(history),
    )
