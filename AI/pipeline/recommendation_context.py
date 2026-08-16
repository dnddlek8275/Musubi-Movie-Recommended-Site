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
    r"다른\s*(?:거|걸|영화|작품)|별로|마음에\s*안|싫어|싫다|말고|빼줘|제외|"
    r"\d{4}\s*년?\s*(?:이후|이전|부터|까지|이상|이하)?\s*만|"
    r"평점\s*\d+(?:\.\d+)?\s*(?:점|이상|이하)?\s*만?|"
    r"(?:한국어|영어|일본어|중국어|프랑스어)\s*(?:영화|작품)?\s*만",
    re.IGNORECASE,
)
_NEGATED_GENRE = re.compile(
    rf"({_GENRE_ALT})(?:는|은|이|가|를|을)?\s*(?:싫|말고|빼|제외)",
    re.IGNORECASE,
)
_COORDINATED_NEGATED_GENRES = re.compile(
    rf"({_GENRE_ALT})(?:와|과|,)\s*({_GENRE_ALT})(?:는|은|이|가|를|을)?\s*(?:싫|말고|빼|제외)",
    re.IGNORECASE,
)
_QUOTED_TITLE = re.compile(r"['‘’\"“”]([^'‘’\"“”]{1,80})['‘’\"“”]")


@dataclass
class RecommendationContext:
    search_message: str
    is_followup: bool = False
    excluded_genres: list[str] = field(default_factory=list)
    excluded_titles: list[str] = field(default_factory=list)


def _recent_movie_request(history: list[dict] | None) -> str:
    for item in reversed(history or []):
        if item.get("role") != "user":
            continue
        content = str(item.get("content") or "").strip()
        if _MOVIE_CONTEXT.search(content):
            return content
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
        return _recent_movie_request(history)

    messages = [str(items[root_index].get("content") or "").strip()]
    for item in items[root_index + 1:]:
        if item.get("role") != "user":
            continue
        content = str(item.get("content") or "").strip()
        if content and _FOLLOWUP.search(content):
            messages.append(content)
    return " ".join(messages)


def is_movie_recommendation_followup(user_message: str, history: list[dict] | None) -> bool:
    return bool(_FOLLOWUP.search(user_message) and _recent_movie_request(history))


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

    previous_request = _recommendation_thread_request(history)
    followup = bool(previous_request and _FOLLOWUP.search(user_message))
    if not followup:
        return RecommendationContext(
            search_message=user_message,
            excluded_genres=excluded_genres,
        )

    return RecommendationContext(
        search_message=f"{previous_request} {user_message}",
        is_followup=True,
        excluded_genres=excluded_genres,
        excluded_titles=_previous_titles(history),
    )
