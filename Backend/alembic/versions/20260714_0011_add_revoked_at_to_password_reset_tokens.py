"""add revoked at to password reset tokens

Revision ID: 20260714_0011
Revises: 20260714_0010
Create Date: 2026-07-14
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260714_0011"
down_revision: str | None = "20260714_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "password_reset_tokens",
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("password_reset_tokens", "revoked_at")
