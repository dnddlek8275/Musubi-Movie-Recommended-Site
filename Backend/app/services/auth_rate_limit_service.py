from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.tokens import AuthRequestEvent


def _key_hash(value: str) -> str:
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        value.strip().casefold().encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def request_ip(request: Request) -> str:
    if settings.AUTH_RATE_LIMIT_TRUST_PROXY_HEADERS:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",", 1)[0].strip()
    return request.client.host if request.client else "unknown"


def assert_request_limit(
    db: Session,
    *,
    scope: str,
    keys: list[tuple[str, int]],
    window: timedelta,
    message: str,
) -> None:
    since = datetime.now(timezone.utc) - window
    limits_by_hash = {_key_hash(key): limit for key, limit in keys}
    attempts_by_hash = dict(
        db.query(AuthRequestEvent.key_hash, func.count(AuthRequestEvent.id))
        .filter(
            AuthRequestEvent.scope == scope,
            AuthRequestEvent.key_hash.in_(limits_by_hash),
            AuthRequestEvent.created_at >= since,
        )
        .group_by(AuthRequestEvent.key_hash)
        .all()
    )
    if any(attempts_by_hash.get(key_hash, 0) >= limit for key_hash, limit in limits_by_hash.items()):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"state": "failure", "message": message},
        )


def record_request_attempt(db: Session, *, scope: str, keys: list[str]) -> None:
    for key in keys:
        db.add(AuthRequestEvent(scope=scope, key_hash=_key_hash(key)))
    db.commit()


def consume_request_limit(
    db: Session,
    *,
    scope: str,
    keys: list[tuple[str, int]],
    window: timedelta,
    message: str,
) -> None:
    assert_request_limit(db, scope=scope, keys=keys, window=window, message=message)
    record_request_attempt(db, scope=scope, keys=[key for key, _ in keys])


def clear_request_attempts(db: Session, *, scope: str, keys: list[str]) -> None:
    hashes = [_key_hash(key) for key in keys]
    db.query(AuthRequestEvent).filter(
        AuthRequestEvent.scope == scope,
        AuthRequestEvent.key_hash.in_(hashes),
    ).delete(synchronize_session=False)
    db.commit()
