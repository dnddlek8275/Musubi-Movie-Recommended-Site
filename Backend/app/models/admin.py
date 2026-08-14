from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String, Text, func

from app.core.base import Base


class AdminAuditLog(Base):
    """관리자 데이터 변경 이력을 보관하는 감사 로그."""

    __tablename__ = "admin_audit_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    admin_user_id = Column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    target_table = Column(String(100), nullable=False)
    target_id = Column(BigInteger, nullable=True)
    action = Column(String(50), nullable=False)
    before_data = Column(Text, nullable=True)
    after_data = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
