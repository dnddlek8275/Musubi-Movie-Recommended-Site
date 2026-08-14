import unittest
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import HTTPException
from starlette.requests import Request

from app.ai_client.chat import open_character_chat_stream
from app.ai_client.base import post_ai
from app.api.chat import chat
from app.core.config import settings
from app.schemas.chat import AutoChatRequest
from app.services.chat_stream_service import stream_and_save_character_answer
from app.services.guest_chat_service import _daily_usage, reserve_guest_request


class FakeSession:
    def __init__(self):
        self.rolled_back = False

    def rollback(self):
        self.rolled_back = True


class ChatRouteErrorTests(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def request():
        return Request({"type": "http", "headers": [], "client": ("127.0.0.1", 1234)})

    async def test_chat_preserves_ai_timeout_status(self):
        session = FakeSession()
        upstream_error = HTTPException(
            status_code=504,
            detail={
                "state": "error",
                "message": "AI 서버 응답 시간이 초과되었습니다.",
            },
        )

        with patch(
            "app.api.chat.start_general_chat",
            new=AsyncMock(side_effect=upstream_error),
        ):
            with self.assertRaises(HTTPException) as raised:
                await chat(
                    AutoChatRequest(message="영화 추천"),
                    self.request(),
                    {"user_id": 1},
                    session,
                )

        self.assertEqual(raised.exception.status_code, 504)
        self.assertTrue(session.rolled_back)

    async def test_chat_maps_unexpected_error_to_500_without_internal_detail(self):
        session = FakeSession()

        with patch(
            "app.api.chat.start_general_chat",
            new=AsyncMock(side_effect=RuntimeError("database password leaked")),
        ):
            with self.assertRaises(HTTPException) as raised:
                await chat(
                    AutoChatRequest(message="영화 추천"),
                    self.request(),
                    {"user_id": 1},
                    session,
                )

        self.assertEqual(raised.exception.status_code, 500)
        self.assertNotIn("database password", str(raised.exception.detail))
        self.assertTrue(session.rolled_back)


class CharacterStreamConnectionTests(unittest.IsolatedAsyncioTestCase):
    async def test_stream_rejects_upstream_error_before_response_starts(self):
        async def handler(request):
            return httpx.Response(503, request=request)

        real_async_client = httpx.AsyncClient
        transport = httpx.MockTransport(handler)

        def make_client(**kwargs):
            return real_async_client(transport=transport, **kwargs)

        with patch("app.ai_client.chat.httpx.AsyncClient", side_effect=make_client):
            with self.assertRaises(HTTPException) as raised:
                await open_character_chat_stream(
                    message="영화 추천",
                    history=[],
                    character="무비비",
                )

        self.assertEqual(raised.exception.status_code, 502)
        self.assertEqual(
            raised.exception.detail["data"]["upstream_status_code"],
            503,
        )

    async def test_stream_connection_timeout_returns_504(self):
        async def handler(request):
            raise httpx.ConnectTimeout("timeout", request=request)

        real_async_client = httpx.AsyncClient
        transport = httpx.MockTransport(handler)

        def make_client(**kwargs):
            return real_async_client(transport=transport, **kwargs)

        with patch("app.ai_client.chat.httpx.AsyncClient", side_effect=make_client):
            with self.assertRaises(HTTPException) as raised:
                await open_character_chat_stream(
                    message="영화 추천",
                    history=[],
                    character="무비비",
                )

        self.assertEqual(raised.exception.status_code, 504)


class AiSyncTimeoutTests(unittest.IsolatedAsyncioTestCase):
    async def test_sync_chat_uses_configured_read_timeout(self):
        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {"answer": "ok"}

        class CapturingClient:
            timeout = None

            async def __aenter__(self):
                return self

            async def __aexit__(self, _exc_type, _exc, _traceback):
                return None

            async def post(self, _url, *, json, timeout):
                self.timeout = timeout
                return FakeResponse()

        client = CapturingClient()
        with patch("app.ai_client.base.httpx.AsyncClient", return_value=client):
            response = await post_ai("/chat/auto", {"message": "안녕"})

        self.assertEqual(response, {"answer": "ok"})
        self.assertEqual(client.timeout.connect, 5.0)
        self.assertEqual(client.timeout.read, settings.AI_CHAT_TIMEOUT_SECONDS)


class CharacterStreamForwardingTests(unittest.IsolatedAsyncioTestCase):
    async def test_done_event_is_forwarded_once(self):
        class FakeAiStream:
            closed = False

            async def iter_lines(self):
                yield 'data: "안녕"'
                yield "data: [DONE]"

            async def aclose(self):
                self.closed = True

        class CommitSession:
            committed = False

            def commit(self):
                self.committed = True

        ai_stream = FakeAiStream()
        session = CommitSession()

        with patch("app.services.chat_stream_service.create_message"):
            chunks = [
                chunk
                async for chunk in stream_and_save_character_answer(
                    db=session,
                    room_id=1,
                    message="인사해줘",
                    history=[],
                    character="마석도",
                    ai_stream=ai_stream,
                )
            ]

        self.assertEqual(chunks.count("data: [DONE]\n\n"), 1)
        self.assertTrue(ai_stream.closed)
        self.assertTrue(session.committed)


class GuestChatProtectionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        _daily_usage.clear()

    async def test_guest_request_limit_is_scoped_by_chat_type(self):
        request = Request(
            {"type": "http", "headers": [], "client": ("203.0.113.10", 1234)}
        )

        for expected_remaining in range(9, -1, -1):
            self.assertEqual(
                await reserve_guest_request(request, "general"),
                expected_remaining,
            )

        with self.assertRaises(HTTPException) as raised:
            await reserve_guest_request(request, "general")

        self.assertEqual(raised.exception.status_code, 429)
        self.assertEqual(
            raised.exception.detail["code"],
            "GUEST_DAILY_LIMIT_REACHED",
        )

        self.assertEqual(
            await reserve_guest_request(request, "character"),
            9,
        )


if __name__ == "__main__":
    unittest.main()
