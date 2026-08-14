"""Deterministic tone checks for non-character recommendation answers."""

from __future__ import annotations

import re


_SENTENCE_END = r"(?=\s*(?:[.!?。]|$))"
_INFORMAL_ENDING = re.compile(
    rf"(?:아니야|거야|딱이야|영화야|작품이야|할게|볼래|어때|같아|좋아|"
    rf"있어|없어|재밌어|즐거워|가벼워|해|돼|봐|한다|이다|하겠다|(?<!니)다){_SENTENCE_END}"
)
_STIFF_ENDING = re.compile(rf"니다{_SENTENCE_END}")
_ENDING_REPLACEMENTS = (
    ("아니야", "아니에요"),
    ("거야", "거예요"),
    ("딱이야", "딱이에요"),
    ("영화야", "영화예요"),
    ("작품이야", "작품이에요"),
    ("재밌어", "재밌어요"),
    ("즐거워", "즐거워요"),
    ("가벼워", "가벼워요"),
    ("할게", "할게요"),
    ("볼래", "보실래요"),
    ("어때", "어떠세요"),
    ("같아", "같아요"),
    ("좋아", "좋아요"),
    ("있어", "있어요"),
    ("없어", "없어요"),
    ("해", "해요"),
    ("돼", "돼요"),
    ("봐", "보세요"),
)
_STIFF_REPLACEMENTS = (
    ("있습니다", "있어요"),
    ("없습니다", "없어요"),
    ("됩니다", "돼요"),
    ("좋습니다", "좋아요"),
    ("같습니다", "같아요"),
    ("영화입니다", "영화예요"),
    ("작품입니다", "작품이에요"),
    ("드립니다", "드려요"),
    ("합니다", "해요"),
    ("입니다", "이에요"),
)


def has_informal_ending(text: str) -> bool:
    return bool(_INFORMAL_ENDING.search(text or ""))


def has_stiff_ending(text: str) -> bool:
    return bool(_STIFF_ENDING.search(text or ""))


def _polite_movie_fallback(movies: list[dict]) -> str:
    titles = [str(movie.get("title") or "").strip() for movie in movies]
    titles = [title for title in titles if title]
    if not titles:
        return "조건에 맞는 영화를 찾지 못했어요. 다른 분위기나 장르를 알려주시겠어요?"

    quoted = [f"‘{title}’" for title in titles[:3]]
    title_text = " · ".join(quoted)
    return (
        "다음 영화들을 골라봤어요.\n\n"
        f"{title_text}\n\n"
        "요청하신 조건과 가까운 작품들이니 취향에 맞는 영화를 골라보세요.\n\n"
        "이 중에 끌리는 영화가 있나요?"
    )


def enforce_general_polite_answer(text: str, movies: list[dict]) -> str:
    """Correct common informal endings and fall back if an unsafe form remains."""
    polished = text or ""
    for stiff, soft in _STIFF_REPLACEMENTS:
        polished = re.sub(re.escape(stiff) + _SENTENCE_END, soft, polished)
    for informal, polite in _ENDING_REPLACEMENTS:
        polished = re.sub(re.escape(informal) + _SENTENCE_END, polite, polished)
    if has_informal_ending(polished) or has_stiff_ending(polished):
        return _polite_movie_fallback(movies)
    return polished
