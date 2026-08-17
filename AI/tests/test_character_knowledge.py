import json
import tempfile
import unittest
from pathlib import Path

from rag.character_knowledge import load_verified_facts, lore_fact_text, verified_fact_reply


class CharacterKnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[1]
        self.path = self.root / "data" / "character_facts_verified_v1.json"

    def test_verified_fact_file_is_valid_for_current_profiles(self):
        profiles = json.loads(
            (self.root / "character_profiles_ALL_50.json").read_text(encoding="utf-8")
        )
        payload, facts = load_verified_facts(self.path, set(profiles["characters"]))
        self.assertEqual(payload["version"], "1.2")
        self.assertEqual(len(facts), 5)
        self.assertEqual(facts[0]["fact_id"], "woody-boot-andy-name")

    def test_lore_text_contains_retrieval_aliases_and_answer(self):
        _, facts = load_verified_facts(
            self.path, {"우디", "스티브 로저스", "토르", "토니 스타크", "골룸"}
        )
        text = lore_fact_text(facts[0])
        self.assertIn("부츠 바닥", text)
        self.assertIn("앤디야", text)
        self.assertIn("user_confirmed_on_screen_detail", text)

    def test_unknown_character_is_rejected(self):
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "facts.json"
            target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "unknown fact character"):
                load_verified_facts(target, {"마석도"})

    def test_verified_fact_reply_requires_all_match_groups(self):
        _, facts = load_verified_facts(
            self.path, {"우디", "스티브 로저스", "토르", "토니 스타크", "골룸"}
        )
        self.assertEqual(
            verified_fact_reply(facts, "스티브 로저스", "내 방패는 무슨 물질로 만들어졌지?"),
            "비브라늄과 강철의 합금으로 만들어졌습니다.",
        )
        self.assertEqual(
            verified_fact_reply(facts, "토르", "내 망치 이름이 뭐지?"),
            "내 망치의 이름은 묠니르다.",
        )
        self.assertEqual(
            verified_fact_reply(facts, "토니 스타크", "가슴에 있는 장치를 뭐라고 불러?"),
            "아크 리액터라고 불러. 아이언맨 기술의 핵심 에너지원이지.",
        )
        self.assertEqual(
            verified_fact_reply(facts, "골룸", "내가 보물이라고 부르는 건 뭐야?"),
            "내 보물은 절대반지야. 내가 오랫동안 집착해 온 반지지.",
        )
        self.assertIsNone(verified_fact_reply(facts, "토르", "망치가 무거워?"))


if __name__ == "__main__":
    unittest.main()
