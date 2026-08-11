# 회원가입 요청(Request) 데이터 형식
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

class RegisterRequest(BaseModel):
    # 사용자 이메일
    email: EmailStr
    # 사용자 비밀번호
    password: str = Field(min_length=10, max_length=128)
    # 사용자 닉네임
    nickname: str = Field(min_length=2, max_length=50)
    verification_code : str = Field(
        min_length=6,
        max_length=6,
        pattern=r"^\d{6}$"
        # 정규표현식을 이용해 숫자 6자리인지 검사
        # ^: 문자열 시작
        # \d{6}: 숫자가 정확히 6개
        # $: 문자열 끝
    )

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        if not any(character.isalpha() and character.isascii() for character in value):
            raise ValueError("비밀번호에 영문을 포함해 주세요.")
        if not any(character.isdigit() for character in value):
            raise ValueError("비밀번호에 숫자를 포함해 주세요.")
        if not any(not character.isalnum() and not character.isspace() for character in value):
            raise ValueError("비밀번호에 특수문자를 포함해 주세요.")
        if any(character.isspace() for character in value):
            raise ValueError("비밀번호에는 공백을 사용할 수 없습니다.")
        return value


class NicknameCheckRequest(BaseModel):
    nickname: str = Field(min_length=2, max_length=50)

class LoginRequest(BaseModel):
    # 일반 회원은 이메일, 별도 생성한 운영 관리자는 관리자 아이디를 사용한다.
    # 기존 API 호환을 위해 요청 필드명은 email을 유지한다.
    email: str = Field(min_length=3, max_length=255)
    # 사용자 비밀번호
    password: str

class PreferenceRequest(BaseModel):
    # 사용자 선호 장르
    genres: list[str] = Field(default_factory=list)
    # 사용자 선호 배우
    actors: list[str] = Field(default_factory=list)
    # 사용자 선호 키워드
    keywords: list[str] = Field(default_factory=list)


class OnboardingPreferencesRequest(BaseModel):
    genres: list[str] = Field(default_factory=list, max_length=20)
    actors: list[str] = Field(default_factory=list, max_length=20)
    keywords: list[str] = Field(default_factory=list, max_length=30)
    onboarding_completed: bool = True

class PreferenceDeleteRequest(BaseModel):
    # 삭제할 선호 종류 구분
    preference_type: str

    # 삭제할 값
    preference_value :str

class EmailVerificationRequest(BaseModel):
    email : EmailStr


class EmailVerificationConfirmRequest(BaseModel):
    email: EmailStr
    verification_code: str = Field(
        min_length=6,
        max_length=6,
        pattern=r"^\d{6}$",
    )


class AccountProfileUpdateRequest(BaseModel):
    nickname: str | None = Field(default=None, min_length=2, max_length=50)
    email: EmailStr | None = None
    personal_context: str | None = Field(default=None, max_length=500)
    verification_code: str | None = Field(
        default=None,
        min_length=6,
        max_length=6,
        pattern=r"^\d{6}$",
    )

# 비밀번호 재설정 이메일 요청
class PasswordResetRequest(BaseModel):
    email :EmailStr

# 이메일 링크를 통한 새 비밀번호 설정 요청
class PasswordResetConfirmRequest(BaseModel):
    # 이메일 링크에 들어 있던 원본 토큰
    token : str = Field(min_length=32, max_length=512)
    # 사용자가 새로 사용할 비밀번호
    new_password : str = Field(min_length=8, max_length=128)
