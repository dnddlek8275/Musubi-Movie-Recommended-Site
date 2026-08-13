"""High-confidence ambiguous input guard for direct AI API callers."""

from __future__ import annotations

import re
from dataclasses import dataclass


_LAUGHTER = re.compile(r"^(?:ㅋ{2,}|ㅎ{2,}|(?:하){2,})[\s!?.~]*$")
_SADNESS = re.compile(r"^(?:ㅠ+|ㅜ+|😢+|😭+|🥲+)[\s!?.~]*$")
_ELLIPSIS = re.compile(r"^(?:\.{2,}|…+)$")
_JAMO_ONLY = re.compile(r"^[ㄱ-ㅎㅏ-ㅣ\s!?.~]+$")
_PUNCTUATION_ONLY = re.compile(r"^[\s.,!~;:'\"`()\[\]{}\-_=+*/\\|]+$")
MEANINGFUL_JAMO_SHORTHANDS = {"ㅇㅇ", "ㄴㄴ", "ㄱㄱ", "ㅎㅇ"}
# 운영 제보로 의미 불명 입력임이 확인된 값만 차단한다. 짧은 영문 전체를
# 차단하면 Up/Hope 같은 영화 제목이나 SF/AI 같은 정상 입력까지 막을 수 있다.
KNOWN_AMBIGUOUS_ASCII_INPUTS = {"cd", "cfr"}

_CONTEXT_FREE_SHORT_REPLIES = {
    "ㅇㅇ": "응, 이어서 말해줘.",
    "ㄴㄴ": "알겠어. 그럼 어떤 쪽이 좋은지 말해줘.",
    "ㄱㄱ": "좋아, 해보자.",
    "ㅎㅇ": "안녕! 오늘은 어떤 이야기 해볼까?",
}

_GENERAL_TEMPLATE_RULES = (
    (
        re.compile(r"^(?:고마워|고맙다|감사해|감사합니다|땡큐)[\s!?.~]*$", re.IGNORECASE),
        "별말을 다 해. 또 궁금한 영화나 이야기가 있으면 말해줘.",
    ),
    (
        re.compile(r"^(?:잘\s*가|안녕히\s*가세요|바이|다음에\s*(?:봐|보자))[\s!?.~]*$", re.IGNORECASE),
        "그래, 다음에 또 영화 이야기하자.",
    ),
    (
        re.compile(
            r"^(?:(?:너|무무)(?:는|가)?\s*)?(?:뭘|뭐를|무엇을|어떤\s*걸?)\s*"
            r"(?:할\s*수\s*있어|도와줄\s*수\s*있어|해줄\s*수\s*있어)[\s?!.~]*$",
            re.IGNORECASE,
        ),
        "영화를 검색하거나 추천하고, 영화 정보와 네 취향에 관해 이야기할 수 있어.",
    ),
)

_MUMU_IDENTITY_REPLY = "나는 Musubi에서 영화 이야기를 함께하는 AI 친구, 무무야."
_IDENTITY_MEDIA_WORDS = ("영화", "작품", "배우", "캐릭터", "노래", "감독")
_DIRECT_IDENTITY_MARKERS = (
    "네이름", "너이름", "너의이름", "니이름", "당신이름", "당신의이름",
    "넌누구", "너는누구", "너누구", "당신은누구",
    "네정체", "너의정체", "정체가뭐", "정체는뭐",
)
_IDENTITY_ONLY_QUESTION = re.compile(
    r"^(?:이름(?:이|은)?뭐(?:야|예요|에요)?|누구(?:야|니|예요|에요)?|정체(?:가|는)?뭐(?:야|예요|에요)?)[?!.~]*$"
)
_MUMU_PERSONAL_CHAT_PATTERNS = re.compile(
    r"(?:너|넌|너는|네가|니가|무무(?:는|가)?).{0,30}"
    r"(?:봤어|본\s*적|가봤|해봤|느꼈|감동(?:했|한\s*적)|마음에\s*와닿|기억해|경험|좋아해|싫어해)|"
    r"(?:내가|내|우리).{0,30}기억해|"
    r"(?:어떻게|뭘로).{0,15}(?:내|나의)\s*취향.{0,10}(?:알|파악)|"
    r"(?:이|그|저)\s*영화.{0,20}(?:봤어|본\s*적)",
    re.IGNORECASE,
)
_EXPLICIT_RECOMMENDATION_REQUEST = re.compile(
    r"추천|골라\s*줘|찾아\s*줘|뭐\s*볼|볼만한|보여\s*줘",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class AIInputRecovery:
    answer: str
    kind: str


def get_input_recovery(message: str) -> AIInputRecovery | None:
    """Classify deterministic recovery inputs consistently with Backend.

    Common Korean chat shorthand is intentionally left to the LLM together with
    conversation history. Mixed natural language such as ``ㄴㄴ 그거 말고`` is
    also never intercepted here.
    """
    text = str(message or "").strip()
    if not text:
        return None

    shorthand = re.sub(r"[\s!?.~]+$", "", text)
    if shorthand in MEANINGFUL_JAMO_SHORTHANDS:
        return None

    if _LAUGHTER.fullmatch(text):
        return AIInputRecovery(
            answer="뭔가 재미있는 일이 있었나 봐. 무슨 일인지 말해줘.",
            kind="laughter",
        )
    if _SADNESS.fullmatch(text):
        return AIInputRecovery(
            answer="속상한 일이 있었어? 괜찮으면 천천히 말해줘.",
            kind="sadness",
        )
    if _ELLIPSIS.fullmatch(text):
        return AIInputRecovery(
            answer="말을 고르는 중이야? 천천히 말해도 괜찮아.",
            kind="ellipsis",
        )
    if text == "?":
        return AIInputRecovery(
            answer="궁금한 게 있어? 편하게 이어서 말해줘.",
            kind="question_mark",
        )
    if _JAMO_ONLY.fullmatch(text) and re.search(r"[ㄱ-ㅎㅏ-ㅣ]", text):
        return AIInputRecovery(
            answer="방금 메시지는 뜻을 정확히 알기 어려워요. 어떤 말을 하려던 건지 한 번만 더 알려주세요.",
            kind="ambiguous_jamo",
        )
    if _PUNCTUATION_ONLY.fullmatch(text):
        return AIInputRecovery(
            answer="혹시 입력 중이었어? 편하게 이어서 말해줘.",
            kind="punctuation",
        )
    if text.casefold() in KNOWN_AMBIGUOUS_ASCII_INPUTS:
        return AIInputRecovery(
            answer="방금 입력은 뜻을 정확히 알기 어려워. 어떤 말을 하려던 건지 한 번만 더 알려줘.",
            kind="ambiguous_short_ascii",
        )
    return None


def get_ambiguous_input_reply(message: str) -> str | None:
    """Backward-compatible answer accessor used by existing chat pipelines."""
    recovery = get_input_recovery(message)
    return recovery.answer if recovery else None


def get_general_short_reply(message: str, *, has_history: bool) -> str | None:
    """Return a concise general-chat reply when no context is available.

    ``ㅎㅇ`` is an unambiguous greeting, so it stays concise even when history
    exists. The other shorthand values are left to the LLM whenever prior turns
    can determine what the user agreed with, rejected, or wants to start.
    """
    text = str(message or "").strip()
    shorthand = re.sub(r"[\s!?.~]+$", "", text)
    if shorthand not in MEANINGFUL_JAMO_SHORTHANDS:
        return None
    if has_history and shorthand != "ㅎㅇ":
        return None
    return _CONTEXT_FREE_SHORT_REPLIES[shorthand]


def get_general_template_reply(message: str) -> str | None:
    """Return a stable answer only for narrow, context-independent intents."""
    text = " ".join(str(message or "").split()).strip()
    if not text:
        return None
    for pattern, answer in _GENERAL_TEMPLATE_RULES:
        if pattern.fullmatch(text):
            return answer
    return None


def get_mumu_identity_reply(message: str) -> str | None:
    """Return Musubi's stable identity without asking the generative model.

    A narrow detector avoids treating questions about a movie, actor, or
    character name as questions about the assistant itself.
    """
    text = str(message or "").strip()
    if not text:
        return None

    compact = re.sub(r"\s+", "", text)
    if _IDENTITY_ONLY_QUESTION.fullmatch(compact):
        return _MUMU_IDENTITY_REPLY

    has_direct_marker = any(marker in compact for marker in _DIRECT_IDENTITY_MARKERS)
    asks_identity = any(token in compact for token in ("뭐", "무엇", "누구", "정체"))
    rename_request = (
        "이름" in compact
        and any(token in compact for token in ("바꿔", "바꾸", "지금부터", "오늘부터"))
    )
    mentions_media_target = any(word in compact for word in _IDENTITY_MEDIA_WORDS)

    if has_direct_marker and (asks_identity or rename_request) and not mentions_media_target:
        return _MUMU_IDENTITY_REPLY
    return None


def is_mumu_personal_chat(message: str) -> bool:
    """Whether the user asks Mumu for human experience, taste, or memory."""
    text = str(message or "").strip()
    return bool(
        text
        and _MUMU_PERSONAL_CHAT_PATTERNS.search(text)
        and not _EXPLICIT_RECOMMENDATION_REQUEST.search(text)
    )


def get_mumu_personal_reply(message: str) -> str | None:
    """Answer personal questions truthfully without fabricating human experience."""
    if not is_mumu_personal_chat(message):
        return None

    compact = re.sub(r"\s+", "", str(message or ""))
    if "취향" in compact and any(token in compact for token in ("알", "파악")):
        return "이 대화에서 네가 알려준 장르, 배우, 좋아하거나 싫어한 작품을 바탕으로 취향을 파악해."
    if "좋아" in compact or "싫어" in compact:
        return "나는 사람처럼 취향을 직접 느끼지는 않지만, 여러 영화의 매력을 비교하며 네 취향에 맞춰 이야기할 수 있어."
    if "기억" in compact:
        return "지금 대화에서 나눈 내용은 이어서 볼 수 있지만, 말해주지 않은 과거를 기억하는 척하진 않을게."
    return "나는 직접 영화관에 가거나 영화를 보지는 못하지만, 영화 정보와 네 이야기를 바탕으로 같이 이야기할 수 있어."
