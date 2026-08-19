import sys
import types
import unittest
from datetime import date
from datetime import date


llm_client_stub = types.ModuleType("llm.client")


def unexpected_llm_call(*args, **kwargs):
    raise AssertionError("explicit mood query must not call the LLM rewriter")


llm_client_stub.chat_json = unexpected_llm_call
llm_client_stub.chat = lambda *args, **kwargs: ""
sys.modules.setdefault("llm.client", llm_client_stub)

from pipeline.query_rewriter import rewrite


class QueryRewriterMoodTests(unittest.TestCase):

    def test_runtime_upper_bound_is_extracted_without_llm(self):
        self.assertEqual(rewrite("두 시간 안 넘는 영화 추천해줘")["runtime_max"], 120)
        self.assertEqual(rewrite("90분 이하 코미디 골라줘")["runtime_max"], 90)
        self.assertEqual(rewrite("1시간 30분 이내 영화")["runtime_max"], 90)

    def test_production_country_and_dialogue_language_are_independent(self):
        result = rewrite("프랑스에서 만든 영화인데 대사는 영어인 작품 추천해줘")
        self.assertEqual(result["production_country"], "FR")
        self.assertEqual(result["language"], "en")

    def test_courage_recovery_request_is_mood_not_literal_title_search(self):
        result = rewrite("그냥 다시 용기 나는 영화 한 편 골라줘")
        self.assertEqual(result["quality_priority"], "mood")

    def test_gentle_suspense_request_is_mood_not_literal_title_search(self):
        result = rewrite("살짝 쫄깃하지만 안 무서운 데이트 영화 두 편 골라줘")
        self.assertEqual(result["quality_priority"], "mood")

    def test_parent_cowatching_request_is_mood(self):
        result = rewrite("부모님이랑 볼 건데 민망한 장면 없고 너무 잔인하지 않은 한국 영화")
        self.assertEqual(result["quality_priority"], "mood")

    def test_group_preferences_are_not_all_hard_genre_constraints(self):
        result = rewrite(
            "친구 넷이서 보는데 한 명은 액션, 한 명은 코미디, 나는 미스터리 좋아해. 넷 다 덜 불만일 영화 골라줘."
        )
        self.assertIsNone(result["genre"])
        self.assertEqual(result["required_genres"], [])
        self.assertEqual(result["quality_priority"], "mood")

    def test_missing_group_preference_repair_makes_named_genre_required(self):
        result = rewrite(
            "친구들은 액션과 코미디를 좋아해. 근데 내가 말한 추리는 하나도 없잖아. 추리 요소가 실제로 있는 걸로 다시 골라줘."
        )
        self.assertEqual(result["genre"], "미스터리")
        self.assertEqual(result["required_genres"], ["미스터리"])

    def test_this_month_already_released_uses_exact_date_window(self):
        result = rewrite("이번 달에 이미 개봉한 영화만 골라줘. 아직 개봉 안 한 건 빼고.")
        today = date.today()
        self.assertEqual(result["release_date_from"], today.replace(day=1).isoformat())
        self.assertEqual(result["release_date_to"], today.isoformat())

    def test_watch_tonight_excludes_future_releases(self):
        result = rewrite("오늘 밤 바로 볼 2025년 이후 한국 미스터리 영화")
        self.assertEqual(result["release_date_to"], date.today().isoformat())

    def test_actor_replacement_uses_new_actor(self):
        result = rewrite("마동석 말고 송강호로 바꿔줘. 액션 조건은 그대로.")
        self.assertEqual(result["actor"], "송강호")

    def test_director_replacement_does_not_swallow_negation_phrase(self):
        result = rewrite("봉준호 말고 박찬욱 감독으로 바꿔줘. 스릴러 조건은 그대로.")
        self.assertEqual(result["director"], "박찬욱")

    def test_korean_audience_threshold_is_extracted(self):
        self.assertEqual(rewrite("관객 500만 명 이상 영화")["audience_min"], 5_000_000)
        self.assertEqual(rewrite("천만 영화 추천해줘")["audience_min"], 10_000_000)
        self.assertEqual(
            rewrite("관객 500만 이상에서 기준만 300만 명으로 낮춰줘")["audience_min"],
            3_000_000,
        )
    def test_light_mood_skips_llm_extraction(self):
        result = rewrite("가볍게 볼 영화 추천해줘")
        self.assertEqual(result["search_query"], "가볍게 볼 영화 추천해줘")
        self.assertIsNone(result["genre"])

    def test_supported_mood_queries_all_skip_llm_extraction(self):
        for message in (
            "감동적인 영화 추천해줘",
            "우울할 때 보기 좋은 영화 추천해줘",
            "데이트할 때 볼 영화 추천해줘",
            "아이와 함께 볼 영화 추천해줘",
            "주말 밤에 볼 유쾌한 영화 세 편 골라줘",
        ):
            with self.subTest(message=message):
                self.assertEqual(rewrite(message)["search_query"], message)

    def test_generic_request_does_not_search_literal_time_words_as_a_title(self):
        result = rewrite("오늘 밤 볼 영화 세 편 추천해줘")
        self.assertEqual(
            result["search_query"],
            "흥행에 성공하고 많은 관객에게 사랑받은 인기 명작 영화",
        )
        self.assertEqual(result["quality_priority"], "generic")

    def test_short_generic_questions_skip_llm_rewrite(self):
        for message in ("오늘 뭐 볼까?", "오늘 뭐 보면 좋을까?"):
            with self.subTest(message=message):
                result = rewrite(message)
                self.assertEqual(
                    result["search_query"],
                    "흥행에 성공하고 많은 관객에게 사랑받은 인기 명작 영화",
                )
                self.assertEqual(result["quality_priority"], "generic")

    def test_mood_recommendation_requests_quality_priority(self):
        result = rewrite("기분이 안 좋을 때 볼 영화 추천해줘")
        self.assertEqual(result["quality_priority"], "mood")

    def test_bedtime_restful_request_skips_llm_and_sets_mood_priority(self):
        message = "잠들기 전에 편안하게 볼 영화 한 편 추천해줘"
        result = rewrite(message)
        self.assertEqual(result["search_query"], message)
        self.assertEqual(result["quality_priority"], "mood")

    def test_music_with_korean_particle_is_an_explicit_genre(self):
        result = rewrite("음악이 좋고 보고 나면 기분 좋아지는 영화가 보고 싶어")
        self.assertEqual(result["genre"], "음악")
        self.assertEqual(result["quality_priority"], "mood")

    def test_discussion_purpose_is_treated_as_explicit_mood(self):
        result = rewrite("보고 나서 같이 얘기할 거리가 많은 SF 영화")
        self.assertEqual(result["quality_priority"], "mood")

    def test_school_age_relative_skips_llm_extraction(self):
        result = rewrite("초등학생 조카랑 같이 볼 영화 골라줘")
        self.assertEqual(result["search_query"], "초등학생 조카랑 같이 볼 영화 골라줘")
        self.assertEqual(result["quality_priority"], "mood")

    def test_avoid_sad_wording_is_explicit_mood(self):
        result = rewrite("로맨스 영화 추천해줘. 너무 슬픈 건 싫어")
        self.assertEqual(result["quality_priority"], "mood")

    def test_bright_romance_wording_is_explicit_mood(self):
        result = rewrite("밝은 로맨스 영화")
        self.assertEqual(result["quality_priority"], "mood")

    def test_adult_animation_wording_is_explicit_mood(self):
        result = rewrite("어른이 봐도 유치하지 않은 애니메이션 영화 추천해줘")
        self.assertEqual(result["genre"], "애니메이션")
        self.assertEqual(result["quality_priority"], "mood")

    def test_multiple_explicit_genres_are_preserved(self):
        result = rewrite("음악 코미디 영화 추천해줘")
        self.assertEqual(result["genre"], "음악")
        self.assertEqual(result["required_genres"], ["음악", "코미디"])

    def test_romantic_wording_maps_to_romance_in_multi_genre_query(self):
        result = rewrite("로맨틱 코미디 영화")
        self.assertEqual(result["required_genres"], ["로맨스", "코미디"])

    def test_korean_particles_do_not_hide_additional_genres(self):
        result = rewrite("한국 로맨스 중 코미디가 섞인 영화")
        self.assertEqual(result["required_genres"], ["로맨스", "코미디"])

    def test_family_is_preserved_as_a_structured_genre(self):
        result = rewrite("가족 애니메이션 영화")
        self.assertEqual(result["required_genres"], ["가족", "애니메이션"])

    def test_common_comedy_typo_is_normalized(self):
        result = rewrite("2020년 이후 한국 코메디 영화")
        self.assertEqual(result["genre"], "코미디")

    def test_both_open_year_bounds_are_preserved(self):
        result = rewrite("2020년 이후이면서 2010년 이전인 영화")
        self.assertEqual(result["year_from"], 2020)
        self.assertEqual(result["year_to"], 2010)

    def test_colloquial_recent_followup_sets_recent_floor_and_latest_sort(self):
        result = rewrite("공포 영화 중 요즘 거 없어?")
        self.assertEqual(result["genre"], "공포")
        self.assertEqual(result["year_from"], date.today().year - 5)
        self.assertTrue(result["sort_latest"])

    def test_cooling_movie_mood_is_quality_prioritized(self):
        result = rewrite("더운 날에 시원한 영화 없나?")
        self.assertEqual(result["quality_priority"], "mood")


if __name__ == "__main__":
    unittest.main()
