import unittest

from app.services.movies.genre_service import genre_movies


class _ScalarResult:
    def all(self):
        return []


class _RecordingSession:
    def __init__(self):
        self.statement = None

    def scalars(self, statement):
        self.statement = statement
        return _ScalarResult()


class GenreMovieSortTests(unittest.TestCase):
    def test_latest_sort_prioritizes_release_date(self):
        db = _RecordingSession()

        genre_movies(db, "드라마", page=1, limit=25, sort="latest")

        order_by = [str(clause) for clause in db.statement._order_by_clauses]
        self.assertIn("movies.release_date DESC NULLS LAST", order_by[0])
        self.assertIn("movies.year DESC NULLS LAST", order_by[1])
        self.assertIn("movies.id DESC", order_by[2])

    def test_default_sort_keeps_relevance_first(self):
        db = _RecordingSession()

        genre_movies(db, "드라마", page=1, limit=20)

        order_by = [str(clause) for clause in db.statement._order_by_clauses]
        self.assertIn("movie_genre_weights.weight DESC", order_by[0])


if __name__ == "__main__":
    unittest.main()
