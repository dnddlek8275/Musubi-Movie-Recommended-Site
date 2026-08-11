#!/usr/bin/env python3
"""Restore Korean-first display titles from CSV and TMDB translations on a local DB."""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
from pathlib import Path

import httpx
from sqlalchemy import bindparam, select, update
from sqlalchemy.engine import make_url

from app.core.config import settings
from app.core.dependencies import SessionLocal
from app.models.movies import Movie
from app.services.admin.tmdb_register_service import extract_display_title
from app.services.admin.tmdb_search_service import TMDB_BASE_URL
from app.services.movies.tmdb_trailer_service import get_tmdb_auth


LOCAL_DB_HOSTS = {"db", "localhost", "127.0.0.1", "::1"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv-path", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--concurrency", type=int, default=12)
    parser.add_argument("--allow-nonlocal", action="store_true")
    return parser.parse_args()


def validate(args: argparse.Namespace) -> None:
    host = make_url(settings.DATABASE_URL).host
    if host not in LOCAL_DB_HOSTS and not args.allow_nonlocal:
        raise SystemExit(f"Refusing to update non-local DB host {host!r}.")
    if not args.csv_path.is_file():
        raise SystemExit("--csv-path must point to an existing CSV file.")
    if not 1 <= args.concurrency <= 20:
        raise SystemExit("--concurrency must be between 1 and 20.")


def restore_csv_titles(path: Path) -> set[int]:
    rows = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not {"tmdb_id", "title"}.issubset(reader.fieldnames or []):
            raise SystemExit("CSV must contain tmdb_id and title columns.")
        for row in reader:
            raw_id = (row.get("tmdb_id") or "").strip()
            title = (row.get("title") or "").strip()[:300]
            if raw_id and title:
                rows.append({"p_tmdb_id": int(float(raw_id)), "p_title": title})

    statement = (
        Movie.__table__.update()
        .where(Movie.tmdb_id == bindparam("p_tmdb_id"))
        .values(title=bindparam("p_title"))
    )
    with SessionLocal.begin() as session:
        for start in range(0, len(rows), 500):
            session.execute(statement, rows[start:start + 500])
    print(f"csv_titles_restored={len(rows):,}")
    return {row["p_tmdb_id"] for row in rows}


def load_checkpoint(path: Path) -> set[int]:
    if not path.exists():
        return set()
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {int(value) for value in payload.get("processed_tmdb_ids", [])}


def save_checkpoint(path: Path, processed: set[int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps({"processed_tmdb_ids": sorted(processed)}), encoding="utf-8")
    temporary.replace(path)


async def fetch_title(client, auth_params, tmdb_id):
    for attempt in range(5):
        try:
            response = await client.get(
                f"/movie/{tmdb_id}",
                params={**auth_params, "language": "ko-KR", "append_to_response": "translations"},
            )
            if response.status_code == 404:
                return tmdb_id, None, "not_found"
            if response.status_code == 429 or response.status_code >= 500:
                await asyncio.sleep(max(float(response.headers.get("Retry-After", 0) or 0), 2 ** attempt))
                continue
            response.raise_for_status()
            return tmdb_id, extract_display_title(response.json()), None
        except (httpx.HTTPError, ValueError, TypeError) as error:
            if attempt == 4:
                return tmdb_id, None, type(error).__name__
            await asyncio.sleep(2 ** attempt)
    return tmdb_id, None, "retry_exhausted"


async def backfill_tmdb(args, csv_ids: set[int]) -> None:
    auth = get_tmdb_auth()
    if auth is None:
        raise SystemExit("TMDB_ACCESS_TOKEN or TMDB_API_KEY is required.")
    headers, auth_params = auth
    processed = load_checkpoint(args.checkpoint)
    with SessionLocal() as session:
        targets = [
            (movie_id, tmdb_id)
            for movie_id, tmdb_id in session.execute(
                select(Movie.id, Movie.tmdb_id).where(Movie.tmdb_id.is_not(None)).order_by(Movie.id)
            )
            if tmdb_id not in csv_ids and tmdb_id not in processed
        ]
    print(f"tmdb_title_pending={len(targets):,} already_processed={len(processed):,}")
    semaphore = asyncio.Semaphore(args.concurrency)
    updated = missing = failed = 0
    async with httpx.AsyncClient(base_url=TMDB_BASE_URL, headers=headers, timeout=20.0) as client:
        async def bounded(tmdb_id):
            async with semaphore:
                return await fetch_title(client, auth_params, tmdb_id)

        for start in range(0, len(targets), 100):
            batch = targets[start:start + 100]
            movie_ids = {tmdb_id: movie_id for movie_id, tmdb_id in batch}
            results = await asyncio.gather(*(bounded(tmdb_id) for _, tmdb_id in batch))
            with SessionLocal.begin() as session:
                for tmdb_id, title, error in results:
                    if error and error != "not_found":
                        failed += 1
                        continue
                    if title:
                        session.execute(update(Movie).where(Movie.id == movie_ids[tmdb_id]).values(title=title))
                        updated += 1
                    else:
                        missing += 1
                    processed.add(tmdb_id)
            save_checkpoint(args.checkpoint, processed)
            print(
                f"progress={min(start + len(batch), len(targets)):,}/{len(targets):,} "
                f"updated={updated:,} missing={missing:,} failed={failed:,}",
                flush=True,
            )
    print(f"TMDB title backfill complete updated={updated:,} missing={missing:,} failed={failed:,}")


async def main() -> None:
    args = parse_args()
    validate(args)
    csv_ids = restore_csv_titles(args.csv_path)
    await backfill_tmdb(args, csv_ids)


if __name__ == "__main__":
    asyncio.run(main())
