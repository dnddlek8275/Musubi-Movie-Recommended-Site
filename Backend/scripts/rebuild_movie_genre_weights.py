#!/usr/bin/env python3
"""Recalculate and persist genre weights for every local movie."""

from __future__ import annotations

import argparse

from sqlalchemy import delete, func, insert, select
from sqlalchemy.engine import make_url

from app.core.config import settings
from app.core.dependencies import SessionLocal
from app.models.movies import Movie, MovieGenreWeight
from app.services.movies.genre_relevance import GENRE_WEIGHT_VERSION, genre_relevance_details


LOCAL_DB_HOSTS = {"db", "localhost", "127.0.0.1", "::1"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--allow-nonlocal", action="store_true")
    args = parser.parse_args()
    host = make_url(settings.DATABASE_URL).host
    if not args.allow_nonlocal and host not in LOCAL_DB_HOSTS:
        raise SystemExit(f"Refusing to update non-local DB host {host!r}.")

    with SessionLocal() as session:
        movies = list(session.scalars(select(Movie).order_by(Movie.id)))
        rows = []
        differentiated = 0
        for movie in movies:
            details = genre_relevance_details(movie)
            if details and len({detail["weight"] for detail in details.values()}) > 1:
                differentiated += 1
            rows.extend({
                "movie_id": movie.id,
                "genre": genre,
                "weight": detail["weight"],
                "evidence_count": detail["evidence_count"],
                "calculation_version": GENRE_WEIGHT_VERSION,
            } for genre, detail in details.items())
        print(
            f"movies={len(movies)}, weights={len(rows)}, "
            f"differentiated={differentiated}, version={GENRE_WEIGHT_VERSION}"
        )
        if not args.apply:
            print("Dry-run complete. Re-run with --apply to persist weights.")
            return

    with SessionLocal.begin() as session:
        session.execute(delete(MovieGenreWeight))
        for start in range(0, len(rows), 2000):
            session.execute(insert(MovieGenreWeight), rows[start:start + 2000])
    with SessionLocal() as session:
        stored = session.scalar(select(func.count()).select_from(MovieGenreWeight))
    print(f"Rebuild complete: stored={stored}")


if __name__ == "__main__":
    main()
