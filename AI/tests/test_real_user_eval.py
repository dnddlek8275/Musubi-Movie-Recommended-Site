import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "run_real_user_eval", ROOT / "eval" / "run_real_user_eval.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class RealUserEvalTests(unittest.TestCase):
    def test_group_answers_are_combined_for_content_checks(self):
        response = {
            "rounds": [
                {"responses": [{"character": "A", "answer": "첫 답변"}]},
                {"responses": [{"character": "B", "answer": "두 번째 답변"}]},
            ]
        }
        self.assertEqual(MODULE.answer_text(response), "첫 답변\n두 번째 답변")

    def test_internal_channel_label_is_rejected(self):
        case = {"checks": {}}
        self.assertIn(
            "internal_token",
            MODULE.evaluate_response(case, {"answer": "thought\n추천 답변입니다.", "movies": []}),
        )

    def test_pair_group_near_duplicates_fail_similarity_gate(self):
        suite = {
            "thresholds": {
                "hard_check_pass_rate": 0.95,
                "critical_failure_count": 0,
                "exact_duplicate_rate_max": 0.05,
                "pair_similarity_max": 0.75,
            }
        }
        shared = "한 시간이나 기다렸는데 기분 나빴어. 다음부터 늦으면 미리 연락해 줘."
        results = [
            {"id": "a", "category": "voice", "pair_group": "same", "answer": shared + " 이렇게 말해.", "failures": []},
            {"id": "b", "category": "voice", "pair_group": "same", "answer": shared + "라고 말해 보세요.", "failures": []},
        ]
        summary = MODULE.summarize(suite, results)
        self.assertGreater(summary["max_pair_similarity"], 0.75)
        self.assertFalse(summary["gates"]["pair_similarity"])

    def test_frozen_suite_schema_is_valid(self):
        suite = json.loads((ROOT / "eval" / "real_user_cases_v1.json").read_text(encoding="utf-8"))
        MODULE.validate_suite(suite)
        self.assertGreaterEqual(len(suite["cases"]), 20)

    def test_recommendation_constraints_detect_violations(self):
        case = {
            "checks": {
                "min_movies": 1,
                "blocked_genres": ["공포"],
                "year_from": 2020,
                "min_rating": 6.0,
            }
        }
        response = {
            "answer": "추천입니다.",
            "movies": [{"title": "실패작", "genres": "공포", "year": 2019, "vote_average": 5.0}],
        }
        failures = MODULE.evaluate_response(case, response)
        self.assertTrue(any(value.startswith("blocked_genre") for value in failures))
        self.assertTrue(any(value.startswith("year_before_minimum") for value in failures))
        self.assertTrue(any(value.startswith("rating_below_minimum") for value in failures))

    def test_maximum_movie_count_is_enforced(self):
        case = {"checks": {"max_movies": 1}}
        response = {"answer": "추천입니다.", "movies": [{"title": "A"}, {"title": "B"}]}
        self.assertIn(
            "too_many_movies:expected<=1:actual=2",
            MODULE.evaluate_response(case, response),
        )

    def test_minimum_answer_length_is_enforced(self):
        case = {"checks": {"min_chars": 10}}
        response = {"answer": "짧아", "movies": []}
        self.assertIn("answer_too_short:2", MODULE.evaluate_response(case, response))

    def test_all_genres_language_year_ceiling_and_blocked_title_are_enforced(self):
        case = {
            "checks": {
                "required_genres_all": ["음악", "코미디"],
                "language": "ja",
                "year_to": 2010,
                "blocked_titles": ["제외작"],
            }
        }
        response = {
            "answer": "추천입니다.",
            "movies": [{
                "title": "제외작",
                "genres": "코미디",
                "language": "ko",
                "year": 2020,
            }],
        }
        failures = MODULE.evaluate_response(case, response)
        self.assertIn("blocked_title:제외작", failures)
        self.assertIn("missing_required_genres:제외작:음악", failures)
        self.assertIn("year_after_maximum:제외작:2020", failures)
        self.assertIn("unexpected_language:제외작:ko", failures)

    def test_quoted_title_alias_inside_returned_title_is_grounded(self):
        case = {"checks": {"answer_titles_must_be_returned": True}}
        response = {
            "answer": "‘핀치’를 추천해요.",
            "movies": [{"title": "'핀치' - Finch", "genres": "SF"}],
        }
        self.assertEqual(MODULE.evaluate_response(case, response), [])

    def test_grounded_title_check_rejects_unreturned_quoted_title(self):
        case = {"checks": {"answer_titles_must_be_returned": True}}
        response = {
            "answer": "『없는 영화』를 추천해요.",
            "movies": [{"title": "있는 영화", "genres": "드라마"}],
        }
        self.assertIn(
            "hallucinated_answer_title:없는 영화",
            MODULE.evaluate_response(case, response),
        )

    def test_summary_keeps_manual_gate_closed(self):
        suite = {
            "thresholds": {
                "hard_check_pass_rate": 0.95,
                "critical_failure_count": 0,
                "exact_duplicate_rate_max": 0.05,
            }
        }
        results = [{"category": "chat", "answer": "서로 다른 답", "failures": []}]
        summary = MODULE.summarize(suite, results)
        self.assertTrue(summary["automatic_gate_passed"])
        self.assertFalse(summary["release_gate_passed"])


if __name__ == "__main__":
    unittest.main()
