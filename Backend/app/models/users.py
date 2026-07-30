from sqlalchemy import ARRAY, BigInteger, Boolean, CheckConstraint, Column, DateTime, Float, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import relationship
from app.core.base import Base

# DB의 users 테이블과 연결
class User(Base):
    __tablename__ = "users"

    # 회원 고유 번호
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    # 이메일, 중복 불가
    email = Column(String(255), unique=True, index=True, nullable=False)
    # 비밀번호 해시값
    password_hash = Column(String(255), nullable=False)
    # 닉네임
    nickname = Column(String(50), nullable=False)
    # 사용자가 온보딩/설정에서 선택한 선호 장르 목록
    preferred_genres = Column(ARRAY(String), nullable=True)
    # 사용자가 직접 선호한다고 선택한 배우 목록
    preferred_actors = Column(ARRAY(String), nullable=True)
    # 추천에 참고할 사용자 선호 키워드 목록
    preferred_keywords = Column(ARRAY(String), nullable=True)
    # 관리자 권한 여부. 일반 사용자는 기본값 false
    is_admin = Column(Boolean, server_default="false", nullable=False)
    # 계정 생성 시간
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    # 계정 정보 수정 시간
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    # 사용자 프로필
    profile_image = Column(String(300), nullable=True)

    # 이 사용자가 남긴 영화 행동 기록 목록
    interactions = relationship(
        "UserMovieInteraction",
        back_populates="user",
        passive_deletes=True,
    )
    # 추천 취향 계산에 사용할 사용자별 선호 점수 목록
    preference_scores = relationship(
        "UserPreferenceScore",
        back_populates="user",
        passive_deletes=True,
    )

class UserPreferenceScore(Base):
    __tablename__ = "user_preference_scores"
    __table_args__ = (
        # 저장 가능한 선호 타입을 DB 제약과 ORM 정의에서 동일하게 유지한다.
        CheckConstraint(
            "preference_type IN ('genre', 'actor', 'director', 'keyword', 'language', 'character')",
            name="ck_user_preference_scores_preference_type",
        ),
        # 같은 사용자에게 같은 선호 값은 하나의 row만 두고 score를 누적한다.
        UniqueConstraint("user_id", "preference_type", "preference_value", name="uq_user_preference_scores_value"),
    )

    # 사용자 취향 고유 번호
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    # 사용자 고유 번호. 사용자 삭제 시 해당 취향 점수도 함께 삭제된다.
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    # 취향 축별 타입. 장르/배우/감독/키워드/언어/캐릭터를 구분한다.
    preference_type = Column(String(20), nullable=False)
    # 취향 축별 실제 값. 예: Action, Tom Hanks, ko, 캐릭터 이름 등
    preference_value = Column(String(200), nullable=False)
    # 추천 점수 계산에 사용할 누적 선호 점수
    score = Column(Float, default=0.0, server_default="0", nullable=False)
    # 선호 점수 row 생성 시간
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    # 선호 점수 row 수정 시간
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # User 모델과 양방향으로 연결
    user = relationship("User", back_populates="preference_scores")
