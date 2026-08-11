import unittest

from pipeline.recommendation_presenter import (
    build_character_grounded_answer,
    build_grounded_answer,
    is_safe_general_recommendation,
    prepare_recommendations,
    select_diverse_movies,
)


class RecommendationPresenterTests(unittest.TestCase):
    def test_character_fallback_keeps_all_titles_and_direct_tone(self):
        movies = prepare_recommendations(
            [
                {"title": "스타워즈", "genres": "모험, 액션"},
                {"title": "아마데우스", "genres": "드라마, 음악"},
                {"title": "위대한 개츠비", "genres": "드라마, 로맨스"},
            ],
            "오늘 볼 영화 추천해줘",
            {},
        )
        answer = build_character_grounded_answer(movies, "마석도")
        self.assertIn("오늘은 ‘스타워즈’부터 봐.", answer)
        self.assertIn("‘아마데우스’와 ‘위대한 개츠비’", answer)
        self.assertTrue(is_safe_general_recommendation(answer, movies))

    def test_character_fallback_uses_cold_preset_without_new_titles(self):
        movies = prepare_recommendations(
            [
                {"title": "A", "genres": "액션"},
                {"title": "B", "genres": "범죄"},
                {"title": "C", "genres": "스릴러"},
            ],
            "영화 추천해줘",
            {},
        )
        answer = build_character_grounded_answer(movies, "장첸")
        self.assertIn("우선 ‘A’, 이걸 고르지.", answer)
        self.assertTrue(is_safe_general_recommendation(answer, movies))

    def test_vague_request_keeps_semantic_rank_instead_of_forcing_genre_spread(self):
        candidates = [
            {"title": "A", "genres": "드라마"},
            {"title": "B", "genres": "드라마"},
            {"title": "C", "genres": "드라마"},
            {"title": "D", "genres": "공포"},
        ]
        selected = select_diverse_movies(candidates, 3, requested_genre=None)
        self.assertEqual([movie["title"] for movie in selected], ["A", "B", "C"])

    def test_diversity_avoids_near_duplicate_candidates(self):
        candidates = [
            {"title": "A", "genres": "액션, 코미디", "director": "감독1", "cast": "배우1", "year": 2021},
            {"title": "B", "genres": "액션, 코미디", "director": "감독1", "cast": "배우1", "year": 2022},
            {"title": "C", "genres": "액션, SF", "director": "감독2", "cast": "배우2", "year": 2015},
            {"title": "D", "genres": "액션, 판타지", "director": "감독3", "cast": "배우3", "year": 2008},
        ]
        selected = select_diverse_movies(candidates, 3, requested_genre="액션")
        self.assertEqual([movie["title"] for movie in selected], ["A", "C", "D"])

    def test_reasons_use_structured_genre_and_rating(self):
        movies = [{"title": "A", "genres": "액션, SF", "vote_average": 7.4}]
        prepared = prepare_recommendations(
            movies,
            "액션 영화 추천해줘",
            {"genre": "액션"},
            limit=1,
        )
        self.assertEqual(prepared[0]["recommendation_role"], "가장 잘 맞는 선택")
        self.assertIn("액션", prepared[0]["recommendation_reason"])
        self.assertIn("7.4", prepared[0]["recommendation_reason"])

    def test_answer_mentions_all_three_card_titles(self):
        movies = prepare_recommendations(
            [
                {"title": "A", "genres": "코미디"},
                {"title": "B", "genres": "가족"},
                {"title": "C", "genres": "애니메이션"},
            ],
            "가볍게 볼 영화",
            {},
        )
        answer = build_grounded_answer(movies)
        for title in ("A", "B", "C"):
            self.assertIn(f"‘{title}’", answer)
        for internal_label in ("가장 잘 맞는 선택", "다른 결의 대안", "취향 확장 선택"):
            self.assertNotIn(internal_label, answer)

    def test_answer_summarizes_alternative_genre_differences(self):
        movies = prepare_recommendations(
            [
                {"title": "블랙 아담", "genres": "액션, 모험, SF"},
                {"title": "익스펜더블 2", "genres": "액션, 모험, 스릴러"},
                {"title": "Husbands in Action", "genres": "액션, 코미디"},
            ],
            "액션 영화 추천해줘",
            {"genre": "액션"},
        )
        answer = build_grounded_answer(movies)
        self.assertIn("스릴러 요소가 있는 ‘익스펜더블 2’", answer)
        self.assertIn("코미디 요소가 있는 ‘Husbands in Action’", answer)
        self.assertNotIn("첫 번째 영화", answer)

    def test_primary_title_does_not_use_ambiguous_object_particle(self):
        movies = prepare_recommendations(
            [{"title": "물괴", "genres": "액션"}],
            "액션 영화 추천해줘",
            {"genre": "액션"},
        )
        answer = build_grounded_answer(movies)
        self.assertIn("‘물괴’부터 추천해요.", answer)
        self.assertNotIn("‘물괴’을", answer)

    def test_plain_genre_reason_avoids_database_verification_wording(self):
        movies = prepare_recommendations(
            [{"title": "물괴", "genres": "액션, 판타지", "vote_average": 5.9}],
            "액션 영화 추천해줘",
            {"genre": "액션"},
        )
        reason = movies[0]["recommendation_reason"]
        self.assertEqual(reason, "액션에 판타지 요소가 더해진 작품이에요.")
        self.assertNotIn("정보가 확인된", reason)

    def test_latest_order_is_not_changed_by_diversity(self):
        movies = [
            {"title": "최신1", "genres": "코미디", "release_date": "2026-03-01"},
            {"title": "최신2", "genres": "코미디", "release_date": "2026-02-01"},
            {"title": "최신3", "genres": "코미디", "release_date": "2026-01-01"},
        ]
        prepared = prepare_recommendations(movies, "최신 코미디", {"sort_latest": True}, limit=3)
        self.assertEqual([movie["title"] for movie in prepared], ["최신1", "최신2", "최신3"])

    def test_duplicate_display_titles_are_removed_before_selection(self):
        movies = [
            {"title": "레이디와 트램프", "genres": "가족, 코미디", "year": 2019},
            {"title": "  레이디와   트램프  ", "genres": "가족, 애니메이션", "year": 1955},
            {"title": "알파 앤 오메가", "genres": "가족, 애니메이션", "year": 2010},
            {"title": "로빈슨 가족", "genres": "가족, 애니메이션", "year": 2007},
        ]
        prepared = prepare_recommendations(movies, "가족 영화", {"genre": "가족"}, limit=3)
        self.assertEqual(
            [movie["title"] for movie in prepared],
            ["레이디와 트램프", "알파 앤 오메가", "로빈슨 가족"],
        )

    def test_alternative_reasons_explain_real_differences(self):
        movies = [
            {"title": "A", "genres": "로맨스, 코미디", "year": 2020, "vote_average": 6.5},
            {"title": "B", "genres": "로맨스, 미스터리", "year": 2019, "vote_average": 6.2},
            {"title": "C", "genres": "로맨스, 코미디", "year": 2024, "vote_average": 7.3},
        ]
        prepared = prepare_recommendations(movies, "데이트 영화", {}, limit=3)
        reasons = [movie["recommendation_reason"] for movie in prepared]

        self.assertIn("미스터리", reasons[1])
        self.assertIn("7.3", reasons[2])
        self.assertEqual(len(set(reasons)), 3)


if __name__ == "__main__":
    unittest.main()
