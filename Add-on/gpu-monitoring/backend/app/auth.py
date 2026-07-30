import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any


class TokenError(ValueError):
    pass


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    rounds = 310_000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, rounds)
    return f"pbkdf2_sha256${rounds}${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, rounds, salt, expected = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(rounds))
        return hmac.compare_digest(digest.hex(), expected)
    except (ValueError, TypeError):
        return False


def create_token(user_id: int, role: str, token_type: str, secret: str, lifetime_seconds: int) -> str:
    payload = {"sub": user_id, "role": role, "type": token_type, "exp": int(time.time()) + lifetime_seconds}
    body = _encode(json.dumps(payload, separators=(",", ":")).encode())
    signature = _encode(hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest())
    return f"{body}.{signature}"


def decode_token(token: str, secret: str, expected_type: str) -> dict[str, Any]:
    try:
        body, signature = token.split(".", 1)
        expected = _encode(hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            raise TokenError("Invalid token signature")
        payload = json.loads(base64.urlsafe_b64decode(_pad(body)))
        if payload.get("type") != expected_type or int(payload.get("exp", 0)) <= int(time.time()):
            raise TokenError("Token expired or has an invalid type")
        return payload
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        raise TokenError("Invalid token") from exc


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def _pad(value: str) -> bytes:
    return (value + "=" * (-len(value) % 4)).encode()
