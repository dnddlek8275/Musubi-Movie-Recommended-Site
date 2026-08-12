"""restore official Korean movie titles

Revision ID: 20260812_0035
Revises: 20260811_0034
"""

from __future__ import annotations

import csv
from pathlib import Path

from alembic import op


revision = "20260812_0035"
down_revision = "20260811_0034"
branch_labels = None
depends_on = None


TITLE_DATA_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "official_korean_title_changes_20260812.csv"
)


def _load_titles(column: str) -> dict[int, str]:
    with TITLE_DATA_PATH.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    titles = {
        int(row["tmdb_id"]): row[column].strip()
        for row in rows
        if row.get("tmdb_id") and row.get(column, "").strip()
    }
    if len(titles) != len(rows):
        raise RuntimeError("Korean movie title data contains duplicates or empty values")
    return titles


def _apply_titles(titles: dict[int, str]) -> None:
    connection = op.get_bind()
    for tmdb_id, title in titles.items():
        connection.exec_driver_sql(
            "UPDATE movies SET title = %(title)s, updated_at = now() "
            "WHERE tmdb_id = %(tmdb_id)s",
            {"tmdb_id": tmdb_id, "title": title},
        )

    connection.exec_driver_sql(
        """
        INSERT INTO movie_vector_sync_jobs (
            tmdb_id, movie_id, operation, status, attempts,
            last_error, completed_at, updated_at
        )
        SELECT tmdb_id, id, 'upsert', 'pending', 0, NULL, NULL, now()
        FROM movies
        WHERE tmdb_id = ANY(%(tmdb_ids)s)
        ON CONFLICT (tmdb_id) DO UPDATE SET
            movie_id = EXCLUDED.movie_id,
            operation = 'upsert',
            status = 'pending',
            attempts = 0,
            last_error = NULL,
            completed_at = NULL,
            updated_at = now()
        """,
        {"tmdb_ids": list(titles)},
    )


def upgrade() -> None:
    _apply_titles(_load_titles("localized_title"))


def downgrade() -> None:
    _apply_titles(_load_titles("current_title"))
