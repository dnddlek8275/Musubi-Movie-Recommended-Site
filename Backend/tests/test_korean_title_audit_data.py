import csv
import re
import unittest
from pathlib import Path


TITLE_DATA_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "data"
    / "official_korean_title_changes_20260812.csv"
)


class KoreanTitleAuditDataTests(unittest.TestCase):
    def test_audited_title_changes_are_unique_and_korean(self):
        with TITLE_DATA_PATH.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))

        self.assertEqual(len(rows), 871)
        self.assertEqual(len({int(row["tmdb_id"]) for row in rows}), len(rows))
        for row in rows:
            with self.subTest(tmdb_id=row["tmdb_id"]):
                self.assertNotEqual(row["current_title"], row["localized_title"])
                self.assertRegex(row["localized_title"], re.compile(r"[가-힣]"))

    def test_report_contains_confirmed_movies(self):
        expected = {
            793058: "하이파이브",
            696047: "시민덕희",
            252067: "피끓는 청춘",
            385137: "봉이 김선달",
            644714: "보이스",
            1451344: "남편들",
            1306816: "좀비딸",
            1063814: "필사의 추격",
            359460: "탐정: 더 비기닝",
            599335: "오케이 마담",
            838209: "파묘",
            254781: "플랜맨",
            783110: "밀수",
            255709: "소원",
        }
        with TITLE_DATA_PATH.open(encoding="utf-8-sig", newline="") as handle:
            actual = {
                int(row["tmdb_id"]): row["localized_title"]
                for row in csv.DictReader(handle)
            }
        for tmdb_id, title in expected.items():
            self.assertEqual(actual.get(tmdb_id), title)


if __name__ == "__main__":
    unittest.main()
