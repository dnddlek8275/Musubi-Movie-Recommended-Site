import copy
import unittest

from eval.finalize_manual_review import finalize


def result() -> dict:
    return {
        "thresholds": {"manual_average_min": 4.0, "manual_dimension_min": 3.5},
        "manual_dimensions": ["relevance", "naturalness"],
        "summary": {
            "automatic_gate_passed": True,
            "gates": {
                "hard_check_pass_rate": True,
                "critical_failure_count": True,
                "manual_review_complete": False,
            },
        },
        "results": [
            {
                "id": "case-1",
                "manual_scores": {"relevance": 4, "naturalness": 5},
                "manual_notes": "응답 원문 검토 완료",
            },
            {
                "id": "case-2",
                "manual_scores": {"relevance": 4, "naturalness": 4},
                "manual_notes": "응답 원문 검토 완료",
            },
        ],
    }


class FinalizeManualReviewTests(unittest.TestCase):
    def test_complete_passing_review_opens_release_gate(self):
        finalized = finalize(result())
        self.assertTrue(finalized["summary"]["release_gate_passed"])
        self.assertEqual(finalized["summary"]["manual_review"]["average"], 4.25)
        self.assertEqual(
            finalized["summary"]["manual_review"]["dimension_averages"],
            {"relevance": 4.0, "naturalness": 4.5},
        )

    def test_missing_case_score_is_rejected(self):
        payload = result()
        payload["results"][1]["manual_scores"] = None
        with self.assertRaisesRegex(ValueError, "manual_scores missing: case-2"):
            finalize(payload)

    def test_out_of_range_score_is_rejected(self):
        payload = result()
        payload["results"][0]["manual_scores"]["relevance"] = 6
        with self.assertRaisesRegex(ValueError, "outside 1..5"):
            finalize(payload)

    def test_manual_failure_keeps_release_gate_closed(self):
        payload = copy.deepcopy(result())
        payload["results"][0]["manual_scores"] = {"relevance": 2, "naturalness": 2}
        finalized = finalize(payload)
        self.assertFalse(finalized["summary"]["release_gate_passed"])

    def test_automatic_failure_cannot_be_overridden(self):
        payload = result()
        payload["summary"]["automatic_gate_passed"] = False
        finalized = finalize(payload)
        self.assertFalse(finalized["summary"]["release_gate_passed"])


if __name__ == "__main__":
    unittest.main()
