"""create movie genre weights

Revision ID: 20260806_0019
Revises: 20260805_0018
"""

from alembic import op
import sqlalchemy as sa


revision = "20260806_0019"
down_revision = "20260805_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "movie_genre_weights",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("movie_id", sa.BigInteger(), nullable=False),
        sa.Column("genre", sa.String(length=50), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column("evidence_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("calculation_version", sa.String(length=50), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("weight >= 0 AND weight <= 1", name="ck_movie_genre_weights_weight"),
        sa.CheckConstraint("evidence_count >= 0", name="ck_movie_genre_weights_evidence_count"),
        sa.ForeignKeyConstraint(["movie_id"], ["movies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("movie_id", "genre", name="uq_movie_genre_weights_movie_genre"),
    )
    op.create_index("ix_movie_genre_weights_movie_id", "movie_genre_weights", ["movie_id"])
    op.create_index("ix_movie_genre_weights_genre", "movie_genre_weights", ["genre"])
    op.create_index("ix_movie_genre_weights_weight", "movie_genre_weights", ["weight"])
    op.create_index(
        "ix_movie_genre_weights_genre_weight",
        "movie_genre_weights",
        ["genre", "weight"],
    )


def downgrade() -> None:
    op.drop_table("movie_genre_weights")
