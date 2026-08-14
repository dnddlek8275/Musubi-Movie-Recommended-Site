import unittest

from app.services.admin.tmdb_register_service import (
    extract_certification,
    extract_display_title,
    require_non_explicit_metadata,
    require_tmdb_adult_false,
)


class TmdbMetadataTests(unittest.TestCase):
    def test_only_explicit_adult_false_is_allowed(self):
        require_tmdb_adult_false({"adult": False})
        for payload in ({"adult": True}, {}, None):
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    require_tmdb_adult_false(payload)

    def test_explicit_keyword_is_rejected_even_when_adult_is_false(self):
        with self.assertRaises(ValueError):
            require_non_explicit_metadata(["softcore"], None, None)

    def test_verified_youth_rating_protects_keyword_false_positive(self):
        require_non_explicit_metadata(["softcore"], "PG-13", "US")

    def test_regular_keywords_are_allowed(self):
        require_non_explicit_metadata(["superhero", "friendship"], "R", "US")

    def test_adult_industry_documentary_is_rejected(self):
        with self.assertRaises(ValueError):
            require_non_explicit_metadata(
                ["porn industry"], None, None, genres=["다큐멘터리"]
            )

    def test_sexploitation_is_rejected(self):
        with self.assertRaises(ValueError):
            require_non_explicit_metadata(["sexploitation"], None, None)

    def test_explicit_korean_overview_is_rejected_without_rating(self):
        with self.assertRaises(ValueError):
            require_non_explicit_metadata(
                [], None, None, "유산을 받는 조건으로 우희의 몸을 탐닉한다."
            )

    def test_explicit_adult_industry_title_is_rejected(self):
        with self.assertRaises(ValueError):
            require_non_explicit_metadata(
                [], "R", "US", None,
                "X-Rated 2: The Greatest Adult Stars of All-Time",
            )

    def test_korean_theatrical_certification_is_preferred(self):
        payload = {
            "results": [
                {"iso_3166_1": "US", "release_dates": [{"type": 3, "certification": "PG-13"}]},
                {
                    "iso_3166_1": "KR",
                    "release_dates": [
                        {"type": 4, "certification": "12"},
                        {"type": 3, "certification": "15"},
                    ],
                },
            ]
        }
        self.assertEqual(extract_certification(payload), ("15", "KR"))

    def test_us_certification_is_used_when_korean_value_is_missing(self):
        payload = {
            "results": [
                {"iso_3166_1": "KR", "release_dates": [{"type": 3, "certification": ""}]},
                {"iso_3166_1": "US", "release_dates": [{"type": 3, "certification": "R"}]},
            ]
        }
        self.assertEqual(extract_certification(payload), ("R", "US"))

    def test_korean_title_is_preferred_over_english(self):
        payload = {
            "original_language": "en",
            "original_title": "Spider-Man: No Way Home",
            "translations": {"translations": [
                {"iso_639_1": "en", "data": {"title": "Spider-Man: No Way Home"}},
                {"iso_639_1": "ko", "data": {"title": "스파이더맨: 노 웨이 홈"}},
            ]},
        }
        self.assertEqual(extract_display_title(payload), "스파이더맨: 노 웨이 홈")

    def test_english_title_is_fallback_when_korean_is_missing(self):
        payload = {
            "original_language": "ja",
            "original_title": "原題",
            "title": "原題",
            "translations": {"translations": [
                {"iso_639_1": "en", "data": {"title": "English title"}},
            ]},
        }
        self.assertEqual(extract_display_title(payload), "English title")

    def test_korean_detail_title_is_used_before_english_translation(self):
        payload = {
            "id": 793058,
            "original_language": "ko",
            "original_title": "하이파이브",
            "title": "하이파이브",
            "translations": {"translations": [
                {"iso_639_1": "ko", "data": {"title": ""}},
                {"iso_639_1": "en", "data": {"title": "Hi-Five"}},
            ]},
        }
        self.assertEqual(extract_display_title(payload), "하이파이브")



if __name__ == "__main__":
    unittest.main()
