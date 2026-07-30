from pydantic_settings import BaseSettings, SettingsConfigDict


# .env 파일에 있는 설정값 가져오기
class Settings(BaseSettings) :
    # DB 호출할 서버 주소
    DATABASE_URL: str

    # TMDB API 인증 정보
    # Access Token이 설정돼 있으면 Bearer 인증에 사용한다.
    TMDB_ACCESS_TOKEN: str | None = None

    # Access Token이 없을 경우 기존 v3 API Key를 사용한다.
    TMDB_API_KEY: str | None = None

    # AI 호출할 서버 주소
    AI_BASE_URL : str = "http://210.109.15.251"

    # JWT 토큰 생성 및 검증 키
    SECRET_KEY : str
    #JWT 서명 알고리즘 - 위조 방지 서명
    ALGORITHM : str = "HS256"
    # access token 만료 시간
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    # token 재발급하는 경우 만료 시간 ( 연장 )
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14

    # 이메일 인증번호 유효시간
    EMAIL_VERIFICATION_EXPIRE_MINUTES: int = 5

    # 인증번호 재전송 제한 시간
    EMAIL_VERIFICATION_RESEND_SECONDS: int = 60

    # 인증번호 최대 입력 실패 횟수
    EMAIL_VERIFICATION_MAX_ATTEMPTS: int = 5

    # SMTP 이메일 발송 설정
    MAIL_HOST: str
    MAIL_PORT: int = 587
    MAIL_USERNAME: str
    MAIL_PASSWORD: str
    MAIL_FROM: str

    # 비밀번호 재설정 화면의 프론트엔드 주소
    FRONTEND_BASE_URL: str

    # 비밀번호 재설정 토큰 유효시간
    PASSWORD_RESET_EXPIRE_MINUTES: int
    
    #프로젝트에 있는 .env파일 읽어오는 설정
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
