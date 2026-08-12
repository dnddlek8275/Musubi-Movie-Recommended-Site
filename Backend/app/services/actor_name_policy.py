from __future__ import annotations

import re
from collections.abc import Iterable


HANGUL_PATTERN = re.compile(r"[가-힣]")
LATIN_STAGE_NAME_PATTERN = re.compile(r"^[A-Z][A-Z0-9._-]{1,9}$")
KOREAN_BIRTHPLACE_TERMS = (
    "south korea",
    "republic of korea",
    "대한민국",
)

# 데이터 제공처의 표기가 계속 영문으로 내려오는 검증된 예외만 내부 배우 ID로 고정한다.
# 이름 문자열 전체를 치환하지 않아 동명이인에게 영향을 주지 않는다.
ACTOR_DISPLAY_NAME_OVERRIDES_BY_ID = {
    10199: "노영학",
}


def contains_hangul(value: object) -> bool:
    return bool(HANGUL_PATTERN.search(str(value or "")))


def clean_person_name(value: object) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:100] if text else None


def select_korean_name(name: object, aliases: Iterable[object] | None = None) -> str | None:
    candidates = [name, *(aliases or [])]
    for candidate in candidates:
        cleaned = clean_person_name(candidate)
        if cleaned and contains_hangul(cleaned):
            return cleaned
    return None


def infer_is_korean(
    *,
    place_of_birth: object,
    korean_name: str | None,
    korean_credit_count: int,
    total_credit_count: int,
) -> bool | None:
    """TMDB에 국적 필드가 없으므로 명시 근거 또는 강한 출연 이력만 사용한다."""

    birthplace = str(place_of_birth or "").strip().casefold()
    if korean_name and total_credit_count >= 2:
        korean_ratio = korean_credit_count / total_credit_count
        if korean_credit_count >= 2 and korean_ratio >= 0.8:
            return True
        if korean_credit_count == 0:
            return False
    if birthplace:
        if any(term in birthplace for term in KOREAN_BIRTHPLACE_TERMS):
            return True
        # 한국 제작물 이력이 충분하지 않고 출생지가 다른 국가로 명시된 경우에만
        # 외국 배우로 분류한다. 해외 출생 한국 배우는 위 출연 이력 규칙이 우선한다.
        return False
    return None


def actor_display_name(actor) -> str:
    override = ACTOR_DISPLAY_NAME_OVERRIDES_BY_ID.get(getattr(actor, "id", None))
    if override:
        return override
    if actor.is_korean is True:
        return clean_person_name(actor.korean_name) or clean_person_name(actor.name) or "이름 미상"
    if actor.is_korean is False:
        return clean_person_name(actor.original_name) or clean_person_name(actor.name) or "Unknown"
    return clean_person_name(actor.name) or clean_person_name(actor.original_name) or "이름 미상"


def resolved_actor_name(
    *,
    current_name: object,
    original_name: object,
    korean_name: object,
    is_korean: bool | None,
) -> str | None:
    current = clean_person_name(current_name)
    original = clean_person_name(original_name)
    korean = clean_person_name(korean_name)
    # RM·IU처럼 공식 활동명이 짧은 대문자 표기인 경우 어색한 자동 번역보다
    # 기존 활동명을 보존한다.
    if is_korean is True and current and LATIN_STAGE_NAME_PATTERN.fullmatch(current):
        return current
    if is_korean is True:
        return korean or current
    if is_korean is False:
        return original or current
    return current


def preserve_resolved_actor_name(actor, incoming_name: object) -> str:
    """영화 동기화가 이미 판정된 배우 이름을 다른 언어로 덮어쓰지 않게 한다."""

    incoming = clean_person_name(incoming_name) or actor.name
    if actor.is_korean is True and actor.korean_name:
        return actor.korean_name
    if actor.is_korean is False and actor.original_name:
        return actor.original_name
    return incoming
