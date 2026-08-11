from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Index, String, Text, func

from app.core.base import Base


class ContactInquiry(Base):
    """푸터 문의 양식으로 접수된 고객 문의."""

    __tablename__ = "contact_inquiries"
    __table_args__ = (
        Index("ix_contact_inquiries_email_created_at", "email", "created_at"),
        Index("ix_contact_inquiries_user_created_at", "user_id", "created_at"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    category = Column(String(30), nullable=False)
    email = Column(String(255), nullable=False)
    subject = Column(String(120), nullable=False)
    message = Column(Text, nullable=False)
    status = Column(String(20), default="received", server_default="received", nullable=False)
    delivery_status = Column(String(20), default="pending", server_default="pending", nullable=False)
    reply_body = Column(Text, nullable=True)
    reply_delivery_status = Column(String(20), nullable=True)
    replied_by_admin_id = Column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    replied_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
