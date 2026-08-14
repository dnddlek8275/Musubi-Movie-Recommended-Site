"""sync external profile image and actor tables

Revision ID: 20260706_0007
Revises: 20260703_0004
Create Date: 2026-07-14
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260706_0007"
down_revision: str | None = "20260703_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 로컬 migration 계보를 external의 0007 스키마와 맞춘다.
    op.add_column("users", sa.Column("profile_image", sa.String(length=300), nullable=True))

    op.create_table(
        "actors",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tmdb_actor_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("profile_path", sa.String(length=300), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_actors_tmdb_actor_id", "actors", ["tmdb_actor_id"], unique=True)
    op.create_index("ix_actors_name", "actors", ["name"])

    op.create_table(
        "movie_actors",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("movie_id", sa.BigInteger(), nullable=False),
        sa.Column("actor_id", sa.BigInteger(), nullable=False),
        sa.Column("character_name", sa.String(length=150), nullable=True),
        sa.Column("cast_order", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["movie_id"], ["movies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["actors.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("movie_id", "actor_id", name="uq_movie_actors_movie_actor"),
    )
    op.create_index("ix_movie_actors_movie_id", "movie_actors", ["movie_id"])
    op.create_index("ix_movie_actors_actor_id", "movie_actors", ["actor_id"])


def downgrade() -> None:
    op.drop_index("ix_movie_actors_actor_id", table_name="movie_actors")
    op.drop_index("ix_movie_actors_movie_id", table_name="movie_actors")
    op.drop_table("movie_actors")
    op.drop_index("ix_actors_name", table_name="actors")
    op.drop_index("ix_actors_tmdb_actor_id", table_name="actors")
    op.drop_table("actors")
    op.drop_column("users", "profile_image")
