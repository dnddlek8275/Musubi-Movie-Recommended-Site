import sys
import types
import unittest


llm_client_stub = types.ModuleType("llm.client")


def unexpected_llm_call(*args, **kwargs):
    raise AssertionError("explicit mood query must not call the LLM rewriter")


llm_client_stub.chat_json = unexpected_llm_call
llm_client_stub.chat = lambda *args, **kwargs: ""
sys.modules.setdefault("llm.client", llm_client_stub)

from pipeline.query_rewriter import rewrite


class QueryRewriterMoodTests(unittest.TestCase):
    def test_light_mood_skips_llm_extraction(self):
        result = rewrite("가볍게 볼 영화 추천해줘")
        self.assertEqual(result["search_query"], "가볍게 볼 영화 추천해줘")
        self.assertIsNone(result["genre"])

    def test_supported_mood_queries_all_skip_llm_extraction(self):
        for message in (
            "감동적인 영화 추천해줘",
            "우울할 때 보기 좋은 영화 추천해줘",
            "데이트할 때 볼 영화 추천해줘",
            "아이와 함께 볼 영화 추천해줘",
            "주말 밤에 볼 유쾌한 영화 세 편 골라줘",
        ):
            with self.subTest(message=message):
                self.assertEqual(rewrite(message)["search_query"], message)

    def test_generic_request_does_not_search_literal_time_words_as_a_title(self):
        result = rewrite("오늘 밤 볼 영화 세 편 추천해줘")
        self.assertEqual(
            result["search_query"],
            "흥행에 성공하고 많은 관객에게 사랑받은 인기 명작 영화",
        )
        self.assertEqual(result["quality_priority"], "generic")

    def test_mood_recommendation_requests_quality_priority(self):
        result = rewrite("기분이 안 좋을 때 볼 영화 추천해줘")
        self.assertEqual(result["quality_priority"], "mood")


if __name__ == "__main__":
    unittest.main()
