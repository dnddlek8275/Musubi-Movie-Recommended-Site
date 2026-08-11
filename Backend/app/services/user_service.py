from pathlib import Path
from uuid import uuid4

from fastapi import Depends, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.models.actors import Actor
from app.models.interactions import UserMovieInteraction
from app.models.movies import Movie
from app.models.users import User, UserPreferenceScore
from app.core.config import settings
from app.services.object_storage_service import (
    delete_object,
    parse_object_uri,
    resolve_object_url,
    upload_object,
)

# 프로젝트 최상위 폴더를 기준으로 업로드 파일의 절대 경로를 구성한다.
# 현재 파일은 app/services/user_service.py에 있으므로 parents[2]가 프로젝트 루트이다.
BASE_DIR = Path(__file__).resolve().parents[2]

# 프로필 이미지가 실제로 저장되고 삭제되는 서버 내부 디렉터리이다.
# 사용자 업로드 파일을 app/uploads 아래에서 종류별로 관리하기 위해
# 프로필 전용 폴더인 images/user_profiles를 사용한다.
PROFILE_IMAGE_ROOT = (
    BASE_DIR / "app" / "uploads" / "images" / "user_profiles"
)

# 기존 로컬 업로드 값의 읽기·삭제 호환을 위한 접두사다. 신규 업로드는
# Object Storage에 저장하며 DB에는 s3://bucket/key 형식으로 기록한다.
PUBLIC_PROFILE_IMAGE_PREFIX = "/uploads/images/user_profiles"

# 배포 환경이나 새로 프로젝트를 내려받은 환경에서도 이미지 저장이 가능하도록
# 필요한 상위 폴더를 함께 생성한다. 폴더가 이미 존재하면 변경하지 않는다.
PROFILE_IMAGE_ROOT.mkdir(parents=True, exist_ok=True)

# 최대 이미지 용량: 5MB
MAX_PROFILE_IMAGE_SIZE = 5 * 1024 * 1024

# 허용할 이미지 MIME 타입과 저장 확장자
ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}

# 유저 정보 ID 확인 후 반환
def get_user(db: Session, user_id : int) -> User|None:
    return db.query(User).filter(User.id == user_id).first()

# 기본 선호 목록과 새로 추가할 목록 - 중복값 제거
def check_unique_values(current_values, new_values):
    result = []
    check = set()

    for value in (current_values or [])+ (new_values or []):
        # 공백 제거
        value = value.strip()

        if not value:
            continue

        # 중복 - 넘어가기
        if value in check :
            continue

        result.append(value)
        check.add(value)
    
    return result

def movies_like_result(
        db: Session,
        user_id : int,
):
    like_movies = db.scalars(
        select(UserMovieInteraction)
        .where(
            UserMovieInteraction.user_id == user_id, 
            UserMovieInteraction.action_type=="like"
        )
    ).all()

    return like_movies

# 최근 조회한 영화 목록
def get_recently_viewed_movies_result(
        db: Session,
        user_id: int,
        limit: int = 5,
):
    # 과거에 동일 영화를 여러 번 조회해 이벤트 행이 중복돼 있어도 영화별
    # 가장 최근 기록 한 건만 선택한다. 바깥 쿼리에서 다시 최신순으로 정렬해
    # 재조회한 영화가 목록 맨 앞으로 오게 한다.
    ranked_interactions = (
        select(
            UserMovieInteraction.id.label("interaction_id"),
            func.row_number().over(
                partition_by=UserMovieInteraction.movie_id,
                order_by=(
                    UserMovieInteraction.created_at.desc(),
                    UserMovieInteraction.id.desc(),
                ),
            ).label("recent_rank"),
        )
        .where(
            UserMovieInteraction.user_id == user_id,
            UserMovieInteraction.action_type.in_(("view", "search_click")),
        )
        .subquery()
    )
    return db.scalars(
        select(UserMovieInteraction)
        .join(
            ranked_interactions,
            ranked_interactions.c.interaction_id == UserMovieInteraction.id,
        )
        .where(ranked_interactions.c.recent_rank == 1)
        .order_by(
            UserMovieInteraction.created_at.desc(),
            UserMovieInteraction.id.desc(),
        )
        .limit(limit)
    ).all()

# 사용자가 이미 조회,검색,좋아요한 영화 ID 
def get_candidate_movies(db: Session, user_id:int):
    interacted_movie_ids = select(UserMovieInteraction.movie.movie_id).where(UserMovieInteraction.user_id == user_id)

    return list(
        db.scalars(
            select(Movie)
            .where(Movie.poster_path.is_not(None))
            .where(Movie.id.not_in(interacted_movie_ids))
            .order_by(Movie.id.desc())
        ).all()
    )

# 이미지를 저장할 수 있는지 확인
def check_profile_image(image : UploadFile, contents : bytes):
    if not contents :
        return False, "이미지 파일이 없습니다.", None
    
    if image.content_type not in ALLOWED_IMAGE_TYPES:
        return False, ".jpg, png, webp이미지만 업로드 할 수 있습니다.", None
    
    if len(contents) > MAX_PROFILE_IMAGE_SIZE:
        return False, "이미지 용량이 너무 커서 업로드 할 수 없습니다.", None

    extension = ALLOWED_IMAGE_TYPES[image.content_type]

    return True, "검증 성공", extension

# 사용자 프로필 이미지 수정 및 저장
async def update_user_profile_image(db: Session, user_id: int, profile_image: UploadFile):
    # 사용자 찾기
    user = get_user(db, user_id)
    if not user:
        return False, "사용자가 없습니다."
    
    # 저장 가능한 이미지인지 확인
    contents = await profile_image.read()
    check_result, message, extension = check_profile_image(profile_image, contents)
    if check_result is False :
        return check_result, message

    if not check_result:
        return False, message
    
    old_profile_image = user.profile_image
    file_name = f"profile_{uuid4().hex}{extension}"
    object_key = f"{settings.OBJECT_STORAGE_PROFILE_PREFIX.strip('/')}/{user_id}/{file_name}"

    try:
        profile_image_uri = upload_object(
            key=object_key,
            contents=contents,
            content_type=profile_image.content_type or "application/octet-stream",
        )
    except Exception:
        return False, "Object Storage에 프로필 이미지를 저장하지 못했습니다."

    try:
        user.profile_image = profile_image_uri
        db.commit()
    except Exception:
        db.rollback()
        try:
            delete_object(profile_image_uri)
        except Exception:
            pass
        raise

    # 새 객체와 DB 반영이 성공한 뒤 이전 객체를 정리한다. 이전 객체 삭제 실패가
    # 새 프로필 반영을 되돌리지는 않으며, 운영 로그/정리 작업에서 처리한다.
    if old_profile_image:
        try:
            delet_user_profile_image(old_profile_image)
        except Exception:
            pass
    return True, "사용자 프로필 이미지 저장 성공"


# 프로필 이미지 저장했는지 확인 및 반환
def get_profile_image_path(profile_image_url:str):
    if not profile_image_url:
            return None
    perfix = PUBLIC_PROFILE_IMAGE_PREFIX + "/"
    if not profile_image_url.startswith(perfix):
        return None
    file_name = profile_image_url.replace(perfix, "", 1)
    return PROFILE_IMAGE_ROOT/file_name


def resolve_profile_image_url(
    profile_image_value: str | None,
    request_base_url: str | None = None,
) -> str | None:
    if not profile_image_value:
        return None

    object_url = resolve_object_url(profile_image_value)
    if object_url:
        return object_url

    if profile_image_value.startswith(("http://", "https://")):
        return profile_image_value

    if profile_image_value.startswith("/") and request_base_url:
        return request_base_url.rstrip("/") + profile_image_value

    return profile_image_value

    

# 파일에서 삭제
def delet_user_profile_image(profile_image_url: str):
    if parse_object_uri(profile_image_url):
        try:
            delete_object(profile_image_url)
            return True, "Object Storage 파일 삭제 완료"
        except Exception:
            return False, "Object Storage에서 프로필 이미지를 삭제하지 못했습니다."

    file_path = get_profile_image_path(profile_image_url)
    if not file_path:
        return False , "프로필 이미지 경로가 없습니다."
    if not file_path.exists():
        return True, "기존 로컬 파일이 이미 없습니다."
    file_path.unlink()
    return True, "파일 삭제 완료"

# 배우 저장
def  user_like_actor(db : Session, user_id:int, actor_id : int):
    # 해당 배우 조회
    actor = db.scalar(select(Actor).where(Actor.id == actor_id))

    if not actor:
        return {
            "state" : "failure",
            "message" : "DB - 배우 조회 싪패",
        }
    
    # 사용자 DB 조회
    user = get_user(db, user_id)

    if not user:
        return {
            "state" : "failure",
            "message" : "DB 사용자 조회 실패"
        }
    
    if actor.name in user.preferred_actors:
        return {
            "state" : "failure",
            "message" : "이미 선택한 배우입니다."
        }
    
    user.preferred_actors = check_unique_values(user.preferred_actors, [actor.name])

    db.commit()
    db.refresh(user)

    return {
        "state" : "success",
        "message" : "선호 배우 저장 성공",
        "data" :
        {
            "user_email" : user.email,
            "user_preferred_actors" : user.preferred_actors
        }
    }
