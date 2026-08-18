import unittest

from unittest.mock import patch

from eval.run_conversation_quality_probe_v2 import normalized_answer, probe_single


class ConversationQualityProbeTests(unittest.TestCase):
    def test_normalized_answer_ignores_spacing_and_punctuation(self):
        self.assertEqual(
            normalized_answer("프로도는 길잡이였지."),
            normalized_answer("프로도는  길잡이였지!"),
        )

    @patch("eval.run_conversation_quality_probe_v2.post")
    def test_dialogue_selection_runs_only_requested_case(self, mocked_post):
        mocked_post.return_value = {
            "character": "골룸",
            "answer": "검증된 답변",
            "rag_used": True,
        }

        rows = probe_single("http://example.invalid", {"gollum_paraphrase"})

        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row["dialogue"] == "gollum_paraphrase" for row in rows))


if __name__ == "__main__":
    unittest.main()
