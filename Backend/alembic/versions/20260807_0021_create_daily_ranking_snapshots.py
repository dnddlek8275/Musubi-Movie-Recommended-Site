"""create daily movie ranking snapshots

Revision ID: 20260807_0021
Revises: 20260806_0020
"""

import sqlalchemy as sa
from alembic import op


revision = "20260807_0021"
down_revision = "20260806_0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "daily_movie_ranking_snapshots",
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("movie_id", sa.BigInteger(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("rank >= 1 AND rank <= 10", name="ck_daily_movie_ranking_snapshot_rank"),
        sa.ForeignKeyConstraint(["movie_id"], ["movies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("snapshot_date", "movie_id"),
        sa.UniqueConstraint("snapshot_date", "rank", name="uq_daily_movie_ranking_snapshot_rank"),
    )
    op.create_index(
        "ix_daily_movie_ranking_snapshots_date",
        "daily_movie_ranking_snapshots",
        ["snapshot_date"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_daily_movie_ranking_snapshots_date",
        table_name="daily_movie_ranking_snapshots",
    )
    op.drop_table("daily_movie_ranking_snapshots")
