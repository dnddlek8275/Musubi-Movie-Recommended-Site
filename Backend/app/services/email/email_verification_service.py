from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session
from app.core.config import settings

from app.core.security import generate_email_verification_code, hash_email_verification_code, verify_email_verification_code
from app.models.tokens import EmailVerificationCode

# 인증번호 생성 후 DB에 bcrypt 해시 저장
def create_email_verification_code(
        db:Session,
        email : str,
        purpose :str = "signup",
):
    # 현재 시간을 UTC 기준으로 저장
    now = datetime.now(timezone.utc)
    # 이메일 주소 정리
    normalized_email = email.strip().lower()

    # 해당 이메일의 가장 최근 인증번호 조회
    latest_code = (
        db.query(EmailVerificationCode)
        .filter(
            EmailVerificationCode.email == normalized_email,
            EmailVerificationCode.purpose == purpose,
        )
        # 최신순으로 정렬
        .order_by(EmailVerificationCode.created_at.desc())
        # 조회한 행을 잠그는 기능
        .with_for_update()
        .first()
    )

    # 인증 번호 재전송 가능 시간
    if latest_code is not None:
        resend_available_at = (latest_code.created_at + timedelta(seconds = settings.EMAIL_VERIFICATION_RESEND_SECONDS))

        # 60 초 전에 재전송 요청하면 거부
        if now < resend_available_at:
                remaining_seconds = int((resend_available_at-now).total_seconds()) #인증번호를 다시 전송할 수 있을 때까지 남은 시간을 초 단위로 계산하는 코드

                raise ValueError(f"{remaining_seconds}초 후 다시 요청해주세요.")
        
        # 기존 미사용 인증번호 만료 처리
        if (latest_code.verified_at is None and latest_code.expires_at > now):
            latest_code.expires_at = now

    # 이메일로 전송할 숫자 6자리 생성
    plain_code = generate_email_verification_code()
    # DB - bcrypt 해시로 저장
    code_hash = hash_email_verification_code(plain_code)

    # EmailVerificationCode 테이블에 저장할 이메일 인증번호 객체
    verification = EmailVerificationCode(
         email = normalized_email,
         purpose = purpose,
         code_hash = code_hash,
         expires_at = (now + timedelta(minutes=settings.EMAIL_VERIFICATION_EXPIRE_MINUTES))
    )

    db.add(verification)
    db.commit()
    db.refresh(verification)

    return verification, plain_code

# 이메일 발송이 실패했을 때 생성된 인증번호 만료 시키는 함수
def expire_email_verification_code(
        db : Session,
        verification : EmailVerificationCode,
):
     verification.expires_at = datetime.now(timezone.utc)
     db.commit()

# 회원가입 인증번호 검증
def validate_email_verification_code(
        db : Session,
        email : str,
        plain_code : str,
        purpose : str = "signup",
):
     now = datetime.now(timezone.utc)
     nomalized_email = email.strip().lower()

     verification = (db.query(EmailVerificationCode)
                     .filter(
                          EmailVerificationCode.email == nomalized_email,
                          EmailVerificationCode.purpose == purpose,
                     )
                     .order_by(EmailVerificationCode.created_at.desc())
                    .with_for_update()
                    .first()
                )
    #  인증번호가 없는 경우
     if verification is None :
          raise ValueError("인증번호 먼저 요청해주세요.")
    #  이미 사용된 코드
     if verification.verified_at is not None:
          raise ValueError("이미 사용된 인증번호 입니다.")
    #  인증번호가 만료된 경우
     if verification.expires_at <= now:
          raise ValueError("인증번호가 만료 되었습니다.")
     
     if (verification.attempt_count >= settings.EMAIL_VERIFICATION_MAX_ATTEMPTS):
          raise ValueError("인증번호 입력 가능 횟수를 초과했습니다.")
     
     is_valid = verify_email_verification_code(plain_code, verification.code_hash)

     if not is_valid:
          verification.attempt_count += 1
          db.commit()
          
          remaining_attempts = (settings.EMAIL_VERIFICATION_MAX_ATTEMPTS - verification.attempt_count)

          raise ValueError(
               f"인증번호가 올바르지 않습니다."
               f"남은 입력 횟수 : {remaining_attempts}회"
          )
     
    #  인증 성공처리
     verification.verified_at = now

     return verification