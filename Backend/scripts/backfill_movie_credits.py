#!/usr/bin/env python3
"""Backfill missing directors and top cast from TMDB without replacing known values."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

import httpx
from sqlalchemy import func, or_, select
from sqlalchemy.engine import make_url

from app.core.config import settings
from app.core.dependencies import SessionLocal
from app.models.movies import Movie
from app.services.admin.movie_service import sync_admin_movie_actors
from app.services.admin.tmdb_search_service import TMDB_BASE_URL, tmdb_image_url
from app.services.movies.tmdb_trailer_service import get_tmdb_auth


LOCAL_DB_HOSTS = {"db", "localhost", "127.0.0.1", "::1"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--allow-nonlocal", action="store_true")
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args()


def validate(args: argparse.Namespace) -> None:
    host = make_url(settings.DATABASE_URL).host
    if host not in LOCAL_DB_HOSTS and not args.allow_nonlocal:
        raise SystemExit(f"Refusing to update non-local DB host {host!r}.")
    if not 1 <= args.concurrency <= 20:
        raise SystemExit("--concurrency must be between 1 and 20.")


def load_checkpoint(path: Path) -> set[int]:
    if not path.exists():
        return set()
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {int(value) for value in payload.get("processed_tmdb_ids", [])}


def save_checkpoint(path: Path, processed: set[int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps({"processed_tmdb_ids": sorted(processed)}),
        encoding="utf-8",
    )
    temporary.replace(path)


def missing_director() -> object:
    return or_(Movie.director.is_(None), func.btrim(Movie.director) == "")


def missing_cast() -> object:
    return or_(Movie.cast.is_(None), func.cardinality(Movie.cast) == 0)


def candidates(processed: set[int]) -> list[tuple[int, int]]:
    query = (
        select(Movie.id, Movie.tmdb_id)
        .where(Movie.tmdb_id.is_not(None), or_(missing_director(), missing_cast()))
        .order_by(Movie.id)
    )
    with SessionLocal() as session:
        return [
            (movie_id, tmdb_id)
            for movie_id, tmdb_id in session.execute(query)
            if tmdb_id not in processed
        ]


def coverage() -> str:
    with SessionLocal() as session:
        total = session.scalar(select(func.count(Movie.id))) or 0
        directors = session.scalar(
            select(func.count(Movie.id)).where(~missing_director())
        ) or 0
        casts = session.scalar(
            select(func.count(Movie.id)).where(~missing_cast())
        ) or 0
    if not total:
        return "database is empty"
    return (
        f"coverage total={total:,} directors={directors:,} ({directors / total:.1%}) "
        f"casts={casts:,} ({casts / total:.1%})"
    )


def parse_credits(payload: object) -> dict:
    if not isinstance(payload, dict):
        return {"director": None, "cast": [], "cast_credits": []}
    crew = payload.get("crew") if isinstance(payload.get("crew"), list) else []
    raw_cast = payload.get("cast") if isinstance(payload.get("cast"), list) else []
    directors = [
        member["name"].strip()
        for member in crew
        if isinstance(member, dict)
        and member.get("job") == "Director"
        and isinstance(member.get("name"), str)
        and member["name"].strip()
    ]
    cast_names: list[str] = []
    cast_credits: list[dict] = []
    for default_order, member in enumerate(raw_cast[:10]):
        if not isinstance(member, dict):
            continue
        actor_id = member.get("id")
        name = member.get("name")
        if not isinstance(actor_id, int) or actor_id <= 0 or not isinstance(name, str) or not name.strip():
            continue
        normalized_name = name.strip()[:100]
        if normalized_name in cast_names:
            continue
        cast_names.append(normalized_name)
        cast_credits.append({
            "tmdb_actor_id": actor_id,
            "name": normalized_name,
            "profile_path": tmdb_image_url(member.get("profile_path")),
            "character_name": member.get("character"),
            "cast_order": member.get("order") if isinstance(member.get("order"), int) else default_order,
        })
    return {
        "director": ", ".join(dict.fromkeys(directors))[:200] or None,
        "cast": cast_names,
        "cast_credits": cast_credits,
    }


async def fetch_credits(client: httpx.AsyncClient, auth_params: dict[str, str], tmdb_id: int):
    for attempt in range(5):
        try:
            response = await client.get(
                f"/movie/{tmdb_id}/credits",
                params={**auth_params, "language": "ko-KR"},
            )
            if response.status_code == 404:
                return tmdb_id, parse_credits({}), "not_found"
            if response.status_code == 429 or response.status_code >= 500:
                await asyncio.sleep(max(float(response.headers.get("Retry-After", 0) or 0), 2 ** attempt))
                continue
            response.raise_for_status()
            return tmdb_id, parse_credits(response.json()), None
        except (httpx.HTTPError, ValueError, TypeError) as error:
            if attempt == 4:
                return tmdb_id, None, type(error).__name__
            await asyncio.sleep(2 ** attempt)
    return tmdb_id, None, "retry_exhausted"


async def run(args: argparse.Namespace) -> None:
    processed = load_checkpoint(args.checkpoint)
    targets = candidates(processed)
    print(f"credits pending={len(targets):,} already_processed={len(processed):,}")
    print(coverage())
    if not args.apply:
        print("dry-run only; pass --apply to update the database")
        return

    auth = get_tmdb_auth()
    if auth is None:
        raise SystemExit("TMDB_ACCESS_TOKEN or TMDB_API_KEY is required.")
    headers, auth_params = auth
    semaphore = asyncio.Semaphore(args.concurrency)
    updated_director = updated_cast = no_values = transient_failed = 0

    async with httpx.AsyncClient(base_url=TMDB_BASE_URL, headers=headers, timeout=20.0) as client:
        async def bounded(tmdb_id: int):
            async with semaphore:
                return await fetch_credits(client, auth_params, tmdb_id)

        for start in range(0, len(targets), 100):
            batch = targets[start:start + 100]
            movie_ids = {tmdb_id: movie_id for movie_id, tmdb_id in batch}
            results = await asyncio.gather(*(bounded(tmdb_id) for _, tmdb_id in batch))
            with SessionLocal.begin() as session:
                for tmdb_id, credits, error in results:
                    if credits is None:
                        transient_failed += 1
                        continue
                    movie = session.get(Movie, movie_ids[tmdb_id])
                    changed = False
                    if movie is not None and (not movie.director or not movie.director.strip()) and credits["director"]:
                        movie.director = credits["director"]
                        updated_director += 1
                        changed = True
                    if movie is not None and not (movie.cast or []) and credits["cast"]:
                        movie.cast = credits["cast"]
                        sync_admin_movie_actors(session, movie, credits["cast_credits"])
                        updated_cast += 1
                        changed = True
                    if not changed:
                        no_values += 1
                    processed.add(tmdb_id)
            save_checkpoint(args.checkpoint, processed)
            print(
                f"progress={min(start + len(batch), len(targets)):,}/{len(targets):,} "
                f"directors={updated_director:,} casts={updated_cast:,} "
                f"no_values={no_values:,} transient_failed={transient_failed:,}",
                flush=True,
            )
    print("TMDB credits backfill complete")
    print(coverage())


async def main() -> None:
    args = parse_args()
    validate(args)
    await run(args)


if __name__ == "__main__":
    asyncio.run(main())
