from datetime import datetime, timezone
from math import log1p
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai_client.recommend import request_recommend_today_movie
from app.models.daily_ai_recommendation import DailyAiRecommendation, DailyAiRecommendationMovie
from app.models.interactions import UserMovieInteraction
from app.models.movies import Movie, MovieStats
from app.services.movies.overview_utils import shorten_text
from app.services.preference_service import get_user_preference_scores

# 추천 흐름
PREFERENCE_WEIGHT = {
    "genre": 1.2,
    "actor": 1.0,
    "director": 1.1,
    "keyword": 0.9,
    "language": 0.5,
    "character": 1.3,
}

# PREFERENCE_SCORE = {
#     "view": 0.5,
#     "search_click": 0.8,
#     "like": 2.0,
# }

# db 영화 출력
def db_movies_to_response(daily_movies):
    result = []

    for item in sorted(daily_movies, key=lambda row: row.display_order):
        movie = item.movie

        result.append({
            "movie_id": movie.id,
            "tmdb_id": movie.tmdb_id,
            "title": movie.title,
            "year": movie.year,
            "genres": ", ".join(movie.genres or []),
            "director": movie.director,
            "cast": ", ".join(movie.cast or []),
            "vote_average": movie.vote_average,
            "overview": shorten_text(movie.overview),
            "poster_url": movie.poster_path,
        })

    return result

# 오늘의 ai 영화 추천
async def get_recommend_today_movie_result(db : Session) :
    # 오늘 추천 DB가 있으면 바로 반환
    today = datetime.now(ZoneInfo("Asia/Seoul")).date()
    daily = db.scalar(
        select(DailyAiRecommendation)
        .where(DailyAiRecommendation.recommend_date == today)
    )
    
    if daily:
        return daily.answer, db_movies_to_response(daily.movies)
    ai_recommend_result = await request_recommend_today_movie()
    
    # ai의 답변
    answer = ai_recommend_result.get("answer")

    # 추천 영화
    movies = ai_recommend_result.get("movies", [])

    # 줄거리 짧게 반환
    for movie in movies:
        # answer+= movie.get("title") + "🎬"
        movie["overview"] = shorten_text(movie.get("overview"))

    save_daily_ai_recommendation(db, today, answer, movies)

    return answer, movies

# 사용자 영화 추천 - 기본 추천 기반
def get_user_recommend_movies_result(
        db : Session,
        user_id : int,
        limit : int = 12,
):
    # 기본 추천 리스트
    base_movies = get_recommend_movies_result(db, limit=max(limit*3, 30))

    # 사용자의 취향 점수 목록
    preferences = get_user_preference_scores(db, user_id)
    # 사용자의 취향 점수가 없는 경우 - 기본 영화 추천
    if not preferences:
        return base_movies[:limit]
    
    interacted_movie_ids = (
        select(UserMovieInteraction.movie_id)
        .where(
            UserMovieInteraction.user_id == user_id
        )
    )

    # 개인화 점수를 계산할 후보 영화 개수
    # 최종 반환 개수보다 넉넉하게 좋회한 뒤 개인화 점수로 재정렬
    candidate_limit = max(limit * 20, 100)

    candidate_query = (
        select(Movie, MovieStats)
        # 영화 통계가 없는 영화도 추천 후보에 포함
        .outerjoin(
            MovieStats,
            MovieStats.movie_id == Movie.id,
        )
        # 포스터가 없는 영화 제외
        .where(Movie.poster_path.is_not(None))
        # 사용자가 이미 행동한 영화 제외
        .where(Movie.id.not_in(interacted_movie_ids))
        .order_by(
            func.coalesce(
                MovieStats.ranking_score,
                0,
            ).desc(),
            Movie.vote_average.desc().nulls_last(),
            Movie.vote_count.desc().nulls_last(),
            Movie.id.desc()
        )
        .limit(candidate_limit)
    )

    # [(Movie, MovieStats), ...]형태로 조회
    candidate_movies = db.execute(
        candidate_query
    ).all()
    
    result = []
    for movie, stats in candidate_movies:
        # 인기, 평점, 투표 수, 최신성을 반영한 기본 추천 점수
        score = default_score(movie, stats)

        # 해당 영화와 일치한 사용자 취향 목록
        matched = []
        for preference in preferences:
            movie_values = get_movie_preference_values(movie, preference.preference_type,)

            # 사용자 취향 값도 영화 값과 동일한 방법으로 정규화
            normalized_preference=(
                preference.preference_value
                .strip()
                .casefold()
            )

            # 영화 정보와 사용자 취향 값이 일치한지 확인
            if normalized_preference in movie_values:
                contribution = (
                    max(preference.score or 0, 0)
                    *PREFERENCE_WEIGHT.get(preference.preference_type, 1.0)
                )

                # 영화의 최총 추천 점수에 개인화 점수 추가
                score += contribution
                # 추천 이유를 만들기 위해 일치한 취향 저장
                matched.append(
                    (contribution,
                    f"{preference.preference_type}:"
                    f"{preference.preference_value}",)
                )
    
        # 기여 점수가 가장 큰 취향을 추천 이유로 먼저 사용
        matched.sort(key = lambda item: item[0], reverse=True)
        # (점수, "genre:액션") 형태에서 문자열만 분리
        matched_labels = [
            label
            for _, label in matched
        ]
        result.append({
            "movie_id": movie.id,
            "title": movie.title,
            "poster_path": movie.poster_path,
            "genres": movie.genres or [],
            "vote_average": movie.vote_average,
            "recommendation_score": round(score, 3),
            "reason": build_user_recommend_reason(matched_labels),
            "matched_preferences": matched_labels,
        })

    result.sort(key = lambda item : item["recommendation_score"], reverse=True)

    if not result:
        result = base_movies

    return result[:limit]
    


# 기본 영화 추천 - 메인 페이지에 보여줄 기본 추천 목록
def get_recommend_movies_result(db : Session, limit : int = 12,):

    candidate_limit = max(limit * 4, 40)

    recommend_result = (
        select(Movie, MovieStats)
        # 통계에 없는 영화도 포함
        .outerjoin(MovieStats, MovieStats.movie_id == Movie.id)
        # 포스터 없는 경우 추천 안함
        .where(Movie.poster_path.is_not(None))
        .order_by(
            func.coalesce(MovieStats.ranking_score, 0).desc(),
            Movie.vote_average.desc().nulls_last(),
            Movie.vote_count.desc().nulls_last(),
            Movie.id.desc(),
        )
        .limit(candidate_limit)
    )

    result_movies = []

    for movie, stats in db.execute(recommend_result).all():
        # 랭킹, 평점, 투표수, 등록 최신성 함께 반영
        score = default_score(movie, stats)

        result_movies.append(
            {
                "movie_id" : movie.id,
                "title" : movie.title,
                "poster_path" : movie.poster_path,
                "genres" : movie.genres or [],
                "vote_average" : movie.vote_average,
                "recommendation_score" : round(score, 3),
                "reason" : build_default_reason(movie, stats),
            }
        )

    # 직접 계산한 추천 점수 기준으로 다시 정령 - 실시간 랭킹이랑 안겹침
    result_movies.sort(key=lambda item:item["recommendation_score"], reverse=True)

    return result_movies[:limit]

# 기본 영화 - 추천 이유 생성
def build_default_reason(movie: Movie, stats : MovieStats | None):
    
    if stats and stats.ranking_score > 0:
        return "최근 조회수 높은 영화 추천"
    if movie.vote_average and movie.vote_average >=7:
        return "평점 높은 영화 추천"
    if movie.vote_count and movie.vote_count>=1000:
        return "인기 있는 영화 추천"
    return "가볍게 둘러보기 좋은 영화 추천"

# 사용자 기반 - 추천 이유 생성
def build_user_recommend_reason(matched : list[str]):
    if not matched:
        return "인기와 평점 기준으로 추천"
    
    # 가장 먼저 매칭된 취향을 대표 추천 이유로 사용
    preference_type, value = matched[0].split(":", 1)

    label = {
        "genre": "좋아하는 장르",
        "actor": "관심 있는 배우",
        "director": "선호하는 감독",
        "keyword": "관심 키워드",
        "language": "선호 언어",
        "character": "좋아하는 캐릭터",
    }.get(preference_type, "취향")

    return f"{label} '{value}'와 잘 맞는 영화"

# 점수 반영
def default_score(movie : Movie, stats : MovieStats | None) :
    # 랭킹 반영
    ranking_score = (stats.ranking_score if stats else 0) * 0.03

    # 평점
    vote_score = (movie.vote_average or 0) * 0.7

    # 투표 수 - log1p 숫자가 커질수록 증가폭을 완만하게 만들어줌
    vote_count_score = log1p(movie.vote_count or 0) * 0.3

    # 최신성
    recent_score = calculate_created_at_recency_score(movie)
    
    return ranking_score + vote_score + vote_count_score + recent_score

# 최신 점수 반영
def calculate_created_at_recency_score(movie : Movie):
    if movie.created_at is None:
        return 0.0
    
    created_at = movie.created_at

    # timezone 정보가 없는 경우
    if created_at.tzinfo is None:
        # UTC로 맞춰서
        created_at = created_at.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)

    # 현재 시간과 영화 등록 시간의 차이
    days_since_created = max((now-created_at).days, 0)

    if days_since_created>= 30 :
        return 0.0
    
    result = 1 - (days_since_created/30)

    return result * 0.5


def save_daily_ai_recommendation(
        db : Session,
        recommend_date,
        answer : str,
        movies : list[dict],
) -> DailyAiRecommendation:
    daily = DailyAiRecommendation(
        recommend_date = recommend_date, 
        answer = answer
    )

    db.add(daily)
    # 임시 저장 daily.id 반환하기 위해
    db.flush()

    for index, movie in enumerate(movies[:3], start=1):
        tmdb_id = int(movie.get("tmdb_id"))

        if not tmdb_id:
            continue
        db_movie = db.scalar(select(Movie).where(Movie.tmdb_id == tmdb_id))

        if db_movie is None:
            continue

        daily_movie = DailyAiRecommendationMovie(
            daily_recommendation_id = daily.id,
            movie_id = db_movie.id,
            display_order = index
        )

        db.add(daily_movie)

    
    db.commit()
    db.refresh(daily)

    return daily

# 영화 취향값 가져오는 함수
def get_movie_preference_values(
        movie,
        preference_type : str,
):
    preference_map = {
        "genre": movie.genres or [],
        "actor": movie.cast or [],
        "director": [movie.director] if movie.director else [],
        "keyword": movie.keywords or [],
        "language": [movie.language] if movie.language else [],
    }

    return {
        value.strip().casefold() # 문자열 앞뒤 공백 제거, 대소문자 차지 없애서 비교하기 쉽게 만드는 형태
        for value in preference_map.get(preference_type, [])
        if isinstance(value, str) and value.strip()
    }
