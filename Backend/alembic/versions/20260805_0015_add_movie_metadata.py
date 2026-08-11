"""add runtime production countries and certification to movies

Revision ID: 20260805_0015
Revises: 20260805_0014
Create Date: 2026-08-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260805_0015"
down_revision: str | None = "20260805_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("movies", sa.Column("runtime", sa.Integer(), nullable=True))
    op.add_column("movies", sa.Column("production_countries", sa.ARRAY(sa.String(length=2)), nullable=True))
    op.add_column("movies", sa.Column("certification", sa.String(length=20), nullable=True))
    op.add_column("movies", sa.Column("certification_country", sa.String(length=2), nullable=True))


def downgrade() -> None:
    op.drop_column("movies", "certification_country")
    op.drop_column("movies", "certification")
    op.drop_column("movies", "production_countries")
    op.drop_column("movies", "runtime")
