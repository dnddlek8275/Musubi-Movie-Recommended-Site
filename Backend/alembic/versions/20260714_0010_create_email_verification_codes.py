"""create email verification codes

Revision ID: 20260714_0010
Revises: 20260714_0009
Create Date: 2026-07-14
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260714_0010"
down_revision: str | None = "20260714_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')
    op.create_table(
        "email_verification_codes",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("purpose", sa.String(length=30), server_default="signup", nullable=False),
        sa.Column("code_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_email_verification_codes_email"),
        "email_verification_codes",
        ["email"],
        unique=False,
    )
    op.create_index(
        "ix_email_verification_codes_email_purpose_created_at",
        "email_verification_codes",
        ["email", "purpose", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_email_verification_codes_email_purpose_created_at", table_name="email_verification_codes")
    op.drop_index(op.f("ix_email_verification_codes_email"), table_name="email_verification_codes")
    op.drop_table("email_verification_codes")
