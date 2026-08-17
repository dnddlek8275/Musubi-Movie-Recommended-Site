import json
import tempfile
import unittest
from pathlib import Path

from eval.compare_model_variants import compare


def write_result(path: Path, version: str, score: float) -> None:
    path.write_text(json.dumps({
        "suite_version": version,
        "thresholds": {"manual_average_min": 4.0, "manual_dimension_min": 3.5},
        "manual_dimensions": ["relevance"],
        "summary": {
            "hard_check_pass_rate": 1.0,
            "critical_failure_count": 0,
            "exact_duplicate_rate": 0.0,
            "automatic_gate_passed": True,
        },
        "results": [{"id": "case-1", "manual_scores": {"relevance": score}}],
    }), encoding="utf-8")


class CompareModelVariantsTests(unittest.TestCase):
    def test_reports_quality_delta_without_latency(self):
        with tempfile.TemporaryDirectory() as directory:
            bf16 = Path(directory) / "bf16.json"
            q4 = Path(directory) / "q4.json"
            write_result(bf16, "1.0", 4.5)
            write_result(q4, "1.0", 4.0)
            report = compare([f"bf16={bf16}", f"q4={q4}"], "bf16")
            self.assertTrue(report["quality_only"])
            self.assertEqual(report["variants"][1]["manual_average_delta"], -0.5)
            self.assertNotIn("seconds", report["variants"][1])

    def test_rejects_mismatched_suite_versions(self):
        with tempfile.TemporaryDirectory() as directory:
            bf16 = Path(directory) / "bf16.json"
            q4 = Path(directory) / "q4.json"
            write_result(bf16, "1.0", 4.5)
            write_result(q4, "2.0", 4.5)
            with self.assertRaises(ValueError):
                compare([f"bf16={bf16}", f"q4={q4}"], "bf16")


if __name__ == "__main__":
    unittest.main()
