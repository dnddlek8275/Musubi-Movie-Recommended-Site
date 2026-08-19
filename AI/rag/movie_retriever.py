"""
Musubi Movie Retriever
Milvus movies 컬렉션 하이브리드 검색
스키마: title / text / overview / genres / director / cast /
        year / language / vote_average / audience_count / poster_path / tmdb_id
"""

from __future__ import annotations
import os
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache

from pymilvus import MilvusClient, AnnSearchRequest, RRFRanker

from rag.embedder import embed_query
from rag.reranker import rerank
from rag.movie_quality import (
    apply_query_preferences,
    blend_semantic_and_quality,
    expand_mood_query,
    prefer_evidenced_candidates,
    prefer_bright_candidates,
    prefer_explainable_candidates,
    prefer_non_sad_candidates,
    prefer_well_received_candidates,
)
from pipeline.topic_grounding import filter_topic_candidates

MILVUS_URI      = os.getenv("CINEVERSE_MILVUS_URI", "http://localhost:19530")
COLLECTION_NAME = os.getenv("MOVIE_COLLECTION_NAME", "movies_active")
RERANK_CANDIDATE_MULTIPLIER = max(
    1, int(os.getenv("RERANK_CANDIDATE_MULTIPLIER", "1"))
)
RERANK_CANDIDATE_MINIMUM = max(
    1, int(os.getenv("RERANK_CANDIDATE_MINIMUM", "12"))
)
RERANK_CANDIDATE_COMPLEX_MAXIMUM = max(
    RERANK_CANDIDATE_MINIMUM,
    int(os.getenv("RERANK_CANDIDATE_COMPLEX_MAXIMUM", "18")),
)

OUTPUT_FIELDS = [
    "title", "text", "overview", "genres", "genres_list",
    "director", "cast", "year", "release_date", "language",
    "production_countries",
    "certification", "certification_country",
    "runtime",
    "vote_average", "vote_count", "audience_count",
    "poster_path", "tmdb_id",
]


@dataclass
class MovieFilter:
    """영화 검색 메타 필터"""
    genre:      str | None   = None
    actor:      str | None   = None
    director:   str | None   = None
    language:   str | None   = None
    production_country: str | None = None
    year_from:  int | None   = None
    year_to:    int | None   = None
    release_date_from: str | None = None
    release_date_to: str | None = None
    min_rating: float | None = None
    runtime_max: int | None = None
    audience_min: int | None = None
    exclude_genres: list[str] = field(default_factory=list)
    required_genres: list[str] = field(default_factory=list)

    def to_expr(self) -> str | None:
        filters = []
        if self.genre:
            filters.append(f'genres like "%{self.genre}%"')
        for genre in self.required_genres:
            if genre and genre != self.genre:
                safe_genre = str(genre).replace('"', '\\"')
                filters.append(f'genres like "%{safe_genre}%"')
        if self.actor:
            filters.append(f'cast like "%{self.actor}%"')
        if self.director:
            filters.append(f'director like "%{self.director}%"')
        if self.language:
            filters.append(f'language == "{self.language}"')
        if self.production_country:
            safe_country = str(self.production_country).replace('"', '\\"')
            filters.append(f'production_countries like "%{safe_country}%"')
        if self.year_from:
            filters.append(f'year >= {self.year_from}')
        if self.year_to:
            filters.append(f'year <= {self.year_to}')
        if self.release_date_from:
            filters.append(f'release_date >= "{self.release_date_from}"')
        if self.release_date_to:
            filters.append(f'release_date <= "{self.release_date_to}"')
        if self.min_rating:
            filters.append(f'vote_average >= {self.min_rating}')
        if self.runtime_max:
            filters.append(f'runtime > 0 and runtime <= {self.runtime_max}')
        if self.audience_min:
            filters.append(f'audience_count >= {self.audience_min}')
        for genre in self.exclude_genres:
            safe_genre = str(genre).replace('"', '\\"')
            filters.append(f'not (genres like "%{safe_genre}%")')
        return " and ".join(filters) if filters else None


@lru_cache(maxsize=1)
def get_client() -> MilvusClient:
    client = MilvusClient(uri=MILVUS_URI)
    client.load_collection(COLLECTION_NAME)
    return client


def retrieve(
    query: str,
    top_k: int = 5,
    movie_filter: MovieFilter | None = None,
    sort_latest: bool = False,
    exclude_titles: set[str] | None = None,
    required_count: int | None = None,
    quality_weight: float = 0.30,
    topic: dict | None = None,
    rerank_mode: str = "standard",
) -> list[dict]:
    """
    영화를 하이브리드 검색 후 CrossEncoder로 재순위.

    흐름:
        BGE-M3 임베딩 → Hybrid Search (Dense + Sparse + RRF) → CrossEncoder 리랭킹

    Args:
        query:        검색 쿼리 (자연어)
        top_k:        최종 반환 개수
        movie_filter: 메타 필터 조건

    Returns:
        재순위된 영화 dict 리스트
    """
    client = get_client()
    effective_query = expand_mood_query(query)
    dense, sparse = embed_query(effective_query)
    fetch_limit = max(top_k * (20 if sort_latest else 10), top_k)
    filter_expr = movie_filter.to_expr() if movie_filter else None

    dense_req = AnnSearchRequest(
        data=[dense],
        anns_field="dense_vector",
        param={"metric_type": "COSINE", "params": {"nprobe": 10}},
        limit=fetch_limit,
        expr=filter_expr,
    )
    sparse_req = AnnSearchRequest(
        data=[sparse],
        anns_field="sparse_vector",
        param={"metric_type": "IP", "params": {}},
        limit=fetch_limit,
        expr=filter_expr,
    )

    try:
        results = client.hybrid_search(
            collection_name=COLLECTION_NAME,
            reqs=[dense_req, sparse_req],
            ranker=RRFRanker(k=60),
            limit=fetch_limit,
            output_fields=OUTPUT_FIELDS,
        )
        hits = results[0] if results else []
    except Exception as e:
        print(f"  [MovieRetriever] hybrid_search 실패: {e}")
        return []

    if not hits:
        return []

    excluded = {str(title).strip() for title in (exclude_titles or set()) if str(title).strip()}
    candidates = [h["entity"] for h in hits if str(h["entity"].get("title") or "").strip() not in excluded]
    required = required_count or top_k
    # Explicit topics are hard constraints. Validate metadata before the GPU
    # CrossEncoder so false candidates neither consume rerank time nor leak out.
    candidates = filter_topic_candidates(candidates, topic)
    if topic and not candidates:
        return []
    # A latest-first request must still have enough real-user evidence. Raw
    # ratings from one or two votes otherwise dominate the date sort despite
    # providing no reliable recommendation signal.
    candidates = prefer_evidenced_candidates(candidates, required=required)
    if not sort_latest:
        candidates = apply_query_preferences(query, candidates, required=required)
        candidates = prefer_explainable_candidates(query, candidates, required=required)
        candidates = prefer_non_sad_candidates(query, candidates, required=required)
        candidates = prefer_bright_candidates(query, candidates, required=required)
        candidates = prefer_well_received_candidates(query, candidates, required=required)

    if sort_latest:
        # The final result is ordered only by release date, so CrossEncoder scores
        # would be discarded immediately. Skip that expensive GPU pass entirely.
        ranked = candidates
        today = date.today().isoformat()
        ranked = [m for m in ranked if not m.get("release_date") or m["release_date"] <= today]
        ranked.sort(key=lambda m: m.get("release_date") or "", reverse=True)
        ranked = ranked[:top_k]
    elif rerank_mode == "skip":
        # Exact metadata constraints (genre/actor/director/language/year/rating)
        # are already enforced by Milvus. Preserve the hybrid RRF order and apply
        # the inexpensive quality blend without competing with llama-server for GPU.
        direct_limit = max(top_k, RERANK_CANDIDATE_MINIMUM)
        ranked = blend_semantic_and_quality(
            candidates[:direct_limit],
            top_k=top_k,
            quality_weight=max(0.0, min(float(quality_weight), 1.0)),
            query=query,
        )
        print(
            f"  [MovieRetriever] rerank=skip candidates={min(len(candidates), direct_limit)} "
            f"reason=metadata_filter"
        )
    else:
        # Keep the wide Milvus pool for recall, but only send the strongest RRF
        # candidates to the GPU CrossEncoder. For the production top_k=9 path this
        # reduces 90 pair evaluations to 12 while retaining four candidates per
        # final recommendation card (required_count=3).
        rerank_limit = max(
            RERANK_CANDIDATE_MINIMUM,
            top_k * RERANK_CANDIDATE_MULTIPLIER,
        )
        if rerank_mode == "complex":
            rerank_limit = max(
                top_k,
                min(
                    RERANK_CANDIDATE_COMPLEX_MAXIMUM,
                    max(rerank_limit, top_k * 2),
                ),
            )
        rerank_candidates = candidates[:rerank_limit]
        print(
            f"  [MovieRetriever] rerank={rerank_mode} "
            f"candidates={len(rerank_candidates)}"
        )
        ranked = rerank(
            effective_query,
            rerank_candidates,
            text_key="text",
            top_k=rerank_limit,
        )
        ranked = blend_semantic_and_quality(
            ranked,
            top_k=top_k,
            quality_weight=max(0.0, min(float(quality_weight), 1.0)),
            query=query,
        )

    # 내부 점수 필드 제거 후 반환
    return [{k: v for k, v in m.items() if k not in {"_score", "_final_score"}} for m in ranked]


def format_for_prompt(movies: list[dict], max_overview: int = 200) -> str:
    """영화 목록을 LLM 프롬프트 주입용 텍스트로 변환"""
    if not movies:
        return ""
    lines = []
    for i, m in enumerate(movies, 1):
        lines.append(
            f"{i}. {m.get('title', '')} ({m.get('release_date') or m.get('year', '')})\n"
            f"   장르: {m.get('genres', '')}\n"
            f"   감독: {m.get('director', '')}\n"
            f"   출연: {str(m.get('cast', ''))[:100]}\n"
            f"   평점: {round(float(m['vote_average']), 1) if m.get('vote_average') is not None else '-'}\n"
            f"   상영시간: {m.get('runtime') or '-'}분\n"
            f"   관람등급: {m.get('certification_country', '')} {m.get('certification', '')}\n"
            f"   줄거리: {str(m.get('overview', ''))[:max_overview]}"
        )
    return "\n\n".join(lines)


def to_response(movies: list[dict]) -> list[dict]:
    """프론트엔드 응답용 영화 dict로 변환 (필요한 필드만, poster_url 풀 URL)"""
    TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"

    def poster_url(value: str | None) -> str:
        path = str(value or "").strip()
        if not path:
            return ""
        if path.startswith(("http://", "https://")):
            return path
        return f"{TMDB_IMAGE_BASE}{path}"

    return [
        {
            "title":        m.get("title", ""),
            "year":         m.get("year", ""),
            "release_date": m.get("release_date", ""),
            "language":     m.get("language", ""),
            "production_countries": m.get("production_countries", ""),
            "genres":       m.get("genres", ""),
            "director":     m.get("director", ""),
            "cast":         m.get("cast", ""),
            "vote_average": round(float(m["vote_average"]), 1) if m.get("vote_average") is not None else None,
            "runtime":      m.get("runtime") or None,
            "audience_count": m.get("audience_count") or None,
            "certification": m.get("certification", ""),
            "certification_country": m.get("certification_country", ""),
            "overview":     m.get("overview", ""),
            "recommendation_role": m.get("recommendation_role", ""),
            "recommendation_reason": m.get("recommendation_reason", ""),
            "poster_url":   poster_url(m.get("poster_path")),
            "tmdb_id":      m.get("tmdb_id", ""),
        }
        for m in movies
    ]
