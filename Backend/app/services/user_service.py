from pathlib import Path
from uuid import uuid4

from fastapi import Depends, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.models.actors import Actor
from app.models.interactions import UserMovieInteraction
from app.models.movies import Movie
from app.models.users import User, UserPreferenceScore

# 프로젝트 최상위 폴더를 기준으로 업로드 파일의 절대 경로를 구성한다.
# 현재 파일은 app/services/user_service.py에 있으므로 parents[2]가 프로젝트 루트이다.
BASE_DIR = Path(__file__).resolve().parents[2]

# 프로필 이미지가 실제로 저장되고 삭제되는 서버 내부 디렉터리이다.
# 사용자 업로드 파일을 app/uploads 아래에서 종류별로 관리하기 위해
# 프로필 전용 폴더인 images/user_profiles를 사용한다.
PROFILE_IMAGE_ROOT = (
    BASE_DIR / "app" / "uploads" / "images" / "user_profiles"
)

# DB에 저장하고 프론트엔드에 전달할 공개 URL의 앞부분이다.
# main.py에서 app/uploads를 "/uploads"로 연결했으므로 실제 저장 경로의
# images/user_profiles 부분까지 동일하게 이어서 작성해야 한다.
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
    return db.scalars(
        select(UserMovieInteraction)
        .where(
            UserMovieInteraction.user_id == user_id,
            UserMovieInteraction.action_type == "view"
        )
        # 최신 순으로 정렬
        .order_by(UserMovieInteraction.created_at.desc())
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
async def update_user_profile_image(db : Session, user_id: int, profile_image:str):
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
    
    if user.profile_image is not None:
        check, message = delet_user_profile_image(user.profile_image)
        if check == False:
            return check, message
    
    # 서버에 이미지 저장
    file_name = f"profile_{uuid4().hex}{extension}"
    file_path = PROFILE_IMAGE_ROOT/file_name

    file_path.write_bytes(contents)

    profile_image_url = f"{PUBLIC_PROFILE_IMAGE_PREFIX}/{file_name}"
    
    # db에 저장
    user.profile_image = profile_image_url
    db.commit()
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

    

# 파일에서 삭제
def delet_user_profile_image(profile_image_url: str):
    file_path = get_profile_image_path(profile_image_url)
    if not file_path:
        return False , "프로필 이미지 경로가 없습니다."
    if not file_path.exists():
        return False, "서버에 이미지가 저장되어 있지 않습니다."
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
