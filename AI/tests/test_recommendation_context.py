import unittest

from pipeline.intent import Intent, classify
from pipeline.recommendation_context import (
    build_card_followup_reply,
    build_recommendation_context,
    is_movie_recommendation_followup,
    is_realtime_ott_request,
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

    def test_movie_recommendation_now_done_routes_to_chat(self):
        message = "코미디 영화 추천은 이제 됐어. 대신 오늘 있었던 웃긴 얘기 들어줄래?"
        self.assertEqual(classify(message, history=self.history), Intent.CHARACTER_CHAT)

    def test_game_request_with_negated_movie_target_routes_to_chat(self):
        message = "친구 셋이 할 협동 게임 추천해줘. 영화는 안 볼 거야."
        self.assertEqual(classify(message), Intent.CHARACTER_CHAT)

    def test_implicit_movie_availability_question_routes_to_recommendation(self):
        self.assertEqual(
            classify("어우 덥다. 더운 날에 시원한 영화 없나?"),
            Intent.MOVIE_RECOMMEND,
        )

    def test_implicit_spaced_watchable_request_routes_to_recommendation(self):
        self.assertEqual(
            classify("퇴근했다. 머리 비우고 웃으면서 볼 만한 거 뭐 없냐?"),
            Intent.MOVIE_RECOMMEND,
        )

    def test_current_ott_availability_requires_realtime_provider_data(self):
        self.assertTrue(is_realtime_ott_request("오늘 넷플릭스에서 바로 볼 수 있는 한국 영화"))
        self.assertTrue(is_realtime_ott_request("티빙에서 지금 내려간 작품이면 안 돼"))
        self.assertFalse(is_realtime_ott_request("넷플릭스를 소재로 한 영화"))

    def test_direct_pick_recovers_movie_offer_without_structured_cards(self):
        history = [
            {"role": "user", "content": "퇴근했다. 머리 비우고 웃으면서 볼 만한 거 뭐 없냐?"},
            {
                "role": "assistant",
                "content": "가벼운 로맨틱 코미디나 유쾌한 애니메이션 영화 한 편 어때?",
            },
        ]
        self.assertEqual(classify("아니, 어때가 아니라 네가 하나 골라줘.", history), Intent.MOVIE_RECOMMEND)
        context = build_recommendation_context("아니, 어때가 아니라 네가 하나 골라줘.", history)
        self.assertIn("머리 비우고 웃으면서", context.search_message)

    def test_recommendation_repair_recovers_previous_movie_request(self):
        history = [
            {"role": "user", "content": "더운 날에 시원한 영화 없나?"},
            {"role": "assistant", "content": "청량한 영화를 보는 건 어때?"},
        ]
        self.assertEqual(classify("추천은 왜 안 해줘?", history), Intent.MOVIE_RECOMMEND)
        context = build_recommendation_context("추천은 왜 안 해줘?", history)
        self.assertIn("시원한 영화", context.search_message)

    def test_recent_colloquial_followup_preserves_horror(self):
        history = [
            {"role": "user", "content": "시원한 영화라 하면 공포 영화야."},
            {"role": "assistant", "content": "세 편 추천", "movies": [{"title": "A"}]},
        ]
        self.assertEqual(classify("요즘 거 없어?", history), Intent.MOVIE_RECOMMEND)
        context = build_recommendation_context("요즘 거 없어?", history)
        self.assertIn("공포", context.search_message)

    def test_action_as_behavior_is_not_movie_genre(self):
        message = "말보다 액션으로 보여주라는 상사에게 뭐라고 답해야 할까?"
        self.assertEqual(classify(message), Intent.CHARACTER_CHAT)

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

    def test_card_rating_comparison_stays_in_chat_intent(self):
        self.assertEqual(
            classify("평점이 제일 높은 건 어느 거야?", history=self.history),
            Intent.CHARACTER_CHAT,
        )

    def test_lightest_comedy_comparison_uses_only_current_cards(self):
        history = [
            {
                "role": "assistant",
                "content": "세 편 추천",
                "recommended_movies": [
                    {"title": "해피 뉴 이어", "genres": ["로맨스", "코미디"]},
                    {"title": "싸이보그지만 괜찮아", "genres": ["드라마", "코미디"]},
                    {"title": "김씨 표류기", "genres": ["드라마", "코미디"]},
                ],
            }
        ]
        message = "셋 중에 제일 가볍게 웃기기만 한 건 뭐야?"
        self.assertEqual(classify(message, history), Intent.CHARACTER_CHAT)
        answer, movies = build_card_followup_reply(message, history)
        self.assertIn("해피 뉴 이어", answer)
        self.assertNotIn("극한직업", answer)
        self.assertEqual([movie["title"] for movie in movies], ["해피 뉴 이어"])

    def test_comfortable_laughing_excludes_horror_and_thriller(self):
        context = build_recommendation_context(
            "친구랑 편하게 웃으며 볼 영화 두 편만 골라줘.",
            [],
        )
        self.assertEqual(set(context.excluded_genres), {"공포", "스릴러"})

    def test_genre_complaint_is_not_reinterpreted_as_positive_request(self):
        history = [
            {"role": "user", "content": "친구랑 편하게 웃으며 볼 코미디 두 편만 골라줘."},
            {
                "role": "assistant",
                "content": "세 편 추천",
                "recommended_movies": [
                    {"title": "직장상사 길들이기", "genres": "공포, 스릴러, 코미디"},
                    {"title": "다른 영화", "genres": "코미디"},
                ],
            },
        ]
        context = build_recommendation_context(
            "첫 번째는 공포 스릴러잖아. 편하게 웃고 싶다는 조건이 왜 무시됐어? 그 작품은 빼고 두 편만 줘.",
            history,
        )
        self.assertTrue(context.is_followup)
        self.assertIn("공포", context.excluded_genres)
        self.assertIn("스릴러", context.excluded_genres)
        self.assertIn("직장상사 길들이기", context.excluded_titles)

    def test_unstored_cast_prominence_is_not_invented(self):
        history = [
            {
                "role": "assistant",
                "content": "세 편 추천",
                "recommended_movies": [
                    {"title": "범죄도시 2", "cast": "마동석, 손석구"},
                    {"title": "연애 빠진 로맨스", "cast": "손석구, 전종서"},
                ],
            }
        ]
        message = "손석구가 주연인 것만 골라줘. 특별출연이면 빼고."
        self.assertEqual(classify(message, history), Intent.CHARACTER_CHAT)
        answer, movies = build_card_followup_reply(message, history)
        self.assertIn("정확히 구분할 수 없어", answer)
        self.assertEqual(movies, [])

    def test_live_ott_availability_does_not_start_new_retrieval(self):
        history = [
            {
                "role": "assistant",
                "content": "두 편 추천",
                "recommended_movies": [
                    {"title": "범죄도시 2"},
                    {"title": "연애 빠진 로맨스"},
                ],
            }
        ]
        message = "그 두 개 중 지금 한국 넷플릭스에 있는 건 뭐야?"
        self.assertEqual(classify(message, history), Intent.CHARACTER_CHAT)
        answer, movies = build_card_followup_reply(message, history)
        self.assertIn("실시간 OTT 제공 정보가 없어", answer)
        self.assertEqual(movies, [])

    def test_two_card_director_comparison_uses_existing_metadata(self):
        history = [
            {
                "role": "assistant",
                "content": "두 편 추천",
                "recommended_movies": [
                    {"title": "범죄도시 2", "director": "이상용"},
                    {"title": "연애 빠진 로맨스", "director": "정가영"},
                ],
            }
        ]
        message = "첫 번째랑 두 번째 감독이 같은 사람이야? 두 감독 이름도 같이 말해줘."
        self.assertEqual(classify(message, history), Intent.CHARACTER_CHAT)
        answer, movies = build_card_followup_reply(message, history)
        self.assertIn("이상용", answer)
        self.assertIn("정가영", answer)
        self.assertIn("서로 다른 감독", answer)
        self.assertEqual([movie["title"] for movie in movies], ["범죄도시 2", "연애 빠진 로맨스"])

    def test_direct_title_metadata_question_uses_matching_card(self):
        history = [
            {
                "role": "assistant",
                "content": "두 편 추천",
                "recommended_movies": [
                    {"title": "범죄도시 2", "director": "이상용"},
                    {"title": "연애 빠진 로맨스", "director": "정가영"},
                ],
            }
        ]
        message = "연애 빠진 로맨스 감독이 누구야? 그 카드 정보만 말해줘."
        self.assertEqual(classify(message, history), Intent.CHARACTER_CHAT)
        answer, movies = build_card_followup_reply(message, history)
        self.assertIn("정가영", answer)
        self.assertNotIn("이상용", answer)
        self.assertEqual([movie["title"] for movie in movies], ["연애 빠진 로맨스"])

    def test_keep_remaining_conditions_preserves_relative_date_request(self):
        history = [
            {
                "role": "user",
                "content": "이번 달에 이미 개봉한 한국 영화 두 편만 골라줘. 아직 개봉 안 한 건 빼고.",
            },
            {
                "role": "assistant",
                "content": "추천 결과",
                "recommended_movies": [{"title": "A"}],
            },
        ]
        message = "평점 7점 이상으로, 나머지 조건은 그대로 두고 두 편 다시 줘."
        context = build_recommendation_context(message, history)
        self.assertTrue(context.is_followup)
        self.assertIn("이번 달", context.search_message)
        self.assertIn("한국 영화", context.search_message)
        self.assertIn("평점 7점 이상", context.search_message)

    def test_actor_override_removes_previous_actor_but_keeps_other_filters(self):
        history = [
            {"role": "user", "content": "2015년 이후 마동석 나오는 액션 영화 두 편만 추천해줘."},
            {
                "role": "assistant",
                "content": "추천 결과",
                "recommended_movies": [{"title": "범죄도시 2"}],
            },
        ]
        message = "마동석 말고 송강호로 바꿔줘. 2015년 이후 액션 조건은 그대로 두고 두 편만."
        context = build_recommendation_context(message, history)
        self.assertTrue(context.is_followup)
        self.assertIn("송강호", context.search_message)
        self.assertIn("2015년 이후", context.search_message)
        self.assertIn("액션", context.search_message)
        before_current = context.search_message.split(message)[0]
        self.assertNotIn("마동석", before_current)

    def test_audience_threshold_adjustment_is_movie_followup(self):
        history = [
            {"role": "user", "content": "관객 500만 이상 한국 영화 추천해줘."},
            {"role": "assistant", "content": "추천 결과", "recommended_movies": [{"title": "A"}]},
        ]
        message = "관객 기준만 300만 명으로 낮춰줘. 한국 영화 조건은 유지해."
        self.assertEqual(classify(message, history), Intent.MOVIE_RECOMMEND)
        context = build_recommendation_context(message, history)
        self.assertTrue(context.is_followup)
        self.assertIn("한국 영화", context.search_message)

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

    def test_card_comparisons_use_structured_year_and_rating(self):
        history = [{
            "role": "assistant",
            "movies": [
                {"title": "A", "year": 2020, "vote_average": 7.1},
                {"title": "B", "year": 2023, "vote_average": 8.2},
                {"title": "C", "year": 2019, "vote_average": 8.0},
            ],
        }]
        latest, _ = build_card_followup_reply("셋 중 가장 최근 영화가 뭐야?", history)
        highest, _ = build_card_followup_reply("평점이 제일 높은 건 뭐야?", history)
        self.assertIn("B", latest)
        self.assertIn("B", highest)
        self.assertIn("8.2", highest)

    def test_card_genre_and_missing_metadata_are_grounded(self):
        history = [{
            "role": "assistant",
            "movies": [
                {"title": "A", "genres": "가족, 코미디"},
                {"title": "B"},
            ],
        }]
        genre, _ = build_card_followup_reply("첫 번째 장르가 뭐였지?", history)
        director, _ = build_card_followup_reply("두 번째 감독이 누구야?", history)
        self.assertIn("가족", genre)
        self.assertIn("코미디", genre)
        self.assertIn("감독 정보는 현재 카드에 없어", director)

    def test_card_out_of_range_is_explicit(self):
        answer, movies = build_card_followup_reply(
            "다섯 번째 영화 제목 알려줘.",
            [{"role": "assistant", "movies": [{"title": "A"}, {"title": "B"}, {"title": "C"}]}],
        )
        self.assertIn("5번째 영화는 없어", answer)
        self.assertEqual(movies, [])

    def test_card_genre_subset_does_not_trigger_new_retrieval(self):
        answer, movies = build_card_followup_reply(
            "방금 세 편 중 코미디인 것만 제목 알려줘.",
            [{"role": "assistant", "movies": [
                {"title": "A", "genres": "코미디"},
                {"title": "B", "genres": "드라마"},
                {"title": "C", "genres": "가족, 코미디"},
            ]}],
        )
        self.assertIn("A", answer)
        self.assertIn("C", answer)
        self.assertNotIn("‘B’", answer)
        self.assertEqual([movie["title"] for movie in movies], ["A", "C"])

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

    def test_double_negative_does_not_exclude_horror(self):
        context = build_recommendation_context(
            "공포를 싫어하는 건 아니야. 공포 영화 한 편 추천해줘.",
            [],
        )
        self.assertNotIn("공포", context.excluded_genres)

    def test_compound_genre_negation_excludes_modifier_not_requested_head(self):
        context = build_recommendation_context(
            "범죄 드라마 말고 그냥 드라마 두 편. 액션도 제외.",
            [],
        )
        self.assertEqual(set(context.excluded_genres), {"범죄", "액션"})

    def test_coordinated_absence_excludes_both_genres(self):
        context = build_recommendation_context(
            "로맨스도 코미디도 없는 SF 영화 추천해줘.",
            [],
        )
        self.assertEqual(set(context.excluded_genres), {"로맨스", "코미디"})

    def test_language_override_removes_old_language_only(self):
        history = [
            {"role": "user", "content": "2020년 이후 한국 코미디 추천해줘."},
            {"role": "assistant", "content": "추천", "movies": [{"title": "A"}]},
        ]
        context = build_recommendation_context(
            "장르와 연도는 그대로 두고 언어만 일본어로 바꿔서 두 편 추천해줘.",
            history,
        )
        self.assertNotIn("한국", context.search_message)
        self.assertIn("2020년 이후", context.search_message)
        self.assertIn("일본어", context.search_message)

    def test_year_override_removes_old_bound_only(self):
        history = [
            {"role": "user", "content": "2023년 이후 일본 애니메이션 추천해줘."},
            {"role": "assistant", "content": "추천", "movies": [{"title": "A"}]},
        ]
        context = build_recommendation_context(
            "장르와 언어는 유지하고 연도만 2010년 이후로 완화해. 두 편만 다시 추천해줘.",
            history,
        )
        self.assertNotIn("2023", context.search_message)
        self.assertIn("2010년 이후", context.search_message)

    def test_couple_compromise_refinement_remains_movie_followup(self):
        history = [
            {
                "role": "user",
                "content": "나는 공포영화 좋아하지만 여자친구는 무서운 걸 싫어해. 안 무서운 데이트 영화 두 편 골라줘.",
            },
            {
                "role": "assistant",
                "content": "추천 결과예요.",
                "movies": [{"title": "스포일러 경고"}, {"title": "러브, 어게인"}],
            },
        ]
        message = "첫 번째는 말기암 이야기잖아. 슬프거나 무거운 건 빼고, 살짝 쫄깃하면서 둘이 재밌게 볼 두 편으로 다시 줘."

        self.assertTrue(is_movie_recommendation_followup(message, history))
        context = build_recommendation_context(message, history)
        self.assertTrue(context.is_followup)
        self.assertIn("공포", context.excluded_genres)
        self.assertIn("스포일러 경고", context.excluded_titles)
        self.assertIn("살짝 쫄깃", context.search_message)

    def test_parent_cowatching_avoids_intense_genres(self):
        context = build_recommendation_context(
            "부모님이랑 같이 볼 건데 민망한 장면 없고 너무 잔인하지 않은 한국 영화 두 편만 골라줘.",
            [],
        )
        self.assertEqual(set(context.excluded_genres), {"공포", "전쟁", "범죄", "스릴러"})

    def test_violence_averse_group_excludes_horror_and_war(self):
        context = build_recommendation_context(
            "친구들은 액션과 코미디를 좋아하지만 한 명은 잔인한 걸 못 봐. 모두 볼 영화 골라줘.",
            [],
        )
        self.assertEqual(set(context.excluded_genres), {"공포", "전쟁"})

    def test_group_missing_preference_followup_preserves_safety_and_excludes_old_cards(self):
        history = [
            {
                "role": "user",
                "content": "친구 넷이서 한 명은 액션, 한 명은 코미디, 나는 추리 좋아하고 한 명은 잔인한 걸 못 봐. 넷 다 볼 두 편 골라줘.",
            },
            {
                "role": "assistant",
                "content": "추천 결과",
                "recommended_movies": [{"title": "디스 민즈 워"}, {"title": "백 인 액션"}, {"title": "스트레치"}],
            },
        ]
        message = "내가 말한 추리는 하나도 없잖아. 세 편 다 말고 추리 요소가 실제로 있는 두 편 다시 골라줘."
        context = build_recommendation_context(message, history)
        self.assertTrue(context.is_followup)
        self.assertEqual(set(context.excluded_titles), {"디스 민즈 워", "백 인 액션", "스트레치"})
        self.assertEqual(set(context.excluded_genres), {"공포", "전쟁"})


if __name__ == "__main__":
    unittest.main()
