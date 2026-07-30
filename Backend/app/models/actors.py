from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import relationship

from app.core.base import Base


# DB의 actors 테이블과 연결
class Actor(Base):
    __tablename__ = "actors"

    # 배우 고유 번호
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    # TMDB에서 제공하는 배우 ID. 외부 API 동기화와 중복 방지에 사용한다.
    tmdb_actor_id = Column(Integer, unique=True, index=True, nullable=True)
    # 배우 이름
    name = Column(String(100), index=True, nullable=False)
    # 배우 프로필 이미지 경로
    profile_path = Column(String(300), nullable=True)
    # 배우 row 생성 시간
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    # 배우 row 수정 시간
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # 이 배우가 출연한 영화 연결 row 목록
    movie_rows = relationship(
        "MovieActor",
        back_populates="actor",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


# DB의 movie_actors 테이블과 연결
# 영화와 배우의 N:M 관계와 배역명, 출연 순서를 저장한다.
class MovieActor(Base):
    __tablename__ = "movie_actors"
    __table_args__ = (
        # 같은 영화에 같은 배우가 중복 저장되지 않도록 DB 레벨에서 막는다.
        UniqueConstraint("movie_id", "actor_id", name="uq_movie_actors_movie_actor"),
    )

    # 영화-배우 연결 row 고유 번호
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    # 연결된 영화 ID. 영화가 삭제되면 연결 row도 함께 삭제된다.
    movie_id = Column(BigInteger, ForeignKey("movies.id", ondelete="CASCADE"), nullable=False, index=True)
    # 연결된 배우 ID. 배우가 삭제되면 연결 row도 함께 삭제된다.
    actor_id = Column(BigInteger, ForeignKey("actors.id", ondelete="CASCADE"), nullable=False, index=True)
    # 영화 안에서 맡은 배역명
    character_name = Column(String(150), nullable=True)
    # 크레딧 출연 순서
    cast_order = Column(Integer, nullable=True)

    # Actor 모델과 양방향으로 연결
    actor = relationship("Actor", back_populates="movie_rows")
