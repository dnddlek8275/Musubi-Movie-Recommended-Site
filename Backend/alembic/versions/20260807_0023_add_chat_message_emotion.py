"""add chat message emotion

Revision ID: 20260807_0023
Revises: 20260807_0022
"""

import sqlalchemy as sa
from alembic import op


revision = "20260807_0023"
down_revision = "20260807_0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chat_messages",
        sa.Column("emotion", sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("chat_messages", "emotion")
