from typing import Any

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    identifier: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str


class AdminUser(BaseModel):
    id: int
    name: str
    nickname: str | None
    email: str
    role: str
    status: str
    created_at: str
    last_login_at: str | None
    last_active_at: str | None


class ApiResponse(BaseModel):
    state: str = "success"
    message: str | None = None
    data: Any = None
