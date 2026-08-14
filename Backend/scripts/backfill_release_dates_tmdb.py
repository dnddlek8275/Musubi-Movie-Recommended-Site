#!/usr/bin/env python3
"""Backfill missing movie release dates from TMDB in resumable priority stages."""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import date
from pathlib import Path

import httpx
from sqlalchemy import func, select, update
from sqlalchemy.engine import make_url

from app.core.config import settings
from app.core.dependencies import SessionLocal
from app.models.movies import Movie
from app.services.admin.tmdb_search_service import TMDB_BASE_URL
from app.services.movies.tmdb_trailer_service import get_tmdb_auth


LOCAL_DB_HOSTS = {"db", "localhost", "127.0.0.1", "::1"}
STAGES = ("recent", "regional")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=STAGES, required=True)
    parser.add_argument("--start-year", type=int, default=2024)
    parser.add_argument("--end-year", type=int, default=2026)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--allow-nonlocal", action="store_true")
    return parser.parse_args()


def validate(args: argparse.Namespace) -> None:
    host = make_url(settings.DATABASE_URL).host
    if host not in LOCAL_DB_HOSTS and not args.allow_nonlocal:
        raise SystemExit(f"Refusing to update non-local DB host {host!r}.")
    if not 1 <= args.concurrency <= 20:
        raise SystemExit("--concurrency must be between 1 and 20.")
    if args.start_year > args.end_year:
        raise SystemExit("--start-year must not exceed --end-year.")


def load_checkpoint(path: Path) -> set[int]:
    if not path.exists():
        return set()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return {int(value) for value in payload.get("processed_tmdb_ids", [])}
    except (OSError, ValueError, TypeError):
        raise SystemExit(f"Invalid checkpoint file: {path}")


def save_checkpoint(path: Path, processed: set[int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps({"processed_tmdb_ids": sorted(processed)}, ensure_ascii=False),
        encoding="utf-8",
    )
    temporary.replace(path)


def candidates(args: argparse.Namespace, processed: set[int]) -> list[tuple[int, int]]:
    query = select(Movie.id, Movie.tmdb_id).where(
        Movie.release_date.is_(None),
        Movie.tmdb_id.is_not(None),
    )
    if args.stage == "recent":
        query = query.where(Movie.year.between(args.start_year, args.end_year))
    else:
        query = query.where(Movie.language.in_(("ko", "ja")))
    query = query.order_by(Movie.id)
    with SessionLocal() as session:
        return [(movie_id, tmdb_id) for movie_id, tmdb_id in session.execute(query) if tmdb_id not in processed]


async def fetch_release_date(
    client: httpx.AsyncClient,
    auth_params: dict[str, str],
    tmdb_id: int,
) -> tuple[int, date | None, str | None]:
    for attempt in range(5):
        try:
            response = await client.get(
                f"/movie/{tmdb_id}",
                params={**auth_params, "language": "ko-KR"},
            )
            if response.status_code == 404:
                return tmdb_id, None, "not_found"
            if response.status_code == 429 or response.status_code >= 500:
                retry_after = float(response.headers.get("Retry-After", 0) or 0)
                await asyncio.sleep(max(retry_after, 2 ** attempt))
                continue
            response.raise_for_status()
            raw = (response.json().get("release_date") or "").strip()
            if not raw:
                return tmdb_id, None, "missing_date"
            try:
                return tmdb_id, date.fromisoformat(raw), None
            except ValueError:
                return tmdb_id, None, "invalid_date"
        except (httpx.HTTPError, ValueError) as error:
            if attempt == 4:
                return tmdb_id, None, type(error).__name__
            await asyncio.sleep(2 ** attempt)
    return tmdb_id, None, "retry_exhausted"


async def main() -> None:
    args = parse_args()
    validate(args)
    auth = get_tmdb_auth()
    if auth is None:
        raise SystemExit("TMDB_ACCESS_TOKEN or TMDB_API_KEY is required.")
    headers, auth_params = auth
    processed = load_checkpoint(args.checkpoint)
    targets = candidates(args, processed)
    print(f"stage={args.stage} pending={len(targets):,} already_processed={len(processed):,}")

    semaphore = asyncio.Semaphore(args.concurrency)

    async with httpx.AsyncClient(
        base_url=TMDB_BASE_URL,
        headers=headers,
        timeout=20.0,
    ) as client:
        async def bounded(tmdb_id: int):
            async with semaphore:
                return await fetch_release_date(client, auth_params, tmdb_id)

        updated = missing = failed = 0
        batch_size = 100
        for start in range(0, len(targets), batch_size):
            batch = targets[start:start + batch_size]
            results = await asyncio.gather(*(bounded(tmdb_id) for _, tmdb_id in batch))
            movie_ids = {tmdb_id: movie_id for movie_id, tmdb_id in batch}
            with SessionLocal.begin() as session:
                for tmdb_id, release_date, error in results:
                    if release_date is not None:
                        result = session.execute(
                            update(Movie)
                            .where(Movie.id == movie_ids[tmdb_id], Movie.release_date.is_(None))
                            .values(release_date=release_date, year=release_date.year)
                        )
                        updated += max(result.rowcount, 0)
                    elif error in {"missing_date", "not_found", "invalid_date"}:
                        missing += 1
                    else:
                        failed += 1
                        continue
                    processed.add(tmdb_id)
            save_checkpoint(args.checkpoint, processed)
            print(
                f"progress={min(start + len(batch), len(targets)):,}/{len(targets):,} "
                f"updated={updated:,} missing={missing:,} transient_failed={failed:,}",
                flush=True,
            )

    with SessionLocal() as session:
        total = session.scalar(select(func.count(Movie.id))) or 0
        dated = session.scalar(select(func.count(Movie.id)).where(Movie.release_date.is_not(None))) or 0
    print(f"complete stage={args.stage} updated={updated:,} missing={missing:,} transient_failed={failed:,}")
    print(f"database coverage={dated:,}/{total:,} ({dated / total:.1%})")


if __name__ == "__main__":
    asyncio.run(main())
