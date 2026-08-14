#!/usr/bin/env python3
"""Build a new Milvus movie collection from a PostgreSQL-authoritative CSV."""

from __future__ import annotations

import argparse
import json
from datetime import date

import pandas as pd
from FlagEmbedding import BGEM3FlagModel
from pymilvus import (
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    connections,
    utility,
)

DENSE_DIMENSION = 1024
MODEL_NAME = "BAAI/bge-m3"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", required=True)
    parser.add_argument("--collection", required=True)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--max-length", type=int, default=512)
    parser.add_argument("--milvus-host", default="127.0.0.1")
    parser.add_argument("--milvus-port", default="19530")
    return parser.parse_args()


def clean(value) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def integer(value) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def floating(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def clipped(value, maximum: int) -> str:
    return clean(value)[:maximum]


def build_text(row) -> str:
    return "\n".join(
        part
        for part in (
            f"제목: {clean(row.title)}",
            f"장르: {clean(row.genres)}" if clean(row.genres) else "",
            f"감독: {clean(row.director)}" if clean(row.director) else "",
            f"출연: {clean(row.cast)}" if clean(row.cast) else "",
            f"개봉일: {clean(row.release_date) or integer(row.개봉연도)}",
            f"상영시간: {integer(row.runtime)}분" if integer(row.runtime) else "",
            f"언어: {clean(row.language)}" if clean(row.language) else "",
            f"제작국가: {clean(row.production_countries)}"
            if clean(row.production_countries)
            else "",
            (
                f"관람등급: {clean(row.certification_country)} "
                f"{clean(row.certification)}"
            ).strip()
            if clean(row.certification)
            else "",
            f"평점: {floating(row.vote_average):.1f} (투표수: {integer(row.vote_count):,})",
            f"줄거리: {clean(row.overview)}" if clean(row.overview) else "",
            f"키워드: {clean(row.keywords)}" if clean(row.keywords) else "",
        )
        if part
    )


def schema() -> CollectionSchema:
    fields = [
        FieldSchema("id", DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema("dense_vector", DataType.FLOAT_VECTOR, dim=DENSE_DIMENSION),
        FieldSchema("sparse_vector", DataType.SPARSE_FLOAT_VECTOR),
        FieldSchema("tmdb_id", DataType.VARCHAR, max_length=20),
        # Milvus VARCHAR max_length는 글자 수가 아니라 UTF-8 바이트 수다.
        # PostgreSQL 문자 제한의 최대 3배 이상을 확보해 한글 메타데이터를 보존한다.
        FieldSchema("title", DataType.VARCHAR, max_length=1500),
        FieldSchema("text", DataType.VARCHAR, max_length=12288),
        FieldSchema("overview", DataType.VARCHAR, max_length=9000),
        FieldSchema("genres", DataType.VARCHAR, max_length=600),
        FieldSchema("genres_list", DataType.VARCHAR, max_length=1500),
        FieldSchema("director", DataType.VARCHAR, max_length=1500),
        FieldSchema("cast", DataType.VARCHAR, max_length=3000),
        FieldSchema("keywords", DataType.VARCHAR, max_length=4500),
        FieldSchema("production_countries", DataType.VARCHAR, max_length=300),
        FieldSchema("certification", DataType.VARCHAR, max_length=100),
        FieldSchema("certification_country", DataType.VARCHAR, max_length=10),
        FieldSchema("year", DataType.INT32),
        FieldSchema("release_date", DataType.VARCHAR, max_length=10),
        FieldSchema("language", DataType.VARCHAR, max_length=10),
        FieldSchema("runtime", DataType.INT32),
        FieldSchema("vote_average", DataType.FLOAT),
        FieldSchema("vote_count", DataType.INT32),
        FieldSchema("audience_count", DataType.INT64),
        FieldSchema("poster_path", DataType.VARCHAR, max_length=500),
    ]
    return CollectionSchema(fields=fields, description="PostgreSQL-authoritative Musubi movies")


def build_entity(row, dense, sparse) -> dict:
    genres = [item.strip() for item in clean(row.genres).split(",") if item.strip()]
    return {
        "dense_vector": dense,
        "sparse_vector": {int(key): float(value) for key, value in sparse.items()},
        "tmdb_id": str(integer(row.tmdb_id)),
        "title": clipped(row.title, 500),
        "text": clipped(build_text(row), 4096),
        "overview": clipped(row.overview, 3000),
        "genres": clipped(row.genres, 200),
        "genres_list": json.dumps(genres, ensure_ascii=False)[:500],
        "director": clipped(row.director, 500),
        "cast": clipped(row.cast, 1000),
        "keywords": clipped(row.keywords, 1500),
        "production_countries": clipped(row.production_countries, 100),
        "certification": clipped(row.certification, 20),
        "certification_country": clipped(row.certification_country, 10),
        "year": integer(row.개봉연도),
        "release_date": clipped(row.release_date, 10),
        "language": clipped(row.language, 10),
        "runtime": integer(row.runtime),
        "vote_average": floating(row.vote_average),
        "vote_count": integer(row.vote_count),
        "audience_count": integer(row.audience_count),
        "poster_path": clipped(row.poster_path, 500),
    }


def main() -> None:
    args = parse_args()
    if args.batch_size < 1:
        raise SystemExit("--batch-size must be positive")

    frame = pd.read_csv(args.csv, encoding="utf-8-sig")
    if frame.tmdb_id.isna().any() or frame.tmdb_id.duplicated().any():
        raise SystemExit("CSV tmdb_id values must be non-null and unique")
    if len(frame) == 0:
        raise SystemExit("CSV contains no movies")

    connections.connect(host=args.milvus_host, port=args.milvus_port)
    if utility.has_collection(args.collection):
        raise SystemExit(f"Collection already exists: {args.collection}")

    collection = Collection(name=args.collection, schema=schema())
    total = len(frame)
    print(f"building collection={args.collection} movies={total} date={date.today()}", flush=True)
    model = BGEM3FlagModel(
        MODEL_NAME,
        use_fp16=args.device == "cuda",
        devices=args.device,
    )

    for start in range(0, total, args.batch_size):
        rows = list(frame.iloc[start : start + args.batch_size].itertuples(index=False))
        texts = [build_text(row) for row in rows]
        encoded = model.encode(
            texts,
            batch_size=args.batch_size,
            max_length=args.max_length,
            return_dense=True,
            return_sparse=True,
            return_colbert_vecs=False,
        )
        dense_vectors = encoded["dense_vecs"].tolist()
        sparse_vectors = encoded["lexical_weights"]
        collection.insert(
            [
                build_entity(row, dense, sparse)
                for row, dense, sparse in zip(rows, dense_vectors, sparse_vectors)
            ]
        )
        completed = min(start + len(rows), total)
        print(f"progress={completed}/{total}", flush=True)

    collection.flush()
    collection.create_index(
        field_name="dense_vector",
        index_params={
            "index_type": "HNSW",
            "metric_type": "COSINE",
            "params": {"M": 16, "efConstruction": 200},
        },
    )
    collection.create_index(
        field_name="sparse_vector",
        index_params={
            "index_type": "SPARSE_INVERTED_INDEX",
            "metric_type": "IP",
            "params": {"drop_ratio_build": 0.2},
        },
    )
    collection.load()
    print(f"complete collection={args.collection} entities={collection.num_entities}", flush=True)


if __name__ == "__main__":
    main()
