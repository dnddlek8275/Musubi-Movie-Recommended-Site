from sqlalchemy import BigInteger, Column, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import relationship

from app.core.base import Base


class MovieVectorSyncJob(Base):
    __tablename__ = "movie_vector_sync_jobs"
    __table_args__ = (
        UniqueConstraint("tmdb_id", name="uq_movie_vector_sync_jobs_tmdb_id"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tmdb_id = Column(Integer, nullable=False, index=True)
    movie_id = Column(
        BigInteger,
        ForeignKey("movies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    operation = Column(String(10), nullable=False)
    status = Column(String(20), nullable=False, server_default="pending", index=True)
    attempts = Column(Integer, nullable=False, server_default="0")
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    movie = relationship("Movie")


class TmdbDailySyncRun(Base):
    __tablename__ = "tmdb_daily_sync_runs"

    sync_date = Column(Date, primary_key=True)
    status = Column(String(20), nullable=False, server_default="running")
    changed_count = Column(Integer, nullable=False, server_default="0")
    imported_count = Column(Integer, nullable=False, server_default="0")
    updated_count = Column(Integer, nullable=False, server_default="0")
    deleted_count = Column(Integer, nullable=False, server_default="0")
    failed_count = Column(Integer, nullable=False, server_default="0")
    last_error = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
