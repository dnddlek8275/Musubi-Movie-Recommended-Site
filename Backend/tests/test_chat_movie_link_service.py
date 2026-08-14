import unittest
from types import SimpleNamespace

from app.services.movies.chat_movie_link_service import enrich_recommended_movies


class FakeSession:
    def __init__(self, movie):
        self.movie = movie

    def get(self, _model, movie_id):
        return self.movie if movie_id == self.movie.id else None

    def scalar(self, _statement):
        return self.movie


class ChatMovieLinkServiceTests(unittest.TestCase):
    def setUp(self):
        self.movie = SimpleNamespace(
            id=51646,
            tmdb_id=933260,
            title="서브스턴스",
            poster_path="/substance.jpg",
        )
        self.db = FakeSession(self.movie)

    def test_tmdb_recommendation_gets_internal_movie_id(self):
        result = enrich_recommended_movies(self.db, [{
            "tmdb_id": "933260",
            "title": "서브스턴스",
        }])

        self.assertEqual(result[0]["movie_id"], 51646)
        self.assertEqual(result[0]["tmdb_id"], "933260")

    def test_existing_internal_movie_id_is_preserved(self):
        result = enrich_recommended_movies(self.db, [{
            "movie_id": 51646,
            "title": "서브스턴스",
        }])

        self.assertEqual(result[0]["movie_id"], 51646)
        self.assertEqual(result[0]["poster_path"], "/substance.jpg")


if __name__ == "__main__":
    unittest.main()
