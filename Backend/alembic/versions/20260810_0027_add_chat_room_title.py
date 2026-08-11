"""add persisted chat room titles

Revision ID: 20260810_0027
Revises: 20260808_0026
"""

import sqlalchemy as sa
from alembic import op


revision = "20260810_0027"
down_revision = "20260808_0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("chat_rooms", sa.Column("title", sa.String(length=30), nullable=True))


def downgrade() -> None:
    op.drop_column("chat_rooms", "title")
