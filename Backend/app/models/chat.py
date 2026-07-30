from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import relationship

from app.core.base import Base


# chat_rooms 테이블과 연결되는 모델입니다.
class ChatRoom(Base):
    __tablename__ = "chat_rooms"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    room_type = Column(String(20), nullable=False)
    characters = Column(ARRAY(String), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    messages = relationship("ChatMessage", back_populates="room", cascade="all, delete-orphan")


# chat_messages 테이블과 연결되는 모델입니다.
class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    room_id = Column(
        BigInteger,
        ForeignKey("chat_rooms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(String(20), nullable=False)
    character_name = Column(String(100), nullable=True)
    content = Column(Text, nullable=False)
    recommended_movies = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    room = relationship("ChatRoom", back_populates="messages")
