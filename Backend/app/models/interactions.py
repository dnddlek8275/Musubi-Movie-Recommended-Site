from sqlalchemy import BigInteger, CheckConstraint, Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from app.core.base import Base


# user_movie_interactions 테이블과 연결되는 ORM 모델
# 조회, 검색 클릭, 좋아요 같은 사용자 행동 이벤트를 저장한다.
class UserMovieInteraction(Base):
    __tablename__ = "user_movie_interactions"

    # action_type과 source에 허용된 값만 저장되도록 제한한다.
    __table_args__ = (
        CheckConstraint(
            "action_type IN ('view', 'search_click', 'like')",
            name="ck_user_movie_interactions_action_type",
        ),
        CheckConstraint(
            "source IN ('direct', 'search', 'recommend', 'ranking', 'admin', 'unknown')",
            name="ck_user_movie_interactions_source",
        ),
    )

    # 사용자-영화 행동 이벤트 고유 ID
    id = Column(BigInteger, primary_key=True, autoincrement=True)

    # 행동을 수행한 사용자 ID
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # 행동 대상 영화 ID
    # 여기에는 tmdb_id가 아니라 movies.id가 들어간다.
    movie_id = Column(BigInteger, ForeignKey("movies.id", ondelete="CASCADE"), nullable=False, index=True)

    # 행동 종류: view, search_click, like
    action_type = Column(String(20), nullable=False)

    # 행동 발생 경로
    source = Column(String(20), server_default="unknown", nullable=False)

    # 행동이 랭킹/추천 점수에 반영되는 값
    score_delta = Column(Integer, nullable=False)

    # 행동 기록 시간
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    # User 모델과 연결
    user = relationship("User", back_populates="interactions")

    # Movie 모델과 연결
    movie = relationship("Movie", back_populates="interactions")
