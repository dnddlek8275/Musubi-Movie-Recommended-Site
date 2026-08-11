from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.movies import Movie, MovieStats
from app.models.ranking import DailyMovieRankingSnapshot


KST = ZoneInfo("Asia/Seoul")
DAILY_RANKING_SNAPSHOT_LIMIT = 10

def movie_detail(db:Session, movie_id : int):
    movie = db.scalar(
        select(Movie)
        .where(Movie.id ==  movie_id)
    )
    return movie

# 영화 랭킹 점수 갱신
def add_movie_ranking_score(db: Session, movie_id: int, score_delta: int, action_type : str):
    movie_stats = db.scalar(select(MovieStats).where(MovieStats.movie_id == movie_id))
    if not movie_stats:
        # MovieStats가 없으면 새로 생성
        movie_stats = MovieStats(
            movie_id=movie_id,
            view_count=0,
            search_click_count=0,
            like_count=0,
            ranking_score=0
        )
    # 점수 추가
    if action_type == "like" :
        movie_stats.like_count += 1
    elif action_type == "view":
        movie_stats.view_count +=1
    else:
        movie_stats.search_click_count+=1
    movie_stats.ranking_score += score_delta
    db.add(movie_stats)


def _ranking_statement(limit: int):
    return (
        # 랭킹 API에 필요한 컬럼 선택
        select(
            # ID
            Movie.id,
            # 영화 제목
            Movie.title,
            # 포스터 이미지 경로
            Movie.poster_path,
            # 누적 통계 테이블 
            # 조회수
            MovieStats.view_count,
            # 검색 클릭 수
            MovieStats.search_click_count,
            # 좋아요 수
            MovieStats.like_count,
            # 랭킹 점수
            MovieStats.ranking_score,
        )
        # .join(MovieStats, Movie.id == MovieStats.movie_id)
        # 통계에 없는 영화도 랭킹 후보에 포함
        .outerjoin(MovieStats, Movie.id == MovieStats.movie_id)
        # ranking_score가 높은 순으로 먼저 정렬
        # ranking_score > view_count > like_count > search_click_count > vote_average > 투표순 > 최신 등록 영화 순
        .order_by(
            func.coalesce(MovieStats.ranking_score, 0).desc(),
            func.coalesce(MovieStats.view_count, 0).desc(),
            func.coalesce(MovieStats.like_count, 0).desc(),
            func.coalesce(MovieStats.search_click_count, 0).desc(),
            Movie.vote_average.desc().nulls_last(),
            Movie.vote_count.desc().nulls_last(),
            Movie.id.desc()
        )
        # 상위 limit 개수만 조회
        .limit(limit)
    )


def current_kst_date():
    return datetime.now(KST).date()


def ensure_daily_ranking_snapshot(db: Session, snapshot_date=None) -> list[DailyMovieRankingSnapshot]:
    target_date = snapshot_date or current_kst_date()
    existing = db.scalars(
        select(DailyMovieRankingSnapshot)
        .where(DailyMovieRankingSnapshot.snapshot_date == target_date)
        .order_by(DailyMovieRankingSnapshot.rank)
    ).all()
    if existing:
        return existing

    current_movies = [
        dict(row._mapping)
        for row in db.execute(_ranking_statement(DAILY_RANKING_SNAPSHOT_LIMIT))
    ]
    for rank, movie in enumerate(current_movies, start=1):
        db.add(
            DailyMovieRankingSnapshot(
                snapshot_date=target_date,
                movie_id=movie["id"],
                rank=rank,
            )
        )

    try:
        db.commit()
    except IntegrityError:
        # 자정 작업과 API 요청이 동시에 최초 스냅샷을 만들면 먼저 저장된 값을 사용한다.
        db.rollback()

    return db.scalars(
        select(DailyMovieRankingSnapshot)
        .where(DailyMovieRankingSnapshot.snapshot_date == target_date)
        .order_by(DailyMovieRankingSnapshot.rank)
    ).all()


# 누적 통계 테이블 기준으로 상위 인기 영화 조회 - 실시간 랭킹
def realtime_movie_ranking_result(db: Session, limit: int = 10) -> list[dict]:
    baseline = ensure_daily_ranking_snapshot(db)
    baseline_ranks = {row.movie_id: row.rank for row in baseline}
    current_movies = [dict(row._mapping) for row in db.execute(_ranking_statement(limit))]

    result = []
    for current_rank, movie in enumerate(current_movies, start=1):
        previous_rank = baseline_ranks.get(movie["id"])
        result.append(
            {
                **movie,
                "rank": current_rank,
                "rank_change": previous_rank - current_rank if previous_rank is not None else None,
                "is_new": current_rank <= DAILY_RANKING_SNAPSHOT_LIMIT and previous_rank is None,
            }
        )
    return result
