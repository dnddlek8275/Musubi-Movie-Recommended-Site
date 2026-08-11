import os
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

if "requests" not in sys.modules:
    requests_stub = types.ModuleType("requests")
    requests_stub.RequestException = RuntimeError
    requests_stub.ConnectionError = ConnectionError
    requests_stub.post = Mock()
    sys.modules["requests"] = requests_stub

from pipeline.intent import Intent, classify
from services import web_search


class WebSearchIntentTests(unittest.TestCase):
    def test_explicit_external_search_is_routed(self):
        self.assertEqual(classify("최신 영화 뉴스를 웹 검색해줘"), Intent.WEB_SEARCH)

    def test_ordinary_movie_request_stays_movie_recommendation(self):
        self.assertEqual(classify("요즘 볼 만한 영화 추천해줘"), Intent.MOVIE_RECOMMEND)


class WebSearchQuotaTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.previous = {
            "db": web_search.DB_PATH,
            "limit": web_search.MONTHLY_LIMIT,
            "warning": web_search.WARNING_AT,
        }
        web_search.DB_PATH = os.path.join(self.temp_dir.name, "usage.sqlite3")
        web_search.MONTHLY_LIMIT = 2
        web_search.WARNING_AT = 1
        self.api_key = patch.dict(os.environ, {"TAVILY_API_KEY": "test-key"})
        self.api_key.start()

    def tearDown(self):
        self.api_key.stop()
        web_search.DB_PATH = self.previous["db"]
        web_search.MONTHLY_LIMIT = self.previous["limit"]
        web_search.WARNING_AT = self.previous["warning"]
        self.temp_dir.cleanup()

    @staticmethod
    def _response(title):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "results": [{
                "title": title,
                "url": "https://example.com/movie",
                "content": "verified result",
            }]
        }
        return response

    @patch("services.web_search.requests.post")
    def test_cache_hit_does_not_consume_another_call(self, post):
        post.return_value = self._response("first")
        first = web_search.search("same query")
        second = web_search.search("same query")

        self.assertFalse(first["cached"])
        self.assertTrue(second["cached"])
        self.assertEqual(second["quota"]["used"], 1)
        self.assertEqual(post.call_count, 1)

    @patch("services.web_search.requests.post")
    def test_hard_cap_blocks_before_provider_call(self, post):
        post.side_effect = [self._response("one"), self._response("two")]
        web_search.search("query one")
        web_search.search("query two")

        with self.assertRaises(web_search.WebSearchQuotaExceeded):
            web_search.search("query three")

        self.assertEqual(post.call_count, 2)
        self.assertEqual(web_search.quota_status()["remaining"], 0)

    @patch("services.web_search.requests.post")
    def test_connection_failure_releases_reserved_call(self, post):
        post.side_effect = web_search.requests.ConnectionError("network unavailable")

        with self.assertRaises(web_search.WebSearchUnavailable):
            web_search.search("unreachable query")

        self.assertEqual(web_search.quota_status()["used"], 0)


if __name__ == "__main__":
    unittest.main()
