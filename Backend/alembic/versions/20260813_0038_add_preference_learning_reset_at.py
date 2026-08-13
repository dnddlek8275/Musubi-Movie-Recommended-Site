"""add preference learning reset timestamp

Revision ID: 20260813_0038
Revises: 20260813_0037
"""

from alembic import op
import sqlalchemy as sa


revision = "20260813_0038"
down_revision = "20260813_0037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("preference_learning_reset_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "preference_learning_reset_at")
