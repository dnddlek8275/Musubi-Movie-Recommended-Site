import unittest
from types import SimpleNamespace

from pydantic import ValidationError

from app.api.movies import rating_identity_matches
from app.schemas.movies import MovieIdentityRequest, MovieRatingRequest


class MovieRatingIdentityTests(unittest.TestCase):
    def setUp(self):
        self.movie = SimpleNamespace(
            id=196,
            tmdb_id=969681,
            title="스파이더맨: 브랜드 뉴 데이",
        )

    def request(self, **overrides):
        values = {
            "score": 5,
            "comment": "재밌어요",
            "expected_movie_id": 196,
            "expected_tmdb_id": 969681,
            "expected_title": "스파이더맨: 브랜드 뉴 데이",
        }
        values.update(overrides)
        return MovieRatingRequest(**values)

    def test_matching_internal_and_tmdb_ids_are_accepted(self):
        self.assertTrue(rating_identity_matches(self.movie, 196, self.request()))

    def test_wrong_route_movie_id_is_rejected(self):
        self.assertFalse(rating_identity_matches(self.movie, 296, self.request()))

    def test_wrong_tmdb_id_is_rejected(self):
        self.assertFalse(
            rating_identity_matches(
                self.movie,
                196,
                self.request(expected_tmdb_id=634649),
            )
        )

    def test_wrong_displayed_title_is_rejected(self):
        self.assertFalse(
            rating_identity_matches(
                self.movie,
                196,
                self.request(expected_title="스파이더맨: 노 웨이 홈"),
            )
        )

    def test_request_without_identity_fields_is_rejected(self):
        with self.assertRaises(ValidationError):
            MovieRatingRequest(score=4, comment="검증 필드가 없는 요청")

    def test_half_star_rating_is_accepted(self):
        self.assertEqual(self.request(score=3.5).score, 3.5)

    def test_rating_must_use_half_star_steps(self):
        with self.assertRaises(ValidationError):
            self.request(score=3.7)

    def test_rating_cannot_be_zero(self):
        with self.assertRaises(ValidationError):
            self.request(score=0)

    def test_delete_identity_uses_the_same_validation(self):
        request = MovieIdentityRequest(
            expected_movie_id=196,
            expected_tmdb_id=634649,
            expected_title="스파이더맨: 브랜드 뉴 데이",
        )
        self.assertFalse(rating_identity_matches(self.movie, 196, request))


if __name__ == "__main__":
    unittest.main()
