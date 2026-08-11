"""create movie ratings

Revision ID: 20260805_0016
Revises: 20260805_0015
Create Date: 2026-08-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260805_0016"
down_revision: str | None = "20260805_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "movie_ratings",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("movie_id", sa.BigInteger(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("score BETWEEN 1 AND 5", name="ck_movie_ratings_score"),
        sa.ForeignKeyConstraint(["movie_id"], ["movies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "movie_id", name="uq_movie_ratings_user_movie"),
    )
    op.create_index("ix_movie_ratings_movie_id", "movie_ratings", ["movie_id"])
    op.create_index("ix_movie_ratings_user_id", "movie_ratings", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_movie_ratings_user_id", table_name="movie_ratings")
    op.drop_index("ix_movie_ratings_movie_id", table_name="movie_ratings")
    op.drop_table("movie_ratings")
