"""Tavily web search with a persistent monthly hard cap and short-lived cache."""

from __future__ import annotations

import json
import os
import sqlite3
import time
from datetime import datetime
from hashlib import sha256
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import requests


TAVILY_URL = "https://api.tavily.com/search"
MONTHLY_LIMIT = int(os.getenv("WEB_SEARCH_MONTHLY_LIMIT", "950"))
WARNING_AT = int(os.getenv("WEB_SEARCH_WARNING_AT", "900"))
CACHE_TTL_SECONDS = int(os.getenv("WEB_SEARCH_CACHE_TTL_SECONDS", "21600"))
TIMEOUT_SECONDS = int(os.getenv("WEB_SEARCH_TIMEOUT_SECONDS", "12"))
DB_PATH = os.getenv("WEB_SEARCH_USAGE_DB", "/home/ubuntu/cineverse/data/web_search_usage.sqlite3")


class WebSearchUnavailable(RuntimeError):
    pass


class WebSearchQuotaExceeded(WebSearchUnavailable):
    pass


def _connect() -> sqlite3.Connection:
    directory = os.path.dirname(DB_PATH)
    if directory:
        os.makedirs(directory, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute(
        "CREATE TABLE IF NOT EXISTS usage (month TEXT PRIMARY KEY, calls INTEGER NOT NULL)"
    )
    connection.execute(
        "CREATE TABLE IF NOT EXISTS cache (cache_key TEXT PRIMARY KEY, payload TEXT NOT NULL, expires_at INTEGER NOT NULL)"
    )
    return connection


def _month() -> str:
    return datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m")


def _cache_key(query: str) -> str:
    return sha256(" ".join(query.casefold().split()).encode("utf-8")).hexdigest()


def quota_status() -> dict:
    with _connect() as connection:
        row = connection.execute(
            "SELECT calls FROM usage WHERE month = ?", (_month(),)
        ).fetchone()
    used = int(row[0]) if row else 0
    return {
        "month": _month(), "used": used, "limit": MONTHLY_LIMIT,
        "remaining": max(MONTHLY_LIMIT - used, 0), "warning": used >= WARNING_AT,
    }


def _reserve_call(connection: sqlite3.Connection) -> None:
    connection.execute("BEGIN IMMEDIATE")
    row = connection.execute(
        "SELECT calls FROM usage WHERE month = ?", (_month(),)
    ).fetchone()
    used = int(row[0]) if row else 0
    if used >= MONTHLY_LIMIT:
        connection.rollback()
        raise WebSearchQuotaExceeded("월간 웹 검색 한도를 모두 사용했습니다.")
    connection.execute(
        "INSERT INTO usage(month, calls) VALUES (?, 1) "
        "ON CONFLICT(month) DO UPDATE SET calls = calls + 1",
        (_month(),),
    )
    connection.commit()


def _release_call() -> None:
    """공급자에 도달하지 못한 연결 실패 예약분만 되돌린다."""
    with _connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            "UPDATE usage SET calls = MAX(calls - 1, 0) WHERE month = ?",
            (_month(),),
        )
        connection.commit()


def _clean_result(item: dict) -> dict | None:
    url = str(item.get("url") or "").strip()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return {
        "title": " ".join(str(item.get("title") or "").split())[:200],
        "url": url[:2000],
        "content": " ".join(str(item.get("content") or "").split())[:1500],
    }


def search(query: str, max_results: int = 5) -> dict:
    api_key = os.getenv("TAVILY_API_KEY", "").strip()
    if not api_key:
        raise WebSearchUnavailable("TAVILY_API_KEY가 설정되지 않았습니다.")
    normalized = " ".join(query.split()).strip()[:400]
    if not normalized:
        raise ValueError("검색어가 비어 있습니다.")
    key = _cache_key(normalized)
    now = int(time.time())
    with _connect() as connection:
        cached = connection.execute(
            "SELECT payload FROM cache WHERE cache_key = ? AND expires_at > ?",
            (key, now),
        ).fetchone()
        if cached:
            payload = json.loads(cached[0])
            payload["cached"] = True
            payload["quota"] = quota_status()
            return payload
        _reserve_call(connection)

    try:
        response = requests.post(
            TAVILY_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "query": normalized, "search_depth": "basic",
                "max_results": max(1, min(max_results, 5)),
                "include_answer": False, "include_raw_content": False,
            },
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        raw = response.json()
    except requests.ConnectionError as error:
        _release_call()
        raise WebSearchUnavailable(f"웹 검색 서비스 연결 오류: {error}") from error
    except (requests.RequestException, ValueError) as error:
        raise WebSearchUnavailable(f"웹 검색 서비스 오류: {error}") from error

    results = [cleaned for item in (raw.get("results") or []) if (cleaned := _clean_result(item))]
    payload = {"query": normalized, "results": results, "cached": False}
    with _connect() as connection:
        connection.execute(
            "INSERT OR REPLACE INTO cache(cache_key, payload, expires_at) VALUES (?, ?, ?)",
            (key, json.dumps(payload, ensure_ascii=False), now + CACHE_TTL_SECONDS),
        )
    payload["quota"] = quota_status()
    return payload
