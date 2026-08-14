"""add actor localized name fields

Revision ID: 20260812_0036
Revises: 20260812_0035
"""

from alembic import op
import sqlalchemy as sa


revision = "20260812_0036"
down_revision = "20260812_0035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("actors", sa.Column("original_name", sa.String(length=100), nullable=True))
    op.add_column("actors", sa.Column("korean_name", sa.String(length=100), nullable=True))
    op.add_column("actors", sa.Column("is_korean", sa.Boolean(), nullable=True))
    op.create_index("ix_actors_is_korean", "actors", ["is_korean"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_actors_is_korean", table_name="actors")
    op.drop_column("actors", "is_korean")
    op.drop_column("actors", "korean_name")
    op.drop_column("actors", "original_name")
