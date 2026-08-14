import asyncio
import hashlib
import hmac
import json
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.ai_client.chat import (
    open_character_chat_stream,
    request_ai_chat,
    request_group_chat,
)
from app.core.config import settings
from app.schemas.chat import AutoChatRequest, CharacterChatRequest, GroupChatRequest
from app.services.character_service import get_active_character
from app.services.chat_input_recovery import get_general_chat_recovery, wait_for_recovery_ui
from app.services.chat_stream_service import make_streaming_response


_usage_lock = asyncio.Lock()
_daily_usage: dict[tuple[str, str, str], int] = defaultdict(int)
_ai_slots = asyncio.Semaphore(max(1, settings.GUEST_CHAT_MAX_CONCURRENCY))
_KST = timezone(timedelta(hours=9))
_MUMU_EMOTIONS = {"default", "joy", "thinking", "searching", "sorry"}


def _normalize_mumu_emotion(value) -> str:
    emotion = str(value or "default").strip().lower()
    return emotion if emotion in _MUMU_EMOTIONS else "default"


def _client_ip(request: Request) -> str:
    if settings.GUEST_CHAT_TRUST_PROXY_HEADERS:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",", 1)[0].strip()
    return request.client.host if request.client else "unknown"


def _client_key(request: Request) -> str:
    # 메모리에 원 IP를 남기지 않도록 서비스 비밀키로 해시한다.
    return hmac.new(
        settings.SECRET_KEY.encode(),
        _client_ip(request).encode(),
        hashlib.sha256,
    ).hexdigest()


async def reserve_guest_request(request: Request, scope: str = "general") -> int:
    today = datetime.now(_KST).date().isoformat()
    normalized_scope = "character" if scope == "character" else "general"
    key = (today, _client_key(request), normalized_scope)
    limit = max(0, settings.GUEST_CHAT_DAILY_LIMIT)

    async with _usage_lock:
        # 장기 실행 프로세스에서 지난 날짜의 키가 계속 쌓이지 않게 정리한다.
        stale_keys = [usage_key for usage_key in _daily_usage if usage_key[0] != today]
        for stale_key in stale_keys:
            del _daily_usage[stale_key]
        used = _daily_usage[key]
        if used >= limit:
            chat_label = "캐릭터 대화" if normalized_scope == "character" else "일반 대화"
            raise HTTPException(
                status_code=429,
                detail={
                    "state": "failure",
                    "code": "GUEST_DAILY_LIMIT_REACHED",
                    "message": f"비회원 {chat_label}는 하루 {limit}회까지 이용할 수 있습니다. 로그인하면 대화를 계속할 수 있습니다.",
                },
            )
        _daily_usage[key] = used + 1
        return limit - _daily_usage[key]


async def get_guest_remaining(request: Request, scope: str = "general") -> int:
    """Read the current remaining count without consuming a guest request."""
    today = datetime.now(_KST).date().isoformat()
    normalized_scope = "character" if scope == "character" else "general"
    key = (today, _client_key(request), normalized_scope)
    limit = max(0, settings.GUEST_CHAT_DAILY_LIMIT)
    async with _usage_lock:
        return max(0, limit - _daily_usage.get(key, 0))


@asynccontextmanager
async def guest_ai_slot():
    try:
        await asyncio.wait_for(_ai_slots.acquire(), timeout=3)
    except TimeoutError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "state": "failure",
                "code": "CHAT_BUSY",
                "message": "현재 채팅 요청이 많습니다. 잠시 후 다시 시도해주세요.",
            },
        ) from exc
    try:
        yield
    finally:
        _ai_slots.release()


def _history(request) -> list[dict]:
    return [
        {
            "role": item.role,
            "content": item.content,
            **({"character": item.character} if item.character else {}),
            **({"recommended_movies": item.recommended_movies} if item.recommended_movies else {}),
        }
        for item in request.history[-10:]
    ]


async def start_guest_general_chat(
    db: Session, http_request: Request, request: AutoChatRequest
):
    recovery = get_general_chat_recovery(request.message)
    if recovery and not request.character:
        await wait_for_recovery_ui()
        return {
            "state": "success",
            "message": "비회원 입력 복구 응답에 성공했습니다.",
            "data": {
                "room_id": None,
                "answer": recovery.answer,
                "character": "무무",
                "intent": "input_recovery",
                "emotion": recovery.emotion,
                "movies": [],
                "guest_remaining": await get_guest_remaining(http_request, "general"),
                "saved": False,
                "input_recovery": recovery.kind,
            },
        }

    character = None
    if request.character:
        character = get_active_character(db, request.character)
        if character is None:
            return {"state": "failure", "message": "지원하지 않는 캐릭터입니다."}

    remaining = await reserve_guest_request(http_request, "general")
    async with guest_ai_slot():
        result = await request_ai_chat(
            message=request.message.strip(),
            history=_history(request),
            character=character,
        )

    answer = result.get("answer")
    if not answer:
        return {"state": "error", "message": "AI 서버에서 답변이 없습니다."}
    return {
        "state": "success",
        "message": "비회원 채팅 응답에 성공했습니다.",
        "data": {
            "room_id": None,
            "answer": answer[:2000],
            "character": result.get("character") or character,
            "intent": result.get("intent"),
            "emotion": _normalize_mumu_emotion(result.get("emotion")),
            "movies": result.get("movies", []),
            "guest_remaining": remaining,
            "saved": False,
        },
    }


async def start_guest_group_chat(
    db: Session, http_request: Request, request: GroupChatRequest
):
    characters = []
    for requested_character in request.characters:
        character = get_active_character(db, requested_character)
        if character is None:
            return {"state": "failure", "message": "채팅할 수 없는 캐릭터가 있습니다."}
        characters.append(character)

    remaining = await reserve_guest_request(http_request, "character")
    async with guest_ai_slot():
        result = await request_group_chat(
            characters=characters,
            message=request.message.strip(),
            history=_history(request),
        )
    return {
        "state": "success",
        "message": "비회원 그룹 채팅 응답에 성공했습니다.",
        "data": {
            "room_id": None,
            "intent": result.get("intent"),
            "rounds": [
                {
                    **round_item,
                    "responses": [
                        {
                            **response,
                            "answer": str(response.get("answer", ""))[:2000],
                        }
                        for response in round_item.get("responses", [])
                    ],
                }
                for round_item in result.get("rounds", [])
            ],
            "movies": result.get("movies", []),
            "guest_remaining": remaining,
            "saved": False,
        },
    }


async def _stream_guest_answer(ai_stream, slot_context):
    emitted = 0
    try:
        async for line in ai_stream.iter_lines():
            if line == "data: [DONE]":
                yield f"{line}\n\n"
                break
            if not line.startswith("data: "):
                continue

            raw = line.removeprefix("data: ").strip()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                payload = raw

            if isinstance(payload, str):
                text = payload
                limited = text[: max(0, 2000 - emitted)]
                emitted += len(limited)
                if limited:
                    yield f"data: {json.dumps(limited, ensure_ascii=False)}\n\n"
            elif isinstance(payload, dict):
                text = str(payload.get("answer", ""))
                limited = text[: max(0, 2000 - emitted)]
                emitted += len(limited)
                payload["answer"] = limited
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

            if emitted >= 2000:
                yield "data: [DONE]\n\n"
                break
    finally:
        await ai_stream.aclose()
        await slot_context.__aexit__(None, None, None)


async def start_guest_character_chat(
    db: Session, http_request: Request, request: CharacterChatRequest
):
    character = get_active_character(db, request.character)
    if character is None:
        return {"state": "failure", "message": "지원하지 않는 캐릭터입니다."}

    remaining = await reserve_guest_request(http_request, "character")
    slot_context = guest_ai_slot()
    await slot_context.__aenter__()
    try:
        ai_stream = await open_character_chat_stream(
            message=request.message.strip(),
            history=_history(request),
            character=character,
        )
    except Exception:
        await slot_context.__aexit__(None, None, None)
        raise

    response = make_streaming_response(_stream_guest_answer(ai_stream, slot_context))
    response.headers["X-Guest-Chat-Remaining"] = str(remaining)
    response.headers["X-Chat-Saved"] = "false"
    return response
