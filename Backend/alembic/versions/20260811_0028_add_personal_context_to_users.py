"""add optional personal context for AI personalization

Revision ID: 20260811_0028
Revises: 20260810_0027
"""

import sqlalchemy as sa
from alembic import op


revision = "20260811_0028"
down_revision = "20260810_0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("personal_context", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "personal_context")
