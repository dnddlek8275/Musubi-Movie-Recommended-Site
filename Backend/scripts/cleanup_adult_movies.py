#!/usr/bin/env python3
"""Audit or delete TMDB-confirmed adult movies from R/unrated local records."""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

from sqlalchemy import or_, select
from sqlalchemy.engine import make_url

from app.core.config import settings
from app.core.dependencies import SessionLocal
from app.models.movies import Movie


LOCAL_DB_HOSTS = {"db", "localhost", "127.0.0.1", "::1"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("export", type=Path, help="TMDB daily movie_ids JSON.gz file")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--allow-nonlocal", action="store_true")
    return parser.parse_args()


def load_adult_ids(path: Path) -> set[int]:
    adult_ids: set[int] = set()
    with gzip.open(path, "rt", encoding="utf-8") as rows:
        for line in rows:
            item = json.loads(line)
            if item.get("adult") is True and isinstance(item.get("id"), int):
                adult_ids.add(item["id"])
    return adult_ids


def main() -> None:
    args = parse_args()
    database_host = make_url(settings.DATABASE_URL).host
    if not args.allow_nonlocal and database_host not in LOCAL_DB_HOSTS:
        raise SystemExit(
            f"Refusing to modify non-local DB host {database_host!r}. "
            "Use --allow-nonlocal only after verifying the target."
        )

    adult_ids = load_adult_ids(args.export)
    with SessionLocal.begin() as session:
        candidates = list(
            session.scalars(
                select(Movie).where(
                    Movie.tmdb_id.in_(adult_ids),
                    or_(
                        Movie.certification.is_(None),
                        Movie.certification == "",
                        (Movie.certification_country == "US")
                        & (Movie.certification.ilike("R")),
                    ),
                )
            ).all()
        )
        candidates.sort(key=lambda movie: (movie.title.casefold(), movie.id))
        r_count = sum(
            movie.certification_country == "US"
            and (movie.certification or "").strip().upper() == "R"
            for movie in candidates
        )
        unrated_count = len(candidates) - r_count
        print(
            f"tmdb_adult_ids={len(adult_ids)}, matched={len(candidates)}, "
            f"r_rated={r_count}, unrated={unrated_count}"
        )
        for movie in candidates:
            print(
                f"  - id={movie.id}, tmdb_id={movie.tmdb_id}, "
                f"certification={movie.certification!r}, title={movie.title}"
            )
        if not args.apply:
            print("Dry-run complete. Re-run with --apply to delete these movies.")
            return
        for movie in candidates:
            session.delete(movie)
        print(f"Delete complete: deleted={len(candidates)}")


if __name__ == "__main__":
    main()
