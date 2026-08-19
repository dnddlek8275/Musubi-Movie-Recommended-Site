import sys
import json
import os
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from pipeline.intent import Intent, classify


llm_client_stub = types.ModuleType("llm.client")


def unexpected_llm_call(*args, **kwargs):
    raise AssertionError("explicit coding topic must not call the LLM rewriter")


llm_client_stub.chat_json = unexpected_llm_call
llm_client_stub.chat = lambda *args, **kwargs: ""
sys.modules.setdefault("llm.client", llm_client_stub)

from pipeline.query_rewriter import rewrite
from pipeline.recommendation_presenter import prepare_recommendations
from pipeline.topic_grounding import (
    filter_topic_candidates,
    interpret_topic,
    log_topic_event,
)


class CodingMovieRecommendationTests(unittest.TestCase):

    def test_dinosaur_preference_language_becomes_grounded_topic(self):
        result = rewrite(
            "초등학생 조카가 공룡을 좋아해. 무서운 장면 없는 영화 두 편만 골라줘."
        )
        self.assertEqual(result["topic"]["topic_id"], "dinosaurs")
        self.assertIn("공룡", result["search_query"])

        candidates = [
            {"title": "공룡 영화", "overview": "어린 공룡의 모험"},
            {"title": "겨울 영화", "overview": "눈사람의 겨울 모험"},
        ]
        filtered = filter_topic_candidates(candidates, result["topic"])
        self.assertEqual([movie["title"] for movie in filtered], ["공룡 영화"])
    def test_coding_book_request_is_not_misrouted_to_movie_search(self):
        messages = (
            "코드 관련 책을 추천해줘",
            "프로그래밍 도서 좀 골라줘",
            "집중할 때 들을 노래 추천해줘",
            "서울 맛집 추천해줘",
            "친구랑 할 게임 추천해줘",
            "요즘 볼 웹툰 추천해줘",
            "주말 여행지 추천해줘",
        )
        for message in messages:
            with self.subTest(message=message):
                self.assertEqual(classify(message), Intent.CHARACTER_CHAT)

    def test_book_topic_can_still_explicitly_request_a_movie(self):
        messages = (
            "코딩 책을 소재로 한 영화 추천해줘",
            "게임을 소재로 한 영화 추천해줘",
            "여행지 풍경이 멋진 영화 추천해줘",
        )
        for message in messages:
            with self.subTest(message=message):
                self.assertEqual(classify(message), Intent.MOVIE_RECOMMEND)

    def test_polite_can_you_recommend_expression_routes_to_movie_pipeline(self):
        messages = (
            "코딩 관련된 영화를 보고 싶은데 추천해 줄 수 있어?",
            "개발자 영화 추천해 주실 수 있어요?",
            "프로그래밍 영화 추천해줄래?",
        )
        for message in messages:
            with self.subTest(message=message):
                self.assertEqual(classify(message), Intent.MOVIE_RECOMMEND)

    def test_coding_topic_skips_llm_and_expands_retrieval_terms(self):
        result = rewrite("코딩 관련된 영화를 보고 싶은데 추천해 줄 수 있어?")
        self.assertIn("프로그래밍", result["search_query"])
        self.assertIn("개발자", result["search_query"])
        self.assertIn("해킹", result["search_query"])

    def test_topic_filter_does_not_pad_with_title_substring_false_positives(self):
        candidates = [
            {
                "title": "컴퓨터 체스",
                "overview": "컴퓨터 프로그래머들이 체스 프로그램을 겨룬다.",
            },
            {
                "title": "코다",
                "overview": "청각 장애인 가족과 음악을 꿈꾸는 소녀의 이야기.",
            },
            {
                "title": "코드 8: 파트 2",
                "overview": "초능력자가 부패 경찰로부터 소녀를 지킨다.",
            },
        ]
        topic = rewrite("코딩 관련 영화를 추천해줘")["topic"]
        filtered = filter_topic_candidates(candidates, topic)
        self.assertEqual([movie["title"] for movie in filtered], ["컴퓨터 체스"])

    def test_topic_reason_uses_movie_evidence(self):
        prepared = prepare_recommendations(
            [
                {
                    "title": "컴퓨터 체스",
                    "overview": "컴퓨터 프로그래머들이 체스 프로그램을 겨룬다.",
                    "genres": "코미디",
                }
            ],
            "코딩 관련 영화를 추천해줘",
            rewrite("코딩 관련 영화를 추천해줘"),
            limit=3,
        )
        self.assertIn("소재가 확인", prepared[0]["recommendation_reason"])

    def test_unknown_topic_preserves_literal_words_without_inventing_synonyms(self):
        result = rewrite("양자 컴퓨팅 관련 영화를 추천해줘")
        topic = result["topic"]
        self.assertEqual(topic["source"], "literal")
        self.assertEqual(topic["evidence_terms"], ["양자", "컴퓨팅"])
        self.assertIn("양자 컴퓨팅", result["search_query"])
        self.assertNotIn("해킹", result["search_query"])

    def test_unknown_topic_requires_metadata_evidence_not_title_only(self):
        topic = interpret_topic("러스트 관련 영화 추천해줘")
        candidates = [
            {"title": "러스트", "overview": "서부에서 벌어지는 한 가족의 이야기."},
            {"title": "메모리 세이프", "overview": "러스트 개발자와 오픈소스 공동체를 다룬다."},
        ]
        filtered = filter_topic_candidates(candidates, topic)
        self.assertEqual([movie["title"] for movie in filtered], ["메모리 세이프"])

    def test_learning_log_does_not_store_raw_prompt_or_user_identity(self):
        topic = interpret_topic("양자 컴퓨팅 관련 영화를 추천해줘")
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "topic.jsonl")
            with patch.dict(os.environ, {"TOPIC_LEARNING_LOG_PATH": path}):
                log_topic_event(topic, "clarification_required")
            event = json.loads(Path(path).read_text(encoding="utf-8"))
        self.assertNotIn("user_message", event)
        self.assertNotIn("user_id", event)
        self.assertEqual(event["label"], "양자 컴퓨팅")


if __name__ == "__main__":
    unittest.main()
