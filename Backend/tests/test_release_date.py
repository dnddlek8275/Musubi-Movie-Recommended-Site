import unittest
from datetime import date, timedelta

from app.models.movies import Movie
from app.services.movies.recommendation_service import calculate_release_date_recency_score


class ReleaseDateRecencyTests(unittest.TestCase):
    def setUp(self):
        self.today = date(2026, 8, 4)

    def score(self, release_date):
        return calculate_release_date_recency_score(
            Movie(title="test", release_date=release_date),
            today=self.today,
        )

    def test_release_today_gets_full_recency_bonus(self):
        self.assertEqual(self.score(self.today), 0.5)

    def test_release_older_than_one_year_gets_no_bonus(self):
        self.assertEqual(self.score(self.today - timedelta(days=365)), 0.0)

    def test_future_release_gets_no_bonus(self):
        self.assertEqual(self.score(self.today + timedelta(days=1)), 0.0)

    def test_unknown_release_date_gets_no_bonus(self):
        self.assertEqual(self.score(None), 0.0)


if __name__ == "__main__":
    unittest.main()
