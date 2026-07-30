
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.users import User, UserPreferenceScore
from app.services.user_service import check_unique_values, get_user

PREFERENCE_ACTION_SCORE = {
    "view": 0.5,
    "search_click": 0.8,
    "like": 2.0,
    # "search": 1.0,
}

PREFERENCE_TYPES = {
    "genre",
    "actor",
    "director",
    "keyword",
    "language",
    "character",
}

# 영화.장르 사용자의 장르에 추가
def movie_genre_add_preferences_user(user, movie):
    user.preferred_genres = check_unique_values(user.preferred_genres, movie.genres)

    user.preferred_actors = check_unique_values(user.preferred_actors, movie.cast)

    user.preferred_keywords = check_unique_values(user.preferred_keywords, movie.keywords)


def get_user_preference_scores(db, user_id):
    return list(
        db.scalars(
            select(UserPreferenceScore)
            .where(UserPreferenceScore.user_id == user_id)
            .order_by(UserPreferenceScore.score.desc())
        ).all()
    )

def delete_my_preference_result(
        db: Session,
        user_id : int,
        preference_type : str,
        preference_value : str,
):
    user = get_user(db, user_id)

    if not user:
        return {
            "state" : "failure",
            "message" : "DB에서 사용자 정보가 없음"
        }
    
    preference_column_map = {
        "genre" : User.preferred_genres,
        "actor" : User.preferred_actors,
        "keyword" : User.preferred_keywords,
    }

    if preference_type not in preference_column_map:
        return {
            "state" : "failure",
            "message" : "허용되지 않는 타입입니다."
        }
    
    target_column = preference_column_map[preference_type]

    # DB에서 배열 컬럼안의 선호 값 하나만 제거
    db.query(User).filter(User.id == user_id).update(
        {
            target_column : func.array_remove(target_column, preference_value)
        },
        synchronize_session=False
    )
    db.commit()
    return {
        "state" : "success",
        "message" : "사용자의 선호값 삭제 성공",
        "data" : {
            "preferred_genres" : user.preferred_genres,
            "preferred_actors" : user.preferred_actors,
            "preferred_keywords" : user.preferred_keywords,
        }
    }
    

# 사용자 해동 점수 누적
def add_user_preference_score(
        db : Session,
        user_id : int,
        preference_type : str,
        preference_value : str,
        action_type : str,
):
    # 액션 형태를 받지 않은 경우 False로 반환
    if not preference_value or not preference_type or not action_type:
        return False
    
    # 저장 형태 앞뒤 공백 제거
    preference_type = preference_type.strip()
    preference_value = preference_value.strip()
    action_type = action_type.strip()

    if not preference_type or not preference_value or not action_type:
        return False
    if preference_type not in PREFERENCE_TYPES:
        return False
    
    score_delta = PREFERENCE_ACTION_SCORE.get(action_type)

    # 지원하지 않는 행동은 점수를 반영하지 않는다.
    if score_delta is None:
        return False
    
    # 저장된 점수가 DB에 있는 경우 편집
    preference_score = db.scalar(
        select(UserPreferenceScore)
        .where(
            UserPreferenceScore.user_id == user_id,
            UserPreferenceScore.preference_type == preference_type,
            UserPreferenceScore.preference_value == preference_value,
        )
    )

    # 이미 있는 점수면 score 컬럼에 누적
    if preference_score:
        preference_score.score = (
            preference_score.score or 0
        ) + score_delta

    else :
        # 처음 발생한 행동이면 새로운 행 생성
        preference_score = UserPreferenceScore(
            user_id = user_id,
            preference_type = preference_type,
            preference_value = preference_value,
            score = score_delta,
        )
        db.add(preference_score)
        
    return True


# 사용자가 영화 한편의 메타데이터를 사용자 취향 점수로 반영
def add_movie_preference_scores(
        db : Session,
        user_id : int,
        movie,
        action_type : str,
):

    added_count = 0

    # 같은 영화 안에 값이 중복되어도 한번반 반영
    for preference_type, preference_value in iter_movie_preference_values(movie):
        saved = add_user_preference_score(
            db = db,
            user_id = user_id,
            preference_type= preference_type,
            preference_value= preference_value,
            action_type= action_type,
        )
        if saved :
            added_count +=1
    # character는 Movie에 직접 없으므로 여기서는 제외 - Character.movie_id로 연결해서 처리
    return added_count

# 사용자가 영화 한편의 메타데이터를 개인 취향 점수에 사용할 값을 꺼낸다.
def iter_movie_preference_values(movie):
    # 영화 필드를 취향 종류별 목록으로 변환
    movie_preferences = {
        "genre" : movie.genres or [],
        "actor" : movie.cast or [],
        "keyword" : movie.keywords or [],
        # 문자열 하나 - 리스트로 감싸기
        "director" : [movie.director] if movie.director else [],
        "language" : [movie.language] if movie.language else [],
    }

    # 같은 영화 안에 값이 중복되어도 한번반 반영
    for preference_type, values in movie_preferences.items():
        unique_values = {
            value.strip()
            for value in values
            if isinstance(value, str) and value.strip()
        }

        for preference_value in unique_values:
            yield preference_type, preference_value

# 사용자 취향 점수 하나 차감하는 함수
def decrease_user_preference_score(
        db : Session,
        user_id : int,
        preference_type : str,
        preference_value : str,
        score_delta : float,
):
    preference_type = preference_type.strip()
    preference_value = preference_value.strip()

    if preference_type not in PREFERENCE_TYPES:
        return False
    
    preference_score = db.scalar(
        select(UserPreferenceScore)
        .where(
            UserPreferenceScore.user_id == user_id,
            UserPreferenceScore.preference_type == preference_type,
            UserPreferenceScore.preference_value == preference_value
        )
    )
    #  과저 데이터에 취향 점수가 없는 경우
    if preference_score is None :
        return False
    
    remaining_score = (preference_score.score or 0.0) - score_delta

    # 점수가 0 이하가 되면 취향 점수 행을 삭제
    if remaining_score <= 0:
        db.delete(preference_score)
    else :
        preference_score.score = remaining_score

    return True

# 영화 한 편에서 발생했던 취향 점수 취소
def decrease_movie_preference_scores(
        db : Session,
        user_id : int,
        movie,
        action_type : str,
        action_count : int =1,
):
    if not action_type or action_count <= 0:
        return 0
    
    action_type = action_type.strip()

    if not action_type:
        return 0
    # like인 경우 2.0 반환
    action_score = PREFERENCE_ACTION_SCORE.get(action_type)

    if action_score is None :
        return 0
    
    # 좋아요가 중복일 경우 모두 차감
    score_delta = action_score * action_count
    decreased_count = 0

    for preference_type, preference_value in iter_movie_preference_values(movie):
        decreased = decrease_user_preference_score(
            db = db,
            user_id = user_id,
            preference_type = preference_type,
            preference_value = preference_value,
            score_delta = score_delta,
        )

        if decreased:
            decreased_count+=1

    return decreased_count