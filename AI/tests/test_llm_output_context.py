import unittest
from cineverse_prompt import clean_and_truncate
from llm.sampling import DEFAULT_PARAMS


class LlmOutputContextTests(unittest.TestCase):
    def test_legacy_end_of_turn_is_not_an_api_stop_sequence(self):
        self.assertNotIn("<end_of_turn>", DEFAULT_PARAMS["stop"])
        self.assertNotIn("<end_of_/turn>", DEFAULT_PARAMS["stop"])

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

    def test_removes_bare_leading_thought_label(self):
        self.assertEqual(
            clean_and_truncate("thought 그냥 잠이나 실컷 자고 싶네.", "마석도"),
            "그냥 잠이나 실컷 자고 싶네.",
        )

    def test_keeps_thought_inside_normal_english_sentence(self):
        self.assertEqual(
            clean_and_truncate("That thought still matters.", ""),
            "That thought still matters.",
        )


if __name__ == "__main__":
    unittest.main()
