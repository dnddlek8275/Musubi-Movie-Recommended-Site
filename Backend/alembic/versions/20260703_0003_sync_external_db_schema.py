"""sync external db schema

Revision ID: 20260703_0003
Revises: 20260702_0002
Create Date: 2026-07-03
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260703_0003"
down_revision: str | None = "20260702_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 캐릭터 기반 취향 학습을 기존 취향 점수 테이블에 함께 저장할 수 있게 허용한다.
    # 기존 제약은 character 타입을 허용하지 않으므로 같은 이름의 check constraint를 교체한다.
    op.drop_constraint(
        "ck_user_preference_scores_preference_type",
        "user_preference_scores",
        type_="check",
    )
    op.create_check_constraint(
        "ck_user_preference_scores_preference_type",
        "user_preference_scores",
        "preference_type IN ('genre', 'actor', 'director', 'keyword', 'language', 'character')",
    )

    # 장르별 검색/추천/집계를 위해 movies.genres 배열을 별도 row 테이블로 정규화한다.
    op.create_table(
        "movie_genres",
        # id: 장르 row를 식별하는 내부 기본키.
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        # movie_id: 장르가 연결된 movies.id. 영화 삭제 시 장르 row도 함께 삭제된다.
        sa.Column("movie_id", sa.BigInteger(), nullable=False),
        # genre: 검색/추천/집계에 직접 사용할 단일 장르명.
        sa.Column("genre", sa.String(length=50), nullable=False),
        sa.ForeignKeyConstraint(["movie_id"], ["movies.id"], ondelete="CASCADE"),
        # 한 영화에 같은 장르가 중복 저장되지 않도록 막는다.
        sa.UniqueConstraint("movie_id", "genre", name="uq_movie_genres_movie_genre"),
    )
    # 영화별 장르 목록 조회와 장르명 기반 검색을 각각 빠르게 하기 위한 인덱스.
    op.create_index("ix_movie_genres_movie_id", "movie_genres", ["movie_id"])
    op.create_index("ix_movie_genres_genre", "movie_genres", ["genre"])

    # 기존 movies.genres 배열에 들어 있던 값을 새 정규화 테이블로 옮긴다.
    # btrim으로 공백 장르명을 정리하고, DISTINCT/ON CONFLICT로 중복 입력을 방지한다.
    op.execute(
        """
        INSERT INTO movie_genres (movie_id, genre)
        SELECT movies.id, trimmed.genre
        FROM movies
        CROSS JOIN LATERAL (
            SELECT DISTINCT btrim(genre_value) AS genre
            FROM unnest(movies.genres) AS genre_value
            WHERE btrim(genre_value) <> ''
        ) AS trimmed
        WHERE movies.genres IS NOT NULL
        ON CONFLICT (movie_id, genre) DO NOTHING
        """
    )


def downgrade() -> None:
    # 정규화 테이블만 제거한다. movies.genres 컬럼은 호환을 위해 유지되어 있으므로 복구 작업은 필요 없다.
    op.drop_index("ix_movie_genres_genre", table_name="movie_genres")
    op.drop_index("ix_movie_genres_movie_id", table_name="movie_genres")
    op.drop_table("movie_genres")

    # character 취향 row가 남아 있으면 이전 제약으로 되돌릴 수 없어 먼저 제거한다.
    op.execute("DELETE FROM user_preference_scores WHERE preference_type = 'character'")
    op.drop_constraint(
        "ck_user_preference_scores_preference_type",
        "user_preference_scores",
        type_="check",
    )
    op.create_check_constraint(
        "ck_user_preference_scores_preference_type",
        "user_preference_scores",
        "preference_type IN ('genre', 'actor', 'director', 'keyword', 'language')",
    )
