from __future__ import annotations

from functools import lru_cache
from urllib.parse import quote

import boto3
from botocore.client import BaseClient
from botocore.config import Config

from app.core.config import settings


S3_URI_PREFIX = "s3://"


def _require(value: str | None, name: str) -> str:
    if value and value.strip():
        return value.strip()
    raise RuntimeError(f"{name} 환경변수가 설정되지 않았습니다.")


@lru_cache(maxsize=1)
def get_object_storage_client() -> BaseClient:
    """카카오클라우드 S3 호환 Object Storage 클라이언트."""
    return boto3.client(
        "s3",
        endpoint_url=_require(
            settings.OBJECT_STORAGE_ENDPOINT,
            "OBJECT_STORAGE_ENDPOINT",
        ).rstrip("/"),
        region_name=settings.OBJECT_STORAGE_REGION,
        aws_access_key_id=_require(
            settings.OBJECT_STORAGE_ACCESS_KEY,
            "OBJECT_STORAGE_ACCESS_KEY",
        ),
        aws_secret_access_key=_require(
            settings.OBJECT_STORAGE_SECRET_KEY,
            "OBJECT_STORAGE_SECRET_KEY",
        ),
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            connect_timeout=5,
            read_timeout=30,
            retries={"max_attempts": 3, "mode": "standard"},
        ),
    )

def object_uri(key: str) -> str:
    bucket = _require(settings.OBJECT_STORAGE_BUCKET, "OBJECT_STORAGE_BUCKET")
    return f"{S3_URI_PREFIX}{bucket}/{key.lstrip('/')}"


def parse_object_uri(value: str) -> tuple[str, str] | None:
    if not value.startswith(S3_URI_PREFIX):
        return None
    remainder = value[len(S3_URI_PREFIX):]
    bucket, separator, key = remainder.partition("/")
    if not separator or not bucket or not key:
        return None
    return bucket, key


def upload_object(*, key: str, contents: bytes, content_type: str) -> str:
    bucket = _require(settings.OBJECT_STORAGE_BUCKET, "OBJECT_STORAGE_BUCKET")
    get_object_storage_client().put_object(
        Bucket=bucket,
        Key=key,
        Body=contents,
        ContentType=content_type,
        CacheControl="private, max-age=3600",
    )
    return object_uri(key)


def delete_object(value: str) -> bool:
    parsed = parse_object_uri(value)
    if not parsed:
        return False
    bucket, key = parsed
    get_object_storage_client().delete_object(Bucket=bucket, Key=key)
    return True


def resolve_object_url(value: str) -> str | None:
    parsed = parse_object_uri(value)
    if not parsed:
        return None

    bucket, key = parsed
    public_base_url = (settings.OBJECT_STORAGE_PUBLIC_BASE_URL or "").rstrip("/")
    if public_base_url:
        return f"{public_base_url}/{quote(key, safe='/')}"

    return get_object_storage_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=settings.OBJECT_STORAGE_PRESIGN_EXPIRES_SECONDS,
    )
