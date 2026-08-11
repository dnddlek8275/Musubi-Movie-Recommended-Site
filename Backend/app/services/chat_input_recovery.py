"""Fast, deterministic replies for incomplete or reaction-only general chat input."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass


RECOVERY_UI_DELAY_SECONDS = 0.6

_LAUGHTER = re.compile(r"^(?:ㅋ{2,}|ㅎ{2,}|(?:하){2,})[\s!?.~]*$")
_SADNESS = re.compile(r"^(?:ㅠ+|ㅜ+|😢+|😭+|🥲+)[\s!?.~]*$")
_ELLIPSIS = re.compile(r"^(?:\.{2,}|…+)$")
_JAMO_ONLY = re.compile(r"^[ㄱ-ㅎㅏ-ㅣ\s!?.~]+$")
_PUNCTUATION_ONLY = re.compile(r"^[\s.,!~;:'\"`()\[\]{}\-_=+*/\\|]+$")

# 자모만으로 구성돼도 독립된 발화로 널리 쓰이는 한국어 채팅 표현이다.
# 난타로 단정하지 않고 이전 대화 기록과 함께 LLM이 해석하게 한다.
MEANINGFUL_JAMO_SHORTHANDS = {"ㅇㅇ", "ㄴㄴ", "ㄱㄱ", "ㅎㅇ"}


@dataclass(frozen=True)
class ChatInputRecovery:
    answer: str
    emotion: str = "default"
    kind: str = "incomplete"


async def wait_for_recovery_ui() -> None:
    """Keep the existing typing indicator visible long enough to be perceived."""
    await asyncio.sleep(RECOVERY_UI_DELAY_SECONDS)


def get_general_chat_recovery(message: str) -> ChatInputRecovery | None:
    """Return a recovery reply only when the input carries no safe conversational intent."""
    text = str(message or "").strip()
    if not text:
        return None
    shorthand = re.sub(r"[\s!?.~]+$", "", text)
    if shorthand in MEANINGFUL_JAMO_SHORTHANDS:
        return None
    if _LAUGHTER.fullmatch(text):
        return ChatInputRecovery(
            answer="뭔가 재미있는 일이 있었나 봐요. 무슨 일인지 들려주세요.",
            emotion="joy",
            kind="laughter",
        )
    if _SADNESS.fullmatch(text):
        return ChatInputRecovery(
            answer="속상한 일이 있었나요? 괜찮다면 천천히 이야기해 주세요.",
            emotion="sorry",
            kind="sadness",
        )
    if _ELLIPSIS.fullmatch(text):
        return ChatInputRecovery(
            answer="말을 고르는 중인가요? 천천히 이야기해도 괜찮아요.",
            emotion="thinking",
            kind="ellipsis",
        )
    if text == "?":
        return ChatInputRecovery(
            answer="궁금한 점이 있나요? 편하게 이어서 말해 주세요.",
            emotion="thinking",
            kind="question_mark",
        )
    if _JAMO_ONLY.fullmatch(text) and re.search(r"[ㄱ-ㅎㅏ-ㅣ]", text):
        return ChatInputRecovery(
            answer="혹시 입력 중이었나요? 어떤 이야기를 하고 싶었는지 조금만 더 알려주세요.",
            emotion="thinking",
            kind="ambiguous_jamo",
        )
    if _PUNCTUATION_ONLY.fullmatch(text):
        return ChatInputRecovery(
            answer="혹시 입력 중이었나요? 편하게 이어서 이야기해 주세요.",
            emotion="thinking",
            kind="punctuation",
        )
    return None
