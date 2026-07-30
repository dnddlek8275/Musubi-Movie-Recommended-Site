from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.models.movies import Movie, MovieStats

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


# 누적 통계 테이블 기준으로 상위 인기 영화 조회 - 실시간 랭킹
def realtime_movie_ranking_result(db: Session, limit: int = 10) -> list[dict]:
    result = (
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
    # DB 조회 결과를 list[dict] 형태로 반환
    return [dict(row._mapping) for row in db.execute(result)]
