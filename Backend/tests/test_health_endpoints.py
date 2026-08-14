import unittest
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from app.core.dependencies import get_db
from app.main import app


class FakeSession:
    def __init__(self, error: Exception | None = None):
        self.error = error
        self.rolled_back = False

    def execute(self, _statement):
        if self.error:
            raise self.error

    def rollback(self):
        self.rolled_back = True


class FakeAIResponse:
    def __init__(self, status_code: int):
        self.status_code = status_code
        self.request = httpx.Request("GET", "http://ai.test/health")

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "AI health check failed",
                request=self.request,
                response=httpx.Response(
                    self.status_code,
                    request=self.request,
                ),
            )


class FakeAsyncClient:
    def __init__(
        self,
        response: FakeAIResponse | None = None,
        error: Exception | None = None,
    ):
        self.response = response
        self.error = error

    async def __aenter__(self):
        return self

    async def __aexit__(self, _exc_type, _exc, _traceback):
        return None

    async def get(self, _url, timeout):
        if self.error:
            raise self.error
        return self.response


class HealthEndpointTests(unittest.TestCase):
    def tearDown(self):
        app.dependency_overrides.clear()

    def test_ready_returns_success_when_database_is_available(self):
        session = FakeSession()
        app.dependency_overrides[get_db] = lambda: session

        response = TestClient(app).get("/ready")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["state"], "success")

    def test_ready_returns_503_and_rolls_back_when_database_is_unavailable(self):
        session = FakeSession(error=RuntimeError("database unavailable"))
        app.dependency_overrides[get_db] = lambda: session

        response = TestClient(app).get("/ready")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"]["state"], "error")
        self.assertTrue(session.rolled_back)

    def test_db_test_returns_flat_500_without_internal_error(self):
        session = FakeSession(error=RuntimeError("database password leaked"))
        app.dependency_overrides[get_db] = lambda: session

        response = TestClient(app).get("/db-test")

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["state"], "error")
        self.assertNotIn("database password", response.text)

    def test_ai_health_returns_success_for_2xx_response(self):
        client = FakeAsyncClient(response=FakeAIResponse(200))

        with patch("app.main.httpx.AsyncClient", return_value=client):
            response = TestClient(app).get("/ai-health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["state"], "success")

    def test_ai_health_returns_502_for_non_2xx_response(self):
        client = FakeAsyncClient(response=FakeAIResponse(503))

        with patch("app.main.httpx.AsyncClient", return_value=client):
            response = TestClient(app).get("/ai-health")

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["detail"]["data"]["status_code"], 503)

    def test_ai_health_returns_504_for_timeout(self):
        request = httpx.Request("GET", "http://ai.test/health")
        client = FakeAsyncClient(error=httpx.ReadTimeout("timeout", request=request))

        with patch("app.main.httpx.AsyncClient", return_value=client):
            response = TestClient(app).get("/ai-health")

        self.assertEqual(response.status_code, 504)
        self.assertEqual(response.json()["detail"]["state"], "error")


if __name__ == "__main__":
    unittest.main()
