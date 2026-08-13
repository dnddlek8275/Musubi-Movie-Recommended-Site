from datetime import datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.current_user import get_current_user
from app.core.api_responses import error_response
from app.core.config import settings
from app.core.dependencies import get_db
from app.schemas.movies import ShowMovies
from app.schemas.users import AccountProfileUpdateRequest, EmailVerificationConfirmRequest, EmailVerificationRequest, NicknameCheckRequest, OnboardingPreferencesRequest, PreferenceDeleteRequest
from app.models.tokens import EmailVerificationCode
from app.models.interactions import MovieRating, MovieWishlist, UserMovieInteraction
from app.models.movies import Movie
from app.models.users import User, UserPreferenceScore
from app.services.interaction_service import delete_liked_movie_result
from app.services.movies.ai_chat_recommend_service import get_chat_ai_recommended_movies_result
from app.services.movies.search_service import get_movie_result
from app.services.preference_delete_service import delete_my_preference_type_result
from app.services.preference_service import delete_my_preference_result, get_combined_user_preference_signals, get_user_preference_scores, save_onboarding_preferences
from app.services.user_service import (
    delet_user_profile_image,
    get_recently_viewed_movies_result,
    get_user,
    movies_like_result,
    resolve_profile_image_url,
    update_user_profile_image,
)
from app.services.email.email_service import send_account_email_verification_code
from app.services.email.email_verification_service import create_email_verification_code, expire_email_verification_code, validate_email_verification_code


# 사용자 관련 API들을 묶는 Router /users/
router = APIRouter(
    prefix="/user",
    tags=["User"],
)


def _nickname_is_used(db: Session, nickname: str, exclude_user_id: int) -> bool:
    normalized = nickname.strip().casefold()
    return db.query(User.id).filter(
        User.id != exclude_user_id,
        func.lower(func.trim(User.nickname)) == normalized,
    ).first() is not None


@router.post("/nickname-check")
async def check_account_nickname(
    request: NicknameCheckRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = current_user["user_id"]
    nickname = request.nickname.strip()
    user = get_user(db, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail={"state": "failure", "message": "사용자 정보를 찾을 수 없습니다."})

    available = not _nickname_is_used(db, nickname, user_id)
    return {
        "state": "success",
        "message": "사용 가능한 닉네임입니다." if available else "이미 사용 중인 닉네임입니다.",
        "data": {"available": available},
    }

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
        user_profile_image = resolve_profile_image_url(
            user.profile_image,
            str(request.base_url),
        )
        return {
            "state" : "success",
            "message" : "정보 조회 성공",
            "data" : {
                "email" : user.email,
                "nickname" : user.nickname,
                "profile_image" : user_profile_image,
                "personal_context": user.personal_context or "",
                # "preferred_genres" : user.preferred_genres,
                # "preferred_actors" : user.preferred_actors,
                # "preferred_keywords" : user.preferred_keywords,
            }
        }
    
    except Exception:
        return error_response("정보 조회 실패")


@router.post("/email-verification/request", status_code=status.HTTP_202_ACCEPTED)
async def request_account_email_verification(
    request: EmailVerificationRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = current_user["user_id"]
    email = str(request.email).strip().lower()
    user = get_user(db, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail={"state": "failure", "message": "사용자 정보를 찾을 수 없습니다."})
    if user.email.strip().lower() == email:
        raise HTTPException(status_code=409, detail={"state": "failure", "message": "현재 사용 중인 이메일입니다."})
    if db.query(User.id).filter(func.lower(User.email) == email).first() is not None:
        raise HTTPException(status_code=409, detail={"state": "failure", "message": "이미 사용 중인 이메일입니다."})

    try:
        verification, plain_code = create_email_verification_code(db, email, "email_change")
    except ValueError as exc:
        raise HTTPException(status_code=429, detail={"state": "failure", "message": str(exc)}) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail={"state": "error", "message": "인증번호 생성에 실패했습니다."}) from exc

    try:
        await send_account_email_verification_code(email, plain_code)
    except Exception as exc:
        expire_email_verification_code(db, verification)
        raise HTTPException(status_code=503, detail={"state": "error", "message": "인증번호 이메일 발송에 실패했습니다."}) from exc

    return {
        "state": "success",
        "message": "인증번호를 이메일로 전송했습니다.",
        "data": {"expires_in_seconds": 300},
    }


@router.post("/email-verification/confirm")
async def confirm_account_email_verification(
    request: EmailVerificationConfirmRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = current_user["user_id"]
    email = str(request.email).strip().lower()
    user = get_user(db, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail={"state": "failure", "message": "사용자 정보를 찾을 수 없습니다."})
    if user.email.strip().lower() == email:
        raise HTTPException(status_code=409, detail={"state": "failure", "message": "현재 사용 중인 이메일입니다."})
    if db.query(User.id).filter(User.id != user_id, func.lower(User.email) == email).first() is not None:
        raise HTTPException(status_code=409, detail={"state": "failure", "message": "이미 사용 중인 이메일입니다."})

    try:
        validate_email_verification_code(db, email, request.verification_code, "email_change")
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail={"state": "failure", "message": str(exc)}) from exc

    return {
        "state": "success",
        "message": "이메일 인증이 완료되었습니다.",
        "data": {"verified": True},
    }


@router.patch("/profile")
async def update_account_profile(
    request: AccountProfileUpdateRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = current_user["user_id"]
    user = get_user(db, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail={"state": "failure", "message": "사용자 정보를 찾을 수 없습니다."})

    nickname = request.nickname.strip() if request.nickname is not None else user.nickname
    next_email = str(request.email).strip().lower() if request.email is not None else user.email
    email_changed = next_email != user.email.strip().lower()
    personal_context = (
        request.personal_context.strip()
        if request.personal_context is not None
        else (user.personal_context or "")
    )

    if _nickname_is_used(db, nickname, user_id):
        raise HTTPException(status_code=409, detail={"state": "failure", "message": "이미 사용 중인 닉네임입니다."})
    if email_changed:
        if db.query(User.id).filter(User.id != user_id, func.lower(User.email) == next_email).first() is not None:
            raise HTTPException(status_code=409, detail={"state": "failure", "message": "이미 사용 중인 이메일입니다."})
        if not request.verification_code:
            raise HTTPException(status_code=400, detail={"state": "failure", "message": "새 이메일 인증을 완료해 주세요."})
        try:
            email_verification = validate_email_verification_code(
                db,
                next_email,
                request.verification_code,
                "email_change",
            )
            # 이메일 저장이 성공하면 같은 인증번호를 다시 사용할 수 없도록 소비한다.
            db.delete(email_verification)
        except ValueError as exc:
            db.rollback()
            raise HTTPException(status_code=400, detail={"state": "failure", "message": str(exc)}) from exc

    user.nickname = nickname
    user.email = next_email
    user.personal_context = personal_context or None
    db.commit()
    db.refresh(user)
    return {
        "state": "success",
        "message": "계정 정보가 수정되었습니다.",
        "data": {
            "email": user.email,
            "nickname": user.nickname,
            "personal_context": user.personal_context or "",
        },
    }


@router.delete("")
async def delete_my_account(
    response: Response,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = current_user["user_id"]
    user = get_user(db, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail={"state": "failure", "message": "사용자 정보를 찾을 수 없습니다."})

    email = user.email.strip().lower()
    profile_image = user.profile_image
    try:
        db.query(EmailVerificationCode).filter(
            func.lower(EmailVerificationCode.email) == email,
        ).delete(synchronize_session=False)
        db.delete(user)
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail={"state": "error", "message": "계정 탈퇴 처리에 실패했습니다."}) from exc

    if profile_image:
        delet_user_profile_image(profile_image)

    response.delete_cookie(
        key="refresh_token",
        path=settings.REFRESH_COOKIE_PATH,
        samesite="lax",
        secure=settings.REFRESH_COOKIE_SECURE,
        httponly=True,
    )
    return {
        "state": "success",
        "message": "계정이 탈퇴 처리되었습니다.",
    }
    
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
        user_profile = resolve_profile_image_url(
            user.profile_image,
            str(request.base_url),
        )
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

        effective_preferences = get_combined_user_preference_signals(db, user_id)
        for preference in effective_preferences:
            response_key = preference_key_map.get(
                preference.preference_type
            )

            # 추천 계산에 쓰는 장르·배우·키워드만 학습 취향으로 응답한다.
            if response_key is None:
                continue

            if preference.behavior_score <= 0:
                continue
            learned_preferences[response_key].append({
                "value": preference.preference_value,
                # 조회·검색·좋아요뿐 아니라 별점·찜과 시간 감쇠까지 반영한 실효 점수다.
                "score": round(preference.behavior_score, 3),
            })

        # 실제 추천 계산과 동일하게 직접 설정값과 행동 학습 점수를 합산한 결과다.
        combined_preferences = {
            "genres": [],
            "actors": [],
            "keywords": [],
        }
        for preference in effective_preferences:
            response_key = preference_key_map.get(preference.preference_type)
            if response_key is None:
                continue
            combined_preferences[response_key].append({
                "value": preference.preference_value,
                "score": round(preference.score, 3),
            })

        return {
            "state" : "success",
            "message" : "취향 조회 성공",
            "data" : {
                # 사용자가 설정에서 직접 선택한 취향
                "explicit_preferences": {
                    "genres": user.preferred_genres or [],
                    "actors": user.preferred_actors or [],
                    "directors": user.preferred_directors or [],
                    "keywords": user.preferred_keywords or [],
                },

                # 좋아요·조회·검색으로 자동 학습된 취향
                "learned_preferences": learned_preferences,
                # 직접 선택값과 행동 학습값을 합산한 실제 추천 기준
                "combined_preferences": combined_preferences,
                "onboarding_completed": user.onboarding_completed,
            },
        }
    except Exception:
        return error_response("취향 조회 실패")


@router.patch("/preferences")
async def save_my_onboarding_preferences(
    request: OnboardingPreferencesRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        user = get_user(db, current_user["user_id"])
        if user is None:
            return {
                "state": "failure",
                "message": "사용자 정보를 찾을 수 없습니다.",
            }

        saved = save_onboarding_preferences(
            db=db,
            user=user,
            genres=request.genres,
            actors=request.actors,
            keywords=request.keywords,
            onboarding_completed=request.onboarding_completed,
        )
        return {
            "state": "success",
            "message": "초기 취향 정보가 저장되었습니다.",
            "data": saved,
        }
    except Exception:
        db.rollback()
        return error_response("초기 취향 정보 저장에 실패했습니다.")


@router.get("/preferences/insights")
async def get_my_preference_insights(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = current_user["user_id"]
    grouped = {"genres": [], "actors": [], "keywords": []}
    key_map = {"genre": "genres", "actor": "actors", "keyword": "keywords"}
    for preference in get_combined_user_preference_signals(db, user_id):
        key = key_map.get(preference.preference_type)
        if key:
            grouped[key].append({
                "value": preference.preference_value,
                "score": round(preference.score or 0.0, 3),
            })

    keyword_labels = {
        "based on novel or book": "소설·책 원작",
        "based on true story": "실화 바탕",
        "revenge": "복수",
        "friendship": "우정",
        "love": "사랑",
        "coming of age": "성장",
        "family": "가족",
        "detective": "탐정·추리",
        "superhero": "슈퍼히어로",
        "dystopia": "디스토피아",
        "supernatural": "초자연",
        "magic": "마법",
        "time travel": "시간 여행",
        "survival": "생존",
        "road trip": "로드 트립",
        "sports": "스포츠",
        "martial arts": "무술",
        "alien": "외계 생명체",
        "dark comedy": "블랙 코미디",
        "animation": "애니메이션",
        "based on webcomic or webtoon": "웹툰 원작",
        "cooking": "요리",
        "food": "요리",
        "magazine editor": "잡지 편집자",
        "musical": "뮤지컬",
        "body exchange": "몸 바꾸기",
        "bromance": "브로맨스",
        "advertising": "광고",
        "romcom": "로맨틱 코미디",
        "remake": "리메이크",
        "castle": "성",
        "transformation": "변신",
        "cartoon": "만화",
        "france": "프랑스",
        "fairy tale": "동화",
        "new york city": "뉴욕",
        "hero": "영웅",
        "based on young adult novel": "청소년 소설 원작",
        "zombie": "좀비",
        "post-apocalyptic future": "포스트 아포칼립스",
        "interspecies romance": "종족을 초월한 사랑",
        "zombie apocalypse": "좀비 아포칼립스",
        "romance": "로맨스",
        "satire": "풍자",
        "20th century": "20세기",
        "fight for survival": "생존 투쟁",
        "police chief": "경찰서장",
        "aliens": "외계 생명체",
        "remote village": "외딴 마을",
        "hunted": "추격",
        "police officer": "경찰관",
        "gwangju uprising": "광주 민주화 운동",
        "democracy": "민주주의",
        "political conspiracy": "정치적 음모",
        "undercover operation": "잠입 작전",
        "taxi": "택시",
        "1980s": "1980년대",
        "double cross": "배신",
        "historical event": "역사적 사건",
        "inter-korean relations": "남북 관계",
        "double agent": "이중 스파이",
        "taxi driver": "택시 기사",
        "north korea": "북한",
        "protest": "시위",
        "south korea": "대한민국",
        "national intelligence service (nis)": "국가정보원",
    }
    templates = {
        "genre": lambda value: f"{value} 장르가 취향에 가장 가까워 보여요.",
        "actor": lambda value: f"{value} 배우의 작품에 관심이 많아 보여요.",
        "keyword": lambda value: f"{value} 느낌의 이야기를 좋아하는 것 같아요.",
    }
    insights = {}
    for singular, plural in (("genre", "genres"), ("actor", "actors"), ("keyword", "keywords")):
        value = str((grouped[plural][0] if grouped[plural] else {}).get("value") or "").strip()
        display_value = keyword_labels.get(value.casefold(), value) if singular == "keyword" else value
        insights[singular] = {
            "value": display_value,
            "reason": templates[singular](display_value) if display_value else "분석할 데이터가 더 필요해요.",
        }

    return {
        "state": "success",
        "message": "활동 취향 분석 문장을 조회했습니다.",
        "data": {"insights": insights},
    }


@router.delete("/preferences/learned")
async def reset_my_learned_preferences(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        user_id = current_user["user_id"]
        user = get_user(db, user_id)
        if user is None:
            return {"state": "failure", "message": "사용자 정보를 찾을 수 없습니다."}
        deleted_count = db.query(UserPreferenceScore).filter(
            UserPreferenceScore.user_id == user_id,
        ).delete(synchronize_session=False)
        user.preference_learning_reset_at = datetime.now(ZoneInfo("Asia/Seoul"))
        db.commit()
        return {
            "state": "success",
            "message": "활동에서 학습한 취향을 초기화했습니다.",
            "data": {"deleted_score_count": deleted_count},
        }
    except Exception:
        db.rollback()
        return error_response("학습 취향 초기화에 실패했습니다.")

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


@router.get("/wishlist")
def get_my_wishlist(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        rows = db.execute(
            select(MovieWishlist, Movie)
            .join(Movie, Movie.id == MovieWishlist.movie_id)
            .where(MovieWishlist.user_id == current_user["user_id"])
            .order_by(MovieWishlist.created_at.desc(), MovieWishlist.id.desc())
        ).all()
        return {
            "state": "success",
            "message": "찜한 영화 조회 성공",
            "data": [get_movie_result(movie) for _wishlist, movie in rows],
        }
    except Exception:
        return error_response("찜한 영화 조회 에러")


# 사용자가 남긴 별점·리뷰를 최신 수정순으로 조회한다.
# 리뷰 문구가 없는 별점 평가도 마이페이지 활동과 건수에 포함한다.
@router.get("/reviews")
def get_my_reviews(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        user_id = current_user["user_id"]
        rows = (
            db.query(MovieRating, Movie)
            .join(Movie, Movie.id == MovieRating.movie_id)
            .filter(
                MovieRating.user_id == user_id,
            )
            .order_by(MovieRating.updated_at.desc(), MovieRating.id.desc())
            .all()
        )
        return {
            "state": "success",
            "message": "내 리뷰 조회 성공",
            "data": [
                {
                    "id": rating.id,
                    "score": rating.score,
                    "comment": rating.comment,
                    "is_spoiler": bool(rating.is_spoiler),
                    "created_at": rating.created_at,
                    "updated_at": rating.updated_at,
                    "movie": get_movie_result(movie),
                }
                for rating, movie in rows
            ],
        }
    except Exception:
        return error_response("내 리뷰 조회 에러")


@router.get("/public/{user_id}/activity")
def get_public_user_activity(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    try:
        user = db.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=404, detail={"state": "failure", "message": "사용자를 찾을 수 없습니다."})

        like_rows = db.execute(
            select(UserMovieInteraction, Movie)
            .join(Movie, Movie.id == UserMovieInteraction.movie_id)
            .where(
                UserMovieInteraction.user_id == user_id,
                UserMovieInteraction.action_type == "like",
            )
            .order_by(UserMovieInteraction.created_at.desc(), UserMovieInteraction.id.desc())
        ).all()
        liked_movies = []
        seen_movie_ids = set()
        for _interaction, movie in like_rows:
            if movie.id in seen_movie_ids:
                continue
            seen_movie_ids.add(movie.id)
            liked_movies.append(get_movie_result(movie))

        wishlist_rows = db.execute(
            select(MovieWishlist, Movie)
            .join(Movie, Movie.id == MovieWishlist.movie_id)
            .where(MovieWishlist.user_id == user_id)
            .order_by(MovieWishlist.created_at.desc(), MovieWishlist.id.desc())
        ).all()

        rating_rows = (
            db.query(MovieRating, Movie)
            .join(Movie, Movie.id == MovieRating.movie_id)
            .filter(MovieRating.user_id == user_id)
            .order_by(MovieRating.updated_at.desc(), MovieRating.id.desc())
            .all()
        )
        return {
            "state": "success",
            "message": "회원 공개 활동 조회 성공",
            "data": {
                "user": {
                    "id": user.id,
                    "nickname": user.nickname,
                    "profile_image": resolve_profile_image_url(user.profile_image, str(request.base_url)),
                },
                "liked_movies": liked_movies,
                "wishlisted_movies": [get_movie_result(movie) for _wishlist, movie in wishlist_rows],
                "reviews": [
                    {
                        "id": rating.id,
                        "score": rating.score,
                        "comment": rating.comment,
                        "is_spoiler": bool(rating.is_spoiler),
                        "updated_at": rating.updated_at,
                        "movie": get_movie_result(movie),
                    }
                    for rating, movie in rating_rows
                ],
            },
        }
    except HTTPException:
        raise
    except Exception:
        return error_response("회원 공개 활동 조회 에러")
    

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
