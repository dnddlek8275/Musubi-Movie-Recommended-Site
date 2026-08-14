from sqlalchemy import BigInteger, Boolean, CheckConstraint, Column, Date, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint, func
from sqlalchemy.orm import relationship

from app.core.base import Base


class DailyMovieRankingSnapshot(Base):
    __tablename__ = "daily_movie_ranking_snapshots"
    __table_args__ = (
        UniqueConstraint("snapshot_date", "rank", name="uq_daily_movie_ranking_snapshot_rank"),
        CheckConstraint("rank >= 1 AND rank <= 10", name="ck_daily_movie_ranking_snapshot_rank"),
    )

    snapshot_date = Column(Date, primary_key=True)
    movie_id = Column(
        BigInteger,
        ForeignKey("movies.id", ondelete="CASCADE"),
        primary_key=True,
    )
    rank = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    movie = relationship("Movie")


class DailyBoxOfficeRanking(Base):
    __tablename__ = "daily_box_office_rankings"
    __table_args__ = (
        UniqueConstraint("box_office_date", "rank", name="uq_daily_box_office_rankings_date_rank"),
        UniqueConstraint("box_office_date", "kobis_movie_code", name="uq_daily_box_office_rankings_date_code"),
        CheckConstraint("rank >= 1 AND rank <= 10", name="ck_daily_box_office_rankings_rank"),
    )

    box_office_date = Column(Date, primary_key=True)
    kobis_movie_code = Column(String(20), primary_key=True)
    rank = Column(Integer, nullable=False)
    movie_id = Column(BigInteger, ForeignKey("movies.id", ondelete="SET NULL"), nullable=True, index=True)
    movie_name = Column(String(300), nullable=False)
    open_date = Column(Date, nullable=True)
    audience_count = Column(BigInteger, nullable=True)
    cumulative_audience_count = Column(BigInteger, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    movie = relationship("Movie")


class KobisMovieMapping(Base):
    __tablename__ = "kobis_movie_mappings"

    kobis_movie_code = Column(String(20), primary_key=True)
    movie_id = Column(BigInteger, ForeignKey("movies.id", ondelete="CASCADE"), nullable=False, index=True)
    tmdb_id = Column(Integer, nullable=True, index=True)
    match_method = Column(String(30), nullable=False)
    evidence = Column(JSON, nullable=False, default=dict)
    manually_verified = Column(Boolean, nullable=False, server_default="false")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    movie = relationship("Movie")
