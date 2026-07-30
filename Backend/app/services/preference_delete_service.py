from sqlalchemy.orm import Session

from app.models.users import UserPreferenceScore
from app.services.user_service import get_user


# 사용자의 장르·배우·키워드 중 요청한 한 종류의 명시적 취향과 학습 점수를 모두 삭제한다.
def delete_my_preference_type_result(
    db: Session,
    user_id: int,
    preference_type: str,
):
    try:
        # URL 등 외부 입력에 포함될 수 있는 앞뒤 공백과 대소문자 차이를 제거해
        # 서비스 내부에서는 DB에 저장된 preference_type 형식과 동일하게 비교한다.
        normalized_preference_type = preference_type.strip().lower()

        # 외부에서 받은 문자열로 User의 임의 속성을 변경하지 않도록
        # 삭제를 허용하는 취향 타입과 실제 배열 속성을 명시적으로 연결한다.
        preference_config = {
            "genre": {
                "attribute": "preferred_genres",
                "label": "선호 장르",
            },
            "actor": {
                "attribute": "preferred_actors",
                "label": "선호 배우",
            },
            "keyword": {
                "attribute": "preferred_keywords",
                "label": "관심 키워드",
            },
        }

        config = preference_config.get(normalized_preference_type)

        # 현재 API에서 지원하는 장르·배우·키워드 이외의 타입은
        # 사용자 데이터에 영향을 주지 않고 정상 실패 응답으로 처리한다.
        if config is None:
            return {
                "state": "failure",
                "message": "허용되지 않는 취향 타입입니다.",
                "data": {
                    "allowed_types": ["genre", "actor", "keyword"],
                },
            }

        # 프로젝트의 기존 사용자 조회 함수를 재사용해 조회 로직의 중복을 피한다.
        user = get_user(db, user_id)

        if not user:
            return {
                "state": "failure",
                "message": "사용자 정보를 찾을 수 없습니다.",
            }

        # 요청한 종류의 명시적 취향 배열만 빈 배열로 초기화한다.
        # 예를 들어 genre를 삭제해도 배우와 키워드 배열은 그대로 유지한다.
        setattr(user, config["attribute"], [])

        # 좋아요·조회·검색으로 자동 누적된 취향 점수 중 요청한 타입만 삭제한다.
        # 다른 취향 타입과 사용자의 영화 행동 기록은 이 함수에서 변경하지 않는다.
        deleted_score_count = db.query(UserPreferenceScore).filter(
            UserPreferenceScore.user_id == user_id,
            UserPreferenceScore.preference_type == normalized_preference_type,
        ).delete(synchronize_session=False)

        # 명시적 취향 배열 변경과 학습 점수 삭제가 함께 반영되도록
        # 모든 DB 변경을 마친 뒤 하나의 트랜잭션으로 확정한다.
        db.commit()

        return {
            "state": "success",
            "message": f"{config['label']}를 모두 삭제했습니다.",
            "data": {
                "preference_type": normalized_preference_type,
                "deleted_score_count": deleted_score_count,
            },
        }

    except Exception as e:
        # 배열 초기화와 학습 점수 삭제 중 하나라도 실패하면
        # 일부 데이터만 변경된 상태가 남지 않도록 전체 작업을 되돌린다.
        db.rollback()
        return {
            "state": "error",
            "message": "취향 전체 삭제 중 에러가 발생했습니다.",
            "error": str(e),
        }
