#!/usr/bin/env python3
"""Import movies_final.csv into the local Musubi PostgreSQL database."""

from __future__ import annotations

import argparse
import csv
from datetime import date
from pathlib import Path

from sqlalchemy import delete, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import make_url

from app.core.config import settings
from app.core.dependencies import SessionLocal
from app.models.movies import Movie, MovieGenre, MovieGenreWeight, MovieStats
from app.services.admin.tmdb_register_service import require_non_explicit_metadata
from app.services.movies.genre_relevance import GENRE_WEIGHT_VERSION, genre_relevance_details


REQUIRED_COLUMNS = {
    "adult",
    "tmdb_id",
    "title",
    "language",
    "genres",
    "overview",
    "director",
    "cast",
    "vote_average",
    "vote_count",
    "poster_path",
    "audience_count",
    "개봉연도",
    "release_date",
    "runtime",
}
LOCAL_DB_HOSTS = {"db", "localhost", "127.0.0.1", "::1"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import movies_final.csv into movies, movie_genres, and movie_stats.",
    )
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--limit", type=int)
    parser.add_argument(
        "--allow-nonlocal",
        action="store_true",
        help="Allow importing into a DB host other than db/localhost. Do not use casually.",
    )
    return parser.parse_args()


def optional_text(value: str | None) -> str | None:
    normalized = (value or "").strip()
    return normalized or None


def string_list(value: str | None) -> list[str] | None:
    items = list(dict.fromkeys(
        item.strip() for item in (value or "").split(",") if item.strip()
    ))
    return items or None


def optional_int(value: str | None) -> int | None:
    normalized = (value or "").strip()
    return int(float(normalized)) if normalized else None


def optional_float(value: str | None) -> float | None:
    normalized = (value or "").strip()
    return float(normalized) if normalized else None


def optional_date(value: str | None) -> date | None:
    normalized = (value or "").strip()
    if not normalized:
        return None
    try:
        return date.fromisoformat(normalized)
    except ValueError:
        return None


def require_adult_false(value: str | None, tmdb_id: str) -> None:
    normalized = (value or "").strip().casefold()
    if normalized not in {"false", "0"}:
        raise ValueError(
            f"TMDB {tmdb_id}: CSV adult 값이 false인 영화만 가져올 수 있습니다."
        )


def movie_values(row: dict[str, str]) -> dict:
    require_adult_false(row.get("adult"), row.get("tmdb_id", ""))
    values = {
        "tmdb_id": int(row["tmdb_id"]),
        "title": row["title"].strip(),
        "overview": optional_text(row["overview"]),
        "genres": string_list(row["genres"]),
        "director": optional_text(row["director"]),
        "cast": string_list(row["cast"]),
        "keywords": string_list(row.get("keywords")),
        "year": optional_int(row["개봉연도"]),
        "release_date": optional_date(row["release_date"]),
        "runtime": optional_int(row["runtime"]),
        "language": optional_text(row["language"]),
        "vote_average": optional_float(row["vote_average"]),
        "vote_count": optional_int(row["vote_count"]),
        "audience_count": optional_int(row["audience_count"]),
        "poster_path": optional_text(row["poster_path"]),
    }
    require_non_explicit_metadata(
        values["keywords"] or [],
        optional_text(row.get("certification")),
        optional_text(row.get("certification_country")),
        values["overview"],
        values["title"],
        values["genres"] or [],
    )
    return values


def import_batch(rows: list[dict]) -> tuple[int, int]:
    movie_table = Movie.__table__
    genre_table = MovieGenre.__table__
    stats_table = MovieStats.__table__
    genre_weight_table = MovieGenreWeight.__table__

    statement = insert(movie_table).values(rows)
    update_columns = {
        column: getattr(statement.excluded, column)
        for column in (
            "title",
            "overview",
            "genres",
            "director",
            "cast",
            "keywords",
            "year",
            "release_date",
            "runtime",
            "language",
            "vote_average",
            "vote_count",
            "audience_count",
            "poster_path",
        )
    }
    update_columns["updated_at"] = func.now()
    statement = statement.on_conflict_do_update(
        index_elements=[movie_table.c.tmdb_id],
        set_=update_columns,
    ).returning(movie_table.c.id, movie_table.c.tmdb_id)

    with SessionLocal.begin() as session:
        ids_by_tmdb = dict(
            (tmdb_id, movie_id)
            for movie_id, tmdb_id in session.execute(statement)
        )
        movie_ids = list(ids_by_tmdb.values())

        session.execute(
            delete(genre_table).where(genre_table.c.movie_id.in_(movie_ids))
        )
        genre_rows = [
            {"movie_id": ids_by_tmdb[row["tmdb_id"]], "genre": genre}
            for row in rows
            for genre in (row["genres"] or [])
        ]
        if genre_rows:
            session.execute(insert(genre_table), genre_rows)

        session.execute(
            delete(genre_weight_table).where(genre_weight_table.c.movie_id.in_(movie_ids))
        )
        weight_rows = []
        for row in rows:
            movie_like = type("MovieMetadata", (), row)()
            for genre, detail in genre_relevance_details(movie_like).items():
                weight_rows.append({
                    "movie_id": ids_by_tmdb[row["tmdb_id"]],
                    "genre": genre,
                    "weight": detail["weight"],
                    "evidence_count": detail["evidence_count"],
                    "calculation_version": GENRE_WEIGHT_VERSION,
                })
        if weight_rows:
            session.execute(insert(genre_weight_table), weight_rows)

        stats_statement = insert(stats_table).values(
            [{"movie_id": movie_id} for movie_id in movie_ids]
        ).on_conflict_do_nothing(index_elements=[stats_table.c.movie_id])
        session.execute(stats_statement)

    return len(rows), len(genre_rows)


def main() -> None:
    args = parse_args()
    if args.batch_size < 1:
        raise SystemExit("--batch-size must be at least 1.")
    if args.limit is not None and args.limit < 1:
        raise SystemExit("--limit must be at least 1.")

    database_host = make_url(settings.DATABASE_URL).host
    if not args.allow_nonlocal and database_host not in LOCAL_DB_HOSTS:
        raise SystemExit(
            f"Refusing to import into non-local DB host {database_host!r}. "
            "Use --allow-nonlocal only after verifying the target."
        )

    if not args.csv_path.is_file():
        raise SystemExit(f"CSV file not found: {args.csv_path}")

    imported_movies = 0
    imported_genres = 0
    batch: list[dict] = []

    with args.csv_path.open(encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        missing_columns = REQUIRED_COLUMNS.difference(reader.fieldnames or [])
        if missing_columns:
            raise SystemExit(
                f"CSV is missing required columns: {', '.join(sorted(missing_columns))}"
            )

        for source_row in reader:
            batch.append(movie_values(source_row))
            if len(batch) >= args.batch_size:
                movie_count, genre_count = import_batch(batch)
                imported_movies += movie_count
                imported_genres += genre_count
                print(f"Imported {imported_movies:,} movies...", flush=True)
                batch.clear()

            if args.limit is not None and imported_movies + len(batch) >= args.limit:
                break

    if batch:
        movie_count, genre_count = import_batch(batch)
        imported_movies += movie_count
        imported_genres += genre_count

    print(
        f"Import complete: {imported_movies:,} movies, "
        f"{imported_genres:,} movie_genres synchronized."
    )


if __name__ == "__main__":
    main()
