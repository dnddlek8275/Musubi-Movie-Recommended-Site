import unittest
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import HTTPException

from app.ai_client.chat import open_character_chat_stream
from app.api.chat import chat
from app.schemas.chat import AutoChatRequest
from app.services.chat_stream_service import stream_and_save_character_answer


class FakeSession:
    def __init__(self):
        self.rolled_back = False

    def rollback(self):
        self.rolled_back = True


class ChatRouteErrorTests(unittest.IsolatedAsyncioTestCase):
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


if __name__ == "__main__":
    unittest.main()
