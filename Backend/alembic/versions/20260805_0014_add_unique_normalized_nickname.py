"""add unique normalized nickname index

Revision ID: 20260805_0014
Revises: 20260804_0013
Create Date: 2026-08-05
"""

from collections.abc import Sequence

from alembic import op


revision: str = "20260805_0014"
down_revision: str | None = "20260804_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "CREATE UNIQUE INDEX uq_users_nickname_normalized "
        "ON users (lower(btrim(nickname)))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_users_nickname_normalized")
