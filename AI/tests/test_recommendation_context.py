import unittest

from pipeline.intent import Intent, classify
from pipeline.recommendation_context import (
    build_recommendation_context,
    is_movie_recommendation_followup,
)


class RecommendationContextTests(unittest.TestCase):
    def setUp(self):
        self.history = [
            {"role": "user", "content": "긴장감 있는 액션 영화 추천해줘"},
            {
                "role": "assistant",
                "content": "‘12 솔져스’를 추천해요.",
                "recommended_movies": [{"title": "12 솔져스"}, {"title": "긴급 명령"}],
            },
        ]

    def test_feedback_is_movie_intent_only_with_movie_history(self):
        message = "너무 무거워. 좀 더 가벼운 걸로"
        self.assertTrue(is_movie_recommendation_followup(message, self.history))
        self.assertEqual(classify(message, history=self.history), Intent.MOVIE_RECOMMEND)
        self.assertEqual(classify(message, history=[]), Intent.CHARACTER_CHAT)

    def test_followup_combines_previous_request_and_current_feedback(self):
        context = build_recommendation_context("좀 더 가벼운 걸로", self.history)
        self.assertTrue(context.is_followup)
        self.assertIn("액션", context.search_message)
        self.assertIn("가벼운", context.search_message)
        self.assertEqual(set(context.excluded_titles), {"12 솔져스", "긴급 명령"})

    def test_negated_genre_is_excluded_instead_of_requested(self):
        context = build_recommendation_context("로맨스는 싫어. 다른 걸로", self.history)
        self.assertEqual(context.excluded_genres, ["로맨스"])

    def test_latest_followup_keeps_previous_genre(self):
        context = build_recommendation_context("좀 더 최신 걸로", self.history)
        self.assertTrue(context.is_followup)
        self.assertIn("액션", context.search_message)
        self.assertIn("최신", context.search_message)

    def test_quoted_titles_are_collected_when_structured_movies_are_missing(self):
        history = [
            {"role": "user", "content": "코미디 영화 추천해줘"},
            {"role": "assistant", "content": "‘로미와 미셀’과 ‘우주에서 온 고양이’를 추천해요."},
        ]
        context = build_recommendation_context("다른 영화 보여줘", history)
        self.assertEqual(set(context.excluded_titles), {"로미와 미셀", "우주에서 온 고양이"})


if __name__ == "__main__":
    unittest.main()
