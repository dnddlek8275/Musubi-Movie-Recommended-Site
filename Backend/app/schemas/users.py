# 회원가입 요청(Request) 데이터 형식
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

class RegisterRequest(BaseModel):
    # 사용자 이메일
    email: EmailStr
    # 사용자 비밀번호
    password: str
    # 사용자 닉네임
    nickname: str
    verification_code : str = Field(
        min_length=6,
        max_length=6,
        pattern=r"^\d{6}$"
        # 정규표현식을 이용해 숫자 6자리인지 검사
        # ^: 문자열 시작
        # \d{6}: 숫자가 정확히 6개
        # $: 문자열 끝
    )

class LoginRequest(BaseModel):
    # 사용자 이메일
    email: EmailStr
    # 사용자 비밀번호
    password: str

class PreferenceRequest(BaseModel):
    # 사용자 선호 장르
    genres: list[str] = Field(default_factory=list)
    # 사용자 선호 배우
    actors: list[str] = Field(default_factory=list)
    # 사용자 선호 키워드
    keywords: list[str] = Field(default_factory=list)

class PreferenceDeleteRequest(BaseModel):
    # 삭제할 선호 종류 구분
    preference_type: str

    # 삭제할 값
    preference_value :str

class EmailVerificationRequest(BaseModel):
    email : EmailStr

# 비밀번호 재설정 이메일 요청
class PasswordResetRequest(BaseModel):
    email :EmailStr

# 이메일 링크를 통한 새 비밀번호 설정 요청
class PasswordResetConfirmRequest(BaseModel):
    # 이메일 링크에 들어 있던 원본 토큰
    token : str = Field(min_length=32, max_length=512)
    # 사용자가 새로 사용할 비밀번호
    new_password : str = Field(min_length=8, max_length=128)