import json

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.admin import AdminAuditLog
from app.models.users import User


def get_admin_role_target(
    db: Session,
    current_admin: User,
    email: str,
    requested_is_admin: bool,
) -> User:
    """이메일로 권한 변경 대상자를 조회하고 변경 가능한 요청인지 검사한다."""

    # 입력값 앞뒤의 공백을 없애고 소문자로 통일해 이메일을 비교한다.
    normalized_email = email.strip().lower()

    # DB에 저장된 이메일의 대소문자와 관계없이 대상 사용자를 조회한다.
    target_user = (
        db.query(User)
        .filter(func.lower(User.email) == normalized_email)
        .first()
    )

    # 입력한 이메일로 가입한 사용자가 없으면 권한 변경을 중단한다.
    if target_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "state": "failure",
                "message": "해당 이메일의 사용자를 찾을 수 없습니다.",
                "code": "USER_NOT_FOUND",
            },
        )

    # 현재 관리자가 자신의 권한을 직접 회수해 관리 기능을 잃는 상황을 막는다.
    if target_user.id == current_admin.id and requested_is_admin is False:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "state": "failure",
                "message": "자신의 관리자 권한은 직접 회수할 수 없습니다.",
                "code": "CANNOT_REVOKE_SELF",
            },
        )

    # 현재 권한과 요청한 권한이 같으면 불필요한 DB 변경과 감사 로그 생성을 막는다.
    if target_user.is_admin == requested_is_admin:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "state": "failure",
                "message": (
                    "이미 관리자 권한을 가진 사용자입니다."
                    if requested_is_admin
                    else "이미 일반 사용자입니다."
                ),
                "code": "ADMIN_ROLE_UNCHANGED",
            },
        )

    return target_user


def change_admin_role(
    db: Session,
    current_admin: User,
    target_user: User,
    is_admin: bool,
) -> None:
    """사용자의 관리자 권한을 변경하고 변경 이력을 세션에 추가한다."""

    # 감사 로그에 변경 전 권한을 남기기 위해 값을 먼저 보관한다.
    previous_is_admin = target_user.is_admin

    # 요청받은 값으로 대상 사용자의 관리자 권한을 변경한다.
    target_user.is_admin = is_admin

    # 권한 부여와 권한 회수를 감사 로그에서 구분할 수 있도록 action을 설정한다.
    action = "GRANT_ADMIN" if is_admin else "REVOKE_ADMIN"

    # 누가 누구의 권한을 어떻게 변경했는지 감사 로그로 기록한다.
    audit_log = AdminAuditLog(
        admin_user_id=current_admin.id,
        target_table="users",
        target_id=target_user.id,
        action=action,
        before_data=json.dumps(
            {
                "email": target_user.email,
                "is_admin": previous_is_admin,
            },
            ensure_ascii=False,
        ),
        after_data=json.dumps(
            {
                "email": target_user.email,
                "is_admin": target_user.is_admin,
            },
            ensure_ascii=False,
        ),
    )

    db.add(audit_log)

    # 여기서는 commit하지 않는다. 호출한 라우터에서 권한 변경과 감사 로그를
    # 한 번에 commit해야 둘 중 하나가 실패할 때 모두 rollback할 수 있다.
