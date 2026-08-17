import json
import tempfile
import unittest
from pathlib import Path

from eval.select_checkpoint import score_candidate, select


def result(manual_score: float, automatic: bool = True) -> dict:
    dimensions = ["relevance", "naturalness"]
    return {
        "thresholds": {"manual_average_min": 4.0, "manual_dimension_min": 3.5},
        "manual_dimensions": dimensions,
        "summary": {
            "automatic_gate_passed": automatic,
            "hard_check_pass_rate": 1.0,
            "critical_failure_count": 0,
            "exact_duplicate_rate": 0.0,
        },
        "results": [{"manual_scores": {name: manual_score for name in dimensions}}],
    }


class SelectCheckpointTests(unittest.TestCase):
    def test_preserves_zero_duplicate_rate(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "candidate.json"
            payload = result(manual_score=4.5)
            payload["summary"]["exact_duplicate_rate"] = 0.0
            path.write_text(json.dumps(payload), encoding="utf-8")

            candidate = score_candidate(path)

            self.assertEqual(candidate["exact_duplicate_rate"], 0.0)

    def test_selects_highest_eligible_manual_score(self):
        with tempfile.TemporaryDirectory() as directory:
            low = Path(directory) / "checkpoint-200.json"
            high = Path(directory) / "checkpoint-400.json"
            low.write_text(json.dumps(result(4.1)), encoding="utf-8")
            high.write_text(json.dumps(result(4.5)), encoding="utf-8")
            decision = select([low, high])
            self.assertEqual(decision["selected"]["checkpoint"], "checkpoint-400")

    def test_never_selects_without_manual_review(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "checkpoint-200.json"
            value = result(4.5)
            value["results"][0]["manual_scores"] = None
            path.write_text(json.dumps(value), encoding="utf-8")
            self.assertIsNone(select([path])["selected"])


if __name__ == "__main__":
    unittest.main()
