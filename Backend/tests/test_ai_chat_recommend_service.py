import unittest
from types import SimpleNamespace
from unittest.mock import ANY, patch

from app.services.movies.ai_chat_recommend_service import (
    get_chat_ai_recommended_movies_result,
)


class AiChatRecommendServiceTests(unittest.TestCase):
    @patch(
        "app.services.movies.ai_chat_recommend_service.enrich_recommended_movies"
    )
    @patch(
        "app.services.movies.ai_chat_recommend_service.get_chat_ai_recommended_movies_messages"
    )
    def test_history_returns_only_clickable_unique_internal_movies(
        self,
        get_messages,
        enrich_movies,
    ):
        first_message = SimpleNamespace(recommended_movies=[{"tmdb_id": 1}])
        second_message = SimpleNamespace(recommended_movies=[{"tmdb_id": 2}])
        get_messages.return_value = [
            (first_message, SimpleNamespace()),
            (second_message, SimpleNamespace()),
        ]
        enrich_movies.side_effect = [
            [{"movie_id": 101, "tmdb_id": 1, "title": "첫 영화"}],
            [
                {"movie_id": 101, "tmdb_id": 1, "title": "첫 영화"},
                {"title": "DB에 없는 영화"},
                {"movie_id": 202, "tmdb_id": 2, "title": "둘째 영화"},
            ],
        ]

        result = get_chat_ai_recommended_movies_result(object(), user_id=7, limit=2)

        self.assertEqual([movie["movie_id"] for movie in result], [101, 202])
        get_messages.assert_called_once_with(ANY, 7, 100)


if __name__ == "__main__":
    unittest.main()
