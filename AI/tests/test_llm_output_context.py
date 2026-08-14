import unittest
from pathlib import Path

from cineverse_prompt import clean_and_truncate


class LlmOutputContextTests(unittest.TestCase):
    def test_legacy_end_of_turn_is_not_an_api_stop_sequence(self):
        source = (Path(__file__).parents[1] / "llm" / "client.py").read_text(encoding="utf-8")
        stop_line = next(line for line in source.splitlines() if '"stop":' in line)
        self.assertNotIn("<end_of_turn>", stop_line)
        self.assertNotIn("<end_of_/turn>", stop_line)

    def test_extracts_answer_after_internal_rewritten_turn(self):
        raw = (
            "<|channel>thought\n"
            "<start_of_turn>user\n"
            "내가 좋아한다고 말한 영화가 뭐였지?<end_of_turn>\n"
            "<start_of_turn>model\n"
            "인터스텔라야. 우주와 시간의 경계를 넘나드는 영화지."
            "<end_of_turn>"
        )
        self.assertEqual(
            clean_and_truncate(raw, "무무"),
            "인터스텔라야. 우주와 시간의 경계를 넘나드는 영화지.",
        )


if __name__ == "__main__":
    unittest.main()
