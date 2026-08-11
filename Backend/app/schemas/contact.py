from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator


ContactCategory = Literal["service", "movie_data", "ai", "account", "other"]


class ContactInquiryRequest(BaseModel):
    category: ContactCategory
    email: EmailStr
    subject: str = Field(min_length=2, max_length=120)
    message: str = Field(min_length=10, max_length=2000)
    # 화면에는 보이지 않는 봇 방지용 필드. 정상 사용자는 항상 빈 값이다.
    website: str = Field(default="", max_length=0)

    @field_validator("subject", "message")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("내용을 입력해 주세요.")
        return normalized
