"""create contact inquiries

Revision ID: 20260811_0029
Revises: 20260811_0028
"""

import sqlalchemy as sa
from alembic import op


revision = "20260811_0029"
down_revision = "20260811_0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "contact_inquiries",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("category", sa.String(length=30), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("subject", sa.String(length=120), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="received", nullable=False),
        sa.Column("delivery_status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_contact_inquiries_email_created_at", "contact_inquiries", ["email", "created_at"])
    op.create_index("ix_contact_inquiries_user_created_at", "contact_inquiries", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_contact_inquiries_user_created_at", table_name="contact_inquiries")
    op.drop_index("ix_contact_inquiries_email_created_at", table_name="contact_inquiries")
    op.drop_table("contact_inquiries")
