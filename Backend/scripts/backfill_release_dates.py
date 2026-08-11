#!/usr/bin/env python3
"""Fill missing movie release dates from movies_final.csv without replacing other data."""

from __future__ import annotations

import argparse
import csv
from datetime import date
from pathlib import Path

from sqlalchemy import bindparam, func, select
from sqlalchemy.engine import make_url

from app.core.config import settings
from app.core.dependencies import SessionLocal
from app.models.movies import Movie


LOCAL_DB_HOSTS = {"db", "localhost", "127.0.0.1", "::1"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fill only NULL movies.release_date values from a CSV file.",
    )
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--allow-nonlocal", action="store_true")
    return parser.parse_args()


def parse_release_date(value: str | None) -> date | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def main() -> None:
    args = parse_args()
    db_host = make_url(settings.DATABASE_URL).host
    if db_host not in LOCAL_DB_HOSTS and not args.allow_nonlocal:
        raise SystemExit(
            f"Refusing to update non-local DB host {db_host!r}; pass --allow-nonlocal explicitly."
        )

    with args.csv_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not {"tmdb_id", "release_date"}.issubset(reader.fieldnames or []):
            raise SystemExit("CSV must contain tmdb_id and release_date columns.")
        rows = []
        for row in reader:
            release_date = parse_release_date(row.get("release_date"))
            tmdb_id = (row.get("tmdb_id") or "").strip()
            if tmdb_id and release_date:
                rows.append({"p_tmdb_id": int(float(tmdb_id)), "p_release_date": release_date})

    statement = (
        Movie.__table__.update()
        .where(Movie.tmdb_id == bindparam("p_tmdb_id"))
        .where(Movie.release_date.is_(None))
        .values(release_date=bindparam("p_release_date"))
    )
    updated = 0
    with SessionLocal.begin() as session:
        for start in range(0, len(rows), args.batch_size):
            result = session.execute(statement, rows[start:start + args.batch_size])
            updated += max(result.rowcount, 0)

    with SessionLocal() as session:
        total = session.scalar(select(func.count(Movie.id))) or 0
        dated = session.scalar(
            select(func.count(Movie.id)).where(Movie.release_date.is_not(None))
        ) or 0
    print(f"CSV usable rows: {len(rows):,}")
    print(f"Updated missing release dates: {updated:,}")
    print(f"Database coverage: {dated:,}/{total:,} ({dated / total:.1%})" if total else "Database is empty")


if __name__ == "__main__":
    main()
