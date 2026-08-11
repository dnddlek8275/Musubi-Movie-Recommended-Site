from sqlalchemy import BigInteger, CheckConstraint, Column, DateTime, ForeignKey, Integer, String, func

from app.core.base import Base


class AiUsageEvent(Base):
    """한 번의 사용자-facing AI 요청에 대한 운영·요금 산정용 계측값."""

    __tablename__ = "ai_usage_events"
    __table_args__ = (
        CheckConstraint(
            "status IN ('success', 'error', 'cancelled')",
            name="ck_ai_usage_events_status",
        ),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    request_type = Column(String(40), nullable=False, index=True)
    request_path = Column(String(200), nullable=False)
    status = Column(String(20), nullable=False, index=True)
    http_status = Column(Integer, nullable=True)
    first_response_ms = Column(Integer, nullable=True)
    total_duration_ms = Column(Integer, nullable=False)
    response_bytes = Column(BigInteger, nullable=False, default=0, server_default="0")
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    error_code = Column(String(100), nullable=True)
    model_name = Column(String(100), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=False, index=True)
    completed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
