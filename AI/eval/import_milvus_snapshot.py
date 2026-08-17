"""Restore an evaluation snapshot into a Milvus Lite database."""

from __future__ import annotations

import argparse
import gzip
import pickle

from pymilvus import DataType, MilvusClient


def create_collection(client: MilvusClient, name: str, description: dict) -> None:
    if client.has_collection(name):
        client.drop_collection(name)
    schema = client.create_schema(auto_id=True, enable_dynamic_field=False)
    for field in description["fields"]:
        params = dict(field.get("params") or {})
        schema.add_field(
            field["name"],
            DataType(field["type"]),
            is_primary=bool(field.get("is_primary")),
            auto_id=bool(field.get("auto_id")),
            **params,
        )
    indexes = client.prepare_index_params()
    indexes.add_index("dense_vector", metric_type="COSINE", index_type="FLAT")
    indexes.add_index("sparse_vector", metric_type="IP", index_type="SPARSE_INVERTED_INDEX")
    client.create_collection(name, schema=schema, index_params=indexes)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True)
    parser.add_argument("--input", required=True)
    args = parser.parse_args()

    client = MilvusClient(uri=args.database)
    with gzip.open(args.input, "rb") as stream:
        header = pickle.load(stream)
        if header.get("version") != 1:
            raise RuntimeError(f"unsupported snapshot: {header}")
        for expected_name in header["collections"]:
            metadata = pickle.load(stream)
            name = metadata["collection"]
            if name != expected_name:
                raise RuntimeError(f"collection order mismatch: {name} != {expected_name}")
            create_collection(client, name, metadata["description"])
            count = 0
            while True:
                batch = pickle.load(stream)
                if batch is None:
                    break
                for row in batch:
                    row.pop("id", None)
                client.insert(name, batch)
                count += len(batch)
                print(f"{name}: {count}", flush=True)
            client.flush(name)
            print(name, client.get_collection_stats(name), flush=True)


if __name__ == "__main__":
    main()
