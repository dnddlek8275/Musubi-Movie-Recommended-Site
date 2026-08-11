"""Build a compact, structured personalization context for AI chat."""

from __future__ import annotations

import json
from collections import defaultdict

from sqlalchemy.orm import Session

from app.services.preference_service import get_combined_user_preference_signals
from app.services.user_service import get_user


_PREFERENCE_LIMITS = {
    "genre": 5,
    "keyword": 8,
    "actor": 3,
    "director": 3,
}


def build_chat_user_context(db: Session, user_id: int) -> str:
    user = get_user(db, user_id)
    if user is None:
        return ""

    preferences: dict[str, list[str]] = defaultdict(list)
    for signal in get_combined_user_preference_signals(db, user_id):
        preference_type = str(signal.preference_type or "").strip()
        value = str(signal.preference_value or "").strip()
        limit = _PREFERENCE_LIMITS.get(preference_type)
        if not limit or not value or len(preferences[preference_type]) >= limit:
            continue
        preferences[preference_type].append(value)

    payload = {
        "personal_context": str(user.personal_context or "").strip()[:500],
        "preferences": dict(preferences),
    }
    if not payload["personal_context"] and not payload["preferences"]:
        return ""
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
