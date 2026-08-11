#!/usr/bin/env python3
"""Import missing theatrical movies for selected Japanese anime franchises."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass

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
from app.services.admin.tmdb_register_service import fetch_admin_tmdb_movie_detail
from app.services.admin.tmdb_search_service import TMDB_BASE_URL
from app.services.movies.tmdb_trailer_service import get_tmdb_auth
from app.services.movies.genre_relevance import sync_movie_genre_weights


LOCAL_DB_HOSTS = {"db", "localhost", "127.0.0.1", "::1"}


@dataclass(frozen=True)
class Franchise:
    label: str
    queries: tuple[str, ...]
    title_markers: tuple[str, ...]


FRANCHISES = {
    "crayon-shinchan": Franchise(
        label="짱구는 못말려",
        queries=("クレヨンしんちゃん", "짱구는 못말려", "Crayon Shin-chan"),
        title_markers=("クレヨンしんちゃん", "짱구", "crayon shin-chan", "crayon shinchan"),
    ),
    "detective-conan": Franchise(
        label="명탐정 코난",
        queries=("名探偵コナン", "명탐정 코난", "Detective Conan"),
        title_markers=("名探偵コナン", "명탐정 코난", "detective conan", "case closed"),
    ),
    "doraemon": Franchise(
        label="도라에몽",
        queries=("映画ドラえもん", "도라에몽 극장판", "Doraemon movie"),
        title_markers=("ドラえもん", "도라에몽", "doraemon"),
    ),
    "pokemon": Franchise(
        label="포켓몬스터",
        queries=("劇場版ポケットモンスター", "극장판 포켓몬스터", "Pokémon movie"),
        title_markers=("ポケットモンスター", "포켓몬", "pokémon", "pokemon"),
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--franchises",
        nargs="+",
        choices=sorted(FRANCHISES),
        default=list(FRANCHISES),
    )
    parser.add_argument("--min-runtime", type=int, default=60)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--allow-nonlocal", action="store_true")
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    if args.min_runtime < 1:
        raise SystemExit("--min-runtime must be at least 1.")
    database_host = make_url(settings.DATABASE_URL).host
    if not args.allow_nonlocal and database_host not in LOCAL_DB_HOSTS:
        raise SystemExit(
            f"Refusing to import into non-local DB host {database_host!r}. "
            "Use --allow-nonlocal only after verifying the target."
        )


def matches_franchise(movie: dict, franchise: Franchise) -> bool:
    if movie.get("original_language") != "ja":
        return False
    searchable = " ".join(
        str(movie.get(field) or "").casefold()
        for field in ("title", "original_title")
    )
    return any(marker.casefold() in searchable for marker in franchise.title_markers)


async def search_query(
    client: httpx.AsyncClient,
    auth_params: dict[str, str],
    query: str,
) -> list[dict]:
    movies: list[dict] = []
    page = 1
    while True:
        response = await client.get(
            "/search/movie",
            params={
                **auth_params,
                "query": query,
                "language": "ko-KR",
                "include_adult": "false",
                "page": page,
            },
        )
        response.raise_for_status()
        payload = response.json()
        results = payload.get("results")
        if not isinstance(results, list):
            break
        movies.extend(movie for movie in results if isinstance(movie, dict))
        total_pages = payload.get("total_pages")
        if not isinstance(total_pages, int) or page >= min(total_pages, 500):
            break
        page += 1
    return movies


async def fetch_candidate(
    semaphore: asyncio.Semaphore,
    tmdb_id: int,
) -> tuple[int, dict | None, str | None]:
    async with semaphore:
        try:
            return tmdb_id, await fetch_admin_tmdb_movie_detail(tmdb_id), None
        except (ValueError, httpx.HTTPError) as error:
            return tmdb_id, None, str(error)


async def fetch_japanese_theatrical_status(
    client: httpx.AsyncClient,
    auth_params: dict[str, str],
    semaphore: asyncio.Semaphore,
    tmdb_id: int,
) -> tuple[int, bool, str | None]:
    async with semaphore:
        try:
            response = await client.get(
                f"/movie/{tmdb_id}/release_dates",
                params=auth_params,
            )
            response.raise_for_status()
            results = response.json().get("results")
            if not isinstance(results, list):
                return tmdb_id, False, None
            japanese_releases = next(
                (
                    item.get("release_dates", [])
                    for item in results
                    if isinstance(item, dict) and item.get("iso_3166_1") == "JP"
                ),
                [],
            )
            # TMDB release types 2 and 3 are limited and general theatrical releases.
            is_theatrical = any(
                isinstance(release, dict) and release.get("type") in {2, 3}
                for release in japanese_releases
            )
            return tmdb_id, is_theatrical, None
        except httpx.HTTPError as error:
            return tmdb_id, False, str(error)


def is_theatrical_candidate(movie: dict, min_runtime: int) -> bool:
    genres = set(normalize_string_list(movie.get("genres")))
    return (
        movie.get("language") == "ja"
        and "애니메이션" in genres
        and isinstance(movie.get("runtime"), int)
        and movie["runtime"] >= min_runtime
        and movie.get("release_date") is not None
        and bool(movie.get("poster_path"))
        and "JP" in set(movie.get("production_countries") or [])
    )


def existing_tmdb_ids(tmdb_ids: list[int]) -> set[int]:
    if not tmdb_ids:
        return set()
    with SessionLocal() as session:
        return set(
            session.scalars(select(Movie.tmdb_id).where(Movie.tmdb_id.in_(tmdb_ids))).all()
        )


def insert_movie(movie_data: dict) -> bool:
    data = movie_data.copy()
    cast_credits = data.pop("cast_credits", [])
    genres = normalize_string_list(data.pop("genres", []))
    data["cast"] = normalize_string_list(data.get("cast"))
    data["keywords"] = normalize_string_list(data.get("keywords"))

    with SessionLocal.begin() as session:
        if session.scalar(select(Movie.id).where(Movie.tmdb_id == data["tmdb_id"])):
            return False
        movie = Movie(**data, genres=[])
        session.add(movie)
        session.flush()
        sync_admin_movie_genres(session, movie, genres)
        sync_movie_genre_weights(session, movie)
        session.add(MovieStats(movie_id=movie.id))
        sync_admin_movie_actors(session, movie, cast_credits)
    return True


async def main() -> None:
    args = parse_args()
    validate_args(args)
    auth = get_tmdb_auth()
    if auth is None:
        raise SystemExit("TMDB authentication is missing.")
    headers, auth_params = auth

    selected = {key: FRANCHISES[key] for key in args.franchises}
    discovered: dict[str, dict[int, dict]] = {key: {} for key in selected}
    async with httpx.AsyncClient(
        base_url=TMDB_BASE_URL,
        headers=headers,
        timeout=30.0,
    ) as client:
        for key, franchise in selected.items():
            query_results = await asyncio.gather(
                *(search_query(client, auth_params, query) for query in franchise.queries)
            )
            for movie in (item for results in query_results for item in results):
                tmdb_id = movie.get("id")
                if isinstance(tmdb_id, int) and tmdb_id > 0 and matches_franchise(movie, franchise):
                    discovered[key][tmdb_id] = movie

        all_ids = sorted({tmdb_id for movies in discovered.values() for tmdb_id in movies})
        release_semaphore = asyncio.Semaphore(8)
        release_rows = await asyncio.gather(
            *(
                fetch_japanese_theatrical_status(
                    client, auth_params, release_semaphore, tmdb_id
                )
                for tmdb_id in all_ids
            )
        )

    japanese_theatrical_ids = {
        tmdb_id for tmdb_id, is_theatrical, error in release_rows if is_theatrical
    }
    release_failures = {
        tmdb_id: error for tmdb_id, is_theatrical, error in release_rows if error is not None
    }
    semaphore = asyncio.Semaphore(8)
    fetched_rows = await asyncio.gather(
        *(fetch_candidate(semaphore, tmdb_id) for tmdb_id in all_ids)
    )
    fetched = {tmdb_id: movie for tmdb_id, movie, error in fetched_rows if movie is not None}
    failures = {tmdb_id: error for tmdb_id, movie, error in fetched_rows if error is not None}
    existing = existing_tmdb_ids(all_ids)

    eligible_by_franchise: dict[str, list[dict]] = {}
    for key, franchise in selected.items():
        eligible = [
            fetched[tmdb_id]
            for tmdb_id in discovered[key]
            if tmdb_id in fetched
            and tmdb_id in japanese_theatrical_ids
            and is_theatrical_candidate(fetched[tmdb_id], args.min_runtime)
        ]
        eligible.sort(key=lambda movie: (movie.get("release_date"), movie["tmdb_id"]))
        eligible_by_franchise[key] = eligible
        missing = [movie for movie in eligible if movie["tmdb_id"] not in existing]
        print(
            f"{franchise.label}: discovered={len(discovered[key])}, "
            f"eligible={len(eligible)}, existing={len(eligible) - len(missing)}, "
            f"missing={len(missing)}"
        )
        for movie in missing:
            print(f"  - {movie['title']} ({movie['release_date']}, TMDB {movie['tmdb_id']})")

    if failures:
        print(f"detail_fetch_failures={len(failures)}")
    if release_failures:
        print(f"release_fetch_failures={len(release_failures)}")
    if not args.apply:
        print("Dry-run complete. Re-run with --apply to insert missing movies.")
        return

    imported = 0
    for key in selected:
        for movie in eligible_by_franchise[key]:
            if movie["tmdb_id"] in existing:
                continue
            if insert_movie(movie):
                imported += 1
                existing.add(movie["tmdb_id"])
                print(f"Imported {imported}: {movie['title']} (TMDB {movie['tmdb_id']})")
    print(
        f"Import complete: imported={imported}, "
        f"detail_fetch_failures={len(failures)}, "
        f"release_fetch_failures={len(release_failures)}."
    )


if __name__ == "__main__":
    asyncio.run(main())
