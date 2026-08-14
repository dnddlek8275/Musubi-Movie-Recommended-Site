"""allow half-star movie ratings

Revision ID: 20260813_0037
Revises: 20260812_0036
"""

from alembic import op
import sqlalchemy as sa


revision = "20260813_0037"
down_revision = "20260812_0036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_movie_ratings_score", "movie_ratings", type_="check")
    op.alter_column(
        "movie_ratings",
        "score",
        existing_type=sa.Integer(),
        type_=sa.Numeric(precision=2, scale=1),
        existing_nullable=False,
        postgresql_using="score::numeric(2, 1)",
    )
    op.create_check_constraint(
        "ck_movie_ratings_score",
        "movie_ratings",
        "score BETWEEN 0.5 AND 5 AND score * 2 = floor(score * 2)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_movie_ratings_score", "movie_ratings", type_="check")
    op.alter_column(
        "movie_ratings",
        "score",
        existing_type=sa.Numeric(precision=2, scale=1),
        type_=sa.Integer(),
        existing_nullable=False,
        postgresql_using="round(score)::integer",
    )
    op.create_check_constraint(
        "ck_movie_ratings_score",
        "movie_ratings",
        "score BETWEEN 1 AND 5",
    )
