"""add wishlist and review spoiler

Revision ID: 20260811_0034
Revises: 20260811_0033
"""

from alembic import op
import sqlalchemy as sa


revision = "20260811_0034"
down_revision = "20260811_0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "movie_ratings",
        sa.Column("is_spoiler", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.create_table(
        "movie_wishlists",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("movie_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["movie_id"], ["movies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "movie_id", name="uq_movie_wishlists_user_movie"),
    )
    op.create_index("ix_movie_wishlists_user_id", "movie_wishlists", ["user_id"])
    op.create_index("ix_movie_wishlists_movie_id", "movie_wishlists", ["movie_id"])


def downgrade() -> None:
    op.drop_index("ix_movie_wishlists_movie_id", table_name="movie_wishlists")
    op.drop_index("ix_movie_wishlists_user_id", table_name="movie_wishlists")
    op.drop_table("movie_wishlists")
    op.drop_column("movie_ratings", "is_spoiler")
