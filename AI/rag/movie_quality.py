"""Pure quality scoring helpers for movie recommendation candidates."""

from __future__ import annotations

import math
import re
import json


MIN_RECOMMENDATION_VOTES = 100

_LIGHT_QUERY = re.compile(r"가볍게|가벼운|유쾌|웃긴|재밌는|부담\s*없이|편하게|머리\s*비우고|힐링")
_TOUCHING_QUERY = re.compile(r"감동|뭉클|눈물\s*나는|마음\s*따뜻")
_UPLIFT_QUERY = re.compile(r"우울할\s*때|기분\s*전환|기분이?\s*(?:안\s*좋|별로)|기운\s*없")
_DATE_QUERY = re.compile(r"데이트|연인(?:과|이랑)?|커플(?:이|끼리)?")
_KIDS_QUERY = re.compile(r"아이와|아이랑|아이하고|어린이와|어린이랑|자녀와|온\s*가족")
_RECOMMENDATION_QUERY = re.compile(r"추천|볼\s*영화|보기\s*좋|뭐\s*볼|골라")

_LIGHT_GENRES = {"코미디", "가족", "애니메이션", "로맨스", "모험", "음악"}
_TOUCHING_GENRES = {"드라마", "가족", "애니메이션", "로맨스"}
_DATE_GENRES = {"로맨스", "코미디"}
_KIDS_GENRES = {"가족", "애니메이션", "모험", "판타지", "코미디"}
_HEAVY_GENRES = {"공포", "스릴러", "범죄", "전쟁", "역사", "다큐멘터리"}


def _with_explicit_genres(expanded: str, original: str) -> str:
    mentioned = [genre for genre in sorted(
        _LIGHT_GENRES | _TOUCHING_GENRES | _DATE_GENRES | _KIDS_GENRES | _HEAVY_GENRES | {"액션", "SF", "판타지", "드라마", "미스터리", "뮤지컬"},
        key=len,
        reverse=True,
    ) if genre in original]
    return " ".join([expanded, *mentioned]) if mentioned else expanded


def expand_mood_query(query: str) -> str:
    """Replace ambiguous mood words with retrieval concepts represented in movie metadata."""
    if _KIDS_QUERY.search(query):
        return _with_explicit_genres("어린이와 함께 보기 좋은 가족 애니메이션 모험 판타지 코미디 영화", query)
    if _UPLIFT_QUERY.search(query):
        return _with_explicit_genres(
            "많은 관객에게 사랑받은 기분 전환이 되는 밝고 유쾌한 코미디 음악 우정 성장 영화",
            query,
        )
    if _DATE_QUERY.search(query):
        return _with_explicit_genres("연인과 함께 보기 좋은 로맨스 코미디 영화", query)
    if _TOUCHING_QUERY.search(query):
        return _with_explicit_genres("감동적이고 따뜻한 휴먼 드라마 가족 성장 우정 영화", query)
    if _LIGHT_QUERY.search(query):
        return _with_explicit_genres("밝고 유쾌하며 편안한 코미디 가족 애니메이션 로맨스 모험 영화", query)
    return query


def _genre_set(movie: dict) -> set[str]:
    raw = movie.get("genres_list") or movie.get("genres") or []
    if isinstance(raw, str):
        if raw.lstrip().startswith("["):
            try:
                parsed = json.loads(raw)
                return {str(genre).strip() for genre in parsed if str(genre).strip()}
            except (TypeError, ValueError, json.JSONDecodeError):
                pass
        return {genre.strip() for genre in raw.split(",") if genre.strip()}
    return {str(genre).strip() for genre in raw if str(genre).strip()}


def is_child_safe_certification(movie: dict) -> bool:
    country = str(movie.get("certification_country") or "").strip().upper()
    certification = re.sub(r"\s+", "", str(movie.get("certification") or "")).upper()
    if country == "US":
        return certification in {"G", "PG"}
    if country == "KR":
        return certification in {"ALL", "전체관람가"}
    return False


def _mood_policy(query: str) -> tuple[set[str], set[str]] | None:
    if _KIDS_QUERY.search(query):
        return _KIDS_GENRES, _HEAVY_GENRES
    if _UPLIFT_QUERY.search(query) or _LIGHT_QUERY.search(query):
        return _LIGHT_GENRES, _HEAVY_GENRES
    if _DATE_QUERY.search(query):
        return _DATE_GENRES, _HEAVY_GENRES
    if _TOUCHING_QUERY.search(query):
        return _TOUCHING_GENRES, {"공포"}
    return None


def apply_query_preferences(query: str, candidates: list[dict], required: int) -> list[dict]:
    """Apply only explicit mood preferences, with staged fallback to preserve recall."""
    policy = _mood_policy(query)
    if not policy:
        return candidates

    preferred_genres, blocked_genres = policy

    preferred = [
        movie for movie in candidates
        if _genre_set(movie) & preferred_genres and not (_genre_set(movie) & blocked_genres)
    ]

    if _KIDS_QUERY.search(query):
        rated_safe = [movie for movie in preferred if is_child_safe_certification(movie)]
        if len(rated_safe) >= required:
            return rated_safe

    if len(preferred) >= required:
        return preferred

    non_heavy = [movie for movie in candidates if not (_genre_set(movie) & blocked_genres)]
    return non_heavy if len(non_heavy) >= required else candidates


def prefer_well_received_candidates(query: str, candidates: list[dict], required: int) -> list[dict]:
    """Avoid poorly rated movies in recommendation requests when alternatives exist."""
    if not _RECOMMENDATION_QUERY.search(query):
        return candidates
    acceptable = [movie for movie in candidates if float(movie.get("vote_average") or 0.0) >= 6.0]
    return acceptable if len(acceptable) >= required else candidates


def has_recommendation_evidence(movie: dict) -> bool:
    """Whether a movie has enough real-user evidence for a generic recommendation."""
    vote_count = max(int(movie.get("vote_count") or 0), 0)
    audience_count = max(int(movie.get("audience_count") or 0), 0)
    return vote_count >= MIN_RECOMMENDATION_VOTES or audience_count > 0


def prefer_evidenced_candidates(candidates: list[dict], required: int) -> list[dict]:
    """Use evidenced movies when there are enough, otherwise preserve recall."""
    evidenced = [movie for movie in candidates if has_recommendation_evidence(movie)]
    return evidenced if len(evidenced) >= required else candidates


def movie_quality_score(movie: dict) -> float:
    """Return a 0..1 confidence score without treating a few perfect votes as reliable."""
    vote_count = max(int(movie.get("vote_count") or 0), 0)
    audience_count = max(int(movie.get("audience_count") or 0), 0)
    vote_average = min(max(float(movie.get("vote_average") or 0.0), 0.0), 10.0)

    popularity = min(math.log1p(vote_count) / math.log1p(5000), 1.0)
    audience = min(math.log1p(audience_count) / math.log1p(1_000_000), 1.0)
    rating_confidence = min(math.log1p(vote_count) / math.log1p(100), 1.0)
    trusted_rating = (vote_average / 10.0) * rating_confidence

    metadata_parts = (
        bool(str(movie.get("overview") or "").strip()),
        bool(str(movie.get("poster_path") or "").strip()),
        bool(str(movie.get("genres") or "").strip()),
        bool(str(movie.get("release_date") or movie.get("year") or "").strip()),
    )
    metadata = sum(metadata_parts) / len(metadata_parts)

    return min(1.0, 0.50 * popularity + 0.25 * trusted_rating + 0.10 * audience + 0.15 * metadata)


def blend_semantic_and_quality(ranked: list[dict], top_k: int, quality_weight: float = 0.30) -> list[dict]:
    """Blend CrossEncoder relevance with evidence quality while preserving strong matches."""
    if not ranked:
        return []

    scores = [float(movie.get("_score") or 0.0) for movie in ranked]
    low, high = min(scores), max(scores)
    span = high - low
    semantic_weight = 1.0 - quality_weight

    rescored = []
    for index, movie in enumerate(ranked):
        if span > 1e-9:
            semantic = (float(movie.get("_score") or 0.0) - low) / span
        else:
            semantic = 1.0 - (index / max(len(ranked) - 1, 1))
        quality = movie_quality_score(movie)
        rescored.append(dict(movie, _final_score=semantic_weight * semantic + quality_weight * quality))

    rescored.sort(key=lambda movie: movie["_final_score"], reverse=True)
    return rescored[:top_k]
