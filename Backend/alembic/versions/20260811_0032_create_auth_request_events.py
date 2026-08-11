"""create auth request events

Revision ID: 20260811_0032
Revises: 20260811_0031
"""

from alembic import op
import sqlalchemy as sa


revision = "20260811_0032"
down_revision = "20260811_0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "auth_request_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("scope", sa.String(length=40), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_auth_request_events_scope_key_created_at",
        "auth_request_events",
        ["scope", "key_hash", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_auth_request_events_scope_key_created_at", table_name="auth_request_events")
    op.drop_table("auth_request_events")
