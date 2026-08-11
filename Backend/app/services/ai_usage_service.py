import asyncio
import logging
import time
from datetime import datetime, timezone

from jose import JWTError, jwt

from app.core.config import settings
from app.core.dependencies import SessionLocal
from app.models.ai_usage import AiUsageEvent


logger = logging.getLogger(__name__)


def classify_ai_request(method: str, path: str) -> str | None:
    if method.upper() != "POST":
        return None
    if path == "/chat/auto":
        return "general_chat"
    if path == "/chat/character":
        return "character_chat"
    if path == "/chat/group":
        return "group_chat"
    if path.startswith("/chat/rooms/") and path.endswith("/messages"):
        return "chat_continue"
    return None


def _user_id_from_headers(headers: list[tuple[bytes, bytes]]) -> int | None:
    authorization = next(
        (
            value.decode("latin-1")
            for key, value in headers
            if key.lower() == b"authorization"
        ),
        "",
    )
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None

    if payload.get("type") != "access":
        return None
    try:
        return int(payload["user_id"])
    except (KeyError, TypeError, ValueError):
        return None


def _save_usage_event(**values) -> None:
    db = SessionLocal()
    try:
        db.add(AiUsageEvent(**values))
        db.commit()
    except Exception:
        db.rollback()
        # 계측 저장 실패가 실제 채팅 응답을 실패시키면 안 된다.
        logger.exception("AI usage event 저장 실패")
    finally:
        db.close()


class AiUsageMiddleware:
    """AI 채팅 HTTP 요청의 성공률·응답시간·응답 크기를 비침습적으로 기록한다."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_type = classify_ai_request(scope.get("method", ""), scope.get("path", ""))
        if request_type is None:
            await self.app(scope, receive, send)
            return

        started_wall = datetime.now(timezone.utc)
        started_monotonic = time.monotonic()
        first_response_ms = None
        response_bytes = 0
        http_status = None
        response_finished = False

        async def measured_send(message):
            nonlocal first_response_ms, response_bytes, http_status, response_finished
            if message["type"] == "http.response.start":
                http_status = int(message["status"])
            elif message["type"] == "http.response.body":
                body = message.get("body", b"")
                if body and first_response_ms is None:
                    first_response_ms = round((time.monotonic() - started_monotonic) * 1000)
                response_bytes += len(body)
                if not message.get("more_body", False):
                    response_finished = True
            await send(message)

        raised = False
        try:
            await self.app(scope, receive, measured_send)
        except BaseException:
            raised = True
            raise
        finally:
            total_duration_ms = round((time.monotonic() - started_monotonic) * 1000)
            if raised or not response_finished:
                status = "cancelled" if http_status is not None else "error"
            elif http_status is not None and 200 <= http_status < 400:
                status = "success"
            else:
                status = "error"

            # SQLAlchemy 동기 세션의 연결·INSERT가 다른 비동기 요청을 막지 않게
            # 작업 스레드에서 저장한다. 저장 완료는 기다려 계측 유실은 방지한다.
            await asyncio.to_thread(
                _save_usage_event,
                user_id=_user_id_from_headers(scope.get("headers", [])),
                request_type=request_type,
                request_path=scope.get("path", "")[:200],
                status=status,
                http_status=http_status,
                first_response_ms=first_response_ms,
                total_duration_ms=total_duration_ms,
                response_bytes=response_bytes,
                started_at=started_wall,
                completed_at=datetime.now(timezone.utc),
            )
