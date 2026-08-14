"""루트 애플리케이션에서 사용하는 SQLAlchemy 모델 모음."""

from app.core.base import Base
from app.models.actors import Actor, MovieActor
from app.models.admin import AdminAuditLog
from app.models.ai_usage import AiUsageEvent
from app.models.character import Character, CharacterAlias
from app.models.chat import ChatMessage, ChatRoom
from app.models.contact import ContactInquiry
from app.models.daily_ai_recommendation import (
    DailyAiRecommendation,
    DailyAiRecommendationMovie,
)
from app.models.interactions import MovieRating, MovieWishlist, UserMovieInteraction
from app.models.movies import Movie, MovieGenre, MovieGenreWeight, MovieStats
from app.models.ranking import DailyBoxOfficeRanking, DailyMovieRankingSnapshot, KobisMovieMapping
from app.models.sync import MovieVectorSyncJob, TmdbDailySyncRun
from app.models.tokens import AuthRequestEvent, EmailVerificationCode, PasswordResetToken, RefreshToken
from app.models.users import User, UserPreferenceScore

__all__ = [
    "Base",
    "Actor",
    "MovieActor",
    "AdminAuditLog",
    "AiUsageEvent",
    "Character",
    "CharacterAlias",
    "ChatMessage",
    "ChatRoom",
    "ContactInquiry",
    "DailyAiRecommendation",
    "DailyAiRecommendationMovie",
    "UserMovieInteraction",
    "MovieRating",
    "MovieWishlist",
    "Movie",
    "MovieGenre",
    "MovieGenreWeight",
    "MovieStats",
    "DailyMovieRankingSnapshot",
    "DailyBoxOfficeRanking",
    "KobisMovieMapping",
    "MovieVectorSyncJob",
    "TmdbDailySyncRun",
    "EmailVerificationCode",
    "AuthRequestEvent",
    "PasswordResetToken",
    "RefreshToken",
    "User",
    "UserPreferenceScore",
]
