import unittest

from pipeline.recommendation_presenter import (
    _korean_object_particle,
    build_character_grounded_answer,
    build_grounded_answer,
    filter_movies_by_requested_genre,
    is_safe_general_recommendation,
    prepare_recommendations,
    select_diverse_movies,
)


class RecommendationPresenterTests(unittest.TestCase):
    def test_runtime_constraint_is_explained_from_metadata(self):
        movies = prepare_recommendations(
            [{"title": "짧은 코미디", "genres": "코미디", "runtime": 108}],
            "두 시간 안 넘는 코미디 추천해줘",
            {"genre": "코미디", "runtime_max": 120},
            limit=1,
        )
        self.assertIn("108분", movies[0]["recommendation_reason"])
        self.assertIn("120분 이하", movies[0]["recommendation_reason"])

    def test_country_and_language_constraint_is_explained(self):
        movies = prepare_recommendations(
            [{"title": "A", "production_countries": "FR", "language": "en"}],
            "프랑스 제작 영어 영화",
            {"production_country": "FR", "language": "en"},
            limit=1,
        )
        reason = movies[0]["recommendation_reason"]
        self.assertIn("프랑스", reason)
        self.assertIn("영어", reason)

    def test_release_date_window_is_explained(self):
        movies = prepare_recommendations(
            [{"title": "A", "release_date": "2026-08-10"}],
            "이번 달 이미 개봉한 영화",
            {"release_date_from": "2026-08-01", "release_date_to": "2026-08-19"},
            limit=1,
        )
        self.assertIn("2026-08-10", movies[0]["recommendation_reason"])
        self.assertIn("2026-08-01", movies[0]["recommendation_reason"])

    def test_final_boundary_never_relaxes_director_genre_and_year(self):
        prepared = prepare_recommendations(
            [
                {"title": "어쩔수가없다", "director": "박찬욱", "genres": "코미디, 범죄, 스릴러", "year": 2025},
                {"title": "다른 애니", "director": "다른 감독", "genres": "애니메이션", "year": 2026},
            ],
            "박찬욱 감독의 2025년 이후 애니메이션",
            {"director": "박찬욱", "genre": "애니메이션", "required_genres": ["애니메이션"], "year_from": 2025},
            limit=2,
        )
        self.assertEqual(prepared, [])

    def test_audience_threshold_is_rechecked_and_explained(self):
        prepared = prepare_recommendations(
            [
                {"title": "흥행작", "audience_count": 7_000_000},
                {"title": "기준 미달", "audience_count": 1_000_000},
            ],
            "관객 500만 이상",
            {"audience_min": 5_000_000},
            limit=2,
        )
        self.assertEqual([movie["title"] for movie in prepared], ["흥행작"])
        self.assertIn("7,000,000명", prepared[0]["recommendation_reason"])
    def test_character_fallback_uses_correct_korean_conjunction_particle(self):
        movies = [
            {"title": "첫 영화", "recommendation_reason": "이유야."},
            {"title": "야! 러그래츠: 파리 대모험"},
            {"title": "엘리멘탈"},
        ]

        answer = build_character_grounded_answer(movies, "슈렉")

        self.assertIn("‘야! 러그래츠: 파리 대모험’과 ‘엘리멘탈’", answer)

    def test_fun_request_reasons_use_comedy_evidence_for_every_card(self):
        movies = prepare_recommendations(
            [
                {"title": "A", "genres": "가족, 로맨스, 코미디"},
                {"title": "B", "genres": "가족, 모험, 애니메이션, 코미디"},
                {"title": "C", "genres": "모험, 애니메이션, 코미디"},
            ],
            "주말 밤에 볼 유쾌한 영화 세 편 골라줘",
            {},
            limit=3,
        )

        self.assertEqual(len(movies), 3)
        self.assertTrue(all("코미디" in movie["recommendation_reason"] for movie in movies))
        self.assertTrue(all("가볍게 보기" in movie["recommendation_reason"] for movie in movies))

    def test_korean_object_particle_matches_genre_final_consonant(self):
        self.assertEqual(_korean_object_particle("공포"), "를")
        self.assertEqual(_korean_object_particle("액션"), "을")
        self.assertEqual(_korean_object_particle("SF"), "를")

    def test_explicit_genre_drops_mismatched_cards(self):
        movies = [
            {"title": "액션 카드", "genres": "액션, 스릴러"},
            {"title": "공포 카드", "genres": "공포, 미스터리"},
            {"title": "장르 배열", "genres_list": '["액션", "모험"]'},
        ]

        filtered = filter_movies_by_requested_genre(movies, "액션")

        self.assertEqual([movie["title"] for movie in filtered], ["액션 카드", "장르 배열"])

    def test_hwarim_fallback_uses_character_voice_instead_of_generic_template(self):
        movies = prepare_recommendations(
            [
                {"title": "베스와 베라", "genres": "공포, 미스터리", "vote_average": 7.4},
                {"title": "부기맨", "genres": "공포"},
            ],
            "공포 영화 추천해줘",
            {"genre": "공포"},
        )

        answer = build_character_grounded_answer(movies, "화림")

        self.assertIn("낌새", answer)
        self.assertIn("베스와 베라", answer)
        self.assertIn("부기맨", answer)
        self.assertNotIn("요청하신", answer)

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

    def test_child_query_filters_unsafe_certification_at_output_boundary(self):
        movies = [
            {"title": "전체 관람", "genres": "애니메이션", "certification": "ALL", "certification_country": "KR"},
            {"title": "12세", "genres": "애니메이션", "certification": "12", "certification_country": "KR"},
        ]
        prepared = prepare_recommendations(
            movies,
            "초등학생 조카랑 같이 볼 영화",
            {},
            limit=3,
        )
        self.assertEqual([movie["title"] for movie in prepared], ["전체 관람"])

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

    def test_thoughtful_scifi_reason_uses_overview_evidence(self):
        movies = prepare_recommendations(
            [{"title": "A", "genres": "SF, 드라마", "overview": "기술이 인간의 미래와 선택에 미치는 영향"}],
            "보고 나서 같이 얘기할 거리가 많은 SF 영화",
            {"genre": "SF"},
            limit=1,
        )
        self.assertIn("기술", movies[0]["recommendation_reason"])
        self.assertIn("이야기할 근거", movies[0]["recommendation_reason"])

    def test_feelgood_reason_uses_overview_evidence(self):
        movies = prepare_recommendations(
            [{"title": "A", "genres": "음악, 코미디", "overview": "친구들과 음악으로 꿈과 희망을 찾는다"}],
            "음악이 좋고 보고 나면 기분 좋아지는 영화",
            {"genre": "음악"},
            limit=1,
        )
        self.assertIn("꿈", movies[0]["recommendation_reason"])
        self.assertIn("기분 좋은", movies[0]["recommendation_reason"])

    def test_gentle_suspense_reason_preserves_compromise_mood(self):
        movies = prepare_recommendations(
            [{"title": "A", "genres": "미스터리, 코미디", "overview": "수수께끼를 유쾌하게 풀어 간다"}],
            "살짝 쫄깃하지만 안 무서운 데이트 영화",
            {},
            limit=1,
        )
        self.assertIn("공포를 피하면서", movies[0]["recommendation_reason"])
        self.assertIn("가볍게 긴장감", movies[0]["recommendation_reason"])

    def test_parent_cowatching_reason_does_not_claim_scene_level_guarantee(self):
        movies = prepare_recommendations(
            [{"title": "A", "genres": "가족, 드라마", "overview": "세대가 서로를 이해해 간다"}],
            "부모님이랑 볼 건데 민망하지 않고 잔인하지 않은 영화",
            {},
            limit=1,
        )
        reason = movies[0]["recommendation_reason"]
        self.assertIn("장르 정보를 근거로", reason)
        self.assertNotIn("민망한 장면이 없", reason)
        self.assertNotIn("잔인하지 않", reason)

    def test_group_compromise_prefers_more_verified_tastes_and_drops_r_rating(self):
        movies = prepare_recommendations(
            [
                {"title": "공통", "genres": "액션, 코미디, 미스터리", "certification": "15"},
                {"title": "성인", "genres": "액션, 코미디, 미스터리", "certification": "R"},
                {"title": "일부", "genres": "액션", "certification": "12"},
            ],
            "친구 넷이서 한 명은 액션, 한 명은 코미디, 나는 미스터리를 좋아하고 한 명은 잔인한 걸 못 봐. 넷 다 덜 불만일 영화",
            {},
            limit=2,
        )
        self.assertEqual([movie["title"] for movie in movies], ["공통", "일부"])
        self.assertIn("액션 · 코미디 · 미스터리", movies[0]["recommendation_reason"])

    def test_adult_animation_reason_uses_mature_theme_evidence(self):
        movies = prepare_recommendations(
            [{"title": "A", "genres": "애니메이션, 드라마", "overview": "사회의 편견과 가족 관계를 다룬다"}],
            "어른이 봐도 유치하지 않은 애니메이션",
            {"genre": "애니메이션"},
            limit=1,
        )
        self.assertIn("사회", movies[0]["recommendation_reason"])
        self.assertIn("성인도 깊이", movies[0]["recommendation_reason"])

    def test_avoid_sad_reason_precedes_generic_date_reason(self):
        movies = prepare_recommendations(
            [{"title": "A", "genres": "로맨스, 코미디", "overview": "새 출발과 유쾌한 사랑 이야기"}],
            "데이트 영화 추천해줘. 너무 슬픈 건 싫어",
            {"genre": "로맨스"},
            limit=1,
        )
        self.assertIn("너무 슬프지 않은", movies[0]["recommendation_reason"])

    def test_bright_date_reason_uses_synopsis_evidence(self):
        movies = prepare_recommendations(
            [{"title": "A", "genres": "로맨스, 코미디", "overview": "새 출발과 유쾌한 사랑 이야기"}],
            "밝은 데이트 로맨스",
            {"genre": "로맨스"},
            limit=1,
        )
        self.assertIn("밝은 데이트 분위기", movies[0]["recommendation_reason"])

    def test_bright_date_alternatives_explain_metadata_differences(self):
        movies = prepare_recommendations(
            [
                {"title": "A", "genres": "로맨스, 코미디", "year": 2020, "overview": "사랑과 새 출발"},
                {"title": "B", "genres": "로맨스, 애니메이션", "year": 2021, "overview": "따뜻한 사랑"},
                {"title": "C", "genres": "로맨스, 코미디", "year": 2023, "vote_average": 7.4, "overview": "설레는 사랑"},
            ],
            "밝은 데이트 로맨스",
            {"genre": "로맨스"},
            limit=3,
        )
        reasons = [movie["recommendation_reason"] for movie in movies]
        self.assertIn("밝은 데이트", reasons[0])
        self.assertIn("애니메이션", reasons[1])
        self.assertGreaterEqual(len(set(reasons)), 2)


if __name__ == "__main__":
    unittest.main()
