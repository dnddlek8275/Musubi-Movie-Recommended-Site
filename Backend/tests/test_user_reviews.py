import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

from app.api.users import get_my_reviews


class FakeReviewQuery:
    def __init__(self, rows):
        self.rows = rows

    def join(self, *_args):
        return self

    def filter(self, *_args):
        return self

    def order_by(self, *_args):
        return self

    def all(self):
        return self.rows


class FakeSession:
    def __init__(self, rows):
        self.rows = rows

    def query(self, *_models):
        return FakeReviewQuery(self.rows)


class UserReviewTests(unittest.TestCase):
    def test_my_reviews_include_movie_identity_and_detail_link_data(self):
        updated_at = datetime(2026, 8, 11, tzinfo=timezone.utc)
        rating = SimpleNamespace(
            id=7,
            score=4,
            comment="다시 보고 싶은 영화",
            is_spoiler=False,
            created_at=updated_at,
            updated_at=updated_at,
        )
        movie = SimpleNamespace(
            id=196,
            title="스파이더맨: 브랜드 뉴 데이",
            genres=["액션"],
            keywords=[],
            cast=[],
            poster_path="/poster.jpg",
            vote_average=8.2,
            year=2026,
            release_date=None,
        )

        response = get_my_reviews(
            current_user={"user_id": 3},
            db=FakeSession([(rating, movie)]),
        )

        self.assertEqual(response["state"], "success")
        self.assertEqual(len(response["data"]), 1)
        self.assertEqual(response["data"][0]["comment"], "다시 보고 싶은 영화")
        self.assertEqual(response["data"][0]["movie"]["movie_id"], 196)

    def test_rating_without_comment_is_still_included(self):
        updated_at = datetime(2026, 8, 11, tzinfo=timezone.utc)
        rating = SimpleNamespace(
            id=8,
            score=5,
            comment=None,
            is_spoiler=False,
            created_at=updated_at,
            updated_at=updated_at,
        )
        movie = SimpleNamespace(
            id=197,
            title="별점만 남긴 영화",
            genres=["드라마"],
            keywords=[],
            cast=[],
            poster_path=None,
            vote_average=7.0,
            year=2026,
            release_date=None,
        )

        response = get_my_reviews(
            current_user={"user_id": 3},
            db=FakeSession([(rating, movie)]),
        )

        self.assertEqual(len(response["data"]), 1)
        self.assertIsNone(response["data"][0]["comment"])


if __name__ == "__main__":
    unittest.main()
