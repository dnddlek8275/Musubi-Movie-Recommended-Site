"""create TMDB daily sync runs and vector sync jobs

Revision ID: 20260807_0024
Revises: 20260807_0023
"""

import sqlalchemy as sa
from alembic import op


revision = "20260807_0024"
down_revision = "20260807_0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tmdb_daily_sync_runs",
        sa.Column("sync_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="running", nullable=False),
        sa.Column("changed_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("imported_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("updated_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("deleted_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failed_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("sync_date"),
    )
    op.create_table(
        "movie_vector_sync_jobs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tmdb_id", sa.Integer(), nullable=False),
        sa.Column("movie_id", sa.BigInteger(), nullable=True),
        sa.Column("operation", sa.String(length=10), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["movie_id"], ["movies.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tmdb_id", name="uq_movie_vector_sync_jobs_tmdb_id"),
    )
    op.create_index("ix_movie_vector_sync_jobs_tmdb_id", "movie_vector_sync_jobs", ["tmdb_id"])
    op.create_index("ix_movie_vector_sync_jobs_movie_id", "movie_vector_sync_jobs", ["movie_id"])
    op.create_index("ix_movie_vector_sync_jobs_status", "movie_vector_sync_jobs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_movie_vector_sync_jobs_status", table_name="movie_vector_sync_jobs")
    op.drop_index("ix_movie_vector_sync_jobs_movie_id", table_name="movie_vector_sync_jobs")
    op.drop_index("ix_movie_vector_sync_jobs_tmdb_id", table_name="movie_vector_sync_jobs")
    op.drop_table("movie_vector_sync_jobs")
    op.drop_table("tmdb_daily_sync_runs")
