import unittest
from pathlib import Path


class CharacterCollectionDefaultTests(unittest.TestCase):
    def test_active_character_collection_is_v5(self):
        root = Path(__file__).resolve().parents[1]
        for relative in ("rag/character_retriever.py", "rag/retriever.py"):
            with self.subTest(relative=relative):
                source = (root / relative).read_text(encoding="utf-8")
                self.assertIn('"characters_verified_v5"', source)


if __name__ == "__main__":
    unittest.main()
