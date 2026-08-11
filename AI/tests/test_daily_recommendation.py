import unittest

from pipeline.daily_recommendation import fallback_daily_copy, validate_daily_copy


class DailyRecommendationCopyTests(unittest.TestCase):
    def setUp(self):
        self.movies = [
            {"title": "영화 하나"},
            {"title": "영화 둘"},
            {"title": "영화 셋"},
        ]

    def test_accepts_a_single_grounded_genre_sentence(self):
        copy = validate_daily_copy(
            "오늘은 액션의 짜릿한 매력을 즐겨보세요.",
            "액션",
            self.movies,
        )
        self.assertEqual(copy, "오늘은 액션의 짜릿한 매력을 즐겨보세요.")

    def test_rejects_copy_that_does_not_match_the_selected_genre(self):
        self.assertEqual(
            validate_daily_copy("로맨틱한 하루를 만들어보세요.", "액션", self.movies),
            "",
        )

    def test_rejects_individual_movie_titles(self):
        self.assertEqual(
            validate_daily_copy("액션 영화 하나를 먼저 만나보세요.", "액션", self.movies),
            "",
        )

    def test_fallback_always_contains_the_selected_genre(self):
        self.assertIn("판타지", fallback_daily_copy("판타지"))


if __name__ == "__main__":
    unittest.main()
