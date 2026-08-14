"""add contact inquiry replies

Revision ID: 20260811_0030
Revises: 20260811_0029
"""

import sqlalchemy as sa
from alembic import op


revision = "20260811_0030"
down_revision = "20260811_0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("contact_inquiries", sa.Column("reply_body", sa.Text(), nullable=True))
    op.add_column("contact_inquiries", sa.Column("reply_delivery_status", sa.String(length=20), nullable=True))
    op.add_column("contact_inquiries", sa.Column("replied_by_admin_id", sa.BigInteger(), nullable=True))
    op.add_column("contact_inquiries", sa.Column("replied_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(
        "fk_contact_inquiries_replied_by_admin_id_users",
        "contact_inquiries",
        "users",
        ["replied_by_admin_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_contact_inquiries_replied_by_admin_id_users", "contact_inquiries", type_="foreignkey")
    op.drop_column("contact_inquiries", "replied_at")
    op.drop_column("contact_inquiries", "replied_by_admin_id")
    op.drop_column("contact_inquiries", "reply_delivery_status")
    op.drop_column("contact_inquiries", "reply_body")
