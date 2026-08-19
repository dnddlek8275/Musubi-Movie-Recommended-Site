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
_MARKUP_ARTIFACT = re.compile(r"<\/?[A-Za-z][^>]*>|\bstyle\s*=", re.IGNORECASE)
_GENERATED_USER_META_QUESTION = re.compile(
    r"^(?:너|당신)(?:는|은|가)?\s*(?:내|나의)\s*(?:질문|말|요청)(?:을|를)?\s*"
    r".{0,12}(?:기억|이해|알고|들었).{0,25}[?？]?$",
    re.IGNORECASE,
)
_IDENTITY_DRIFT = re.compile(
    r"^(?:내\s*이름은|나는|전|저는)\s*(?!무무(?:야|예요|입니다|라고|\b))"
    r"[가-힣A-Za-z][가-힣A-Za-z0-9 ]{0,24}(?:야|예요|입니다|라고\s*해)[.!?~]*$",
    re.IGNORECASE,
)
_INVENTED_HUMAN_EXPERIENCE = re.compile(
    r"(?:나는|내가|저는|제가).{0,20}(?:어제|오늘|지난주).{0,30}"
    r"(?:영화관에\s*갔|영화를\s*봤|감동했|울었|웃었)",
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
    if _MARKUP_ARTIFACT.search(text):
        return "markup_artifact"
    if len(text) <= 80 and _USER_ROLE_REQUEST.fullmatch(text):
        return "generated_user_request"
    normalize = lambda value: re.sub(r"[^0-9A-Za-z가-힣]+", "", str(value or "")).casefold()
    answer_key = normalize(text)
    user_key = normalize(user_message)
    if len(user_key) >= 4 and answer_key == user_key:
        return "user_echo"
    return None


def general_output_rejection_reason(answer: str, user_message: str) -> str | None:
    """Apply common guards plus Mumu-only identity and experience boundaries."""
    reason = output_rejection_reason(answer, user_message)
    if reason:
        return reason
    text = " ".join(str(answer or "").split()).strip()
    if len(text) <= 100 and _GENERATED_USER_META_QUESTION.fullmatch(text):
        return "generated_user_meta_question"
    if _IDENTITY_DRIFT.fullmatch(text):
        return "assistant_identity_drift"
    if _INVENTED_HUMAN_EXPERIENCE.search(text):
        return "invented_human_experience"
    return None


def general_history_recall_reply(user_message: str, history: list[dict]) -> str | None:
    """Answer narrow recall questions only from explicit recorded user history."""
    compact = re.sub(r"\s+", "", str(user_message or ""))
    if re.search(r"(?:왜.*자신감.*떨어|자신감.*왜.*떨어)", compact):
        for item in reversed(history):
            if item.get("role") != "user":
                continue
            content = str(item.get("content") or "").strip()
            match = re.search(r"([^.!?]{2,100}?)(해서|줘서|여서)\s*자신감(?:이|을)?.{0,16}떨어", content)
            if match:
                cause = match.group(1).strip(" ,")
                return f"네가 말한 이유는 ‘{cause}{match.group(2)}’였어."
        return "대화 기록에서 자신감이 떨어졌다고 말한 이유를 정확히 확인하지 못했어."
    if re.search(r"(?:불러달라고한|부르기로한)이름", compact):
        patterns = (
            re.compile(r"(?:말고|아니라)\s*([가-힣A-Za-z]{2,20})(?:이?라고)?\s*불러"),
            re.compile(r"나를\s*([가-힣A-Za-z]{2,20})(?:이?라고)?\s*불러"),
        )
        for item in reversed(history):
            if item.get("role") != "user":
                continue
            content = str(item.get("content") or "")
            for pattern in patterns:
                match = pattern.search(content)
                if match:
                    name = re.sub(r"(?:이?라고)$", "", match.group(1)).strip()
                    return f"지금 불러달라고 한 이름은 {name}이야."
        return "대화 기록에서 불러달라고 한 이름을 확인하지 못했어."

    if re.search(r"(?:최종|지금).*(?:미팅|일정).*요일", compact):
        for item in reversed(history):
            if item.get("role") != "user":
                continue
            match = re.search(r"(월|화|수|목|금|토|일)요일", str(item.get("content") or ""))
            if match:
                return f"최종 미팅 요일은 {match.group(0)}이야."

    if re.search(r"지금.*마시고싶.*뭐", compact):
        for item in reversed(history):
            if item.get("role") != "user":
                continue
            content = str(item.get("content") or "")
            match = re.search(r"(?:대신\s*)?([^,.!?]{1,20}(?:차|커피|물|주스))를?\s*마시고\s*싶", content)
            if match:
                return f"지금 마시고 싶다고 한 건 {match.group(1).strip()}야."

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
