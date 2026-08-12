import asyncio
import json
import unittest

from api.admission import AdmissionSettings, AIAdmissionMiddleware, WeightedAdmissionController


class MemoryEventLog:
    def __init__(self):
        self.events = []

    async def write(self, event, **fields):
        self.events.append((event, fields))


async def request(middleware, path="/chat/auto"):
    messages = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        messages.append(message)

    await middleware(
        {"type": "http", "method": "POST", "path": path},
        receive,
        send,
    )
    status = next(message["status"] for message in messages if message["type"] == "http.response.start")
    body = b"".join(message.get("body", b"") for message in messages if message["type"] == "http.response.body")
    return status, json.loads(body) if body else None


class AdmissionMiddlewareTests(unittest.IsolatedAsyncioTestCase):
    async def test_queue_full_returns_429(self):
        gate = asyncio.Event()

        async def slow_app(scope, receive, send):
            await gate.wait()
            body = b"{}"
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": body})

        settings = AdmissionSettings(capacity=1, max_queue=1, wait_timeout_seconds=1)
        event_log = MemoryEventLog()
        middleware = AIAdmissionMiddleware(slow_app, settings=settings, event_log=event_log)

        active = asyncio.create_task(request(middleware))
        await asyncio.sleep(0.01)
        queued = asyncio.create_task(request(middleware))
        await asyncio.sleep(0.01)
        status, payload = await request(middleware)
        self.assertEqual(status, 429)
        self.assertEqual(payload["detail"]["code"], "AI_QUEUE_FULL")
        gate.set()
        await asyncio.gather(active, queued)
        self.assertIn("AI_REQUEST_REJECTED", [event for event, _ in event_log.events])

    async def test_queue_wait_timeout_returns_503(self):
        gate = asyncio.Event()

        async def slow_app(scope, receive, send):
            await gate.wait()
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"{}"})

        settings = AdmissionSettings(capacity=1, max_queue=1, wait_timeout_seconds=0.02)
        middleware = AIAdmissionMiddleware(slow_app, settings=settings, event_log=MemoryEventLog())
        active = asyncio.create_task(request(middleware))
        await asyncio.sleep(0.01)
        status, payload = await request(middleware)
        self.assertEqual(status, 503)
        self.assertEqual(payload["detail"]["code"], "AI_QUEUE_WAIT_TIMEOUT")
        gate.set()
        await active

    async def test_group_request_reserves_full_capacity(self):
        controller = WeightedAdmissionController(capacity=5, max_queue=1)
        state, _ = await controller.acquire(5, timeout=1)
        self.assertEqual(state, "acquired")
        self.assertEqual(controller.available, 0)
        await controller.release(5)
        self.assertEqual(controller.available, 5)

    async def test_non_ai_path_bypasses_limiter(self):
        async def app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"{}"})

        middleware = AIAdmissionMiddleware(
            app,
            settings=AdmissionSettings(capacity=1, max_queue=0, wait_timeout_seconds=1),
            event_log=MemoryEventLog(),
        )
        status, _ = await request(middleware, path="/health")
        self.assertEqual(status, 200)


if __name__ == "__main__":
    unittest.main()
