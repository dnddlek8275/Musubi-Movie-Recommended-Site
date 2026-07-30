"""initial schema

Revision ID: 20260616_0001
Revises:
Create Date: 2026-06-16
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260616_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 초기 마이그레이션은 기획 확정 스키마를 새 DB에 한 번에 구성한다.
    # users: 로그인 계정, 프로필, 추천 선호도, 관리자 여부를 저장하는 기본 사용자 테이블.
    op.create_table(
        "users",
        # id: 사용자 행을 식별하는 내부 기본키.
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        # email: 로그인과 계정 식별에 사용하는 이메일 주소.
        sa.Column("email", sa.String(length=255), nullable=False),
        # password_hash: 원문 비밀번호가 아니라 해시된 비밀번호 값.
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        # nickname: 서비스 화면에 표시할 사용자 이름.
        sa.Column("nickname", sa.String(length=50), nullable=False),
        # preferred_genres: 온보딩/설정에서 사용자가 선택한 선호 장르 목록.
        sa.Column("preferred_genres", postgresql.ARRAY(sa.String()), nullable=True),
        # preferred_actors: 사용자가 선호한다고 명시한 배우 이름 목록.
        sa.Column("preferred_actors", postgresql.ARRAY(sa.String()), nullable=True),
        # preferred_keywords: 추천에 참고할 사용자 선호 키워드 목록.
        sa.Column("preferred_keywords", postgresql.ARRAY(sa.String()), nullable=True),
        # is_admin: 관리자 권한 여부. 기본값은 일반 사용자(false).
        sa.Column("is_admin", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        # created_at: 사용자 계정이 생성된 시각.
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        # updated_at: 사용자 계정 정보가 마지막으로 수정된 시각.
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    # 이메일은 로그인 식별자로 쓰이므로 중복을 막기 위해 unique index를 둔다.
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # movies: TMDB 동기화 데이터와 추천/검색에 필요한 영화 메타데이터를 저장한다.
    op.create_table(
        "movies",
        # id: 영화 행을 식별하는 내부 기본키.
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        # tmdb_id: 외부 TMDB API에서 제공하는 영화 식별자.
        sa.Column("tmdb_id", sa.Integer(), nullable=True),
        # title: 영화 제목.
        sa.Column("title", sa.String(length=300), nullable=False),
        # overview: 영화 줄거리/소개 문구.
        sa.Column("overview", sa.Text(), nullable=True),
        # genres: 영화 장르 목록.
        sa.Column("genres", postgresql.ARRAY(sa.String()), nullable=True),
        # director: 대표 감독 이름.
        sa.Column("director", sa.String(length=200), nullable=True),
        # cast: 주요 출연 배우 이름 목록.
        sa.Column("cast", postgresql.ARRAY(sa.String()), nullable=True),
        # keywords: 추천/검색에 활용할 영화 키워드 목록.
        sa.Column("keywords", postgresql.ARRAY(sa.String()), nullable=True),
        # year: 개봉 연도.
        sa.Column("year", sa.Integer(), nullable=True),
        # language: 영화 원어 또는 대표 언어 코드.
        sa.Column("language", sa.String(length=10), nullable=True),
        # vote_average: TMDB 등 외부 데이터의 평균 평점.
        sa.Column("vote_average", sa.Float(), nullable=True),
        # vote_count: 평균 평점 산정에 사용된 투표 수.
        sa.Column("vote_count", sa.Integer(), nullable=True),
        # audience_count: 관객 수 또는 서비스에서 수집한 관객 규모 정보.
        sa.Column("audience_count", sa.BigInteger(), nullable=True),
        # poster_path: 포스터 이미지 경로 또는 URL.
        sa.Column("poster_path", sa.String(length=300), nullable=True),
        # last_synced_at: 외부 영화 정보를 마지막으로 동기화한 시각.
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        # created_at: 영화 행이 DB에 생성된 시각.
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        # updated_at: 영화 정보가 마지막으로 수정된 시각.
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    # 제목 검색과 TMDB 중복 적재 방지를 위해 조회용/고유 인덱스를 각각 생성한다.
    op.create_index("ix_movies_title", "movies", ["title"])
    op.create_index("ix_movies_tmdb_id", "movies", ["tmdb_id"], unique=True)

    # characters: 영화 캐릭터 챗봇에 필요한 인물 정보와 시스템 프롬프트를 저장한다.
    # 연결된 영화가 삭제되어도 캐릭터 자체는 남길 수 있도록 movie_id는 SET NULL로 처리한다.
    op.create_table(
        "characters",
        # id: 캐릭터 행을 식별하는 내부 기본키.
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        # movie_id: 캐릭터가 연결된 movies.id. 연결 영화 삭제 시 NULL로 바뀐다.
        sa.Column("movie_id", sa.BigInteger(), sa.ForeignKey("movies.id", ondelete="SET NULL"), nullable=True),
        # name: 캐릭터 이름.
        sa.Column("name", sa.String(length=100), nullable=False),
        # movie_title: 화면 표시와 검색 보조용 영화 제목 스냅샷.
        sa.Column("movie_title", sa.String(length=200), nullable=False),
        # actor: 해당 캐릭터를 연기한 배우 이름.
        sa.Column("actor", sa.String(length=100), nullable=True),
        # lang: 캐릭터 응답에 사용할 언어 코드.
        sa.Column("lang", sa.String(length=10), nullable=False),
        # system_prompt: 캐릭터 말투와 설정을 정의하는 LLM 시스템 프롬프트.
        sa.Column("system_prompt", sa.Text(), nullable=False),
        # profile_image: 캐릭터 프로필 이미지 경로 또는 URL.
        sa.Column("profile_image", sa.String(length=300), nullable=True),
        # is_active: 캐릭터를 서비스에 노출할지 여부.
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        # created_at: 캐릭터 행이 생성된 시각.
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        # updated_at: 캐릭터 정보가 마지막으로 수정된 시각.
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    # 캐릭터 이름 기반 목록/검색 화면을 빠르게 열기 위한 인덱스.
    op.create_index("ix_characters_name", "characters", ["name"])

    # chat_rooms: 사용자가 만든 일반/캐릭터/그룹 채팅방을 저장한다.
    # 사용자가 삭제되면 해당 사용자의 채팅방도 함께 삭제된다.
    op.create_table(
        "chat_rooms",
        # id: 채팅방 행을 식별하는 내부 기본키.
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        # user_id: 채팅방을 소유한 users.id. 사용자 삭제 시 채팅방도 삭제된다.
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        # room_type: 일반, 캐릭터, 그룹 채팅방을 구분하는 값.
        sa.Column("room_type", sa.String(length=20), nullable=False),
        # characters: 캐릭터/그룹 채팅에 참여하는 캐릭터 이름 목록.
        sa.Column("characters", postgresql.ARRAY(sa.String()), nullable=True),
        # created_at: 채팅방이 생성된 시각.
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        # updated_at: 채팅방 정보가 마지막으로 수정된 시각.
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("room_type IN ('general', 'character', 'group')", name="ck_chat_rooms_room_type"),
    )
    # 사용자별 채팅방 목록 조회를 위한 인덱스.
    op.create_index("ix_chat_rooms_user_id", "chat_rooms", ["user_id"])

    # chat_messages: 채팅방 안의 사용자/assistant 메시지를 시간순으로 저장한다.
    # 채팅방이 삭제되면 메시지도 함께 삭제되어 고아 메시지가 남지 않는다.
    op.create_table(
        "chat_messages",
        # id: 메시지 행을 식별하는 내부 기본키.
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        # room_id: 메시지가 속한 chat_rooms.id. 채팅방 삭제 시 메시지도 삭제된다.
        sa.Column("room_id", sa.BigInteger(), sa.ForeignKey("chat_rooms.id", ondelete="CASCADE"), nullable=False),
        # role: 메시지 작성 주체. 사용자(user) 또는 assistant만 허용된다.
        sa.Column("role", sa.String(length=20), nullable=False),
        # character_name: assistant 메시지일 때 응답한 캐릭터 이름.
        sa.Column("character_name", sa.String(length=100), nullable=True),
        # content: 실제 채팅 메시지 본문.
        sa.Column("content", sa.Text(), nullable=False),
        # created_at: 메시지가 생성된 시각.
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("role IN ('user', 'assistant')", name="ck_chat_messages_role"),
    )
    # 채팅방별 메시지 조회 성능을 위한 인덱스.
    op.create_index("ix_chat_messages_room_id", "chat_messages", ["room_id"])

    # user_movie_interactions: 조회, 검색 클릭, 좋아요 같은 사용자 행동 이벤트를 누적 기록한다.
    # 추천 점수와 영화 통계 계산의 원천 데이터로 사용된다.
    op.create_table(
        "user_movie_interactions",
        # id: 사용자-영화 행동 이벤트를 식별하는 내부 기본키.
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        # user_id: 행동을 수행한 users.id. 사용자 삭제 시 이벤트도 삭제된다.
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        # movie_id: 행동 대상 movies.id. 영화 삭제 시 이벤트도 삭제된다.
        sa.Column("movie_id", sa.BigInteger(), sa.ForeignKey("movies.id", ondelete="CASCADE"), nullable=False),
        # action_type: 사용자가 수행한 행동 종류.
        sa.Column("action_type", sa.String(length=20), nullable=False),
        # source: 행동이 발생한 진입 경로. 값이 없으면 unknown으로 저장된다.
        sa.Column("source", sa.String(length=20), server_default="unknown", nullable=False),
        # score_delta: 해당 행동이 추천 선호도나 랭킹 점수에 반영되는 가중치.
        sa.Column("score_delta", sa.Integer(), nullable=False),
        # created_at: 행동 이벤트가 발생/기록된 시각.
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("action_type IN ('view', 'search_click', 'like')", name="ck_user_movie_interactions_action_type"),
        sa.CheckConstraint(
            "source IN ('direct', 'search', 'recommend', 'ranking', 'admin', 'unknown')",
            name="ck_user_movie_interactions_source",
        ),
    )
    # 사용자/영화/시간 기준 집계와 최근 행동 조회를 위해 각각 인덱스를 둔다.
    op.create_index("ix_user_movie_interactions_user_id", "user_movie_interactions", ["user_id"])
    op.create_index("ix_user_movie_interactions_movie_id", "user_movie_interactions", ["movie_id"])
    op.create_index("ix_user_movie_interactions_created_at", "user_movie_interactions", ["created_at"])

    # user_preference_scores: 사용자별 장르, 배우, 감독, 키워드, 언어 선호 점수를 저장한다.
    # 같은 사용자의 같은 선호 항목은 하나의 점수 행만 갖도록 unique constraint를 둔다.
    op.create_table(
        "user_preference_scores",
        # id: 사용자 선호 점수 행을 식별하는 내부 기본키.
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        # user_id: 선호 점수가 속한 users.id. 사용자 삭제 시 점수도 삭제된다.
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        # preference_type: 선호 항목의 종류. 장르, 배우, 감독, 키워드, 언어 중 하나.
        sa.Column("preference_type", sa.String(length=20), nullable=False),
        # preference_value: 실제 선호 값. 예: Action, Tom Hanks, ko 등.
        sa.Column("preference_value", sa.String(length=200), nullable=False),
        # score: 사용자의 해당 선호 값에 대한 누적 점수.
        sa.Column("score", sa.Float(), server_default="0", nullable=False),
        # created_at: 선호 점수 행이 처음 생성된 시각.
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        # updated_at: 선호 점수가 마지막으로 갱신된 시각.
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "preference_type IN ('genre', 'actor', 'director', 'keyword', 'language')",
            name="ck_user_preference_scores_preference_type",
        ),
        sa.UniqueConstraint("user_id", "preference_type", "preference_value", name="uq_user_preference_scores_value"),
    )
    # 사용자별 선호 점수 전체를 빠르게 읽기 위한 인덱스.
    op.create_index("ix_user_preference_scores_user_id", "user_preference_scores", ["user_id"])

    # movie_stats: 영화별 행동 집계와 랭킹 점수를 캐시한다.
    # movie_id를 기본키로 사용해 movies와 1:1 관계를 만든다.
    op.create_table(
        "movie_stats",
        # movie_id: 통계를 집계할 movies.id이자 이 테이블의 기본키.
        sa.Column("movie_id", sa.BigInteger(), sa.ForeignKey("movies.id", ondelete="CASCADE"), primary_key=True),
        # view_count: 영화 상세 조회 횟수 누적값.
        sa.Column("view_count", sa.Integer(), server_default="0", nullable=False),
        # search_click_count: 검색 결과에서 영화가 클릭된 횟수 누적값.
        sa.Column("search_click_count", sa.Integer(), server_default="0", nullable=False),
        # like_count: 사용자가 좋아요를 누른 횟수 누적값.
        sa.Column("like_count", sa.Integer(), server_default="0", nullable=False),
        # ranking_score: 랭킹 정렬에 사용할 종합 점수.
        sa.Column("ranking_score", sa.Integer(), server_default="0", nullable=False),
        # created_at: 영화 통계 행이 생성된 시각.
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        # updated_at: 영화 통계 값이 마지막으로 갱신된 시각.
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    # 랭킹 화면에서 높은 점수 순으로 정렬/조회할 때 쓰는 인덱스.
    op.create_index("ix_movie_stats_ranking_score", "movie_stats", ["ranking_score"])

    # admin_audit_logs: 관리자가 데이터 변경 작업을 했을 때 변경 전후 내용을 남기는 감사 로그.
    # 관리자 계정이 삭제되어도 로그는 보존하기 위해 admin_user_id는 SET NULL로 처리한다.
    op.create_table(
        "admin_audit_logs",
        # id: 감사 로그 행을 식별하는 내부 기본키.
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        # admin_user_id: 작업을 수행한 관리자 users.id. 계정 삭제 시 NULL로 바뀐다.
        sa.Column("admin_user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        # target_table: 관리자가 변경한 대상 테이블 이름.
        sa.Column("target_table", sa.String(length=100), nullable=False),
        # target_id: 변경 대상 행의 id. 대상이 특정 행이 아닐 수 있어 nullable이다.
        sa.Column("target_id", sa.BigInteger(), nullable=True),
        # action: 생성, 수정, 삭제 등 관리자가 수행한 작업 이름.
        sa.Column("action", sa.String(length=50), nullable=False),
        # before_data: 변경 전 데이터를 문자열로 저장한 값.
        sa.Column("before_data", sa.Text(), nullable=True),
        # after_data: 변경 후 데이터를 문자열로 저장한 값.
        sa.Column("after_data", sa.Text(), nullable=True),
        # created_at: 감사 로그가 기록된 시각.
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    # downgrade는 upgrade의 역순으로 삭제한다.
    # 외래키를 참조하는 자식 테이블부터 제거해야 참조 무결성 오류가 나지 않는다.
    op.drop_table("admin_audit_logs")
    op.drop_index("ix_movie_stats_ranking_score", table_name="movie_stats")
    op.drop_table("movie_stats")
    op.drop_index("ix_user_preference_scores_user_id", table_name="user_preference_scores")
    op.drop_table("user_preference_scores")
    op.drop_index("ix_user_movie_interactions_created_at", table_name="user_movie_interactions")
    op.drop_index("ix_user_movie_interactions_movie_id", table_name="user_movie_interactions")
    op.drop_index("ix_user_movie_interactions_user_id", table_name="user_movie_interactions")
    op.drop_table("user_movie_interactions")
    op.drop_index("ix_chat_messages_room_id", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_index("ix_chat_rooms_user_id", table_name="chat_rooms")
    op.drop_table("chat_rooms")
    op.drop_index("ix_characters_name", table_name="characters")
    op.drop_table("characters")
    op.drop_index("ix_movies_tmdb_id", table_name="movies")
    op.drop_index("ix_movies_title", table_name="movies")
    op.drop_table("movies")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
