from datetime import datetime, timedelta, timezone
import hashlib
import secrets

from passlib.context import CryptContext
from jose import jwt
from app.core.config import settings

# bcrypt 방식으로 비밀번호를 해시하기 위한 설정
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

#비밀번호 hash함수
def hash_password(password:str) :
    #입력받은 비밀번호 bcrypt 해시값으로 반환
    return pwd_context.hash(password)

# 토큰 hash함수
def hash_token(token : str) :
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

# 비밀번호 재설정 이메일 링크에 넣을 무작위 일회성 토큰 생성
def generate_password_reset_token():
    # 예측하기 어려운 URL-safe 무작위 문자열 생성
    # token_urlsafe이므로 이메일 링크의 query parameter 사용 가능
    return secrets.token_urlsafe(32)

# 로그인할 때 사용
def verify_password(plain_password: str, hashed_password: str) -> bool:
    # plain_password: 사용자가 로그인할 때 입력한 비밀번호
    # hashed_password: DB에 저장된 암호화된 비밀번호
    # bcrypt는 같은 비밀번호라도 매번 다른 해시가 나오기 때문에 verify()를 써야 함
    return pwd_context.verify(plain_password, hashed_password)

# 로그인 성공시 access token 생성 - JWT
def create_access_token(data : dict):
    # 원본 data를 직접 수정하지 않기 위해 복사
    to_encode = data.copy()
    # access token 만료 시간 설정
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    # access token임을 구분할 수 있도록 type을 넣습니다.
    to_encode.update({
        "exp": expire,
        "type": "access"
    })

    # 토큰 생성
    return jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm = settings.ALGORITHM
    )

# refresh token 생성
def create_refresh_token(data : dict):
    # 원본 data를 직접 수정하지 않기 위해 복사
    to_encode = data.copy()
    # refresh token 만료 시간 설정
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    # refresh token임을 구분할 수 있도록 type을 넣습니다.
    to_encode.update({
        "exp":expire,
        "type" : "refresh"
    })
    #토큰 반환
    refresh_token = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )

    return refresh_token, expire.isoformat()

# 이메일로 보낼 보안용 숫자 6자리 생성
def generate_email_verification_code():
    return f"{secrets.randbelow(1_000_000):06d}" # 0부터 999999 사이의 숫자를 안전하게 뽑아서, 항상 6자리 문자열로 만드는 코드 :06d -> 숫자를 6자리 정수 형태로 만들고, 자릿수가 부족하면 앞을 0으로 채우라는 뜻

# 인증번호를 bcrypt로 해쉬로 변환
def hash_email_verification_code(code : str):
    return pwd_context.hash(code)

# 입력한 인증번호와 DB 해시 비교
def verify_email_verification_code(
        plain_code : str,
        hashed_code : str,
):
    return pwd_context.verify(plain_code, hashed_code)