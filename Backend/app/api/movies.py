import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.ai_client.recommend import request_ai_recommend
from app.core.current_user import get_current_user, get_optional_current_user
from app.core.api_responses import error_response
from app.core.dependencies import get_db
from app.schemas.movies import MovieCastData, MovieDetailData, MovieDetailResponse, MovieIdentityRequest, MovieRatingRequest, PersonFilmographyResponse, RecommendRequest
from app.schemas.users import PreferenceRequest
from app.services.actor_service import get_actors_result, get_onboarding_actors_result
from app.services.movies.genre_service import country_movies, genre_movies
from app.services.movies.chat_movie_link_service import resolve_chat_movie
from app.services.movies.ranking_service import movie_detail, realtime_movie_ranking_result
from app.services.movies.discovery_section_service import get_discovery_sections_result
from app.services.interaction_service import detail_movie_result, like_movie_result
from app.services.movies.search_service import (
    search_movie_sections_result,
    search_movies_result,
    search_suggestions_result,
)
from app.services.movies.recommendation_service import get_guest_recommend_movies_result, get_recommend_movies_result, get_recommend_today_movie_result, get_similar_movies_result, get_user_recommend_movies_result
from app.services.movies.tmdb_trailer_service import get_movie_trailer_videos
from app.services.user_service import user_like_actor
from app.services.preference_service import CURATED_LEARNABLE_KEYWORD_ORDER, toggle_person_preference
from app.models.interactions import MovieRating, MovieWishlist
from app.models.actors import Actor, MovieActor
from app.services.actor_name_policy import actor_display_name
from app.models.movies import Movie, MovieGenre
from app.models.users import User

TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"
logger = logging.getLogger(__name__)


def rating_identity_matches(movie: Movie, movie_id: int, request: MovieIdentityRequest) -> bool:
    if request.expected_movie_id != movie_id:
        return False
    if request.expected_tmdb_id is not None and request.expected_tmdb_id != movie.tmdb_id:
        return False
    if request.expected_title.strip() != movie.title.strip():
        return False
    return True

def tmdb_image_url(path: str | None) -> str | None:
    if not path or not path.strip():
        return None

    image_path = path.strip()
    if image_path.startswith(("http://", "https://")):
        return image_path

    if not image_path.startswith("/"):
        image_path = f"/{image_path}"
    return f"{TMDB_IMAGE_BASE_URL}{image_path}"


def get_rating_summary(db: Session, movie_id: int, user_id: int | None = None) -> dict:
    average, count = db.execute(
        select(func.avg(MovieRating.score), func.count(MovieRating.id))
        .where(MovieRating.movie_id == movie_id)
    ).one()
    my_rating = None
    my_comment = None
    my_is_spoiler = False
    if user_id is not None:
        my_rating_row = db.execute(
            select(MovieRating.score, MovieRating.comment, MovieRating.is_spoiler).where(
                MovieRating.movie_id == movie_id,
                MovieRating.user_id == user_id,
            )
        ).one_or_none()
        if my_rating_row is not None:
            my_rating = my_rating_row.score
            my_comment = my_rating_row.comment
            my_is_spoiler = bool(my_rating_row.is_spoiler)

    review_rows = db.execute(
        select(MovieRating, User.nickname)
        .join(User, User.id == MovieRating.user_id)
        .where(
            MovieRating.movie_id == movie_id,
            MovieRating.comment.is_not(None),
            func.btrim(MovieRating.comment) != "",
        )
        .order_by(MovieRating.updated_at.desc(), MovieRating.id.desc())
    ).all()
    return {
        "musubi_rating": round(float(average), 1) if average is not None else None,
        "rating_count": int(count or 0),
        "my_rating": my_rating,
        "my_comment": my_comment,
        "my_is_spoiler": my_is_spoiler,
        "reviews": [
            {
                "id": rating.id,
                "user_id": rating.user_id,
                "nickname": nickname,
                "score": rating.score,
                "comment": rating.comment,
                "is_spoiler": bool(rating.is_spoiler),
                "updated_at": rating.updated_at,
                "is_mine": user_id is not None and rating.user_id == user_id,
            }
            for rating, nickname in review_rows
        ],
    }


def get_movie_cast_details(db: Session, movie_id: int) -> list[MovieCastData]:
    rows = db.execute(
        select(Actor, MovieActor.character_name)
        .join(MovieActor, MovieActor.actor_id == Actor.id)
        .where(MovieActor.movie_id == movie_id)
        .order_by(MovieActor.cast_order.asc().nullslast(), MovieActor.id.asc())
    ).all()
    return [
        MovieCastData(
            actor_id=actor.id,
            name=actor_display_name(actor),
            character_name=character_name,
            profile_path=tmdb_image_url(actor.profile_path),
        )
        for actor, character_name in rows
    ]


def serialize_filmography_movie(movie: Movie, character_name: str | None = None) -> dict:
    return {
        "id": movie.id,
        "title": movie.title,
        "poster_path": tmdb_image_url(movie.poster_path),
        "genres": movie.genres or [],
        "year": movie.year,
        "release_date": movie.release_date,
        "vote_average": movie.vote_average,
        "character_name": character_name,
    }


# 영화 관련 API들을 묶는 Router /movies/
router = APIRouter(
    prefix="/movies",
    tags=["Movies"]
)


@router.get("/preference-options")
def get_preference_options(db: Session = Depends(get_db)):
    """온보딩에서 사용할 실제 DB 기반 장르와 키워드 선택지를 반환한다."""
    try:
        genre_rows = (
            db.query(MovieGenre.genre, func.count(MovieGenre.movie_id).label("count"))
            .filter(
                MovieGenre.genre.isnot(None),
                func.btrim(MovieGenre.genre) != "",
            )
            .group_by(MovieGenre.genre)
            .order_by(func.count(MovieGenre.movie_id).desc(), MovieGenre.genre.asc())
            .all()
        )

        return {
            "state": "success",
            "message": "온보딩 선택지 조회 성공",
            "data": {
                "genres": [row.genre for row in genre_rows if row.genre],
                # 행동 기반 취향 학습과 같은 60개 키워드를 모두 제공한다.
                # DB 등장 빈도나 limit에 따라 온보딩 선택지가 빠지지 않도록 한다.
                "keywords": list(CURATED_LEARNABLE_KEYWORD_ORDER),
            },
        }
    except Exception:
        return error_response("온보딩 선택지 조회 실패")

# 배우 조회
@router.get("/actors")
def get_actors(
    q: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=100),
    onboarding: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    try:
        if onboarding and not (q or "").strip():
            actors_result = get_onboarding_actors_result(db)
        else:
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
                    "actor_name" : actor_display_name(actor),
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
    preferences: PreferenceRequest | None = None,
    limit : int = Query(12, ge=1, le=30),
    current_user :dict = Depends(get_optional_current_user),
    db : Session = Depends(get_db),
):
    try:
        if current_user:
            recommend_movies = get_user_recommend_movies_result(db = db, user_id = current_user["user_id"], limit=limit)
        elif preferences and (preferences.genres or preferences.actors or preferences.keywords):
            recommend_movies = get_guest_recommend_movies_result(
                db=db,
                genres=preferences.genres,
                actors=preferences.actors,
                keywords=preferences.keywords,
                limit=limit,
            )
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


# 검색어 자동완성 GET /movies/search/suggestions
@router.get("/search/suggestions")
async def search_suggestions(
    keyword: str = Query(..., min_length=1, max_length=100),
    limit: int = Query(8, ge=1, le=12),
    db: Session = Depends(get_db),
):
    try:
        return search_suggestions_result(db, keyword, limit)
    except Exception:
        return error_response("검색어 자동완성 에러")


# 영화 검색 GET /movies/search
@router.get("/search/grouped")
async def search_movies_grouped(
    keyword: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=40),
    search_type: str | None = Query(None, alias="type"),
    category: str | None = Query(None),
    page: int = Query(1, ge=1),
    exclude_ids: list[int] = Query(default=[]),
    db: Session = Depends(get_db),
):
    try:
        return search_movie_sections_result(
            db,
            keyword,
            limit,
            search_type,
            category,
            page,
            exclude_ids,
        )
    except Exception:
        return error_response("카테고리별 영화 검색 에러")


# 기존 단일 목록 검색은 다른 호출부와의 호환을 위해 유지한다.
@router.get("/search")
async def search_movies(
    keyword: str = Query(..., min_length=1),
    page : int = Query(1, ge=1),
    limit : int = Query(80, ge=1, le=100),
    search_type: str | None = Query(None, alias="type"),
    current_user: dict | None = Depends(get_optional_current_user),
    db : Session = Depends(get_db),
):
    try :
        return search_movies_result(
            db,
            keyword,
            page,
            limit,
            search_type,
            current_user["user_id"] if current_user else None,
        )
    
    except Exception:
        return error_response("영화 검색 에러")


@router.get("/resolve")
def resolve_recommended_movie(
    movie_id: int | None = Query(None, ge=1),
    tmdb_id: int | None = Query(None, ge=1),
    title: str | None = Query(None, min_length=1, max_length=300),
    year: int | None = Query(None, ge=1880, le=2200),
    db: Session = Depends(get_db),
):
    """AI 추천 카드 식별자를 서비스 내부 상세 페이지 ID로 변환한다."""
    if movie_id is None and tmdb_id is None and not str(title or "").strip():
        raise HTTPException(status_code=422, detail="영화 식별 정보가 필요합니다.")

    movie = resolve_chat_movie(
        db,
        movie_id=movie_id,
        tmdb_id=tmdb_id,
        title=title,
        year=year,
    )
    if movie is None:
        raise HTTPException(status_code=404, detail="서비스에 등록된 영화를 찾을 수 없습니다.")

    return {
        "state": "success",
        "message": "영화 상세 페이지 연결 정보 조회 성공",
        "data": {
            "movie_id": movie.id,
            "tmdb_id": movie.tmdb_id,
            "title": movie.title,
        },
    }


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


@router.post("/discovery-sections")
def get_discovery_sections(
    preferences: PreferenceRequest | None = None,
    limit: int = Query(25, ge=1, le=25),
    current_user: dict | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    try:
        sections = get_discovery_sections_result(
            db=db,
            user_id=current_user["user_id"] if current_user else None,
            guest_preferences=preferences,
            limit=limit,
        )
        return {
            "state": "success",
            "message": "영화 탐색 섹션 조회 성공",
            "data": sections,
        }
    except Exception:
        return error_response("영화 탐색 섹션 조회 에러")


@router.get("/people/actor/{identifier}", response_model=PersonFilmographyResponse)
def get_actor_filmography(
    identifier: str,
    current_user: dict | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    actor = None
    if identifier.isdigit():
        actor = db.scalar(select(Actor).where(Actor.id == int(identifier)))
    else:
        actor = db.scalar(
            select(Actor)
            .where(or_(
                func.lower(Actor.name) == identifier.strip().lower(),
                func.lower(Actor.korean_name) == identifier.strip().lower(),
                func.lower(Actor.original_name) == identifier.strip().lower(),
            ))
            .order_by(Actor.id.asc())
        )

    person_name = actor_display_name(actor) if actor is not None else identifier.strip()
    if not person_name:
        raise HTTPException(status_code=404, detail="배우 정보를 찾을 수 없습니다.")

    credit_rows = []
    if actor is not None:
        credit_rows = db.execute(
            select(Movie, MovieActor.character_name)
            .join(MovieActor, MovieActor.movie_id == Movie.id)
            .where(MovieActor.actor_id == actor.id)
            .order_by(
                Movie.release_date.desc().nullslast(),
                Movie.year.desc().nullslast(),
                Movie.id.desc(),
            )
        ).all()

    known_movie_ids = {movie.id for movie, _ in credit_rows}
    fallback_movies = []
    if actor is None:
        fallback_movies = db.scalars(
            select(Movie)
            .where(Movie.cast.any(person_name))
            .order_by(
                Movie.release_date.desc().nullslast(),
                Movie.year.desc().nullslast(),
                Movie.id.desc(),
            )
        ).all()

    movies = [
        serialize_filmography_movie(movie, character_name)
        for movie, character_name in credit_rows
    ]
    movies.extend(
        serialize_filmography_movie(movie)
        for movie in fallback_movies
        if movie.id not in known_movie_ids
    )

    if actor is None and not movies:
        raise HTTPException(status_code=404, detail="배우 정보를 찾을 수 없습니다.")

    user = db.get(User, current_user["user_id"]) if current_user is not None else None

    return {
        "state": "success",
        "message": "배우 필모그래피 조회 성공",
        "data": {
            "id": actor.id if actor is not None else None,
            "name": person_name,
            "role": "actor",
            "profile_path": tmdb_image_url(actor.profile_path) if actor is not None else None,
            "is_liked": person_name in (user.preferred_actors or []) if user is not None else False,
            "movie_count": len(movies),
            "movies": movies,
        },
    }


@router.get("/people/director/{name}", response_model=PersonFilmographyResponse)
def get_director_filmography(
    name: str,
    current_user: dict | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    person_name = name.strip()
    if not person_name:
        raise HTTPException(status_code=404, detail="감독 정보를 찾을 수 없습니다.")

    normalized_directors = func.concat(
        ",",
        func.lower(func.regexp_replace(Movie.director, r"\s*,\s*", ",", "g")),
        ",",
    )
    movies = db.scalars(
        select(Movie)
        .where(
            Movie.director.isnot(None),
            normalized_directors.contains(f",{person_name.lower()},"),
        )
        .order_by(
            Movie.release_date.desc().nullslast(),
            Movie.year.desc().nullslast(),
            Movie.id.desc(),
        )
    ).all()

    if not movies:
        raise HTTPException(status_code=404, detail="감독 정보를 찾을 수 없습니다.")

    filmography = [serialize_filmography_movie(movie) for movie in movies]
    user = db.get(User, current_user["user_id"]) if current_user is not None else None
    return {
        "state": "success",
        "message": "감독 필모그래피 조회 성공",
        "data": {
            "id": None,
            "name": person_name,
            "role": "director",
            "profile_path": None,
            "is_liked": person_name in (user.preferred_directors or []) if user is not None else False,
            "movie_count": len(filmography),
            "movies": filmography,
        },
    }


@router.post("/people/actor/{identifier}/like")
def toggle_actor_like(
    identifier: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    actor = None
    if identifier.isdigit():
        actor = db.scalar(select(Actor).where(Actor.id == int(identifier)))
    else:
        actor = db.scalar(
            select(Actor)
            .where(or_(
                func.lower(Actor.name) == identifier.strip().lower(),
                func.lower(Actor.korean_name) == identifier.strip().lower(),
                func.lower(Actor.original_name) == identifier.strip().lower(),
            ))
            .order_by(Actor.id.asc())
        )
    if actor is None:
        raise HTTPException(status_code=404, detail="배우 정보를 찾을 수 없습니다.")

    try:
        is_liked = toggle_person_preference(
            db,
            current_user["user_id"],
            "actor",
            actor.name,
        )
        return {
            "state": "success",
            "message": "배우 좋아요가 반영되었습니다.",
            "data": {"is_liked": is_liked, "name": actor_display_name(actor), "role": "actor"},
        }
    except Exception:
        db.rollback()
        return error_response("배우 좋아요 반영에 실패했습니다.")


@router.post("/people/director/{name}/like")
def toggle_director_like(
    name: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    person_name = name.strip()
    if not person_name:
        raise HTTPException(status_code=404, detail="감독 정보를 찾을 수 없습니다.")

    normalized_directors = func.concat(
        ",",
        func.lower(func.regexp_replace(Movie.director, r"\s*,\s*", ",", "g")),
        ",",
    )
    director_movie_id = db.scalar(
        select(Movie.id)
        .where(
            Movie.director.isnot(None),
            normalized_directors.contains(f",{person_name.lower()},"),
        )
        .limit(1)
    )
    if director_movie_id is None:
        raise HTTPException(status_code=404, detail="감독 정보를 찾을 수 없습니다.")

    try:
        is_liked = toggle_person_preference(
            db,
            current_user["user_id"],
            "director",
            person_name,
        )
        return {
            "state": "success",
            "message": "감독 좋아요가 반영되었습니다.",
            "data": {"is_liked": is_liked, "name": person_name, "role": "director"},
        }
    except Exception:
        db.rollback()
        return error_response("감독 좋아요 반영에 실패했습니다.")


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
        trailer_videos = await get_movie_trailer_videos(
            movie_detail_result.tmdb_id
        )

        # SQLAlchemy Movie 객체를 MovieDetailData로 변환한다.
        movie_data = MovieDetailData.model_validate(
            movie_detail_result
        )

        # DB에는 없는 trailer_url을 응답 데이터에만 추가한다.
        rating_summary = get_rating_summary(
            db,
            movie_id,
            current_user["user_id"] if current_user is not None else None,
        )
        movie_data = movie_data.model_copy(
            update={
                "trailer_url": trailer_videos[0]["url"] if trailer_videos else None,
                "trailer_videos": trailer_videos,
                "cast_details": get_movie_cast_details(db, movie_id),
                **rating_summary,
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


@router.post("/{movie_id}/wishlist")
def add_movie_to_wishlist(
    movie_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        user_id = current_user["user_id"]
        if db.get(Movie, movie_id) is None:
            return {"state": "failure", "message": "영화 정보를 찾을 수 없습니다."}
        existing = db.scalar(select(MovieWishlist).where(
            MovieWishlist.user_id == user_id,
            MovieWishlist.movie_id == movie_id,
        ))
        if existing is None:
            db.add(MovieWishlist(user_id=user_id, movie_id=movie_id))
            db.commit()
        return {"state": "success", "message": "찜한 영화에 저장했습니다.", "data": {"movie_id": movie_id, "wishlisted": True}}
    except Exception:
        db.rollback()
        return error_response("영화 찜 저장 실패")


@router.delete("/{movie_id}/wishlist")
def remove_movie_from_wishlist(
    movie_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        user_id = current_user["user_id"]
        rows = db.scalars(select(MovieWishlist).where(
            MovieWishlist.user_id == user_id,
            MovieWishlist.movie_id == movie_id,
        )).all()
        for row in rows:
            db.delete(row)
        db.commit()
        return {"state": "success", "message": "찜한 영화에서 제거했습니다.", "data": {"movie_id": movie_id, "wishlisted": False}}
    except Exception:
        db.rollback()
        return error_response("영화 찜 삭제 실패")


@router.get("/{movie_id}/similar")
def get_similar_movies(
    movie_id: int,
    limit: int = Query(6, ge=1, le=6),
    current_user: dict | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    try:
        movies = get_similar_movies_result(
            db,
            movie_id,
            limit,
            current_user["user_id"] if current_user else None,
        )
        if movies is None:
            return {"state": "failure", "message": "해당 영화를 찾을 수 없습니다.", "data": []}
        return {
            "state": "success",
            "message": "콘텐츠 기반 유사 영화 조회 성공",
            "data": movies,
        }
    except Exception:
        return error_response("유사 영화 조회 실패")


@router.put("/{movie_id}/rating")
def rate_movie(
    movie_id: int,
    request: MovieRatingRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        movie = db.scalar(select(Movie).where(Movie.id == movie_id))
        if movie is None:
            return {"state": "failure", "message": "해당 영화를 찾을 수 없습니다."}

        user_id = current_user["user_id"]
        if not rating_identity_matches(movie, movie_id, request):
            logger.warning(
                "rating_movie_identity_mismatch user_id=%s path_movie_id=%s "
                "expected_movie_id=%s expected_tmdb_id=%s actual_tmdb_id=%s "
                "expected_title=%r actual_title=%r",
                user_id,
                movie_id,
                request.expected_movie_id,
                request.expected_tmdb_id,
                movie.tmdb_id,
                request.expected_title,
                movie.title,
            )
            return JSONResponse(
                status_code=409,
                content={
                    "state": "failure",
                    "message": "영화 식별 정보가 일치하지 않아 리뷰를 저장하지 않았습니다. 페이지를 새로고침해 주세요.",
                },
            )

        rating = db.scalar(
            select(MovieRating).where(
                MovieRating.movie_id == movie_id,
                MovieRating.user_id == user_id,
            )
        )
        if rating is None:
            rating = MovieRating(
                user_id=user_id,
                movie_id=movie_id,
                score=request.score,
                comment=(request.comment or "").strip() or None,
                is_spoiler=request.is_spoiler,
            )
            db.add(rating)
        else:
            rating.score = request.score
            rating.comment = (request.comment or "").strip() or None
            rating.is_spoiler = request.is_spoiler
            rating.updated_at = func.now()

        db.commit()
        return {
            "state": "success",
            "message": "영화 평가가 저장되었습니다.",
            "data": get_rating_summary(db, movie_id, user_id),
        }
    except Exception:
        db.rollback()
        return error_response("영화 평가 저장 실패")


@router.delete("/{movie_id}/rating")
def delete_movie_rating(
    movie_id: int,
    request: MovieIdentityRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        user_id = current_user["user_id"]
        movie = db.scalar(select(Movie).where(Movie.id == movie_id))
        if movie is None:
            return {"state": "failure", "message": "해당 영화를 찾을 수 없습니다."}
        if not rating_identity_matches(movie, movie_id, request):
            logger.warning(
                "delete_rating_movie_identity_mismatch user_id=%s path_movie_id=%s "
                "expected_movie_id=%s expected_tmdb_id=%s actual_tmdb_id=%s "
                "expected_title=%r actual_title=%r",
                user_id,
                movie_id,
                request.expected_movie_id,
                request.expected_tmdb_id,
                movie.tmdb_id,
                request.expected_title,
                movie.title,
            )
            return JSONResponse(
                status_code=409,
                content={
                    "state": "failure",
                    "message": "영화 식별 정보가 일치하지 않아 리뷰를 삭제하지 않았습니다. 페이지를 새로고침해 주세요.",
                },
            )
        rating = db.scalar(
            select(MovieRating).where(
                MovieRating.movie_id == movie_id,
                MovieRating.user_id == user_id,
            )
        )
        if rating is not None:
            db.delete(rating)
            db.commit()
        return {
            "state": "success",
            "message": "영화 평가가 삭제되었습니다.",
            "data": get_rating_summary(db, movie_id, user_id),
        }
    except Exception:
        db.rollback()
        return error_response("영화 평가 삭제 실패")

    
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
    sort: Literal["relevance", "latest"] = Query("relevance"),
    db : Session = Depends(get_db),
):
    try:
        movies_result = genre_movies(db, genre, page, limit, sort)
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
                    "genres": movie.genres or [],
                    "year": movie.year,
                    "release_date": movie.release_date,
                }for movie in movies_result
            ]
        }
    except Exception:
        return error_response("장르별 영화 에러")


@router.get("/country/{country_code}")
def get_country_movies(
    country_code: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
):
    try:
        movies_result = country_movies(db, country_code, page, limit)
        return {
            "state": "success",
            "message": "제작국가별 영화 조회 성공",
            "data": [
                {
                    "movie_id": movie.id,
                    "title": movie.title,
                    "poster_path": movie.poster_path,
                    "vote_average": movie.vote_average,
                    "genres": movie.genres or [],
                    "year": movie.year,
                    "release_date": movie.release_date,
                    "production_countries": movie.production_countries or [],
                }
                for movie in movies_result
            ],
        }
    except Exception:
        return error_response("제작국가별 영화 조회 에러")

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
