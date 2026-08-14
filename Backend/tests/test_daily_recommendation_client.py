from datetime import date
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from app.ai_client.recommend import request_recommend_today_movie


class DailyRecommendationClientTests(IsolatedAsyncioTestCase):
    async def test_uses_fixed_copy_endpoint_and_preserves_selected_movies(self):
        movies = [
            {
                "movie_id": 1,
                "tmdb_id": 101,
                "title": "영화 하나",
                "release_date": date(2026, 8, 1),
            },
            {"movie_id": 2, "tmdb_id": 102, "title": "영화 둘"},
            {"movie_id": 3, "tmdb_id": 103, "title": "영화 셋"},
        ]

        with patch(
            "app.ai_client.recommend.post_ai",
            new=AsyncMock(return_value={"answer": "액션 추천 문구", "movies": movies}),
        ) as post_ai:
            await request_recommend_today_movie("액션", movies)

        path, payload = post_ai.await_args.args
        self.assertEqual(path, "/recommend/daily-copy")
        self.assertEqual(payload["genre"], "액션")
        self.assertEqual(
            [movie["title"] for movie in payload["movies"]],
            ["영화 하나", "영화 둘", "영화 셋"],
        )
        self.assertEqual(payload["movies"][0]["release_date"], "2026-08-01")
