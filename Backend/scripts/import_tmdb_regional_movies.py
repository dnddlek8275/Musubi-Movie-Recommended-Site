#!/usr/bin/env python3
"""Import sufficiently rated Korean and Japanese movies from TMDB."""

from __future__ import annotations

import argparse
import asyncio

import httpx
from sqlalchemy import select
from sqlalchemy.engine import make_url

from app.core.config import settings
from app.core.dependencies import SessionLocal
from app.models.movies import Movie, MovieStats
from app.services.admin.movie_service import (
    normalize_string_list,
    sync_admin_movie_actors,
    sync_admin_movie_genres,
)
from app.services.admin.tmdb_register_service import (
    fetch_admin_tmdb_movie_detail,
)
from app.services.movies.genre_relevance import sync_movie_genre_weights
from app.services.admin.tmdb_search_service import TMDB_BASE_URL
from app.services.movies.tmdb_trailer_service import get_tmdb_auth


LOCAL_DB_HOSTS = {"db", "localhost", "127.0.0.1", "::1"}
SUPPORTED_LANGUAGES = {"ko", "ja"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Discover Korean/Japanese movies from TMDB and add missing movies "
            "with genres, top cast, and zero-initialized stats."
        ),
    )
    parser.add_argument(
        "--languages",
        nargs="+",
        default=["ko", "ja"],
        choices=sorted(SUPPORTED_LANGUAGES),
    )
    parser.add_argument("--min-rating", type=float, default=6.0)
    parser.add_argument("--min-votes", type=int, default=100)
    parser.add_argument("--max-pages", type=int, default=500)
    parser.add_argument(
        "--limit-per-language",
        type=int,
        help="Stop after this many eligible candidates per language.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write missing movies to the local DB. Without this flag, dry-run only.",
    )
    parser.add_argument(
        "--allow-nonlocal",
        action="store_true",
        help="Allow a DB host other than db/localhost. Do not use casually.",
    )
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    if args.min_rating < 0 or args.min_rating > 10:
        raise SystemExit("--min-rating must be between 0 and 10.")
    if args.min_votes < 0:
        raise SystemExit("--min-votes must be at least 0.")
    if args.max_pages < 1 or args.max_pages > 500:
        raise SystemExit("--max-pages must be between 1 and 500.")
    if args.limit_per_language is not None and args.limit_per_language < 1:
        raise SystemExit("--limit-per-language must be at least 1.")

    database_host = make_url(settings.DATABASE_URL).host
    if not args.allow_nonlocal and database_host not in LOCAL_DB_HOSTS:
        raise SystemExit(
            f"Refusing to import into non-local DB host {database_host!r}. "
            "Use --allow-nonlocal only after verifying the target."
        )


async def discover_candidates(
    client: httpx.AsyncClient,
    auth_params: dict[str, str],
    *,
    language: str,
    min_rating: float,
    min_votes: int,
    max_pages: int,
    limit: int | None,
) -> list[dict]:
    candidates: list[dict] = []

    for page in range(1, max_pages + 1):
        response = await client.get(
            "/discover/movie",
            params={
                **auth_params,
                "include_adult": "false",
                "include_video": "false",
                "language": "ko-KR",
                "sort_by": "popularity.desc",
                "vote_average.gte": min_rating,
                "vote_count.gte": min_votes,
                "with_original_language": language,
                "page": page,
            },
        )
        response.raise_for_status()
        payload = response.json()
        results = payload.get("results")

        if not isinstance(results, list):
            raise ValueError("TMDB discover 응답의 results가 목록이 아닙니다.")

        candidates.extend(
            movie
            for movie in results
            if (
                isinstance(movie, dict)
                and isinstance(movie.get("id"), int)
                and movie["id"] > 0
                and movie.get("poster_path")
            )
        )

        if limit is not None and len(candidates) >= limit:
            return candidates[:limit]

        total_pages = payload.get("total_pages")
        if not isinstance(total_pages, int) or page >= min(total_pages, 500):
            break

    return candidates


def registered_tmdb_ids(tmdb_ids: list[int]) -> set[int]:
    if not tmdb_ids:
        return set()

    with SessionLocal() as session:
        return set(
            session.scalars(
                select(Movie.tmdb_id).where(Movie.tmdb_id.in_(tmdb_ids))
            ).all()
        )


def insert_movie(movie_data: dict) -> None:
    data = movie_data.copy()
    cast_credits = data.pop("cast_credits", [])
    genres = normalize_string_list(data.pop("genres", []))
    data["cast"] = normalize_string_list(data.get("cast"))
    data["keywords"] = normalize_string_list(data.get("keywords"))

    with SessionLocal.begin() as session:
        if session.scalar(
            select(Movie.id).where(Movie.tmdb_id == data["tmdb_id"])
        ) is not None:
            return

        movie = Movie(**data, genres=[])
        session.add(movie)
        session.flush()
        sync_admin_movie_genres(session, movie, genres)
        sync_movie_genre_weights(session, movie)
        session.add(MovieStats(movie_id=movie.id))
        sync_admin_movie_actors(session, movie, cast_credits)


async def main() -> None:
    args = parse_args()
    validate_args(args)
    auth = get_tmdb_auth()

    if auth is None:
        raise SystemExit(
            "TMDB authentication is missing. Set TMDB_ACCESS_TOKEN "
            "or TMDB_API_KEY."
        )

    headers, auth_params = auth
    candidates_by_language: dict[str, list[dict]] = {}

    async with httpx.AsyncClient(
        base_url=TMDB_BASE_URL,
        headers=headers,
        timeout=20.0,
    ) as client:
        for language in args.languages:
            candidates_by_language[language] = await discover_candidates(
                client,
                auth_params,
                language=language,
                min_rating=args.min_rating,
                min_votes=args.min_votes,
                max_pages=args.max_pages,
                limit=args.limit_per_language,
            )

    all_tmdb_ids = [
        movie["id"]
        for candidates in candidates_by_language.values()
        for movie in candidates
    ]
    existing_ids = registered_tmdb_ids(all_tmdb_ids)
    missing_by_language = {
        language: [
            movie for movie in candidates if movie["id"] not in existing_ids
        ]
        for language, candidates in candidates_by_language.items()
    }

    for language, candidates in candidates_by_language.items():
        missing = missing_by_language[language]
        print(
            f"{language}: eligible={len(candidates):,}, "
            f"existing={len(candidates) - len(missing):,}, "
            f"missing={len(missing):,}"
        )
        for movie in missing[:10]:
            print(
                f"  - {movie.get('title') or movie.get('original_title')} "
                f"(TMDB {movie['id']}, rating={movie.get('vote_average')}, "
                f"votes={movie.get('vote_count')})"
            )

    if not args.apply:
        print("Dry-run complete. Re-run with --apply to insert missing movies.")
        return

    imported = 0
    failed = 0
    for language in args.languages:
        for candidate in missing_by_language[language]:
            try:
                movie_data = await fetch_admin_tmdb_movie_detail(candidate["id"])
                if not movie_data.get("poster_path"):
                    continue
                insert_movie(movie_data)
                imported += 1
                print(
                    f"Imported {imported:,}: {movie_data['title']} "
                    f"(TMDB {movie_data['tmdb_id']})",
                    flush=True,
                )
            except (ValueError, httpx.HTTPError) as error:
                failed += 1
                print(
                    f"Failed TMDB {candidate['id']}: {error}",
                    flush=True,
                )

    print(f"Import complete: imported={imported:,}, failed={failed:,}.")


if __name__ == "__main__":
    asyncio.run(main())
