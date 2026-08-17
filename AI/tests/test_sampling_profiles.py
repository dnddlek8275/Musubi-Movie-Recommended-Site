import unittest

from llm.sampling import DEFAULT_PARAMS, SAMPLING_PROFILES, sampling_params


class SamplingProfileTests(unittest.TestCase):
    def test_profiles_cover_service_tasks(self):
        self.assertEqual(
            set(SAMPLING_PROFILES),
            {"character_chat", "grounded_recommendation", "character_recommendation", "structured"},
        )

    def test_structured_profile_is_deterministic(self):
        params = sampling_params("structured")
        self.assertEqual(params["temperature"], 0.0)
        self.assertEqual(params["top_k"], 1)

    def test_call_override_wins_without_mutating_defaults(self):
        params = sampling_params("character_chat", temperature=0.2)
        self.assertEqual(params["temperature"], 0.2)
        self.assertEqual(DEFAULT_PARAMS["temperature"], 0.75)

    def test_unknown_profile_fails_closed(self):
        with self.assertRaises(ValueError):
            sampling_params("unknown")


if __name__ == "__main__":
    unittest.main()
