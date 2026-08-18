import unittest

from pipeline.intent import Intent, classify
from pipeline.recommendation_context import (
    build_card_followup_reply,
    build_recommendation_context,
    is_movie_recommendation_followup,
    requested_movie_count,
)


class RecommendationContextTests(unittest.TestCase):
    def test_explicit_requested_movie_count(self):
        self.assertEqual(requested_movie_count("SF 영화 딱 한 편만 추천해줘"), 1)
        self.assertEqual(requested_movie_count("코미디 2편만 골라줘"), 2)
        self.assertEqual(requested_movie_count("가족 영화 세 편 추천해줘"), 3)
        self.assertIsNone(requested_movie_count("영화 추천해줘"))

    def test_explicit_movie_recommendation_negation_stays_in_chat(self):
        self.assertEqual(
            classify("친구가 나보고 조커 같다고 놀렸어. 영화 추천은 필요 없어."),
            Intent.CHARACTER_CHAT,
        )

    def test_common_comedy_typo_routes_to_movie_recommendation(self):
        self.assertEqual(
            classify("2020년 이후 한국 코메디 세 개 골라줘"),
            Intent.MOVIE_RECOMMEND,
        )

    def test_explicit_movie_topic_close_routes_back_to_chat(self):
        self.assertEqual(
            classify("영화는 나중에 볼게. 오늘 회사에서 속상했던 얘기 좀 들어줘."),
            Intent.CHARACTER_CHAT,
        )

    def test_colloquial_horror_negation_is_excluded(self):
        context = build_recommendation_context("한국 코메디 추천. 무서운 건 절대 ㄴㄴ", [])
        self.assertIn("공포", context.excluded_genres)

    def test_genre_word_suffix_is_supported_in_negation(self):
        context = build_recommendation_context("잔인한 범죄물만 빼고 추천해줘", [])
        self.assertEqual(context.excluded_genres, ["범죄"])

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

    def test_coordinated_negated_genres_are_all_excluded(self):
        context = build_recommendation_context("밝은 로맨스 추천해줘. 공포와 전쟁은 빼줘", [])
        self.assertEqual(context.excluded_genres, ["공포", "전쟁"])

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

    def test_chained_followup_preserves_intermediate_mood_constraint(self):
        history = [
            {"role": "user", "content": "로맨스 영화 추천해줘"},
            {"role": "assistant", "content": "A를 추천해요.", "recommended_movies": [{"title": "A"}]},
            {"role": "user", "content": "더 밝은 걸로"},
            {"role": "assistant", "content": "B를 추천해요.", "recommended_movies": [{"title": "B"}]},
        ]
        context = build_recommendation_context("2020년 이후만", history)
        self.assertTrue(context.is_followup)
        self.assertIn("로맨스", context.search_message)
        self.assertIn("더 밝은 걸로", context.search_message)
        self.assertIn("2020년 이후만", context.search_message)
        self.assertEqual(context.excluded_titles, ["B"])

    def test_language_only_refinement_is_a_movie_followup(self):
        self.assertTrue(is_movie_recommendation_followup("영어 영화만", self.history))

    def test_rating_only_refinement_is_a_movie_followup(self):
        self.assertTrue(is_movie_recommendation_followup("평점 7점 이상만", self.history))

    def test_natural_other_movie_variants_keep_movie_intent(self):
        for message in ("다른 것도 보여줘", "다른 건?", "또 골라줘", "추가로 알려줘"):
            with self.subTest(message=message):
                self.assertEqual(classify(message, history=self.history), Intent.MOVIE_RECOMMEND)

    def test_structured_movie_cards_are_sufficient_followup_evidence(self):
        history = [
            {"role": "user", "content": "오늘 볼 거 골라줘"},
            {
                "role": "assistant",
                "content": "이 영화들을 골랐어요.",
                "recommended_movies": [{"title": "A"}],
            },
        ]
        self.assertEqual(classify("다른 것도 보여줘", history=history), Intent.MOVIE_RECOMMEND)
        context = build_recommendation_context("다른 것도 보여줘", history)
        self.assertTrue(context.is_followup)
        self.assertIn("오늘 볼 거 골라줘", context.search_message)
        self.assertEqual(context.excluded_titles, ["A"])

    def test_ambiguous_other_request_without_movie_cards_is_not_movie_intent(self):
        history = [
            {"role": "user", "content": "오늘 저녁 메뉴 골라줘"},
            {"role": "assistant", "content": "파스타는 어때요?"},
        ]
        self.assertEqual(classify("다른 것도 보여줘", history=history), Intent.CHARACTER_CHAT)

    def test_card_ordinal_recall_uses_structured_title(self):
        answer, movies = build_card_followup_reply("두 번째 영화가 뭐였지?", self.history)
        self.assertEqual(answer, "2번째 영화는 ‘긴급 명령’이야.")
        self.assertEqual([movie["title"] for movie in movies], ["긴급 명령"])

    def test_card_overview_uses_only_structured_metadata(self):
        history = [
            {
                "role": "assistant",
                "content": "추천 결과",
                "recommended_movies": [
                    {"title": "겟 아웃", "overview": "가족의 비밀을 마주한다."},
                    {"title": "어스", "overview": "자신과 닮은 존재들이 나타난다."},
                ],
            }
        ]
        answer, movies = build_card_followup_reply("두 번째 영화 줄거리 알려줘", history)
        self.assertIn("자신과 닮은 존재들이 나타난다.", answer)
        self.assertNotIn("좀비", answer)
        self.assertEqual([movie["title"] for movie in movies], ["어스"])

    def test_card_overview_does_not_invent_missing_metadata(self):
        answer, movies = build_card_followup_reply("첫 번째 영화 줄거리 알려줘", self.history)
        self.assertEqual(answer, "‘12 솔져스’의 줄거리 정보는 현재 카드에 없어.")
        self.assertEqual([movie["title"] for movie in movies], ["12 솔져스"])

    def test_remainder_light_comparison_stays_with_existing_cards(self):
        history = [
            {
                "role": "assistant",
                "content": "추천 결과",
                "recommended_movies": [
                    {"title": "겟 아웃", "genres": "공포, 미스터리"},
                    {"title": "어스", "genres": "공포, 스릴러"},
                    {"title": "해피 데스데이", "genres": "공포, 코미디"},
                ],
            }
        ]
        answer, movies = build_card_followup_reply(
            "첫 번째 말고 나머지 둘 중 더 가벼운 건 뭐야?",
            history,
        )
        self.assertIn("해피 데스데이", answer)
        self.assertEqual([movie["title"] for movie in movies], ["해피 데스데이"])

    def test_explicit_preference_reset_drops_old_genre(self):
        history = [
            {"role": "user", "content": "공포 영화 추천해줘."},
            {"role": "assistant", "content": "추천 결과", "movies": [{"title": "A"}]},
        ]
        context = build_recommendation_context(
            "공포 조건은 전부 취소하고 2020년 이후 한국 코미디 두 편만 새로 골라줘.",
            history,
        )
        self.assertNotIn("공포 영화 추천", context.search_message)
        self.assertIn("한국 코미디", context.search_message)

    def test_year_release_removes_prior_year_but_keeps_other_filters(self):
        history = [
            {"role": "user", "content": "2023년 이후 일본 애니메이션 추천해줘."},
            {"role": "assistant", "content": "추천 결과", "movies": [{"title": "A"}]},
        ]
        context = build_recommendation_context(
            "연도 제한만 없애고 일본 애니메이션 두 편으로 다시 추천해줘.",
            history,
        )
        self.assertNotIn("2023", context.search_message)
        self.assertIn("일본 애니메이션", context.search_message)


if __name__ == "__main__":
    unittest.main()
