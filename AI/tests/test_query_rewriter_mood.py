import sys
import types
import unittest


llm_client_stub = types.ModuleType("llm.client")


def unexpected_llm_call(*args, **kwargs):
    raise AssertionError("explicit mood query must not call the LLM rewriter")


llm_client_stub.chat_json = unexpected_llm_call
llm_client_stub.chat = lambda *args, **kwargs: ""
sys.modules.setdefault("llm.client", llm_client_stub)

from pipeline.query_rewriter import rewrite


class QueryRewriterMoodTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
