import unittest

from rag.movie_quality import (
    apply_query_preferences,
    blend_semantic_and_quality,
    expand_mood_query,
    has_recommendation_evidence,
    intent_match_score,
    is_child_safe_certification,
    movie_quality_score,
    prefer_evidenced_candidates,
    prefer_bright_candidates,
    prefer_explainable_candidates,
    prefer_non_sad_candidates,
    prefer_well_received_candidates,
)


class MovieQualityTests(unittest.TestCase):
    def test_movie_liking_wording_applies_well_received_preference(self):
        candidates = [
            {"title": "낮은1", "vote_average": 5.3},
            {"title": "낮은2", "vote_average": 5.7},
            {"title": "적정1", "vote_average": 6.2},
            {"title": "적정2", "vote_average": 6.4},
            {"title": "적정3", "vote_average": 6.7},
        ]

        result = prefer_well_received_candidates(
            "전개 빠른 액션 영화가 좋아",
            candidates,
            required=3,
        )

        self.assertEqual([movie["title"] for movie in result], ["적정1", "적정2", "적정3"])

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

    def test_bedtime_query_blocks_intense_movies(self):
        candidates = [
            {"title": "인피니티 워", "genres": "액션, 모험, SF"},
            {"title": "잔잔한 드라마", "genres": "드라마"},
            {"title": "따뜻한 로맨스", "genres": "로맨스"},
            {"title": "음악 영화", "genres": "음악"},
        ]
        result = apply_query_preferences(
            "잠들기 전에 편안하게 볼 영화 한 편 추천해줘",
            candidates,
            required=3,
        )
        self.assertEqual(
            [movie["title"] for movie in result],
            ["잔잔한 드라마", "따뜻한 로맨스", "음악 영화"],
        )

    def test_bedtime_query_expands_to_restful_concepts(self):
        expanded = expand_mood_query("잠들기 전에 편안하게 볼 영화")
        self.assertIn("잔잔", expanded)
        self.assertIn("평온", expanded)

    def test_bedtime_intent_penalizes_action_spectacle(self):
        calm = {
            "genres": "드라마, 음악",
            "overview": "평온한 일상 속에서 따뜻한 위로를 전하는 잔잔한 이야기",
        }
        intense = {
            "genres": "액션, 모험, SF",
            "overview": "우주 전쟁과 전투, 폭발 속에서 생존을 건 추격이 이어진다",
        }
        query = "잠들기 전에 편안하게 볼 영화"
        self.assertGreater(intent_match_score(query, calm), intent_match_score(query, intense))

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

    def test_school_age_relative_query_never_relaxes_child_safety(self):
        candidates = [
            {"title": "안전", "genres": "가족", "certification_country": "KR", "certification": "ALL"},
            {"title": "미확인", "genres": "가족", "certification_country": "US", "certification": "NR"},
            {"title": "공포", "genres": "공포", "certification_country": "US", "certification": "R"},
        ]
        result = apply_query_preferences(
            "초등학생 조카랑 무섭지 않은 영화 골라줘.",
            candidates,
            required=3,
        )
        self.assertEqual([movie["title"] for movie in result], ["안전"])

    def test_blocked_mood_genres_stay_blocked_when_pool_is_small(self):
        candidates = [
            {"title": "코미디", "genres": "코미디"},
            {"title": "공포", "genres": "공포"},
        ]
        result = apply_query_preferences("부담 없이 볼 영화", candidates, required=3)
        self.assertEqual([movie["title"] for movie in result], ["코미디"])

    def test_poor_rating_is_avoided_when_enough_recommendation_options_exist(self):
        candidates = [
            {"title": "낮음", "vote_average": 4.3},
            {"title": "보통1", "vote_average": 6.0},
            {"title": "보통2", "vote_average": 6.1},
            {"title": "보통3", "vote_average": 7.0},
        ]
        result = prefer_well_received_candidates("데이트 영화 추천", candidates, required=3)
        self.assertEqual({movie["title"] for movie in result}, {"보통1", "보통2", "보통3"})

    def test_want_to_watch_wording_is_a_recommendation_request(self):
        candidates = [
            {"title": "낮음", "vote_average": 5.0},
            {"title": "보통1", "vote_average": 6.0},
            {"title": "보통2", "vote_average": 6.5},
            {"title": "보통3", "vote_average": 7.0},
        ]
        result = prefer_well_received_candidates(
            "음악이 좋고 보고 나면 기분 좋아지는 영화가 보고 싶어", candidates, required=3
        )
        self.assertEqual([movie["title"] for movie in result], ["보통1", "보통2", "보통3"])

    def test_viewing_purpose_without_recommend_verb_avoids_low_ratings(self):
        candidates = [
            {"title": "낮음", "vote_average": 5.4},
            {"title": "보통1", "vote_average": 6.0},
            {"title": "보통2", "vote_average": 6.5},
            {"title": "보통3", "vote_average": 7.0},
        ]
        result = prefer_well_received_candidates("철학적인 SF 영화 세 편", candidates, required=3)
        self.assertEqual([movie["title"] for movie in result], ["보통1", "보통2", "보통3"])

    def test_mood_expansions_use_distinct_search_concepts(self):
        self.assertIn("휴먼 드라마", expand_mood_query("감동적인 영화"))
        self.assertIn("기분 전환", expand_mood_query("우울할 때 볼 영화"))
        self.assertIn("로맨스", expand_mood_query("데이트 영화"))
        self.assertIn("어린이", expand_mood_query("아이와 함께 볼 영화"))
        self.assertIn("철학적", expand_mood_query("같이 얘기할 거리가 많은 SF 영화"))
        self.assertIn("기분이 좋아지는", expand_mood_query("보고 나면 기분 좋아지는 영화"))

    def test_discussion_intent_prefers_thoughtful_metadata(self):
        thoughtful = {"genres": "SF, 드라마", "overview": "언어와 시간, 인간의 선택을 질문한다."}
        spectacle = {"genres": "SF, 액션", "overview": "거대한 전쟁과 폭발이 이어진다."}
        query = "보고 나서 같이 얘기할 거리가 많은 SF 영화"
        self.assertGreater(intent_match_score(query, thoughtful), intent_match_score(query, spectacle))

    def test_feelgood_intent_penalizes_tragic_metadata(self):
        hopeful = {"genres": "음악, 코미디", "overview": "우정과 꿈을 통해 희망을 찾는다."}
        tragic = {"genres": "음악, 드라마", "overview": "전쟁과 죽음, 절망을 겪는다."}
        query = "음악이 좋고 보고 나면 기분 좋아지는 영화"
        self.assertGreater(intent_match_score(query, hopeful), intent_match_score(query, tragic))

    def test_avoid_sad_intent_prefers_bright_romance(self):
        bright = {"genres": "로맨스, 코미디", "overview": "새 출발과 사랑을 그린 밝고 유쾌한 이야기"}
        tragic = {"genres": "로맨스, 드라마", "overview": "연인의 죽음과 상실, 이별을 다룬 비극"}
        query = "데이트하면서 볼 로맨스 영화, 너무 슬픈 건 싫어"
        self.assertGreater(intent_match_score(query, bright), intent_match_score(query, tragic))

    def test_sad_movie_request_is_not_mistaken_for_avoidance(self):
        movie = {"genres": "드라마", "overview": "이별과 상실을 다룬 이야기"}
        self.assertIsNone(intent_match_score("슬픈 영화 추천해줘", movie))

    def test_avoid_sad_date_query_expands_to_bright_concepts(self):
        expanded = expand_mood_query("데이트 영화 추천해줘. 너무 슬픈 건 싫어")
        self.assertIn("밝고 유쾌", expanded)

    def test_explicit_bright_date_query_penalizes_terminal_illness(self):
        bright = {"genres": "로맨스, 코미디", "overview": "새 출발과 설레는 사랑을 그린 유쾌한 이야기"}
        tragic = {"genres": "로맨스, 코미디", "overview": "말기암 진단을 받은 연인의 사랑 이야기"}
        query = "2010년 이후 밝은 데이트 로맨스"
        self.assertGreater(intent_match_score(query, bright), intent_match_score(query, tragic))

    def test_explicit_bright_date_query_filters_terminal_illness_when_possible(self):
        candidates = [
            {"title": "말기암", "overview": "말기암 진단을 받은 연인"},
            {"title": "밝음1", "overview": "유쾌한 데이트"},
            {"title": "밝음2", "overview": "새로운 사랑"},
            {"title": "밝음3", "overview": "설레는 만남"},
        ]
        result = prefer_non_sad_candidates("밝은 데이트 로맨스", candidates, required=3)
        self.assertEqual([movie["title"] for movie in result], ["밝음1", "밝음2", "밝음3"])

    def test_explicit_bright_date_query_filters_cancer_with_limited_time(self):
        candidates = [
            {"title": "암 발병", "overview": "연인의 암이 발병해 시간이 얼마 남지 않았다"},
            {"title": "밝음1", "overview": "유쾌한 데이트"},
            {"title": "밝음2", "overview": "새로운 사랑"},
            {"title": "밝음3", "overview": "설레는 만남"},
        ]
        result = prefer_non_sad_candidates("더 밝은 로맨스", candidates, required=3)
        self.assertEqual([movie["title"] for movie in result], ["밝음1", "밝음2", "밝음3"])

    def test_explicit_bright_date_query_filters_distress_signals(self):
        candidates = [
            {"title": "어두움", "overview": "정신 착란과 출구 없는 인생에서 괴로워한다"},
            {"title": "밝음1", "overview": "유쾌한 데이트"},
            {"title": "밝음2", "overview": "새로운 사랑"},
            {"title": "밝음3", "overview": "설레는 만남"},
        ]
        result = prefer_non_sad_candidates("더 밝은 로맨스", candidates, required=3)
        self.assertEqual([movie["title"] for movie in result], ["밝음1", "밝음2", "밝음3"])

    def test_explicit_bright_romance_prefers_positive_synopsis_evidence(self):
        candidates = [
            {"title": "외도", "overview": "남편의 외도를 의심해 미행한다"},
            {"title": "밝음1", "overview": "유쾌한 데이트"},
            {"title": "밝음2", "overview": "새 출발과 사랑"},
            {"title": "밝음3", "overview": "행복한 만남"},
        ]
        result = prefer_bright_candidates("더 밝은 로맨스", candidates, required=3)
        self.assertEqual([movie["title"] for movie in result], ["밝음1", "밝음2", "밝음3"])

    def test_explicit_bright_romance_expands_to_bright_concepts(self):
        self.assertIn("밝고 유쾌", expand_mood_query("밝은 데이트 로맨스"))

    def test_adult_animation_intent_prefers_mature_metadata(self):
        mature = {
            "genres": "애니메이션, 드라마",
            "overview": "사회의 편견과 가족 관계, 인간의 책임을 다룬다.",
            "certification_country": "KR", "certification": "12",
        }
        childish = {
            "genres": "애니메이션, 가족",
            "overview": "유아와 어린이용 꼬마 모험 이야기",
            "certification_country": "KR", "certification": "ALL",
        }
        query = "어른이 봐도 유치하지 않은 애니메이션"
        self.assertGreater(intent_match_score(query, mature), intent_match_score(query, childish))

    def test_adult_animation_query_expands_to_mature_concepts(self):
        expanded = expand_mood_query("어른이 봐도 유치하지 않은 애니메이션")
        self.assertIn("성숙한 주제", expanded)
        self.assertIn("정체성", expanded)

    def test_intent_can_break_close_semantic_scores(self):
        spectacle = {"title": "전쟁", "_score": 0.90, "genres": "SF, 액션", "overview": "우주 전쟁"}
        thoughtful = {
            "title": "대화", "_score": 0.88, "genres": "SF, 드라마",
            "overview": "언어와 시간, 인간의 선택을 질문한다.",
        }
        tail = {"title": "하위", "_score": 0.20, "genres": "코미디", "overview": ""}
        result = blend_semantic_and_quality(
            [spectacle, thoughtful, tail], top_k=2, query="같이 얘기할 거리가 많은 SF 영화"
        )
        self.assertEqual(result[0]["title"], "대화")

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

    def test_mood_query_prefers_candidates_with_synopsis_evidence(self):
        candidates = [
            {"title": "공란", "overview": ""},
            {"title": "근거1", "overview": "밝은 우정 이야기"},
            {"title": "근거2", "overview": "가족의 모험"},
            {"title": "근거3", "overview": "꿈을 이루는 코미디"},
        ]
        result = prefer_explainable_candidates("기분 좋아지는 영화", candidates, required=3)
        self.assertEqual([movie["title"] for movie in result], ["근거1", "근거2", "근거3"])

    def test_synopsis_gate_preserves_recall_when_evidence_is_insufficient(self):
        candidates = [
            {"title": "공란", "overview": ""},
            {"title": "근거", "overview": "밝은 이야기"},
        ]
        result = prefer_explainable_candidates("기분 좋아지는 영화", candidates, required=2)
        self.assertEqual(result, candidates)

    def test_synopsis_gate_does_not_change_plain_genre_search(self):
        candidates = [{"title": "공란", "overview": ""}, {"title": "근거", "overview": "줄거리"}]
        self.assertEqual(prefer_explainable_candidates("액션 영화", candidates, required=1), candidates)

    def test_avoid_sad_query_filters_tragic_synopsis_when_alternatives_exist(self):
        candidates = [
            {"title": "비극", "overview": "연인의 죽음과 이별로 슬픔에 잠긴다"},
            {"title": "밝음1", "overview": "유쾌한 데이트"},
            {"title": "밝음2", "overview": "새로운 사랑"},
            {"title": "밝음3", "overview": "설레는 만남"},
        ]
        result = prefer_non_sad_candidates("비극적인 사랑은 제외하고 로맨스", candidates, required=3)
        self.assertEqual([movie["title"] for movie in result], ["밝음1", "밝음2", "밝음3"])

    def test_avoid_sad_filter_preserves_recall_when_alternatives_are_insufficient(self):
        candidates = [
            {"title": "비극", "overview": "죽음과 이별"},
            {"title": "밝음", "overview": "유쾌한 만남"},
        ]
        self.assertEqual(
            prefer_non_sad_candidates("슬픈 영화는 빼줘", candidates, required=2),
            candidates,
        )

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
