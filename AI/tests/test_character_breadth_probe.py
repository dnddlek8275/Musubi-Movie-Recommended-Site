import unittest
from pathlib import Path

from eval.run_character_breadth_probe import SCENARIOS, build_cases, load_character_names


class CharacterBreadthProbeTests(unittest.TestCase):
    def test_every_profile_receives_exactly_one_balanced_case(self):
        profile_path = Path(__file__).resolve().parents[1] / "character_profiles_ALL_50.json"
        names = load_character_names(profile_path)
        cases = build_cases(names)
        self.assertEqual(len(names), 50)
        self.assertEqual(len(cases), 50)
        self.assertEqual(
            {case["payload"]["character"] for case in cases},
            set(names),
        )
        counts = {
            scenario["name"]: sum(case["category"] == scenario["name"] for case in cases)
            for scenario in SCENARIOS
        }
        self.assertEqual(set(counts.values()), {10})

    def test_relation_target_is_never_the_same_character(self):
        cases = build_cases(["엘사", "마석도", "토니 스타크"])
        relation = next(case for case in cases if case["category"] == "unknown_relation")
        self.assertNotIn(
            relation["payload"]["character"] + "와",
            relation["payload"]["message"],
        )


if __name__ == "__main__":
    unittest.main()
