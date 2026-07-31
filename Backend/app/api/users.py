from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from sqlalchemy.orm import Session

from app.core.current_user import get_current_user
from app.core.api_responses import error_response
from app.core.dependencies import get_db
from app.schemas.movies import ShowMovies
from app.schemas.users import PreferenceDeleteRequest
from app.services.interaction_service import delete_liked_movie_result
from app.services.movies.ai_chat_recommend_service import get_chat_ai_recommended_movies_result
from app.services.movies.search_service import get_movie_result
from app.services.preference_delete_service import delete_my_preference_type_result
from app.services.preference_service import delete_my_preference_result, get_user_preference_scores
from app.services.user_service import delet_user_profile_image, get_profile_image_path, get_recently_viewed_movies_result, get_user, movies_like_result, update_user_profile_image


# 사용자 관련 API들을 묶는 Router /users/
router = APIRouter(
    prefix="/user",
    tags=["User"],
)

# 내 정보 조회 GET /user
@router.get("")
async def get_my_info(
    request : Request,
    cureent_user : dict = Depends(get_current_user),
    db : Session = Depends(get_db),
    ):
    try:
        # JWT 검증
        user_id = cureent_user["user_id"]
        # 사용자 정보 가져오기
        user = get_user(db, user_id)
        if not user:
            return {
                "state" : "failure",
                "message" : "DB에서 사용자 정보를 찾을 수 없습니다.",
            }
        if user.profile_image:
            user_profile_image = str(request.base_url).rstrip("/") + user.profile_image
        else : user_profile_image = None
        return {
            "state" : "success",
            "message" : "정보 조회 성공",
            "data" : {
                "email" : user.email,
                "nickname" : user.nickname,
                "profile_image" : user_profile_image,
                # "preferred_genres" : user.preferred_genres,
                # "preferred_actors" : user.preferred_actors,
                # "preferred_keywords" : user.preferred_keywords,
            }
        }
    
    except Exception:
        return error_response("정보 조회 실패")
    
# # 프로필 수정
@router.patch("/profile_image")
async def update_user_profile(
    request : Request,
    image : Annotated[UploadFile, File(...)],
    current_user : dict = Depends(get_current_user),
    db : Session = Depends(get_db),
):
    try:
        user_id = current_user["user_id"]
        result, message = await update_user_profile_image(db, user_id, image)
        if result is False:
            return{
                "state" : "failure",
                "message" : message
            }
        user = get_user(db, user_id)
        user_profile = str(request.base_url).rstrip("/") + user.profile_image
        return {
            "state" : "success",
            "message" : "이미지 수정 성공",
            "data" : {
                "user_profile" : user_profile
            }
        }
    except Exception:
        return error_response("사용자 프로필 수정 API 에러")
    
@router.delete("/delete/profile_image")
async def user_delete_profile(
    current_user = Depends(get_current_user),
    db : Session = Depends(get_db),
):
    try:
        user_id = current_user["user_id"]
        user = get_user(db, user_id)
        if user.profile_image is None:
            return {
                "state" : "failure",
                "message" : "사용자 프로필 이미지가 없습니다."
            }
        result, message = delet_user_profile_image(user.profile_image)
        if result is False:
            return {
                "state" : "failure",
                "message" : message,
            }
        user.profile_image = None
        db.commit()
        db.refresh(user)
        return{
            "state" : "success",
            "message" : "사용자 프로필 이미지 삭제 성공"
        }
    except Exception:
        db.rollback()
        return error_response("사용자 프로필 이미지 삭제 에러")

# 취향 GET /user/preferences
@router.get("/preferences")
async def get_my_preferences(
    current_user : dict = Depends(get_current_user),
    db : Session = Depends(get_db),
) :
    try:
        # JWT 검증
        user_id = current_user["user_id"]
        user = get_user(db, user_id)

        if user is None:
            return {
                "state": "failure",
                "message": "사용자 정보를 찾을 수 없습니다.",
            }
        
        # 좋아요·조회·검색으로 자동 학습된 취향 점수 조회
        preference_scores = get_user_preference_scores(db,user_id)
         # 프론트에서 사용하기 편하도록 취향 타입별로 분리한다.
        learned_preferences = {
            "genres": [],
            "actors": [],
            "keywords": [],
        }

        # DB의 단수형 preference_type을 응답의 복수형 키로 변환한다.
        preference_key_map = {
            "genre": "genres",
            "actor": "actors",
            "keyword": "keywords",
        }

        for preference in preference_scores:
            response_key = preference_key_map.get(
                preference.preference_type
            )

            # 현재 화면에서 보여주지 않는 director, language 등은 제외한다.
            if response_key is None:
                continue

            learned_preferences[response_key].append({
                "value": preference.preference_value,
                "score": round(preference.score or 0.0, 3),
            })

        return {
            "state" : "success",
            "message" : "취향 조회 성공",
            "data" : {
                # 사용자가 설정에서 직접 선택한 취향
                "explicit_preferences": {
                    "genres": user.preferred_genres or [],
                    "actors": user.preferred_actors or [],
                    "keywords": user.preferred_keywords or [],
                },

                # 좋아요·조회·검색으로 자동 학습된 취향
                "learned_preferences": learned_preferences,
            },
        }
    except Exception:
        return error_response("취향 조회 실패")

# 로그인한 사용자의 장르·배우·키워드 중 요청한 한 종류를 모두 삭제한다.
@router.delete("/preferences/{preference_type}")
async def delete_my_preference_type(
    preference_type: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        # 요청값으로 사용자 ID를 받지 않고 JWT에서 검증된 ID를 사용해
        # 로그인한 사용자가 자신의 취향 정보만 삭제할 수 있도록 제한한다.
        user_id = current_user["user_id"]

        # 취향 타입 검증, 사용자 조회, 명시적 취향 배열 초기화와 학습 점수 삭제는
        # 별도 서비스 함수에 맡겨 API가 인증과 요청 전달 역할에 집중하도록 한다.
        return delete_my_preference_type_result(
            db=db,
            user_id=user_id,
            preference_type=preference_type,
        )

    except Exception:
        # 인증 정보 확인이나 서비스 호출 과정에서 예상하지 못한 오류가 발생하면
        # 처리 중인 DB 변경이 남지 않도록 현재 트랜잭션을 되돌린다.
        db.rollback()
        return error_response("취향 전체 삭제 API 처리 중 에러가 발생했습니다.")

# 선호 종류 - 키 삭제
@router.delete("/preference/delete")
async def delete_my_preference(
    request : PreferenceDeleteRequest,
    current_user : dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        user_id = current_user["user_id"]

        preference_type = request.preference_type.strip()
        preference_value = request.preference_value.strip()
    
        if not preference_value:
            return {
                "state" : "failure",
                "message" : "삭제할 선호 값을 입력해주세요."
            }
        
        return delete_my_preference_result(db, user_id, preference_type, preference_value)
        
    except Exception:
        return error_response("사용자의 선호 키 삭제 에러")

# 좋아요 누른 영화 - 조회 /user/movies-like
@router.get("/movies-like")
async def get_my_like(
    current_user : dict = Depends(get_current_user),
    db : Session = Depends(get_db),
):
    try:
        # JWT 검증
        user_id = current_user["user_id"]

        # 사용자가 좋아요 누른 영화
        movies_result = movies_like_result(db, user_id)

        if not movies_result:
            return {
                "state" : "failure",
                "message" : "좋아요 누른 영화가 없습니다.",
            }
        
        return {
            "state" : "success",
            "message" : "좋아요 누른 영화 조회 성공",
            "data" : [
                get_movie_result(like.movie)
                for like in movies_result
            ],
        }

    except Exception:
        return error_response("좋아요 조회 에러")
    

# 좋아요 누른 영화 삭제
@router.delete("/movie-like/{movie_id}")
async def delete_movie_like(
    movie_id : int,
    current_user : dict = Depends(get_current_user),
    db : Session = Depends(get_db),
):
    try:
        user_id = current_user["user_id"]

        return delete_liked_movie_result(db, user_id, movie_id)
    except Exception:
        return error_response("좋아요 삭제 에러")


# 최근에 상세 조회한 영화 조회
@router.get("/recently-viewed", response_model=ShowMovies)
async def get_recently_movies(
    current_user : dict = Depends(get_current_user),
    limit : int = Query(5, ge=1, le=50),
    db : Session = Depends(get_db)
):
    try:
        # JWT 검증
        user_id = current_user["user_id"]

        movies_viewed_result = get_recently_viewed_movies_result(db, user_id, limit)

        if not movies_viewed_result:
            return {
                "state" : "failure",
                "message" : "최근 조회한 영화가 없습니다.",
                "data" : [],
            }
        return {
            "state" : "success",
            "message" : "최근 조회한 영화 조회 성공",
            "data" : [
                get_movie_result(viewed.movie)
                for viewed in movies_viewed_result
            ]

        }
    except Exception:
        return error_response("최근 본 영화 조회 에러")

# AI 채팅에서 추천받은 영화 이력을 조회한다.
@router.get("/chatai-recommended-movies")
def get_ai_recommended_movies(
    current_user : dict = Depends(get_current_user),
    limit : int = Query(10, ge=1, le=50),
    db : Session = Depends(get_db),
):
    try:
        user_id = current_user["user_id"]
        ai_movies_result = get_chat_ai_recommended_movies_result(db, user_id, limit)
        if ai_movies_result is None:
            return {
                "state" : "failure",
                "message" : "ai가 추천했던 영화가 없습니다.",
            }
        return {
            "state" : "success",
            "message" : "ai가 추천한 영화 API 성공",
            "data" : ai_movies_result,
        }
    except Exception:
        return error_response("ai가 추천한 영화 API 에러")
