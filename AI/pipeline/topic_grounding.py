"""Configurable topic interpretation, evidence validation, and safe learning logs.

The language model may help retrieval elsewhere, but it is never accepted as proof
that a movie belongs to a requested topic.  This module preserves the user's literal
topic and validates candidates against stored movie metadata before reranking.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Iterable


_AI_DIR = Path(__file__).resolve().parents[1]
DEFAULT_PROFILE_PATH = _AI_DIR / "data" / "topic_profiles.json"
DEFAULT_LOG_PATH = _AI_DIR / "logs" / "topic-learning.jsonl"

_TOPIC_PATTERNS = (
    re.compile(r"(?P<topic>[^?!.]{1,80}?)\s*(?:와|과)?\s*관련(?:된|한)?\s*(?:영화|작품)"),
    re.compile(r"(?P<topic>[^?!.]{1,80}?)\s*(?:에\s*)?관한\s*(?:영화|작품)"),
    re.compile(r"(?P<topic>[^?!.]{1,80}?)\s*(?:을|를)?\s*다룬\s*(?:영화|작품)"),
    re.compile(r"(?P<topic>[^?!.]{1,80}?)\s*소재(?:의|인)?\s*(?:영화|작품)"),
)
_REQUEST_FILLER = re.compile(
    r"^(?:혹시|나|저|나는|저는|요즘|오늘|이번에|그냥|좀|볼\s*만한|보고\s*싶은)\s*"
)
_TRAILING_FILLER = re.compile(
    r"\s*(?:영화|작품)?\s*(?:을|를)?\s*(?:보고\s*싶|찾|추천|골라|알려).*$"
)
_TOKEN = re.compile(r"[가-힣]{2,}|[A-Za-z][A-Za-z0-9+#.-]{1,}")
_GENERIC_TOPICS = {
    "관련", "영화", "작품", "추천", "소재", "이야기", "내용", "분야", "무언가", "뭔가",
}
_EVIDENCE_FIELDS = (
    "overview", "keywords", "text", "genres", "genres_list", "cast", "director",
)


@dataclass(frozen=True)
class TopicInterpretation:
    topic_id: str
    label: str
    search_terms: tuple[str, ...]
    evidence_terms: tuple[str, ...]
    confidence: float
    source: str
    literal_topic: str
    ambiguous: bool = False
    clarification_question: str = ""

    def to_dict(self) -> dict:
        value = asdict(self)
        value["search_terms"] = list(self.search_terms)
        value["evidence_terms"] = list(self.evidence_terms)
        return value


def _normalized(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


@lru_cache(maxsize=8)
def _load_profiles(path_value: str) -> tuple[dict, ...]:
    path = Path(path_value)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(f"  [TopicGrounding] 주제 프로필 로드 실패: {exc}")
        return ()
    profiles = payload.get("profiles") if isinstance(payload, dict) else None
    return tuple(profile for profile in (profiles or []) if isinstance(profile, dict))


def get_topic_profiles() -> tuple[dict, ...]:
    path = os.getenv("TOPIC_PROFILE_PATH", str(DEFAULT_PROFILE_PATH))
    return _load_profiles(path)


def _profile_match(text: str) -> TopicInterpretation | None:
    normalized = _normalized(text)
    for profile in get_topic_profiles():
        aliases = tuple(str(value).strip() for value in profile.get("aliases", []) if str(value).strip())
        if not any(_normalized(alias) in normalized for alias in aliases):
            continue
        search_terms = tuple(
            str(value).strip() for value in profile.get("search_terms", []) if str(value).strip()
        )
        evidence_terms = tuple(
            str(value).strip() for value in profile.get("evidence_terms", []) if str(value).strip()
        )
        return TopicInterpretation(
            topic_id=str(profile.get("id") or "configured-topic"),
            label=str(profile.get("label") or aliases[0]),
            search_terms=search_terms or aliases,
            evidence_terms=evidence_terms or aliases,
            confidence=1.0,
            source="profile",
            literal_topic=next(alias for alias in aliases if _normalized(alias) in normalized),
        )
    return None


def _extract_literal_topic(text: str) -> str:
    for pattern in _TOPIC_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        topic = _REQUEST_FILLER.sub("", match.group("topic").strip())
        topic = _TRAILING_FILLER.sub("", topic).strip(" ,·/")
        topic = re.sub(r"(?:은|는|이|가|을|를|와|과)$", "", topic).strip()
        return re.sub(r"\s+", " ", topic)
    return ""


def interpret_topic(user_message: str) -> TopicInterpretation | None:
    """Interpret only explicit topic requests without inventing unknown synonyms."""
    configured = _profile_match(user_message)
    if configured:
        return configured

    literal = _extract_literal_topic(user_message)
    if not literal:
        return None
    tokens = tuple(
        dict.fromkeys(
            token for token in _TOKEN.findall(literal)
            if _normalized(token) not in _GENERIC_TOPICS
        )
    )
    if not tokens:
        return TopicInterpretation(
            topic_id="literal",
            label=literal or "요청한 주제",
            search_terms=(),
            evidence_terms=(),
            confidence=0.0,
            source="literal",
            literal_topic=literal,
            ambiguous=True,
            clarification_question="어떤 소재나 주제의 영화를 찾는지 한 단어만 더 알려주시겠어요?",
        )
    return TopicInterpretation(
        topic_id="literal",
        label=literal,
        search_terms=tokens,
        evidence_terms=tokens,
        confidence=0.72,
        source="literal",
        literal_topic=literal,
    )


def topic_from_dict(value: dict | TopicInterpretation | None) -> TopicInterpretation | None:
    if isinstance(value, TopicInterpretation):
        return value
    if not isinstance(value, dict):
        return None
    try:
        return TopicInterpretation(
            topic_id=str(value.get("topic_id") or "literal"),
            label=str(value.get("label") or value.get("literal_topic") or "요청한 주제"),
            search_terms=tuple(str(term) for term in value.get("search_terms", []) if str(term)),
            evidence_terms=tuple(str(term) for term in value.get("evidence_terms", []) if str(term)),
            confidence=float(value.get("confidence") or 0.0),
            source=str(value.get("source") or "literal"),
            literal_topic=str(value.get("literal_topic") or value.get("label") or ""),
            ambiguous=bool(value.get("ambiguous")),
            clarification_question=str(value.get("clarification_question") or ""),
        )
    except (TypeError, ValueError):
        return None


def _term_in_text(term: str, text: str) -> bool:
    normalized_term = _normalized(term)
    normalized_text = _normalized(text)
    if not normalized_term:
        return False
    if re.fullmatch(r"[a-z0-9+#. -]+", normalized_term):
        return bool(re.search(rf"(?<![a-z0-9]){re.escape(normalized_term)}(?![a-z0-9])", normalized_text))
    return normalized_term in normalized_text


def topic_evidence(movie: dict, topic_value: dict | TopicInterpretation | None) -> list[tuple[str, str]]:
    """Return (field, term) evidence; title alone is not thematic evidence."""
    topic = topic_from_dict(topic_value)
    if not topic or topic.ambiguous:
        return []
    matches: list[tuple[str, str]] = []
    for field in _EVIDENCE_FIELDS:
        raw = movie.get(field)
        if isinstance(raw, (list, tuple, set)):
            raw = " ".join(str(item) for item in raw)
        for term in topic.evidence_terms:
            if _term_in_text(term, str(raw or "")):
                matches.append((field, term))
    return matches


def filter_topic_candidates(
    candidates: Iterable[dict],
    topic_value: dict | TopicInterpretation | None,
) -> list[dict]:
    topic = topic_from_dict(topic_value)
    movies = list(candidates)
    if not topic:
        return movies
    if topic.ambiguous or not topic.evidence_terms:
        return []
    return [movie for movie in movies if topic_evidence(movie, topic)]


def build_topic_search_query(user_message: str, topic_value: dict | TopicInterpretation) -> str:
    topic = topic_from_dict(topic_value)
    if not topic:
        return user_message
    terms = " ".join(topic.search_terms)
    if topic.source == "profile":
        return f"{terms} 영화".strip()
    return f"{user_message} {terms}".strip()


def topic_no_result_message(topic_value: dict | TopicInterpretation | None) -> str:
    topic = topic_from_dict(topic_value)
    if not topic:
        return "조건에 맞는 영화를 찾지 못했어요. 다른 분위기나 장르를 알려주시겠어요?"
    if topic.clarification_question:
        return topic.clarification_question
    return (
        f"현재 영화 정보에서 ‘{topic.label}’ 소재라는 근거가 확인되는 작품을 찾지 못했어요. "
        "비슷한 표현이나 더 넓은 주제로 다시 알려주시겠어요?"
    )


def build_topic_reason(movie: dict, topic_value: dict | TopicInterpretation | None) -> str | None:
    topic = topic_from_dict(topic_value)
    evidence = topic_evidence(movie, topic)
    if not topic or not evidence:
        return None
    _, term = evidence[0]
    return f"작품 정보에서 {term} 소재가 확인돼 {topic.label} 관련 영화로 골랐어요."


def build_learning_event(
    topic_value: dict | TopicInterpretation,
    outcome: str,
    movies: Iterable[dict] = (),
) -> dict:
    """Build an intentionally privacy-minimal review event (no raw prompt/user id)."""
    topic = topic_from_dict(topic_value)
    if not topic:
        return {}
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "topic_id": topic.topic_id,
        "label": topic.label,
        "source": topic.source,
        "confidence": topic.confidence,
        "ambiguous": topic.ambiguous,
        "search_terms": list(topic.search_terms),
        "evidence_terms": list(topic.evidence_terms),
        "outcome": str(outcome),
        "movies": [
            {
                "tmdb_id": movie.get("tmdb_id"),
                "title": str(movie.get("title") or ""),
            }
            for movie in movies
        ],
    }


def log_topic_event(
    topic_value: dict | TopicInterpretation | None,
    outcome: str,
    movies: Iterable[dict] = (),
) -> None:
    event = build_learning_event(topic_value, outcome, movies)
    if not event:
        return
    path = Path(os.getenv("TOPIC_LEARNING_LOG_PATH", str(DEFAULT_LOG_PATH)))
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, ensure_ascii=False) + "\n")
    except OSError as exc:
        # Recommendation availability must not depend on an audit-log filesystem.
        print(f"  [TopicGrounding] 학습 후보 로그 저장 실패: {exc}")
