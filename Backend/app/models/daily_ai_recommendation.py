from sqlalchemy import BigInteger, CheckConstraint, Column, Date, DateTime, ForeignKey, Integer, Text, UniqueConstraint, func
from sqlalchemy.orm import relationship

from app.core.base import Base


class DailyAiRecommendation(Base):
    __tablename__ = "daily_ai_recommendations"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    recommend_date = Column(Date, nullable=False, unique=True, index=True)
    answer = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    movies = relationship(
        "DailyAiRecommendationMovie",
        back_populates="daily_recommendation",
        cascade="all, delete-orphan",
    )


class DailyAiRecommendationMovie(Base):
    __tablename__ = "daily_ai_recommendation_movies"
    __table_args__ = (
        UniqueConstraint("daily_recommendation_id", "display_order", name="uq_daily_ai_recommendation_movies_order"),
        CheckConstraint("display_order >= 1 AND display_order <= 3", name="ck_daily_ai_recommendation_movies_display_order"),
    )

    daily_recommendation_id = Column(
        BigInteger,
        ForeignKey("daily_ai_recommendations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    movie_id = Column(
        BigInteger,
        ForeignKey("movies.id", ondelete="CASCADE"),
        primary_key=True,
    )
    display_order = Column(Integer, nullable=False)

    daily_recommendation = relationship("DailyAiRecommendation", back_populates="movies")
    movie = relationship("Movie")