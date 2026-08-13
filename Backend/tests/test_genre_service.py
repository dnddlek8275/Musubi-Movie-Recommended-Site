import unittest

from sqlalchemy.dialects import postgresql

from app.services.movies.genre_service import country_movies, genre_movies


class _ScalarResult:
    def all(self):
        return []


class _FakeSession:
    def __init__(self):
        self.statement = None

    def scalars(self, statement):
        self.statement = statement
        return _ScalarResult()


class GenreServiceTests(unittest.TestCase):
    def test_sf_joins_display_genre_with_normalized_weight_key(self):
        db = _FakeSession()

        genre_movies(db, "SF", sort="latest")

        compiled = db.statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
        sql = str(compiled).lower()
        self.assertIn("lower(btrim(movie_genres.genre)) = 'sf'", sql)
        self.assertIn("movie_genre_weights.genre = lower(btrim(movie_genres.genre))", sql)

    def test_country_movies_filters_korea_and_orders_by_latest_release(self):
        db = _FakeSession()

        country_movies(db, "kr")

        compiled = db.statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
        sql = str(compiled).lower()
        self.assertIn("production_countries && array['kr']", sql)
        self.assertIn("release_date desc nulls last", sql)


if __name__ == "__main__":
    unittest.main()
