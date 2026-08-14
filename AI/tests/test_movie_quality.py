import unittest

from rag.movie_quality import (
    apply_query_preferences,
    blend_semantic_and_quality,
    expand_mood_query,
    has_recommendation_evidence,
    is_child_safe_certification,
    movie_quality_score,
    prefer_evidenced_candidates,
    prefer_well_received_candidates,
)


class MovieQualityTests(unittest.TestCase):
    def test_ambiguous_light_mood_is_expanded_to_retrieval_concepts(self):
        expanded = expand_mood_query("가볍게 볼 영화")
        self.assertIn("코미디", expanded)
        self.assertIn("가족", expanded)
        self.assertNotIn("가볍게", expanded)

    def test_light_query_prefers_light_genres_and_blocks_heavy_movies(self):
        candidates = [
            {"title": "공포", "genres": "공포, 미스터리"},
            {"title": "범죄", "genres": "드라마, 범죄"},
            {"title": "코미디", "genres": "코미디"},
            {"title": "가족", "genres": "가족, 모험"},
            {"title": "로맨스", "genres": "로맨스, 드라마"},
        ]
        result = apply_query_preferences("가볍게 볼 영화", candidates, required=3)
        self.assertEqual([movie["title"] for movie in result], ["코미디", "가족", "로맨스"])

    def test_light_query_relaxes_to_non_heavy_when_preferred_pool_is_small(self):
        candidates = [
            {"title": "공포", "genres": "공포"},
            {"title": "드라마1", "genres": "드라마"},
            {"title": "드라마2", "genres": "드라마"},
            {"title": "코미디", "genres": "코미디"},
        ]
        result = apply_query_preferences("부담 없이 볼 영화", candidates, required=3)
        self.assertEqual({movie["title"] for movie in result}, {"드라마1", "드라마2", "코미디"})

    def test_uplift_query_does_not_match_horror_from_word_fragment(self):
        candidates = [
            {"title": "울프맨", "genres_list": '["공포", "스릴러"]'},
            {"title": "코미디", "genres_list": '["코미디"]'},
            {"title": "가족", "genres_list": '["가족", "모험"]'},
            {"title": "애니", "genres_list": '["애니메이션"]'},
        ]
        result = apply_query_preferences("우울할 때 보기 좋은 영화", candidates, required=3)
        self.assertEqual({movie["title"] for movie in result}, {"코미디", "가족", "애니"})

    def test_kids_query_prefers_known_child_safe_certifications(self):
        candidates = [
            {"title": "전체", "genres": "가족", "certification_country": "KR", "certification": "ALL"},
            {"title": "PG", "genres": "애니메이션", "certification_country": "US", "certification": "PG"},
            {"title": "G", "genres": "모험", "certification_country": "US", "certification": "G"},
            {"title": "등급없음", "genres": "가족", "certification_country": "US", "certification": "NR"},
        ]
        result = apply_query_preferences("아이와 함께 볼 영화", candidates, required=3)
        self.assertEqual({movie["title"] for movie in result}, {"전체", "PG", "G"})
        self.assertTrue(is_child_safe_certification(candidates[0]))
        self.assertFalse(is_child_safe_certification(candidates[3]))

    def test_poor_rating_is_avoided_when_enough_recommendation_options_exist(self):
        candidates = [
            {"title": "낮음", "vote_average": 4.3},
            {"title": "보통1", "vote_average": 6.0},
            {"title": "보통2", "vote_average": 6.1},
            {"title": "보통3", "vote_average": 7.0},
        ]
        result = prefer_well_received_candidates("데이트 영화 추천", candidates, required=3)
        self.assertEqual({movie["title"] for movie in result}, {"보통1", "보통2", "보통3"})

    def test_mood_expansions_use_distinct_search_concepts(self):
        self.assertIn("휴먼 드라마", expand_mood_query("감동적인 영화"))
        self.assertIn("기분 전환", expand_mood_query("우울할 때 볼 영화"))
        self.assertIn("로맨스", expand_mood_query("데이트 영화"))
        self.assertIn("어린이", expand_mood_query("아이와 함께 볼 영화"))

    def test_light_followup_preserves_explicit_previous_genre(self):
        expanded = expand_mood_query("액션 영화 추천해줘 너무 무거워 더 가벼운 걸로")
        self.assertIn("액션", expanded)
        self.assertIn("코미디", expanded)

    def test_zero_vote_empty_movie_has_no_recommendation_evidence(self):
        movie = {"vote_count": 0, "audience_count": 0, "overview": ""}
        self.assertFalse(has_recommendation_evidence(movie))

    def test_perfect_rating_with_one_vote_is_not_trusted_like_established_movie(self):
        tiny = {"vote_average": 10.0, "vote_count": 1, "overview": "짧은 설명"}
        established = {"vote_average": 7.5, "vote_count": 2000, "overview": "충분한 설명"}
        self.assertLess(movie_quality_score(tiny), movie_quality_score(established))

    def test_evidence_gate_is_used_only_when_enough_candidates_exist(self):
        weak = {"title": "신뢰도 없음", "vote_count": 0}
        strong = {"title": "신뢰도 있음", "vote_count": 200}
        self.assertEqual(prefer_evidenced_candidates([weak, strong], required=1), [strong])
        self.assertEqual(prefer_evidenced_candidates([weak, strong], required=2), [weak, strong])

    def test_quality_can_break_close_semantic_scores(self):
        weak = {"title": "약한 후보", "_score": 0.90, "vote_count": 0}
        strong = {
            "title": "검증 후보", "_score": 0.88, "vote_average": 7.8,
            "vote_count": 4000, "overview": "줄거리", "poster_path": "/poster.jpg",
            "genres": "코미디", "year": 2020,
        }
        tail = {"title": "하위 후보", "_score": 0.20, "vote_count": 20}
        result = blend_semantic_and_quality([weak, strong, tail], top_k=2)
        self.assertEqual(result[0]["title"], "검증 후보")


if __name__ == "__main__":
    unittest.main()
