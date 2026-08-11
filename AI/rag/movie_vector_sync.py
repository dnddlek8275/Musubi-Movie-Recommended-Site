from __future__ import annotations

import json
import os

from pymilvus import Collection, connections

from rag.embedder import embed


COLLECTION_NAME = os.getenv("MOVIE_COLLECTION_NAME", "movies_active")
MILVUS_HOST = os.getenv("MILVUS_HOST", "127.0.0.1")
MILVUS_PORT = os.getenv("MILVUS_PORT", "19530")


def _text(value) -> str:
    return str(value or "").strip()


def _integer(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _floating(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def build_movie_text(movie: dict) -> str:
    genres = ", ".join(movie.get("genres") or [])
    cast = ", ".join(movie.get("cast") or [])
    keywords = ", ".join(movie.get("keywords") or [])
    countries = ", ".join(movie.get("production_countries") or [])
    parts = [
        f"제목: {_text(movie.get('title'))}",
        f"장르: {genres}" if genres else "",
        f"감독: {_text(movie.get('director'))}" if movie.get("director") else "",
        f"출연: {cast}" if cast else "",
        f"개봉일: {_text(movie.get('release_date')) or _integer(movie.get('year'))}",
        f"상영시간: {_integer(movie.get('runtime'))}분" if movie.get("runtime") else "",
        f"언어: {_text(movie.get('language'))}" if movie.get("language") else "",
        f"제작국가: {countries}" if countries else "",
        f"관람등급: {_text(movie.get('certification_country'))} {_text(movie.get('certification'))}".strip()
        if movie.get("certification") else "",
        f"평점: {_floating(movie.get('vote_average')):.1f} (투표수: {_integer(movie.get('vote_count')):,})",
        f"줄거리: {_text(movie.get('overview'))}" if movie.get("overview") else "",
        f"키워드: {keywords}" if keywords else "",
    ]
    return "\n".join(part for part in parts if part)


def _entity(movie: dict, dense: list[float], sparse: dict) -> dict:
    genres = [_text(value) for value in movie.get("genres") or [] if _text(value)]
    cast = [_text(value) for value in movie.get("cast") or [] if _text(value)]
    keywords = [_text(value) for value in movie.get("keywords") or [] if _text(value)]
    countries = [_text(value) for value in movie.get("production_countries") or [] if _text(value)]
    return {
        "dense_vector": dense,
        "sparse_vector": {int(key): float(value) for key, value in sparse.items()},
        "tmdb_id": str(_integer(movie.get("tmdb_id"))),
        "title": _text(movie.get("title"))[:500],
        "text": build_movie_text(movie)[:4096],
        "overview": _text(movie.get("overview"))[:3000],
        "genres": ", ".join(genres)[:200],
        "genres_list": json.dumps(genres, ensure_ascii=False)[:500],
        "director": _text(movie.get("director"))[:500],
        "cast": ", ".join(cast)[:1000],
        "keywords": ", ".join(keywords)[:1500],
        "production_countries": ", ".join(countries)[:100],
        "certification": _text(movie.get("certification"))[:20],
        "certification_country": _text(movie.get("certification_country"))[:10],
        "year": _integer(movie.get("year")),
        "release_date": _text(movie.get("release_date"))[:10],
        "language": _text(movie.get("language"))[:10],
        "runtime": _integer(movie.get("runtime")),
        "vote_average": _floating(movie.get("vote_average")),
        "vote_count": _integer(movie.get("vote_count")),
        "audience_count": _integer(movie.get("audience_count")),
        "poster_path": _text(movie.get("poster_path"))[:500],
    }


def sync_movies(upserts: list[dict], deletes: list[int]) -> dict:
    invalid_ids = [movie.get("tmdb_id") for movie in upserts if _integer(movie.get("tmdb_id")) <= 0]
    if invalid_ids:
        raise ValueError("upserts contain invalid tmdb_id")
    upsert_ids = {_integer(movie["tmdb_id"]) for movie in upserts}
    delete_ids = {_integer(value) for value in deletes if _integer(value) > 0} - upsert_ids

    texts = [build_movie_text(movie) for movie in upserts]
    if texts:
        dense_vectors, sparse_vectors = embed(texts)
        entities = [
            _entity(movie, dense, sparse)
            for movie, dense, sparse in zip(upserts, dense_vectors, sparse_vectors)
        ]
    else:
        entities = []

    connections.connect(alias="movie_sync", host=MILVUS_HOST, port=MILVUS_PORT)
    collection = Collection(COLLECTION_NAME, using="movie_sync")
    ids_to_replace = sorted(upsert_ids | delete_ids)
    if ids_to_replace:
        quoted_ids = ",".join(json.dumps(str(value)) for value in ids_to_replace)
        collection.delete(expr=f"tmdb_id in [{quoted_ids}]")
    if entities:
        collection.insert(entities)
    collection.flush()
    return {"upserted": len(entities), "deleted": len(delete_ids)}
