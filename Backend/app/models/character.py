from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import relationship

from app.core.base import Base


class Character(Base):
    __tablename__ = "characters"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    movie_id = Column(BigInteger, ForeignKey("movies.id", ondelete="SET NULL"), nullable=True)
    name = Column(String(100), index=True, nullable=False)
    movie_title = Column(String(200), nullable=False)
    actor = Column(String(100), nullable=True)
    lang = Column(String(10), nullable=False)
    system_prompt = Column(Text, nullable=False)
    profile_image = Column(String(300), nullable=True)
    is_active = Column(Boolean, default=True, server_default="true", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # 이 캐릭터를 부를 수 있는 별칭 목록과 연결한다.
    # 캐릭터가 삭제되면 character_aliases row도 함께 삭제되도록 cascade를 설정한다.
    alias_rows = relationship(
        "CharacterAlias",
        back_populates="character",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    @property
    def aliases(self) -> list[str]:
        # API 응답이나 서비스 로직에서 별칭 row 객체 대신 문자열 목록으로 쓰기 위한 편의 속성.
        return [alias.alias for alias in self.alias_rows]


class CharacterAlias(Base):
    __tablename__ = "character_aliases"

    # 별칭 row의 내부 고유 ID.
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    # 어떤 캐릭터의 별칭인지 연결하는 외래키.
    # characters row가 삭제되면 연결된 별칭도 DB에서 함께 삭제된다.
    character_id = Column(
        BigInteger,
        ForeignKey("characters.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    # 사용자가 자유 채팅에서 입력할 수 있는 별칭.
    # 같은 별칭이 여러 캐릭터로 매핑되지 않도록 unique로 막는다.
    alias = Column(String(100), unique=True, index=True, nullable=False)

    # 별칭에서 원본 캐릭터 객체로 접근할 수 있게 연결한다.
    character = relationship("Character", back_populates="alias_rows")
