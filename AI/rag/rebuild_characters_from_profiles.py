"""Build a profile-only character collection without generated events or quotes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlparse

from pymilvus import DataType, MilvusClient

from rag.embedder import embed
from rag.character_knowledge import load_verified_facts, lore_fact_text


ALLOWED_SOURCE_HOSTS = {
    "www.dc.com",
    "www.harrypotter.com",
    "www.koreanfilm.or.kr",
    "www.marvel.com",
    "movies.disney.com",
    "www.tolkienestate.com",
    "www.pixar.com",
}


def build_profile_text(character: dict) -> str:
    inter = character.get("interaction_style") or {}
    parts = [
        f"캐릭터: {character['name']}",
        f"작품: {character['movie']}",
        f"정체성: {character['identity']}",
        "성격: " + " / ".join((character.get("personality") or [])[:4]),
        "말투: " + " / ".join((character.get("speech_style") or [])[:5]),
        "사고방식: " + " / ".join((character.get("thinking_style") or [])[:3]),
        "사용자 응대: " + " / ".join((inter.get("with_user") or [])[:3]),
        "고유 관점: " + " / ".join((character.get("signature_elements") or [])[:3]),
        # ``avoid`` often contains other character names as negative examples.
        # Storing those names in retrieval text falsely looks like relationship
        # evidence, so avoidance rules stay in the system prompt only.
    ]
    return "\n".join(part for part in parts if not part.endswith(": "))[:4000]


def create_collection(client: MilvusClient, collection_name: str) -> None:
    if client.has_collection(collection_name):
        stats = client.get_collection_stats(collection_name)
        if int(stats.get("row_count") or 0) != 0:
            raise RuntimeError(f"non-empty collection already exists: {collection_name}")
        client.drop_collection(collection_name)
    schema = client.create_schema(auto_id=True, enable_dynamic_field=False)
    schema.add_field("id", DataType.INT64, is_primary=True)
    schema.add_field("character_name", DataType.VARCHAR, max_length=100)
    schema.add_field("movie", DataType.VARCHAR, max_length=200)
    schema.add_field("lang", DataType.VARCHAR, max_length=10)
    schema.add_field("data_type", DataType.VARCHAR, max_length=20)
    schema.add_field("text", DataType.VARCHAR, max_length=4000)
    schema.add_field("metadata", DataType.VARCHAR, max_length=8000)
    schema.add_field("dense_vector", DataType.FLOAT_VECTOR, dim=1024)
    schema.add_field("sparse_vector", DataType.SPARSE_FLOAT_VECTOR)
    indexes = client.prepare_index_params()
    indexes.add_index(
        "dense_vector", metric_type="COSINE", index_type="IVF_FLAT", params={"nlist": 64}
    )
    indexes.add_index(
        "sparse_vector", metric_type="IP", index_type="SPARSE_INVERTED_INDEX"
    )
    client.create_collection(collection_name, schema=schema, index_params=indexes)


def load_verified_relations(path: str, profile_names: set[str]) -> tuple[dict, list[dict]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    relations = payload.get("relations") or []
    seen: set[tuple[str, str]] = set()
    required = {
        "character_name", "related_character", "relation_type", "summary",
        "source_work", "source_title", "source_publisher", "source_url", "response",
    }
    for index, relation in enumerate(relations):
        missing = sorted(required - relation.keys())
        if missing:
            raise RuntimeError(f"relation {index} missing fields: {missing}")
        if relation["character_name"] not in profile_names:
            raise RuntimeError(f"unknown source character: {relation['character_name']}")
        key = (relation["character_name"], relation["related_character"])
        if key in seen:
            raise RuntimeError(f"duplicate relation: {key}")
        seen.add(key)
        parsed = urlparse(relation["source_url"])
        if parsed.scheme != "https" or parsed.hostname not in ALLOWED_SOURCE_HOSTS:
            raise RuntimeError(f"unapproved relation source: {relation['source_url']}")
        if len(relation["summary"]) > 500:
            raise RuntimeError(f"relation summary too long: {key}")
        if not relation["response"].strip() or len(relation["response"]) > 300:
            raise RuntimeError(f"invalid relation response: {key}")
    return payload, relations


def relation_text(relation: dict) -> str:
    return (
        f"캐릭터: {relation['character_name']}\n"
        f"상대 인물: {relation['related_character']}\n"
        f"관계: {relation['relation_type']}\n"
        f"확인된 내용: {relation['summary']}\n"
        f"답변 기준: {relation['response']}\n"
        f"작품: {relation['source_work']}"
    )


def insert_batches(
    client: MilvusClient,
    collection_name: str,
    entities: list[dict],
    batch_size: int,
    label: str,
) -> None:
    for offset in range(0, len(entities), batch_size):
        source_batch = entities[offset:offset + batch_size]
        texts = [entity["_text"] for entity in source_batch]
        dense, sparse = embed(texts)
        batch = []
        for entity, text, dense_vector, sparse_vector in zip(source_batch, texts, dense, sparse):
            batch.append({
                **{key: value for key, value in entity.items() if key != "_text"},
                "text": text,
                "dense_vector": dense_vector,
                "sparse_vector": sparse_vector,
            })
        client.insert(collection_name, batch)
        print(f"inserted {label} {offset + len(batch)}/{len(entities)}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profiles", default="character_profiles_ALL_50.json")
    parser.add_argument("--relations", default="data/character_relations_verified_v1.json")
    parser.add_argument("--facts", default="data/character_facts_verified_v1.json")
    parser.add_argument("--collection", default="characters_verified_v6")
    parser.add_argument("--milvus-uri", default="http://127.0.0.1:19530")
    parser.add_argument("--batch-size", type=int, default=10)
    args = parser.parse_args()

    profiles = json.loads(Path(args.profiles).read_text(encoding="utf-8"))
    characters = list(profiles["characters"].values())
    if len(characters) != 50:
        raise RuntimeError(f"expected 50 characters, got {len(characters)}")
    relation_payload, relations = load_verified_relations(
        args.relations, {character["name"] for character in characters}
    )
    fact_payload, facts = load_verified_facts(
        args.facts, {character["name"] for character in characters}
    )
    client = MilvusClient(uri=args.milvus_uri)
    create_collection(client, args.collection)
    profile_entities = []
    for character in characters:
        profile_entities.append({
                "character_name": character["name"],
                "movie": character["movie"],
                "lang": "ko",
                "data_type": "profile",
                "_text": build_profile_text(character),
                "metadata": json.dumps(
                    {"source": "character_profiles_ALL_50.json", "profile_version": profiles.get("version")},
                    ensure_ascii=False,
                ),
            })
    relation_entities = []
    for relation in relations:
        relation_entities.append({
            "character_name": relation["character_name"],
            "movie": relation["source_work"],
            "lang": "ko",
            "data_type": "relation",
            "_text": relation_text(relation),
            "metadata": json.dumps({
                "related_character": relation["related_character"],
                "relation_type": relation["relation_type"],
                "source_title": relation["source_title"],
                "source_publisher": relation["source_publisher"],
                "source_url": relation["source_url"],
                "relation_version": relation_payload.get("version"),
                "verified_at": relation_payload.get("verified_at"),
            }, ensure_ascii=False),
        })
    fact_entities = []
    for fact in facts:
        fact_entities.append({
            "character_name": fact["character_name"],
            "movie": fact["source_work"],
            "lang": "ko",
            "data_type": "lore_fact",
            "_text": lore_fact_text(fact),
            "metadata": json.dumps({
                "fact_id": fact["fact_id"],
                "category": fact["category"],
                "evidence_type": fact["evidence_type"],
                "evidence_note": fact["evidence_note"],
                "source_title": fact["source_title"],
                "source_publisher": fact["source_publisher"],
                "source_url": fact["source_url"],
                "fact_version": fact_payload.get("version"),
                "verified_at": fact_payload.get("verified_at"),
            }, ensure_ascii=False),
        })
    insert_batches(client, args.collection, profile_entities, args.batch_size, "profiles")
    insert_batches(client, args.collection, relation_entities, args.batch_size, "relations")
    insert_batches(client, args.collection, fact_entities, args.batch_size, "lore facts")
    client.flush(collection_name=args.collection)
    stats = client.get_collection_stats(args.collection)
    print(json.dumps({
        "collection": args.collection,
        "profiles": len(profile_entities),
        "relations": len(relation_entities),
        "lore_facts": len(fact_entities),
        **stats,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
