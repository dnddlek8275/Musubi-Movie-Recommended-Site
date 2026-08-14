import json
import unittest

from pipeline.user_context import build_user_context_prompt, preference_search_terms


class UserContextTests(unittest.TestCase):
    def test_structured_preferences_are_preserved_in_prompt(self):
        value = json.dumps({
            "personal_context": "잔인한 영화는 피하고 싶음",
            "preferences": {"genre": ["SF", "액션"], "keyword": ["인공지능"]},
        }, ensure_ascii=False)
        prompt = build_user_context_prompt(value)
        self.assertIn('"preferences"', prompt)
        self.assertIn("인공지능", prompt)

    def test_preference_terms_are_bounded_and_ordered(self):
        value = json.dumps({
            "preferences": {
                "genre": ["SF", "액션", "드라마", "공포"],
                "keyword": ["인공지능", "우정"],
                "actor": ["배우 A"],
            },
        }, ensure_ascii=False)
        self.assertEqual(
            preference_search_terms(value),
            "SF 액션 드라마 인공지능 우정 배우 A",
        )

    def test_plain_freeform_context_remains_supported(self):
        prompt = build_user_context_prompt("따뜻한 영화를 좋아함")
        self.assertIn("user_provided_context", prompt)


if __name__ == "__main__":
    unittest.main()
