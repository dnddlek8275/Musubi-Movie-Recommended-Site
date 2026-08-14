"""add review comment to movie ratings

Revision ID: 20260805_0017
Revises: 20260805_0016
Create Date: 2026-08-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260805_0017"
down_revision: str | None = "20260805_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("movie_ratings", sa.Column("comment", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("movie_ratings", "comment")
