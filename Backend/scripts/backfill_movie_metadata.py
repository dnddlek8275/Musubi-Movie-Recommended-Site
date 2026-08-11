#!/usr/bin/env python3
"""Backfill runtime, production countries and certification without replacing known values."""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
from pathlib import Path

import httpx
from sqlalchemy import bindparam, func, or_, select, update
from sqlalchemy.engine import make_url

from app.core.config import settings
from app.core.dependencies import SessionLocal
from app.models.movies import Movie
from app.services.admin.tmdb_register_service import extract_certification
from app.services.admin.tmdb_search_service import TMDB_BASE_URL
from app.services.movies.tmdb_trailer_service import get_tmdb_auth


LOCAL_DB_HOSTS = {"db", "localhost", "127.0.0.1", "::1"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=("csv", "tmdb"), required=True)
    parser.add_argument("--csv-path", type=Path)
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--allow-nonlocal", action="store_true")
    return parser.parse_args()


def validate(args: argparse.Namespace) -> None:
    host = make_url(settings.DATABASE_URL).host
    if host not in LOCAL_DB_HOSTS and not args.allow_nonlocal:
        raise SystemExit(f"Refusing to update non-local DB host {host!r}.")
    if args.source == "csv" and (args.csv_path is None or not args.csv_path.is_file()):
        raise SystemExit("--csv-path is required for the csv source.")
    if args.source == "tmdb" and args.checkpoint is None:
        raise SystemExit("--checkpoint is required for the tmdb source.")
    if not 1 <= args.concurrency <= 20:
        raise SystemExit("--concurrency must be between 1 and 20.")


def print_coverage() -> None:
    with SessionLocal() as session:
        total = session.scalar(select(func.count(Movie.id))) or 0
        runtime = session.scalar(select(func.count(Movie.id)).where(Movie.runtime.is_not(None))) or 0
        countries = session.scalar(select(func.count(Movie.id)).where(Movie.production_countries.is_not(None))) or 0
        certification = session.scalar(select(func.count(Movie.id)).where(Movie.certification.is_not(None))) or 0
    print(
        f"coverage total={total:,} runtime={runtime:,} ({runtime / total:.1%}) "
        f"countries={countries:,} ({countries / total:.1%}) "
        f"certification={certification:,} ({certification / total:.1%})"
        if total else "database is empty"
    )


def backfill_csv(path: Path) -> None:
    rows = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not {"tmdb_id", "runtime"}.issubset(reader.fieldnames or []):
            raise SystemExit("CSV must contain tmdb_id and runtime columns.")
        for row in reader:
            raw_runtime = (row.get("runtime") or "").strip()
            raw_tmdb_id = (row.get("tmdb_id") or "").strip()
            if not raw_runtime or not raw_tmdb_id:
                continue
            runtime = int(float(raw_runtime))
            if runtime > 0:
                rows.append({"p_tmdb_id": int(float(raw_tmdb_id)), "p_runtime": runtime})

    statement = (
        Movie.__table__.update()
        .where(Movie.tmdb_id == bindparam("p_tmdb_id"), Movie.runtime.is_(None))
        .values(runtime=bindparam("p_runtime"))
    )
    updated = 0
    with SessionLocal.begin() as session:
        for start in range(0, len(rows), 500):
            result = session.execute(statement, rows[start:start + 500])
            updated += max(result.rowcount, 0)
    print(f"csv usable={len(rows):,} updated_runtime={updated:,}")
    print_coverage()


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


def tmdb_candidates(processed: set[int]) -> list[tuple[int, int]]:
    query = (
        select(Movie.id, Movie.tmdb_id)
        .where(
            Movie.tmdb_id.is_not(None),
            or_(
                Movie.runtime.is_(None),
                Movie.production_countries.is_(None),
                Movie.certification.is_(None),
            ),
        )
        .order_by(Movie.id)
    )
    with SessionLocal() as session:
        return [
            (movie_id, tmdb_id)
            for movie_id, tmdb_id in session.execute(query)
            if tmdb_id not in processed
        ]


async def fetch_metadata(
    client: httpx.AsyncClient,
    auth_params: dict[str, str],
    tmdb_id: int,
) -> tuple[int, dict | None, str | None]:
    for attempt in range(5):
        try:
            response = await client.get(
                f"/movie/{tmdb_id}",
                params={
                    **auth_params,
                    "language": "ko-KR",
                    "append_to_response": "release_dates",
                },
            )
            if response.status_code == 404:
                return tmdb_id, {}, "not_found"
            if response.status_code == 429 or response.status_code >= 500:
                await asyncio.sleep(max(float(response.headers.get("Retry-After", 0) or 0), 2 ** attempt))
                continue
            response.raise_for_status()
            detail = response.json()
            runtime = detail.get("runtime")
            runtime = runtime if isinstance(runtime, int) and runtime > 0 else None
            raw_countries = detail.get("production_countries") or []
            countries = list(dict.fromkeys(
                item["iso_3166_1"].strip().upper()
                for item in raw_countries
                if isinstance(item, dict)
                and isinstance(item.get("iso_3166_1"), str)
                and len(item["iso_3166_1"].strip()) == 2
            ))
            certification, certification_country = extract_certification(detail.get("release_dates"))
            return tmdb_id, {
                "runtime": runtime,
                "production_countries": countries or None,
                "certification": certification,
                "certification_country": certification_country,
            }, None
        except (httpx.HTTPError, ValueError, TypeError) as error:
            if attempt == 4:
                return tmdb_id, None, type(error).__name__
            await asyncio.sleep(2 ** attempt)
    return tmdb_id, None, "retry_exhausted"


async def backfill_tmdb(args: argparse.Namespace) -> None:
    auth = get_tmdb_auth()
    if auth is None:
        raise SystemExit("TMDB_ACCESS_TOKEN or TMDB_API_KEY is required.")
    headers, auth_params = auth
    processed = load_checkpoint(args.checkpoint)
    targets = tmdb_candidates(processed)
    print(f"tmdb pending={len(targets):,} already_processed={len(processed):,}")
    semaphore = asyncio.Semaphore(args.concurrency)
    updated = permanent_missing = transient_failed = 0

    async with httpx.AsyncClient(base_url=TMDB_BASE_URL, headers=headers, timeout=20.0) as client:
        async def bounded(tmdb_id: int):
            async with semaphore:
                return await fetch_metadata(client, auth_params, tmdb_id)

        for start in range(0, len(targets), 100):
            batch = targets[start:start + 100]
            movie_ids = {tmdb_id: movie_id for movie_id, tmdb_id in batch}
            results = await asyncio.gather(*(bounded(tmdb_id) for _, tmdb_id in batch))
            with SessionLocal.begin() as session:
                for tmdb_id, metadata, error in results:
                    if metadata is None:
                        transient_failed += 1
                        continue
                    values = {key: value for key, value in metadata.items() if value is not None}
                    if values:
                        preserved_values = {
                            key: func.coalesce(getattr(Movie, key), value)
                            for key, value in values.items()
                        }
                        session.execute(
                            update(Movie)
                            .where(Movie.id == movie_ids[tmdb_id])
                            .values(**preserved_values)
                        )
                        updated += 1
                    else:
                        permanent_missing += 1
                    processed.add(tmdb_id)
            save_checkpoint(args.checkpoint, processed)
            print(
                f"progress={min(start + len(batch), len(targets)):,}/{len(targets):,} "
                f"updated={updated:,} no_values={permanent_missing:,} transient_failed={transient_failed:,}",
                flush=True,
            )
    print("TMDB metadata backfill complete")
    print_coverage()


async def main() -> None:
    args = parse_args()
    validate(args)
    if args.source == "csv":
        backfill_csv(args.csv_path)
    else:
        await backfill_tmdb(args)


if __name__ == "__main__":
    asyncio.run(main())
