from app.core.base import Base
from sqlalchemy import ARRAY, BigInteger, Column, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import relationship

# movies 테이블과 연결되는 SQLAlchemy ORM 모델
# 영화의 기본 정보(title, overview, genres, poster_path 등)를 저장한다.
class Movie(Base):
    __tablename__ = "movies"
    id = Column(BigInteger, primary_key=True, autoincrement=True) # 내부 DB에서 사용하는 영화 고유 ID
    # TMDB에서 제공하는 영화 ID - 외부 API와 연결할 때 사용한다.
    tmdb_id = Column(Integer, unique=True, index=True, nullable=True)
    # 영화 제목
    title = Column(String(300), index=True, nullable=False)
    # 영화 줄거리
    overview = Column(Text, nullable=True)
    # 영화 장르 목록 - PostgreSQL ARRAY 타입 사용
    genres = Column(ARRAY(String), nullable=True)
    # 감독 이름
    director = Column(String(200), nullable=True)
    # 출연 배우 목록
    cast = Column(ARRAY(String), nullable=True)
    # 영화 키워드 목록
    keywords = Column(ARRAY(String), nullable=True)
    # 개봉 연도
    year = Column(Integer, nullable=True)
    # 언어 코드
    language = Column(String(10), nullable=True)
    # TMDB 평균 평점
    vote_average = Column(Float, nullable=True)
    # TMDB 투표 수
    # 우리 서비스 좋아요 수가 아니라 TMDB 기준 투표 수
    vote_count = Column(Integer, nullable=True)
    # 관객 수 데이터가 있을 경우 저장
    audience_count = Column(BigInteger, nullable=True)
    # 포스터 이미지 경로
    poster_path = Column(String(300), nullable=True)
    # TMDB 또는 외부 데이터와 마지막으로 동기화한 시간
    last_synced_at = Column(DateTime(timezone=True), nullable=True)
    # 데이터 생성 시간
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    # 데이터 수정 시간
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # 이 영화에 대해 사용자들이 남긴 행동 기록 목록
    interactions = relationship(
        "UserMovieInteraction",
        back_populates="movie",
        passive_deletes=True,
    )
    # 정규화된 장르 row 목록
    # movies.genres 배열과 함께 유지하되, 장르 검색/추천은 이 테이블을 기준으로 빠르게 처리할 수 있다.
    genre_rows = relationship(
        "MovieGenre",
        back_populates="movie",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


# movie_genres 테이블과 연결되는 ORM 모델
# movies.genres 배열을 검색/집계하기 쉽게 영화-장르 단위 row로 풀어 저장한다.
class MovieGenre(Base):
    __tablename__ = "movie_genres"
    __table_args__ = (
        # 같은 영화에 같은 장르가 중복 저장되지 않도록 DB 레벨에서 막는다.
        UniqueConstraint("movie_id", "genre", name="uq_movie_genres_movie_genre"),
    )

    # 장르 row 고유 ID
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    # 연결된 영화 ID. 영화가 삭제되면 해당 장르 row도 함께 삭제된다.
    movie_id = Column(BigInteger, ForeignKey("movies.id", ondelete="CASCADE"), nullable=False, index=True)
    # 단일 장르명. 장르명 검색을 위해 인덱스를 둔다.
    genre = Column(String(50), nullable=False, index=True)

    # Movie 모델과 양방향으로 연결
    movie = relationship("Movie", back_populates="genre_rows")

# movie_stats 테이블과 연결되는 ORM 모델
# 영화별 조회수, 검색 클릭 수, 좋아요 수, 랭킹 점수를 저장한다.
class MovieStats(Base):
    __tablename__ = "movie_stats"

    # movies.id를 참조하는 영화 ID
    movie_id = Column(BigInteger, ForeignKey("movies.id", ondelete="CASCADE"), primary_key=True,)
    # 영화 상세 페이지 조회 수
    view_count = Column(Integer, default=0, server_default="0", nullable=False)

    # 검색 결과에서 클릭된 횟수
    search_click_count = Column(Integer, default=0, server_default="0", nullable=False)

    # 좋아요 수
    like_count = Column(Integer, default=0, server_default="0", nullable=False)

    # 랭킹 정렬에 사용할 점수
    ranking_score = Column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
        index=True,
    )
    # 통계 row 생성 시간
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    # 통계 row 수정 시간
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Movie 모델과 연결
    # 꼭 없어도 list_top_movies 쿼리는 동작하지만, 관계 설정을 해두면 나중에 편하다.
    movie = relationship("Movie")
