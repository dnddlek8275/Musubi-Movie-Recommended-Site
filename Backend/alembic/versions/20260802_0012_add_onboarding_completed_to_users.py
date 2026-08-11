"""add onboarding completed to users

Revision ID: 20260802_0012
Revises: 20260714_0011
Create Date: 2026-08-02
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260802_0012"
down_revision: str | None = "20260714_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "onboarding_completed",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    # 온보딩 도입 전에 생성된 계정은 기존 이용 흐름을 유지한다.
    # 마이그레이션 이후 생성되는 계정만 기본값(false)으로 최초 온보딩을 거친다.
    op.execute("UPDATE users SET onboarding_completed = true")


def downgrade() -> None:
    op.drop_column("users", "onboarding_completed")
