import unittest
from datetime import date

import httpx

from scripts.sync_tmdb_daily import (
    _eligible_new_movie,
    discover_recent_qualified_ids,
    fetch_changed_ids,
)


class TmdbDailySyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_fetch_changed_ids_follows_pages(self):
        def handler(request: httpx.Request) -> httpx.Response:
            page = int(request.url.params["page"])
            return httpx.Response(
                200,
                json={
                    "results": [{"id": page}, {"id": 10}],
                    "total_pages": 2,
                },
            )

        async with httpx.AsyncClient(
            base_url="https://example.test",
            transport=httpx.MockTransport(handler),
        ) as client:
            result = await fetch_changed_ids(client, {}, date(2026, 8, 6))
        self.assertEqual(result, {1, 2, 10})

    async def test_discover_excludes_adult_and_missing_poster(self):
        def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "results": [
                        {"id": 1, "adult": False, "poster_path": "/ok.jpg"},
                        {"id": 2, "adult": True, "poster_path": "/adult.jpg"},
                        {"id": 3, "adult": False, "poster_path": None},
                    ],
                    "total_pages": 1,
                },
            )

        async with httpx.AsyncClient(
            base_url="https://example.test",
            transport=httpx.MockTransport(handler),
        ) as client:
            result = await discover_recent_qualified_ids(client, {}, date(2026, 8, 6))
        self.assertEqual(result, {1})

    def test_new_movie_quality_threshold(self):
        self.assertTrue(
            _eligible_new_movie(
                {"poster_path": "/ok.jpg", "vote_average": 6.0, "vote_count": 100}
            )
        )
        self.assertFalse(
            _eligible_new_movie(
                {"poster_path": "/ok.jpg", "vote_average": 10.0, "vote_count": 99}
            )
        )


if __name__ == "__main__":
    unittest.main()
