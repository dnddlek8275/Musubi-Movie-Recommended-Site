"""create persistent KOBIS movie mappings

Revision ID: 20260808_0025
Revises: 20260807_0024
"""

import sqlalchemy as sa
from alembic import op


revision = "20260808_0025"
down_revision = "20260807_0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "kobis_movie_mappings",
        sa.Column("kobis_movie_code", sa.String(length=20), nullable=False),
        sa.Column("movie_id", sa.BigInteger(), nullable=False),
        sa.Column("tmdb_id", sa.Integer(), nullable=True),
        sa.Column("match_method", sa.String(length=30), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("manually_verified", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["movie_id"], ["movies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("kobis_movie_code"),
    )
    op.create_index("ix_kobis_movie_mappings_movie_id", "kobis_movie_mappings", ["movie_id"])
    op.create_index("ix_kobis_movie_mappings_tmdb_id", "kobis_movie_mappings", ["tmdb_id"])


def downgrade() -> None:
    op.drop_index("ix_kobis_movie_mappings_tmdb_id", table_name="kobis_movie_mappings")
    op.drop_index("ix_kobis_movie_mappings_movie_id", table_name="kobis_movie_mappings")
    op.drop_table("kobis_movie_mappings")
