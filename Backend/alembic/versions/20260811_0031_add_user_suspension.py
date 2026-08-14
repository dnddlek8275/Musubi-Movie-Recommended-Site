"""add user suspension

Revision ID: 20260811_0031
Revises: 20260811_0030
"""

import sqlalchemy as sa
from alembic import op


revision = "20260811_0031"
down_revision = "20260811_0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("is_suspended", sa.Boolean(), server_default="false", nullable=False))
    op.add_column("users", sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("suspended_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "suspended_reason")
    op.drop_column("users", "suspended_at")
    op.drop_column("users", "is_suspended")
