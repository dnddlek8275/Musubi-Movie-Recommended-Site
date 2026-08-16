"""Generate a short, grounded copy for an already-selected daily movie set."""

from __future__ import annotations

import re


def fallback_daily_copy(genre: str) -> str:
    normalized_genre = str(genre or "영화").strip() or "영화"
    return f"오늘은 {normalized_genre}의 매력을 서로 다른 분위기로 즐길 수 있는 세 편을 골라봤어요."


def validate_daily_copy(text: str, genre: str, movies: list[dict]) -> str:
    """Return a safe one-line copy, or an empty string when it is not grounded."""
    normalized = re.sub(r"\s+", " ", str(text or "")).strip()
    normalized = normalized.strip("*#-• ")
    expected_genre = str(genre or "").strip()
    titles = {
        str(movie.get("title") or "").strip()
        for movie in movies
        if str(movie.get("title") or "").strip()
    }

    if not normalized or len(normalized) > 80:
        return ""
    if expected_genre and expected_genre not in normalized:
        return ""
    if any(title in normalized for title in titles):
        return ""
    if len(re.findall(r"[.!?。]", normalized)) > 1:
        return ""
    return normalized


def generate_daily_copy(genre: str, movies: list[dict]) -> str:
    """Let the LLM phrase a theme without allowing it to select other movies."""
    from llm.client import chat

    title_list = " / ".join(
        str(movie.get("title") or "").strip()
        for movie in movies
        if str(movie.get("title") or "").strip()
    )
    messages = [
        {
            "role": "system",
            "content": (
                "너는 Musubi 홈 화면의 짧은 추천 문구 편집자다. 영화 선택은 이미 끝났다. "
                "전달받은 장르와 세 영화 전체에 공통으로 어울리는 부드러운 한국어 한 문장만 작성한다. "
                "영화를 새로 추천하거나 영화 제목·개별 줄거리·확인되지 않은 사실을 언급하지 않는다. "
                "반드시 전달받은 장르명을 그대로 한 번 포함하고 45자 안팎으로 작성한다. "
                "마크다운과 따옴표는 사용하지 않는다."
            ),
        },
        {
            "role": "user",
            "content": (
                f"장르: {genre}\n"
                f"이미 선정된 영화: {title_list}\n"
                "이 목록을 바꾸지 말고 홈 화면에 표시할 공통 추천 문구 한 문장만 작성해 주세요."
            ),
        },
    ]
    raw = chat(messages, max_tokens=96, profile="grounded_recommendation")
    return validate_daily_copy(raw, genre, movies) or fallback_daily_copy(genre)
