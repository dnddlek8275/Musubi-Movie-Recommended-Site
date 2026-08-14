import unittest
from datetime import date
from types import SimpleNamespace

from app.services.movies.box_office_service import (
    build_kobis_match_evidence,
    match_kobis_movie,
    normalize_movie_title,
    parse_kobis_date,
    select_registered_tmdb_match,
)


class BoxOfficeServiceTests(unittest.TestCase):
    def test_normalize_movie_title_ignores_spacing_and_punctuation(self):
        self.assertEqual(
            normalize_movie_title("스파이더맨: 브랜드 뉴 데이"),
            normalize_movie_title("스파이더맨 브랜드뉴데이"),
        )

    def test_match_prefers_exact_release_date(self):
        old = SimpleNamespace(id=1, release_date=date(2000, 1, 1), year=2000)
        current = SimpleNamespace(id=2, release_date=date(2026, 7, 15), year=2026)
        mapping = {normalize_movie_title("호프"): [old, current]}
        matched = match_kobis_movie(mapping, "호프", date(2026, 7, 15))
        self.assertEqual(matched.id, 2)

    def test_match_refuses_ambiguous_same_title(self):
        first = SimpleNamespace(id=1, release_date=None, year=None)
        second = SimpleNamespace(id=2, release_date=None, year=None)
        mapping = {normalize_movie_title("동명 영화"): [first, second]}
        self.assertIsNone(match_kobis_movie(mapping, "동명 영화", None))

    def test_korean_tmdb_title_matches_registered_english_title(self):
        results = [{
            "tmdb_id": 1058424,
            "title": "호프",
            "original_title": "Hope",
            "year": 2026,
            "is_registered": True,
        }]
        self.assertEqual(
            select_registered_tmdb_match(results, "호프", date(2026, 7, 15)),
            1058424,
        )

    def test_tmdb_fallback_rejects_wrong_release_year(self):
        results = [{
            "tmdb_id": 1058424,
            "title": "호프",
            "original_title": "Hope",
            "year": 2025,
            "is_registered": True,
        }]
        self.assertIsNone(
            select_registered_tmdb_match(results, "호프", date(2026, 7, 15))
        )

    def test_high_confidence_match_requires_metadata(self):
        movie = SimpleNamespace(
            title="Hope",
            release_date=date(2026, 7, 15),
            year=2026,
            director="나홍진",
            runtime=156,
            production_countries=["KR"],
        )
        detail = {
            "movieNm": "호프",
            "movieNmEn": "HOPE",
            "prdtYear": "2026",
            "showTm": "156",
            "directors": [{"peopleNm": "나홍진", "peopleNmEn": "NA Hong-jin"}],
            "nations": [{"nationNm": "한국"}],
        }
        evidence = build_kobis_match_evidence(movie, detail, date(2026, 7, 15))
        self.assertTrue(evidence["high_confidence"])
        self.assertEqual(evidence["metadata_matches"], 3)

    def test_production_year_allows_later_korean_release(self):
        movie = SimpleNamespace(
            title="다윗",
            release_date=date(2025, 12, 14),
            year=2025,
            director="Phil Cunningham, Brent Dawes",
            runtime=110,
            production_countries=["US", "ZA"],
        )
        detail = {
            "movieNm": "다윗",
            "movieNmEn": "David",
            "prdtYear": "2025",
            "showTm": "109",
            "directors": [{"peopleNmEn": "Phil Cunningham"}],
            "nations": [{"nationNm": "미국"}],
        }
        evidence = build_kobis_match_evidence(movie, detail, date(2026, 7, 10))
        self.assertTrue(evidence["year_match"])
        self.assertTrue(evidence["high_confidence"])

    def test_same_title_and_year_alone_are_not_enough(self):
        movie = SimpleNamespace(
            title="동명 영화",
            release_date=date(2026, 1, 1),
            year=2026,
            director=None,
            runtime=None,
            production_countries=[],
        )
        detail = {"movieNm": "동명 영화"}
        evidence = build_kobis_match_evidence(movie, detail, date(2026, 8, 1))
        self.assertFalse(evidence["high_confidence"])

    def test_parse_kobis_date(self):
        self.assertEqual(parse_kobis_date("20260715"), date(2026, 7, 15))
        self.assertEqual(parse_kobis_date("2026-07-15"), date(2026, 7, 15))
        self.assertIsNone(parse_kobis_date(""))
        self.assertIsNone(parse_kobis_date("2026/07/15"))


if __name__ == "__main__":
    unittest.main()
