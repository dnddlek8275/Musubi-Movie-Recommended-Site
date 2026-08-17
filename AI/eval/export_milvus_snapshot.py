"""Export selected Milvus collections as a compressed pickle stream."""

from __future__ import annotations

import argparse
import gzip
import pickle

from pymilvus import MilvusClient


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--uri", default="http://127.0.0.1:19530")
    parser.add_argument("--output", required=True)
    parser.add_argument("--batch-size", type=int, default=250)
    parser.add_argument("collections", nargs="+")
    args = parser.parse_args()

    client = MilvusClient(uri=args.uri)
    with gzip.open(args.output, "wb", compresslevel=3) as stream:
        pickle.dump({"version": 1, "collections": args.collections}, stream)
        for name in args.collections:
            description = client.describe_collection(name)
            output_fields = [
                field["name"] for field in description["fields"] if not field.get("is_primary")
            ]
            pickle.dump({"collection": name, "description": description}, stream)
            iterator = client.query_iterator(
                collection_name=name,
                batch_size=args.batch_size,
                filter="",
                output_fields=output_fields,
            )
            count = 0
            while True:
                batch = iterator.next()
                if not batch:
                    break
                pickle.dump(batch, stream)
                count += len(batch)
                print(f"{name}: {count}", flush=True)
            iterator.close()
            pickle.dump(None, stream)


if __name__ == "__main__":
    main()
