"""add release date to movies

Revision ID: 20260804_0013
Revises: 20260802_0012
Create Date: 2026-08-04
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260804_0013"
down_revision: str | None = "20260802_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("movies", sa.Column("release_date", sa.Date(), nullable=True))
    op.create_index(
        "ix_movies_release_date",
        "movies",
        ["release_date"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_movies_release_date", table_name="movies")
    op.drop_column("movies", "release_date")
