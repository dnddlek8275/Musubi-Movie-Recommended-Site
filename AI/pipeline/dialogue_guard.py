"""Deterministic dialogue guards shared by general and character chat.

The log deliberately excludes raw user/assistant text.  It is intended to show
which guard is firing often enough to deserve a reviewed template later.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path


_AI_DIR = Path(__file__).resolve().parents[1]
DEFAULT_LOG_PATH = _AI_DIR / "logs" / "dialogue-guard.jsonl"

_USER_ROLE_REQUEST = re.compile(
    r"^.{0,50}(?:추천|골라|찾아|보여|설명)\s*(?:해\s*)?(?:줘|주세요|줄래)[.!?~]*$",
    re.IGNORECASE,
)
_ROLE_MARKER = re.compile(
    r"(?:<\|?user\|?>|<start_of_turn>\s*user|^\s*user\s*:|^\s*사용자\s*:)",
    re.IGNORECASE,
)


def output_rejection_reason(answer: str, user_message: str) -> str | None:
    """Return a reason when the model emitted a new user turn instead of an answer.

    Follow-up questions such as ``원하는 장르를 알려줘`` are valid.  The narrow
    request-like check only rejects a short answer that asks the assistant to do
    recommendation/search work, which is a leaked synthetic user turn.
    """
    text = " ".join(str(answer or "").split()).strip()
    if not text:
        return "empty_output"
    if _ROLE_MARKER.search(text):
        return "user_role_marker"
    if len(text) <= 80 and _USER_ROLE_REQUEST.fullmatch(text):
        return "generated_user_request"

    normalize = lambda value: re.sub(r"[^0-9A-Za-z가-힣]+", "", str(value or "")).casefold()
    answer_key = normalize(text)
    user_key = normalize(user_message)
    if len(user_key) >= 4 and answer_key == user_key:
        return "user_echo"
    return None


def general_history_recall_reply(user_message: str, history: list[dict]) -> str | None:
    """Answer explicit recent-movie recall questions only from recorded history."""
    compact = re.sub(r"\s+", "", str(user_message or ""))
    if not (
        re.search(r"(?:방금|아까|전에).*(?:말한|얘기한)", compact)
        and re.search(r"영화.*(?:뭐|무엇|제목)", compact)
    ):
        return None

    patterns = (
        re.compile(
            r"(?:가장\s*)?(?:좋아하는\s*)?영화(?:는|가)?\s*['\"‘“]?"
            r"([^.!?\n'\"’”]{1,50}?)['\"’”]?(?:이야|야|예요|에요|라고|였)"
        ),
        re.compile(
            r"['\"‘“]([^.!?\n'\"’”]{1,50})['\"’”].{0,12}(?:영화|작품)"
        ),
    )
    for item in reversed(history):
        if item.get("role") != "user":
            continue
        content = str(item.get("content") or "").strip()
        for pattern in patterns:
            match = pattern.search(content)
            if match:
                title = match.group(1).strip(" ,:：")
                if title:
                    return f"방금 말한 영화는 {title}야."
    return "대화 기록에서 방금 말한 영화 제목을 정확히 확인하지 못했어. 제목을 한 번만 다시 알려줘."


def log_dialogue_guard_event(
    *,
    reason: str,
    mode: str,
    user_message: str,
    character_name: str | None = None,
) -> None:
    """Append a privacy-minimal guard event without storing conversation text."""
    raw = str(user_message or "")
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "reason": str(reason),
        "mode": str(mode),
        "character": str(character_name or ""),
        "input_length": len(raw),
        "input_hash": hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16],
    }
    path = Path(os.getenv("DIALOGUE_GUARD_LOG_PATH", str(DEFAULT_LOG_PATH)))
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, ensure_ascii=False) + "\n")
    except OSError as exc:
        print(f"  [DialogueGuard] 로그 저장 실패: {exc}")
