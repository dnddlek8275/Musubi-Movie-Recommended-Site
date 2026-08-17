import unittest

from train.filter_multiturn import audit_record
from train.prepare_splits import normalize


class FilterMultiturnTests(unittest.TestCase):
    def test_rejects_unrelated_standalone_second_question(self):
        sample = {
            "conversations": [
                {"role": "user", "content": "회사에서 실수했어."},
                {"role": "assistant", "content": "무슨 실수였는지 말해 봐."},
                {"role": "user", "content": "데이트 영화 추천해줘."},
                {"role": "assistant", "content": "밝은 로맨스는 어때?"},
            ]
        }
        failures = audit_record(sample, {normalize("데이트 영화 추천해줘.")})
        self.assertTrue(any(value.startswith("context_independence") for value in failures))
        self.assertTrue(any(value.startswith("standalone_prompt_reused") for value in failures))

    def test_accepts_explicit_contextual_followup(self):
        sample = {
            "conversations": [
                {"role": "user", "content": "친구가 내 비밀을 말했어."},
                {"role": "assistant", "content": "그건 신뢰가 깨진 일이라 화날 만해."},
                {"role": "user", "content": "그럼 그 친구에게 뭐라고 답할까?"},
                {"role": "assistant", "content": "내 비밀을 말해서 신뢰가 깨졌다고 전해."},
            ]
        }
        self.assertEqual(audit_record(sample, set()), [])


if __name__ == "__main__":
    unittest.main()
