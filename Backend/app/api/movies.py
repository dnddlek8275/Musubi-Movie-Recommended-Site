from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.ai_client.recommend import request_ai_recommend
from app.core.current_user import get_current_user, get_optional_current_user
from app.core.api_responses import error_response
from app.core.dependencies import get_db
from app.schemas.movies import MovieDetailData, MovieDetailResponse, RecommendRequest
from app.services.actor_service import get_actors_result
from app.services.movies.genre_service import genre_movies
from app.services.movies.ranking_service import movie_detail, realtime_movie_ranking_result
from app.services.interaction_service import detail_movie_result, like_movie_result
from app.services.movies.search_service import search_movies_result
from app.services.movies.recommendation_service import get_recommend_movies_result, get_recommend_today_movie_result, get_user_recommend_movies_result
from app.services.movies.tmdb_trailer_service import get_movie_trailer_url
from app.services.user_service import user_like_actor

TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"


def tmdb_image_url(path: str | None) -> str | None:
    if not path or not path.strip():
        return None

    image_path = path.strip()
    if image_path.startswith(("http://", "https://")):
        return image_path

    if not image_path.startswith("/"):
        image_path = f"/{image_path}"
    return f"{TMDB_IMAGE_BASE_URL}{image_path}"


# 영화 관련 API들을 묶는 Router /movies/
router = APIRouter(
    prefix="/movies",
    tags=["Movies"]
)

# 배우 조회
@router.get("/actors")
def get_actors(
    q: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    try:
        actors_result = get_actors_result(
            db,
            query=q,
            page=page,
            limit=limit,
        )

        if not actors_result:
            return {
                "state" : "failure",
                "message" : "DB에 저장된 배우가 없습니다.",
                "data": [],
            }
        
        return {
            "state" : "success",
            "message" : "배우 조회 성공",
            "data" : [
                {
                    "actor_id" : actor.id,
                    "actor_name" : actor.name,
                    "profile_path": tmdb_image_url(actor.profile_path),
                }for actor in actors_result
            ],
            "pagination": {
                "page": page,
                "limit": limit,
                "has_more": len(actors_result) == limit,
            },
        }
    except Exception:
        return error_response("배우 조회 API 에러")

# 배우 저장
@router.post("/actor/{actor_id}")
def like_actor(
    actor_id : int,
    current_user = Depends(get_current_user),
    db : Session = Depends(get_db)
):
    try:
        user_id = current_user["user_id"]

        return user_like_actor(db, user_id, actor_id)
    except Exception:
        return error_response("배우 저장 API 에러")

# AI 영화 추천 POST /movies/recommend
@router.post("/recommend")
def recommend_movies(
    # request: RecommendRequest,
    limit : int = Query(12, ge=1, le=30),
    current_user :dict = Depends(get_optional_current_user),
    db : Session = Depends(get_db),
):
    try:
        if current_user:
            recommend_movies = get_user_recommend_movies_result(db = db, user_id = current_user["user_id"], limit=limit)
        else :
            recommend_movies = get_recommend_movies_result(db, limit)

        if not recommend_movies:
            return {
                "state" : "failure",
                "message" : "추천하는 영화가 없습니다.",
            }
        return {
            "state" : "success",
            "message": "영화 추천 API입니다.",
            "data" : recommend_movies,
        }
    except Exception:
        return error_response("영화 추천 오류")


# 영화 검색 GET /movies/search
@router.get("/search")
async def search_movies(
    keyword: str = Query(..., min_length=1),
    page : int = Query(1, ge=1),
    limit : int = Query(20, ge=1, le=50),
    # current_user : dict = Depends(get_optional_current_user),
    db : Session = Depends(get_db),
):
    try :
        return search_movies_result(db, keyword, page, limit)
    
    except Exception:
        return error_response("영화 검색 에러")


# 실시간 랭킹 10 GET /movies/ranking
@router.get("/ranking")
async def get_realtime_movie_ranking(
    # 랭킹 조회 개수 제한
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
    ):
    try:
        ranking_result = realtime_movie_ranking_result(db, limit)
        return {
            "state": "success",
            "message": "영화 랭킹 조회 성공",
            "data": ranking_result,
        }
    except Exception:
        return error_response("영화 랭킹 조회 에러")


# 영화 상세 조회 GET /movies/{id}
@router.get("/{movie_id}", response_model= MovieDetailResponse)
async def get_movie_detail(
    movie_id: int,
    source : str = Query("direct"),
    current_user : dict | None = Depends(get_optional_current_user),
    db : Session = Depends(get_db),
):
    try:
        movie_detail_result = movie_detail(db, movie_id)
        if movie_detail_result is None :
            return {
                "state" : "failure",
                "message" : "해당 영화에 대한 정보가 없습니다.",
            }
        
        # 회원일 경우 점수 반영
        if current_user is not None:
            # JWT에서 user_id 가져오기
            user_id = current_user["user_id"]

            # 검색한 경우 action_type 수정
            if source == "search" :
                action_type = "search_click"
            else :
                action_type = "view"

            detail_movie_result(db, user_id, movie_id, action_type)

        # movies 테이블에는 이미 tmdb_id가 저장돼 있다.
        # 해당 값으로 TMDB 예고편 API를 실시간 호출한다.
        trailer_url = await get_movie_trailer_url(
            movie_detail_result.tmdb_id
        )

        # SQLAlchemy Movie 객체를 MovieDetailData로 변환한다.
        movie_data = MovieDetailData.model_validate(
            movie_detail_result
        )

        # DB에는 없는 trailer_url을 응답 데이터에만 추가한다.
        movie_data = movie_data.model_copy(
            update={
                "trailer_url": trailer_url,
            }
        )
        return {
            "state" : "success",
            "message" : "영화 조회 성공",
            "data" : movie_data,
        }
    except Exception:
        return error_response("영화 상세 조회 에러")

# 좋아요 POST /movies/{id}/like
@router.post("/{movie_id}/like")
def like_movie(
    movie_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
    ):
    try:
        # JWT 회원 정보에서 user_id를 가져온다.
        user_id = current_user["user_id"]

        if not movie_id :
            return {
                "state" : "failure",
                "message" : "movie_id가 없습니다."
            }
        result = like_movie_result(db, user_id, movie_id)
        return result
    except Exception:
        return error_response("좋아요 API 호출 실패")

    
@router.get("/today/recommend")
async def get_today_recommend_movies(
    db: Session = Depends(get_db)
):
    try:
        answer, movies = await get_recommend_today_movie_result(db)

        if answer is None:
            return {
                "state" : "failure",
                "message" : "오늘의 영화 추천은 없습니다.",
            }
        
        result = {
            "answer" : answer,
            "movies" : movies,
        }
        
        return {
            "state" : "success",
            "message" : "오늘의 AI 추천 영화 조회 성공",
            "data" : result,
        }
    
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        return error_response("오늘의 AI 추천 영화 조회 에러")

@router.get("/genre/{genre}")
def get_genre_movies(
    genre : str,
    page : int = Query(1, ge=1),
    limit : int = Query(20, ge=1, le=50),
    db : Session = Depends(get_db),
):
    try:
        movies_result = genre_movies(db, genre, page, limit)
        if movies_result is None:
            return {
                "state" : "failure",
                "message" : "해당 장르에 관한 영화는 없습니다.",
            }
        
        return {
            "state" : "success",
            "message" : "장르별 영화 성공",
            "data" : [
                {
                    "movie_id" : movie.id,
                    "title" : movie.title,
                    "poster_path": movie.poster_path,
                    "vote_average": movie.vote_average,
                }for movie in movies_result
            ]
        }
    except Exception:
        return error_response("장르별 영화 에러")

# ai의 영화 추천
@router.post("/ai-recommend")
async def ai_recommend_movies(request : RecommendRequest):
    ai_result = await request_ai_recommend(request.model_dump())

    return {
        "state" : "success",
        "message" : "AI 영화 추천 성공",
        "data" : {
            "answer" : ai_result.get("answer"),
            "movies" : ai_result.get("movies", []),
        }
    }
