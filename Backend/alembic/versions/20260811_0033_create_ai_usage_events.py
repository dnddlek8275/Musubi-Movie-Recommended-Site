"""create ai usage events

Revision ID: 20260811_0033
Revises: 20260811_0032
"""

import sqlalchemy as sa
from alembic import op


revision = "20260811_0033"
down_revision = "20260811_0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_usage_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("request_type", sa.String(length=40), nullable=False),
        sa.Column("request_path", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("first_response_ms", sa.Integer(), nullable=True),
        sa.Column("total_duration_ms", sa.Integer(), nullable=False),
        sa.Column("response_bytes", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("model_name", sa.String(length=100), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('success', 'error', 'cancelled')",
            name="ck_ai_usage_events_status",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_usage_events_user_id", "ai_usage_events", ["user_id"])
    op.create_index("ix_ai_usage_events_request_type", "ai_usage_events", ["request_type"])
    op.create_index("ix_ai_usage_events_status", "ai_usage_events", ["status"])
    op.create_index("ix_ai_usage_events_started_at", "ai_usage_events", ["started_at"])


def downgrade() -> None:
    op.drop_index("ix_ai_usage_events_started_at", table_name="ai_usage_events")
    op.drop_index("ix_ai_usage_events_status", table_name="ai_usage_events")
    op.drop_index("ix_ai_usage_events_request_type", table_name="ai_usage_events")
    op.drop_index("ix_ai_usage_events_user_id", table_name="ai_usage_events")
    op.drop_table("ai_usage_events")
