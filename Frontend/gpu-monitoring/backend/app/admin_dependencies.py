import sqlite3
from typing import Callable

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .auth import TokenError, decode_token
from .config import get_settings
from .database import Database

security = HTTPBearer(auto_error=False)
settings = get_settings()
database = Database(settings.database_path)


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(security)) -> sqlite3.Row:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Authentication is required")
    try:
        payload = decode_token(credentials.credentials, settings.admin_secret_key, "access")
    except TokenError as exc:
        raise HTTPException(status_code=401, detail="Authentication has expired or is invalid") from exc
    user = database.user_by_id(int(payload["sub"]))
    if not user or user["status"] != "ACTIVE":
        raise HTTPException(status_code=401, detail="Account is unavailable")
    return user


def require_roles(*roles: str) -> Callable:
    def dependency(user: sqlite3.Row = Depends(current_user)) -> sqlite3.Row:
        if user["role"] not in roles:
            raise HTTPException(status_code=403, detail="Administrator permission is required")
        return user
    return dependency


require_admin = require_roles("ADMIN", "SUPER_ADMIN")
