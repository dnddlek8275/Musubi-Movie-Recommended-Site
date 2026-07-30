from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import ExpiredSignatureError, JWTError, jwt
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.dependencies import get_db
from app.models.users import User

bearer_scheme = HTTPBearer(auto_error = False)

# access token 검증 실패 시 401 error 반환 함수
def auth_error(message : str, code: str):
    # 인증 정보가 없거나 잘못되었을 때 사용하는 HTTP 상태 코드
    raise HTTPException(
        status_code= status.HTTP_401_UNAUTHORIZED,
        detail={
            "state" : "failure",
            "message" : message,
            "code" : code,
        },
        # Bearer 토큰 인증이 필요하다는 것을 알려주는 HTTP 헤더
        headers={"WWW-Authenticate": "Bearer"},
    )
# access token 검증 후, 정상이면 회원 정보 반환
def decode_access_token(access_token : str)->dict :
    try:
        payload = jwt.decode(
            access_token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
    except ExpiredSignatureError:
        auth_error("로그인 시간이 만료되었습니다.", "ACCESS_TOKEN_EXPIRED")
    except JWTError:
        auth_error("회원의 로그인 상태에 문제가 있습니다.", "INVALID_ACCESS_TOKEN")
    
    if payload.get("type") !="access":
        auth_error("회원의 로그인 상태에 문제가 있습니다.", "INVALID_TOKEN_TYPE")
    
    user_id = payload.get("user_id")
    user_email = payload.get("user_email")

    if not user_email or not user_id :
        auth_error("사용자 정보가 올바르지 않습니다.", "INVALID_TOKEN_PAYLOAD")

    return {
        "user_id" : user_id,
        "user_email" : user_email
    }

# 회원 전용 기능에서 사용하는 함수
def get_current_user(credentials : HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> dict:
    # 토큰이 없으면 로그인 필요하다고 반환
    if not credentials:
        return auth_error("로그인이 필요합니다.", "LOGIN_REQUIRED")
    
    # 토큰 type = "bearer" 인지 확인
    if credentials.scheme.lower() != "bearer":
        return auth_error("Authorization 헤더 방식이 올바르지 않습니다.", "INVALID_AUTH_SCHEME")
    
    return decode_access_token(credentials.credentials)

# 회원·비회원 가능한 기능에 사용하는 함수
def get_optional_current_user(credentials : HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> dict:
    # 토큰 자체가 없으면 비회원(None)으로 반환
    if not credentials:
        return None
    
    # 토큰 type = "bearer" 인지 확인 -> 비회원이 아니라 인증 오류로 처리
    if credentials.scheme.lower() != "bearer":
        return auth_error("Authorization 헤더 방식이 올바르지 않습니다.", "INVALID_AUTH_SCHEME")
    
    return decode_access_token(credentials.credentials)

def get_current_admin(
        current_user : dict = Depends(get_current_user),
        db : Session = Depends(get_db)
):
    user_id = current_user["user_id"]
    user = db.get(User, user_id)


    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "state" : "failure",
                "message" : "사용자를 찾을 수 없습니다."
            }
        )

    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "state" : "failure",
                "message" : "관리자 권한이 필요합니다."
            }
        )
    return user
