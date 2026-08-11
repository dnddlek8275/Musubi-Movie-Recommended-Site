from datetime import datetime, timedelta, timezone

from urllib.parse import quote
from fastapi import APIRouter, Depends, HTTPException, Header, Request, Response, status
from jose import JWTError, jwt
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.schemas.users import EmailVerificationConfirmRequest, EmailVerificationRequest, LoginRequest, NicknameCheckRequest, PasswordResetConfirmRequest, PasswordResetRequest, RegisterRequest
from app.core.security import create_access_token, create_refresh_token, hash_password, hash_token, verify_password
from app.core.api_responses import error_response
from app.core.config import settings
from app.core.dependencies import get_db
from app.models.users import User
from app.models.tokens import RefreshToken
from app.services.email.email_service import send_password_reset_email, send_signup_verification_code
from app.services.email.email_verification_service import create_email_verification_code, expire_email_verification_code, validate_email_verification_code
from app.services.password_reset_service import create_password_reset_token, reset_password_with_token, revoke_password_reset_token
from app.services.auth_rate_limit_service import (
    assert_request_limit,
    clear_request_attempts,
    consume_request_limit,
    record_request_attempt,
    request_ip,
)


# 인증 관련 API들을 묶는 Router /auth/
router = APIRouter(
    prefix="/auth",
    tags=["Auth"]
)


def normalized_nickname(value: str) -> str:
    return value.strip().casefold()


def nickname_exists(db: Session, nickname: str) -> bool:
    return db.query(User.id).filter(
        func.lower(func.trim(User.nickname)) == normalized_nickname(nickname)
    ).first() is not None


@router.post("/nickname-check")
async def check_nickname(
    request: NicknameCheckRequest,
    db: Session = Depends(get_db),
):
    nickname = request.nickname.strip()
    if len(nickname) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"state": "failure", "message": "닉네임은 2자 이상 입력해 주세요."},
        )

    available = not nickname_exists(db, nickname)
    return {
        "state": "success",
        "message": "사용 가능한 닉네임입니다." if available else "이미 사용 중인 닉네임입니다.",
        "data": {"available": available},
    }

# 이메일 인증번호 요청
@router.post("/email-verification/request", status_code= status.HTTP_202_ACCEPTED,) # 요청은 접수했지만 실제 처리는 진행 중이거나 비동기로 처리
async def request_email_verification(
    request : EmailVerificationRequest,
    http_request: Request,
    db : Session = Depends(get_db),
):
    # DB에 동일한 형식으로 저장하기 위해 정규화
    email = str(request.email).strip().lower()
    client_ip = request_ip(http_request)
    consume_request_limit(
        db,
        scope="signup_email",
        keys=[
            (f"email:{email}", settings.EMAIL_REQUEST_LIMIT_PER_HOUR),
            (f"ip:{client_ip}", settings.AUTH_IP_REQUEST_LIMIT_PER_HOUR),
        ],
        window=timedelta(hours=1),
        message="이메일 요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.",
    )

    # 가입된 이메일인지 확인
    existing_user = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )
    
    if existing_user:
        raise HTTPException(
            # 409 Conflict는 현재 서버 데이터 상태와 충돌해서 처리할 수 없다는 의미
            status_code= status.HTTP_409_CONFLICT,
            detail={
                "state" : "failure",
                "message" : "중복 이메일입니다. 이미 가입된 이메일입니다."
            },
        )
    
    try:
        # 인증번호 원문 생성 DB는 인증번호 해시값 저장
        verification, plain_code = create_email_verification_code(db, email, "signup")
    # 재전송 제한 시간 안에 다시 요청한 경우
    except ValueError as exc:
        raise HTTPException(
            status_code= status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "state" : "failure",
                "message" : str(exc),
            },
        )from exc
    except Exception as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "state" : "error",
                "message" : "인증번호 생성에 실패했습니다."
            },
        )from exc
    try:
        # 사용자 이메일로 인증번호 원문 전송
        await send_signup_verification_code(email, plain_code)
    # 이메일 발송 실패시 인증번호 만료 처리
    except Exception as exc:
        expire_email_verification_code(db, verification)

        raise HTTPException(
            status_code= status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "state" : "error",
                "message" : "인증번호 이메일 발송에 실패했습니다."
            },
        )from exc
        
    return {
        "state" : "success",
        "message" : "인증번호를 이메일로 전송했습니다.",
        "data" : {
            "expires_in_seconds" : settings.EMAIL_VERIFICATION_EXPIRE_MINUTES * 60,
        },
    }


@router.post("/email-verification/confirm")
async def confirm_email_verification(
    request: EmailVerificationConfirmRequest,
    db: Session = Depends(get_db),
):
    email = str(request.email).strip().lower()

    if db.query(User.id).filter(User.email == email).first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "state": "failure",
                "message": "중복 이메일입니다. 이미 가입된 이메일입니다.",
            },
        )

    try:
        validate_email_verification_code(
            db,
            email,
            request.verification_code,
            "signup",
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"state": "failure", "message": str(exc)},
        ) from exc

    return {
        "state": "success",
        "message": "이메일 인증이 완료되었습니다.",
        "data": {"verified": True},
    }


# 회원가입 API POST /auth/register
@router.post("/register")
async def register(request: RegisterRequest, db: Session = Depends(get_db)):
    try :
        normalized_email = str(request.email).strip().lower()
        nickname = request.nickname.strip()

        # 이메일 중복 확인
        existing_user = (db.query(User).filter(User.email == normalized_email).first())

        if existing_user :
            return {
                "state" : "failure",
                "message" : "회원가입 실패 - 이메일 중복"
            }

        if nickname_exists(db, nickname):
            return error_response(
                "이미 사용 중인 닉네임입니다.",
                status_code=status.HTTP_409_CONFLICT,
                state="failure",
            )
        
        if not request.password or request.password is None:
            return {
                "state" : "failure",
                "message" : "비밀번호 입력해주세요"
            }
        
        # 사용자가 이메일로 받은 인증번호 검사
        validate_email_verification_code(db, normalized_email, request.verification_code, "signup")

        #비밀번호 hash 
        hashed_pwd = hash_password(request.password)

        new_user = User(
            email = normalized_email,
            password_hash = hashed_pwd,
            nickname = nickname,
        )
        
        #DB 저장
        db.add(new_user)
        
        #실제로 DB 저장
        db.commit()
        #저장 후 생성 id 조회
        db.refresh(new_user)
        # return new_user
        return {
            "state":"success",
            "message":"회원가입 성공",
            "data" : {
                "id" : new_user.id,
                "email" : new_user.email,
                # "password_hashed" : new_user.password_hash,
                "nickname" : new_user.nickname
            }
        }
    except IntegrityError:
        db.rollback()
        return error_response(
            "이미 사용 중인 이메일 또는 닉네임입니다.",
            status_code=status.HTTP_409_CONFLICT,
            state="failure",
        )
    except ValueError as e:
        db.rollback()
        return error_response(
            str(e),
            status_code=status.HTTP_400_BAD_REQUEST,
            state="failure",
        )
    except Exception:
        # 저장 취소 롤백
        db.rollback()
        return error_response("회원가입 에러")


# 비밀번호 재설정 이메일 요청
@router.post("/password-reset/request", status_code=status.HTTP_202_ACCEPTED)
async def request_password_reset(
    request : PasswordResetRequest,
    http_request: Request,
    db : Session = Depends(get_db),
):
    # 이메일 정규화
    email = str(request.email).strip().lower()
    client_ip = request_ip(http_request)
    consume_request_limit(
        db,
        scope="password_reset",
        keys=[
            (f"email:{email}", settings.EMAIL_REQUEST_LIMIT_PER_HOUR),
            (f"ip:{client_ip}", settings.AUTH_IP_REQUEST_LIMIT_PER_HOUR),
        ],
        window=timedelta(hours=1),
        message="비밀번호 재설정 요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.",
    )

    # 가입된 사용자 조회
    user = (db.query(User).filter(User.email==email).first())

    success_response = {
        "state" : "success",
        "message" : "이메일로 비밀번호 재설정 링크가 발송되었습니다.",
    }

    if user is None:
        return error_response(
            "가입된 이메일이 아닙니다.",
            status_code=status.HTTP_404_NOT_FOUND,
            state="failure",
        )
    
    try:
        reset_token, plain_token =create_password_reset_token(db, user)
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail= {
                "state" : "error",
                "message" : "비밀번호 재설정 요청 처리에 에러가 발생했습니다.",
            },
        )from exc
    # 프론트엔드 비밀번호 변경 페이지 주소 설정
    reset_url = (
        f"{settings.FRONTEND_BASE_URL.rstrip('/')}"
        f"/?resetToken={quote(plain_token, safe='')}"
    )
    try:
        await send_password_reset_email(
            email = user.email,
            reset_url = reset_url
        )
    except Exception as exc:
        revoke_password_reset_token(db, reset_token)

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "state" : "error",
                "message" : "비밀번호 재설정 발송에 에러가 발생했습니다."
            }
        )from exc
    return success_response

@router.post("/password-reset/confirm")
async def confirm_password_reset(
    request : PasswordResetConfirmRequest,
    db : Session = Depends(get_db),
):
    try:
        reset_password_with_token(
            db = db,
            plain_token = request.token,
            new_password= request.new_password,
        )
    except ValueError as exc:
        db.rollback()

        raise HTTPException(
            status_code= status.HTTP_400_BAD_REQUEST,
            detail={
                "state" : "failure",
                "message" : str(exc),
            },
        )from exc
    except Exception as exc:
        db.rollback()

        raise HTTPException(
            status_code= status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "state" : "error",
                "message" : "비밀번호 변경에 실패했습니다."
            }
        ) from exc
    
    return {
        "state" : "success",
        "message" : "비밀번호가 변경되었습니다."
    }


# 로그인 POST /auth/login
@router.post("/login")
async def login(
    request: LoginRequest,
    http_request: Request,
    http_response: Response, 
    user_agent: str | None = Header(default=None),
    db: Session = Depends(get_db)
    ):
    try :
        login_id = request.email.strip().lower()
        client_ip = request_ip(http_request)
        login_keys = [
            (f"email:{login_id}", settings.LOGIN_FAILURE_LIMIT),
            (f"ip:{client_ip}", settings.LOGIN_FAILURE_LIMIT),
        ]
        assert_request_limit(
            db,
            scope="login_failure",
            keys=login_keys,
            window=timedelta(minutes=settings.LOGIN_FAILURE_WINDOW_MINUTES),
            message="로그인 시도가 너무 많습니다. 잠시 후 다시 시도해 주세요.",
        )
        # 기존 회원인지 아닌지 구분
        user = (db.query(User).filter(User.email == login_id).first())
        
        if not user:
            record_request_attempt(
                db,
                scope="login_failure",
                keys=[key for key, _ in login_keys],
            )
            return {
                "state" : "failure",
                "message" : "해당 이메일은 가입된 회원이 아닙니다."
            }
        
        # 비밀번호 비교
        user_pwd = verify_password(request.password, user.password_hash)
        if not user_pwd :
            record_request_attempt(
                db,
                scope="login_failure",
                keys=[key for key, _ in login_keys],
            )
            return { 
                "state" : "failure",
                "message" : "해당 회원의 비밀번호가 일치하지 않습니다."
            }
        clear_request_attempts(
            db,
            scope="login_failure",
            keys=[f"email:{login_id}"],
        )
        if user.is_suspended:
            return {
                "state": "failure",
                "message": "사용이 정지된 계정입니다. 문의하기를 통해 관리자에게 확인해 주세요.",
                "code": "ACCOUNT_SUSPENDED",
            }
        # 로그인 성공 토큰 생성 access_token, refresh_token
        # 토큰에는 사용자 이메일만 저장합니다.
        access_token = create_access_token(
            data ={
                "user_email" : user.email,
                "user_id" : user.id
            }
        )
        # refresh_token 생성 반환, 만료시간 반환
        refresh_token, expires_at = create_refresh_token(
            data = {
                "user_email" : user.email,
                "user_id" : user.id
            }
        )
        expires_at_dt = datetime.fromisoformat(expires_at)

        # DB에 저장할 refresh token을 hash 값으로 저장
        refresh_token_hash = hash_token(refresh_token)
        
        # refresh_tokens 테이블에 직접 저장
        refresh_token_row = RefreshToken(
            user_id=user.id,
            token_hash=refresh_token_hash,
            expires_at=expires_at_dt,
            user_agent=user_agent,
        )

        db.add(refresh_token_row)
        db.commit()

        # HttpOnly Cooki에 refresh token 저장
        http_response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=settings.REFRESH_COOKIE_SECURE,
            samesite="lax",
            max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
            path=settings.REFRESH_COOKIE_PATH,
        )
        
        return {
            "state" : "success",
            "message": "로그인 성공",
            "data" : {
                "access_token" : access_token,
                # "refresh_token" : refresh_token,
                "token_type" : "bearer", # 토큰 보내는 방식
                "email" : user.email,
                "nickname" : user.nickname,
                "onboarding_completed" : user.onboarding_completed,
            }
        }

    except Exception:
        db.rollback()
        return error_response("로그인 에러")


# 토큰 재발급 POST /auth/refresh - access_token이 만료되었을 때 refresh token 검증 후 재발급
@router.post("/refresh")
async def refresh_token(http_request : Request, db:Session = Depends(get_db)):
    try:
        
        # 브라우저 내에 있는 refresh_token 꺼내기
        refresh_token = http_request.cookies.get("refresh_token")
        if not refresh_token:
            return {
                "state" : "failure",
                "message" : "refresh_token이 브라우저 내 쿠기에 없습니다."
            }
        
        # refresh token JWT 자체 검증
        payload = jwt.decode(
            refresh_token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )

        if payload.get("type") != "refresh":
            return {
                "state" : "failure",
                "message" : "refresh_token이 아닙니다."
            }

        # 토큰 내 사용자 정보 꺼내기
        user_email = payload.get("user_email")
        user_id = payload.get("user_id")

        if not user_email or not user_id:
            return{
                "state" : "failure",
                "message" : "refresh_token 내 회원 정보가 올바르지 않습니다."
            }
        
        # DB에 있는 refresh_token_hash랑 비교 및 검증
        refresh_token_hash = hash_token(refresh_token)

        saved_refresh_token = (
            db.query(RefreshToken)
            .filter(RefreshToken.token_hash == refresh_token_hash)
            .first()
        )
        if saved_refresh_token is None:
            return {
                "state" : "failure",
                "message" : "유효하지 않은 refresh_token",
            }
        # 로그아웃된 경우
        elif saved_refresh_token.revoked_at is not None:
            return {
                "state": "failure",
                "message": "이미 로그아웃 처리된 refresh_token입니다."
            }
        
        # 만료된 토큰인지 검증
        now = datetime.now(timezone.utc)
        expires_at = saved_refresh_token.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if expires_at < now:
            return {
                "state": "failure",
                "message": "DB에 저장된 refresh_token이 만료되었습니다."
            }
        # 다른 유저의 토큰인 경우
        if saved_refresh_token.user_id != user_id:
            return {
                "state": "failure",
                "message": "해당 DB내 토큰이 브라우저 토큰과 다른 토큰입니다."
            }
        current_user = db.get(User, user_id)
        if current_user is None:
            return {
                "state": "failure",
                "message": "사용자 정보를 찾을 수 없습니다.",
            }
        if current_user.is_suspended:
            saved_refresh_token.revoked_at = now
            db.commit()
            return {
                "state": "failure",
                "message": "사용이 정지된 계정입니다. 문의하기를 통해 관리자에게 확인해 주세요.",
                "code": "ACCOUNT_SUSPENDED",
            }
        # 토큰 재발급 해서 사용한거 last_used_at 저장
        saved_refresh_token.last_used_at = now
        db.commit()
        current_email = current_user.email
        new_access_token = create_access_token(
            data = {
                "user_email" : current_email,
                "user_id" : user_id
            }
        )
        return {
            "state" : "success",
            "message": "토큰 재발급 성공",
            "data" : {
                "access_token": new_access_token,
                "token_type": "bearer",
                "email": current_email,
                "nickname": current_user.nickname,
            }
        }
    #refresh_token 만료
    except JWTError:
        db.rollback()
        return error_response(
            "refresh_token 만료 or 오류",
            status_code=status.HTTP_401_UNAUTHORIZED,
            state="failure",
        )
    
    except Exception:
        db.rollback()
        return error_response("토큰 재발급 실패")


# 로그아웃 POST /auth/logout
@router.post("/logout")
async def logout(http_request : Request, http_response: Response, db:Session = Depends(get_db)):
    try :
        
        # 클라이언트 브라우저가 보낸 쿠키 - refresh 토큰
        refresh_token = http_request.cookies.get("refresh_token")

        if refresh_token :
            refresh_token_hash = hash_token(refresh_token)

            saved_refresh_token = (
                db.query(RefreshToken)
                .filter(RefreshToken.token_hash == refresh_token_hash)
                .first()
            )
            # DB에 토큰이 있고, 아직 폐기되지 않은 토큰이면 revoked_at 기록
            if saved_refresh_token and saved_refresh_token.revoked_at is None:
                saved_refresh_token.revoked_at = datetime.now(timezone.utc)
                db.commit()

        # 브라우저 쿠키 삭제
        http_response.delete_cookie(
            key="refresh_token",
            path=settings.REFRESH_COOKIE_PATH,
            samesite="lax",
            secure=settings.REFRESH_COOKIE_SECURE,
            httponly=True,
        )
        return {
            "state" : "success",
            "message": "로그아웃 성공",
            "data" : {
                "detail" : "클라이언트 쪽에서 access_token, refresh_token 삭제"
            }
        }
    except Exception:
        db.rollback()
        return error_response("로그아웃 에러")
