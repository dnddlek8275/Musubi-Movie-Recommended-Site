import unittest

from train.prepare_splits import normalize, prepare


def record(prompt: str, answer: str = "충분히 긴 테스트 답변입니다.") -> dict:
    return {
        "character": "테스트",
        "conversations": [
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": answer},
        ],
    }


class PrepareSplitsTests(unittest.TestCase):
    def test_normalization_handles_spacing_and_punctuation(self):
        self.assertEqual(normalize("영화 추천해 줘!"), normalize("영화추천해줘"))

    def test_near_duplicates_never_cross_splits(self):
        records = [
            record("오늘 볼 영화 추천해줘"),
            record("오늘 볼 영화 추천해 줘!"),
            record("아이와 볼 애니메이션 알려줘"),
            record("회사에서 실수해서 속상해"),
            record("긴장감 있는 액션 영화가 좋아"),
            record("친구와 다퉜는데 뭐라고 할까"),
        ]
        splits, report = prepare(records, seed=42, dev_ratio=0.2, test_ratio=0.2, threshold=0.88)
        locations = {
            normalize("오늘 볼 영화 추천해줘"): [
                name
                for name, values in splits.items()
                if any(normalize(item["conversations"][0]["content"]) == normalize("오늘 볼 영화 추천해줘") for item in values)
            ]
        }
        self.assertEqual(len(locations[normalize("오늘 볼 영화 추천해줘")]), 1)
        self.assertEqual(report["exact_prompt_overlap"], {"train_dev": 0, "train_test": 0, "dev_test": 0})

    def test_invalid_empty_records_are_removed(self):
        records = [record("정상 질문"), {"input": "", "output": "답변"}]
        _, report = prepare(records, seed=42, dev_ratio=0.1, test_ratio=0.1, threshold=0.88)
        self.assertEqual(report["invalid_records_removed"], 1)


if __name__ == "__main__":
    unittest.main()
