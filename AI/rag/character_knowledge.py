"""Validation and text construction for verified character lore facts."""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlparse


ALLOWED_EVIDENCE_TYPES = {
    "official_source",
    "user_confirmed_on_screen_detail",
}
ALLOWED_SOURCE_HOSTS = {
    "www.dc.com",
    "www.harrypotter.com",
    "www.koreanfilm.or.kr",
    "www.marvel.com",
    "movies.disney.com",
    "movies.disney.co.kr",
    "toystory.disney.com",
    "www.pixar.com",
    "www.tolkienestate.com",
}
FACT_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
RELATION_QUESTION_PATTERN = re.compile(
    r"무슨사이|어떤사이|관계|어떻게생각|누구(?:야|지|냐|예요|에요)?|친구|동료|적(?:이야|인가|이냐)?"
)


def load_verified_facts(path: str | Path, profile_names: set[str]) -> tuple[dict, list[dict]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    facts = payload.get("facts") or []
    required = {
        "fact_id", "character_name", "category", "subject", "aliases",
        "summary", "response", "source_work", "evidence_type", "evidence_note",
        "source_title", "source_publisher", "source_url",
    }
    seen: set[str] = set()
    for index, fact in enumerate(facts):
        missing = sorted(required - fact.keys())
        if missing:
            raise RuntimeError(f"fact {index} missing fields: {missing}")
        fact_id = str(fact["fact_id"])
        if not FACT_ID_PATTERN.fullmatch(fact_id) or fact_id in seen:
            raise RuntimeError(f"invalid or duplicate fact_id: {fact_id}")
        seen.add(fact_id)
        if fact["character_name"] not in profile_names:
            raise RuntimeError(f"unknown fact character: {fact['character_name']}")
        if fact["evidence_type"] not in ALLOWED_EVIDENCE_TYPES:
            raise RuntimeError(f"unsupported evidence type: {fact['evidence_type']}")
        if not isinstance(fact["aliases"], list) or not all(
            isinstance(alias, str) and alias.strip() for alias in fact["aliases"]
        ):
            raise RuntimeError(f"invalid aliases: {fact_id}")
        match_groups = fact.get("match_groups")
        if match_groups is not None and (
            not isinstance(match_groups, list)
            or not match_groups
            or not all(
                isinstance(group, list)
                and group
                and all(isinstance(term, str) and term.strip() for term in group)
                for group in match_groups
            )
        ):
            raise RuntimeError(f"invalid match_groups: {fact_id}")
        parsed = urlparse(str(fact["source_url"]))
        if parsed.scheme != "https" or parsed.hostname not in ALLOWED_SOURCE_HOSTS:
            raise RuntimeError(f"unapproved fact source: {fact['source_url']}")
        if not str(fact["summary"]).strip() or len(fact["summary"]) > 500:
            raise RuntimeError(f"invalid fact summary: {fact_id}")
        if not str(fact["response"]).strip() or len(fact["response"]) > 300:
            raise RuntimeError(f"invalid fact response: {fact_id}")
    return payload, facts


def verified_fact_reply(facts: list[dict], character_name: str, user_message: str) -> str | None:
    """Return an exact curated answer only when every configured intent group matches."""
    normalized = re.sub(r"\s+", "", str(user_message or "")).casefold()
    for fact in facts:
        if fact.get("character_name") != character_name:
            continue
        groups = fact.get("match_groups") or []
        if not groups:
            continue
        if all(any(re.sub(r"\s+", "", term).casefold() in normalized for term in group) for group in groups):
            return str(fact["response"]).strip()
    return None


def load_verified_relations(path: str | Path, profile_names: set[str]) -> tuple[dict, list[dict]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    relations = payload.get("relations") or []
    required = {
        "character_name", "related_character", "relation_type", "summary", "response",
        "source_work", "source_title", "source_publisher", "source_url",
    }
    seen: set[tuple[str, str]] = set()
    for index, relation in enumerate(relations):
        missing = sorted(required - relation.keys())
        if missing:
            raise RuntimeError(f"relation {index} missing fields: {missing}")
        character_name = str(relation["character_name"]).strip()
        related_character = str(relation["related_character"]).strip()
        key = (character_name, related_character)
        if not character_name or not related_character or key in seen:
            raise RuntimeError(f"invalid or duplicate relation: {key}")
        seen.add(key)
        if character_name not in profile_names:
            raise RuntimeError(f"unknown relation character: {character_name}")
        parsed = urlparse(str(relation["source_url"]))
        if parsed.scheme != "https" or parsed.hostname not in ALLOWED_SOURCE_HOSTS:
            raise RuntimeError(f"unapproved relation source: {relation['source_url']}")
        if not str(relation["summary"]).strip() or len(relation["summary"]) > 500:
            raise RuntimeError(f"invalid relation summary: {key}")
        if not str(relation["response"]).strip() or len(relation["response"]) > 300:
            raise RuntimeError(f"invalid relation response: {key}")
    return payload, relations


def verified_relation_reply(
    relations: list[dict], character_name: str, user_message: str
) -> str | None:
    """Return a curated relation answer only for an explicit relation question."""
    normalized = re.sub(r"\s+", "", str(user_message or "")).casefold()
    if not RELATION_QUESTION_PATTERN.search(normalized):
        return None
    for relation in relations:
        if relation.get("character_name") != character_name:
            continue
        related = re.sub(r"\s+", "", str(relation["related_character"])).casefold()
        if related and related in normalized:
            return str(relation["response"]).strip()
    return None


def lore_fact_text(fact: dict) -> str:
    return (
        f"캐릭터: {fact['character_name']}\n"
        f"사실 주제: {fact['subject']}\n"
        f"검색 별칭: {', '.join(fact['aliases'])}\n"
        f"확인된 내용: {fact['summary']}\n"
        f"답변 기준: {fact['response']}\n"
        f"작품: {fact['source_work']}\n"
        f"근거 등급: {fact['evidence_type']}"
    )
