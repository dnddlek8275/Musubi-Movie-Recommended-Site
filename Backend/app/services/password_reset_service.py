from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import generate_password_reset_token, hash_password, hash_token
from app.models.tokens import PasswordResetToken, RefreshToken
from app.models.users import User

# 비밀번호 재설정 토큰 생성 함수
def create_password_reset_token(
        db : Session,
        user : User,
):
    now = datetime.now(timezone.utc)

    # 이전에 발급한 미사용 비밀번호 재설정 토큰 폐기
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.used_at.is_(None),
        PasswordResetToken.revoked_at.is_(None),
    ).update(
        {PasswordResetToken.revoked_at : now},
        synchronize_session=False,
    )

    # 이메일 링크에 넣을 원본 토큰 생성
    plain_token = generate_password_reset_token()
    # 원본 토큰을 SHA0256으로 해시
    token_hash = hash_token(plain_token)

    # DB에는 원본 토큰말고 해시 저장
    reset_token = PasswordResetToken(
        user_id = user.id,
        token_hash = token_hash,
        expires_at = (now + timedelta(minutes=settings.PASSWORD_RESET_EXPIRE_MINUTES))
    )

    db.add(reset_token)
    db.commit()
    db.refresh(reset_token)

    return reset_token, plain_token


# 비밀번호 재설정 이메일 발송 실패시 토큰 폐기
def revoke_password_reset_token(
        db: Session,
        reset_token : PasswordResetToken,
):
    reset_token.revoked_at =datetime.now(timezone.utc)
    db.commit()


# 비밀번호 재설정 토큰 검증하고 비밀번호 변경 함수
def reset_password_with_token(
        db : Session,
        plain_token : str,
        new_password : str,
):
    now = datetime.now(timezone.utc)

    # 이메일 링크에 포함된 원본 토큰을 해시
    token_hash = hash_token(plain_token)

    reset_token = (db.query(PasswordResetToken).filter(PasswordResetToken.token_hash == token_hash)
                   .with_for_update()
                   .first()
                )
    
    # 이미 사용한 토큰
    if reset_token is None:
        raise ValueError("유효하지 않은 비밀번호 재설정 링크입니다.")
    
    # 이미 사용한 토큰의 재사용 방지
    if reset_token.used_at is not None:
        raise ValueError("이미 사용된 비밀번호 재설정 링크입니다.")

    # 폐기된 토큰
    if reset_token.revoked_at is not None:
        raise ValueError("유효하지 않는 비밀번호 재설정 링크입니다.")
    
    # 만료 시간이 지난 토큰
    if reset_token.expires_at <= now:
        raise ValueError("만료된 비밀번호 재설정 링크입니다.")
    
    # 비밀번호를 변경할 사용자 조회
    user = (
        db.query(User)
        .filter(User.id == reset_token.user_id)
        .with_for_update()
        .first()
    )

    if user is None:
        raise ValueError("해당 사용자의 정보가 없습니다.")
    
    # 새 비밀번호 bcrypt 해시로 저장
    user.password_hash = hash_password(new_password)

    # 현재 재설정 토큰 사용 완료 처리 - expires_at은 원래 값 유지
    reset_token.used_at =now

    # 기존 로그인용 refresh_token 모두 폐기
    db.query(RefreshToken).filter(
        RefreshToken.user_id == user.id,
        RefreshToken.revoked_at.is_(None)
    ).update(
        {RefreshToken.revoked_at:now},
        synchronize_session=False,
    )

    # 현재 토큰 이외의 다른 재설정 토큰 모두 폐기
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.id != reset_token.id,
        PasswordResetToken.used_at.is_(None),
        PasswordResetToken.revoked_at.is_(None),
    ).update(
        {PasswordResetToken.revoked_at : now},
        synchronize_session=False,
    )

    # 비밀번호 변경과 토큰 사용 한번에 저장
    db.commit()