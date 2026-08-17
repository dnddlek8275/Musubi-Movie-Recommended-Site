import unittest

from train.tokenization import tokenize_conversation


class TinyTokenizer:
    eos_token = "<eos>"

    def __call__(self, text, **kwargs):
        return {"input_ids": [ord(char) for char in text]}


class TrainingTokenizationTests(unittest.TestCase):
    def test_masks_user_and_supervises_assistant(self):
        tokenizer = TinyTokenizer()
        record = {
            "conversations": [
                {"role": "user", "content": "질문"},
                {"role": "assistant", "content": "답변"},
            ]
        }
        encoded = tokenize_conversation(record, tokenizer, 1000)
        user_length = len("<start_of_turn>user\n질문<end_of_turn>\n")
        self.assertTrue(all(label == -100 for label in encoded["labels"][:user_length]))
        self.assertTrue(any(label != -100 for label in encoded["labels"][user_length:]))
        self.assertEqual(len(encoded["input_ids"]), len(encoded["labels"]))

    def test_rejects_unknown_roles(self):
        with self.assertRaises(ValueError):
            tokenize_conversation(
                {"conversations": [{"role": "system", "content": "지시"}]},
                TinyTokenizer(),
                100,
            )

    def test_supports_raw_input_output_records(self):
        encoded = tokenize_conversation(
            {"input": "질문", "output": "실제 답변"},
            TinyTokenizer(),
            1000,
        )
        supervised_text = "".join(
            chr(token)
            for token, label in zip(encoded["input_ids"], encoded["labels"])
            if label != -100
        )
        self.assertIn("실제 답변", supervised_text)

    def test_rejects_record_without_conversation_or_pair(self):
        with self.assertRaises(ValueError):
            tokenize_conversation({}, TinyTokenizer(), 100)

    def test_truncation_keeps_lengths_aligned(self):
        encoded = tokenize_conversation(
            {"conversations": [{"role": "assistant", "content": "아주 긴 답변"}]},
            TinyTokenizer(),
            12,
        )
        self.assertEqual(len(encoded["input_ids"]), 12)
        self.assertEqual(len(encoded["attention_mask"]), 12)


if __name__ == "__main__":
    unittest.main()
