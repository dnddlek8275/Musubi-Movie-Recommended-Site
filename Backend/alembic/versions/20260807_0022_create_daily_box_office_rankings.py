"""create daily KOBIS box office rankings

Revision ID: 20260807_0022
Revises: 20260807_0021
"""

import sqlalchemy as sa
from alembic import op


revision = "20260807_0022"
down_revision = "20260807_0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "daily_box_office_rankings",
        sa.Column("box_office_date", sa.Date(), nullable=False),
        sa.Column("kobis_movie_code", sa.String(length=20), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("movie_id", sa.BigInteger(), nullable=True),
        sa.Column("movie_name", sa.String(length=300), nullable=False),
        sa.Column("open_date", sa.Date(), nullable=True),
        sa.Column("audience_count", sa.BigInteger(), nullable=True),
        sa.Column("cumulative_audience_count", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("rank >= 1 AND rank <= 10", name="ck_daily_box_office_rankings_rank"),
        sa.ForeignKeyConstraint(["movie_id"], ["movies.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("box_office_date", "kobis_movie_code"),
        sa.UniqueConstraint("box_office_date", "rank", name="uq_daily_box_office_rankings_date_rank"),
        sa.UniqueConstraint("box_office_date", "kobis_movie_code", name="uq_daily_box_office_rankings_date_code"),
    )
    op.create_index(
        "ix_daily_box_office_rankings_date",
        "daily_box_office_rankings",
        ["box_office_date"],
    )
    op.create_index(
        "ix_daily_box_office_rankings_movie_id",
        "daily_box_office_rankings",
        ["movie_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_daily_box_office_rankings_movie_id", table_name="daily_box_office_rankings")
    op.drop_index("ix_daily_box_office_rankings_date", table_name="daily_box_office_rankings")
    op.drop_table("daily_box_office_rankings")
