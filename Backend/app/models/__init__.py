"""루트 애플리케이션에서 사용하는 SQLAlchemy 모델 모음."""

from app.core.base import Base
from app.models.actors import Actor, MovieActor
from app.models.admin import AdminAuditLog
from app.models.character import Character, CharacterAlias
from app.models.chat import ChatMessage, ChatRoom
from app.models.daily_ai_recommendation import (
    DailyAiRecommendation,
    DailyAiRecommendationMovie,
)
from app.models.interactions import UserMovieInteraction
from app.models.movies import Movie, MovieGenre, MovieStats
from app.models.tokens import EmailVerificationCode, PasswordResetToken, RefreshToken
from app.models.users import User, UserPreferenceScore

__all__ = [
    "Base",
    "Actor",
    "MovieActor",
    "AdminAuditLog",
    "Character",
    "CharacterAlias",
    "ChatMessage",
    "ChatRoom",
    "DailyAiRecommendation",
    "DailyAiRecommendationMovie",
    "UserMovieInteraction",
    "Movie",
    "MovieGenre",
    "MovieStats",
    "EmailVerificationCode",
    "PasswordResetToken",
    "RefreshToken",
    "User",
    "UserPreferenceScore",
]
