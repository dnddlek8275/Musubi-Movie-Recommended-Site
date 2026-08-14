import unittest

from pipeline.recommendation_presenter import (
    is_fact_grounded_recommendation,
    is_safe_general_recommendation,
)


class GeneralRecommendationValidationTests(unittest.TestCase):
    def test_rejects_one_genre_label_for_mixed_unnamed_cards(self):
        movies = [
            {"title": "액션 카드", "genres": "액션, 모험"},
            {"title": "공포 카드", "genres": "공포, 미스터리"},
        ]
        answer = "액션 영화 어때? ‘액션 카드’와 ‘공포 카드’를 골랐어."

        self.assertFalse(is_fact_grounded_recommendation(answer, movies))

    def test_family_conversation_is_not_mistaken_for_a_set_genre_label(self):
        movies = [
            {"title": "첫 카드", "genres": "코미디"},
            {"title": "둘째 카드", "genres": "애니메이션"},
        ]
        answer = "가족과 함께 보기엔 ‘첫 카드’와 ‘둘째 카드’가 괜찮아."

        self.assertTrue(
            is_fact_grounded_recommendation(answer, movies, "가족과 볼 영화 추천해줘")
        )

    def setUp(self):
        self.movies = [
            {"title": "물괴"},
            {"title": "해적: 도깨비 깃발"},
            {"title": "조작된 도시"},
        ]

    def test_accepts_exact_card_titles_without_internal_labels(self):
        answer = (
            "‘물괴’부터 추천해요.\n\n"
            "다른 선택으로는 ‘해적: 도깨비 깃발’, ‘조작된 도시’도 함께 골라봤어요.\n\n"
            "이 중에 끌리는 영화가 있나요?"
        )
        self.assertTrue(is_safe_general_recommendation(answer, self.movies))

    def test_rejects_missing_card_title(self):
        self.assertFalse(
            is_safe_general_recommendation(
                "‘물괴’와 ‘해적: 도깨비 깃발’을 추천해요.",
                self.movies,
            )
        )

    def test_rejects_unapproved_quoted_title(self):
        answer = (
            "‘물괴’, ‘해적: 도깨비 깃발’, ‘조작된 도시’를 골랐어요. "
            "대신 ‘범죄도시’도 좋아요."
        )
        self.assertFalse(is_safe_general_recommendation(answer, self.movies))

    def test_rejects_internal_role_and_markdown(self):
        answer = (
            "**‘물괴’**부터 추천해요. ‘해적: 도깨비 깃발’은 다른 결의 대안이고 "
            "‘조작된 도시’도 있어요."
        )
        self.assertFalse(is_safe_general_recommendation(answer, self.movies))

    def test_rejects_unsupported_mood_claim_even_when_titles_match(self):
        movies = [
            {
                "title": "스타워즈",
                "genres": "모험, 액션, SF",
                "overview": "은하 제국에 맞서는 이야기",
            },
            {"title": "아마데우스", "genres": "드라마, 역사, 음악"},
            {"title": "위대한 개츠비", "genres": "드라마, 로맨스"},
        ]
        answer = (
            "‘스타워즈’는 긴장감 넘치는 스릴이 있어. "
            "‘아마데우스’와 ‘위대한 개츠비’도 추천해."
        )
        self.assertFalse(is_fact_grounded_recommendation(answer, movies))

    def test_accepts_claims_present_in_each_movie_card(self):
        movies = [
            {"title": "스타워즈", "genres": "모험, 액션, SF"},
            {"title": "아마데우스", "genres": "드라마, 역사, 음악"},
            {"title": "위대한 개츠비", "genres": "드라마, 로맨스"},
        ]
        answer = (
            "‘스타워즈’는 액션을 보고 싶을 때 고를 만해. "
            "음악 장르의 ‘아마데우스’와 로맨스 장르의 ‘위대한 개츠비’도 있어."
        )
        self.assertTrue(is_fact_grounded_recommendation(answer, movies))

    def test_rejects_genre_borrowed_from_another_card(self):
        movies = [
            {"title": "스타워즈", "genres": "모험, 액션, SF"},
            {"title": "아마데우스", "genres": "드라마, 역사, 음악"},
            {"title": "위대한 개츠비", "genres": "드라마, 로맨스"},
        ]
        answer = (
            "로맨스 장르의 ‘스타워즈’를 먼저 봐. "
            "‘아마데우스’와 ‘위대한 개츠비’도 추천해."
        )
        self.assertFalse(is_fact_grounded_recommendation(answer, movies))


if __name__ == "__main__":
    unittest.main()
