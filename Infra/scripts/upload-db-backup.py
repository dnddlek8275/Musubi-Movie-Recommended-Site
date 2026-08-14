#!/usr/bin/env python3
import argparse
import os
from pathlib import Path

import boto3


def required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"missing required environment variable: {name}")
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("backup", type=Path)
    parser.add_argument("checksum", type=Path)
    args = parser.parse_args()

    bucket = required("OBJECT_STORAGE_BUCKET")
    prefix = os.environ.get("OBJECT_STORAGE_PREFIX", "backups/postgresql").strip("/")
    client = boto3.client(
        "s3",
        endpoint_url=required("OBJECT_STORAGE_ENDPOINT"),
        region_name=required("OBJECT_STORAGE_REGION"),
        aws_access_key_id=required("OBJECT_STORAGE_ACCESS_KEY"),
        aws_secret_access_key=required("OBJECT_STORAGE_SECRET_KEY"),
    )

    for path in (args.backup, args.checksum):
        key = f"{prefix}/{path.name}"
        client.upload_file(str(path), bucket, key)
        result = client.head_object(Bucket=bucket, Key=key)
        if result.get("ContentLength") != path.stat().st_size:
            raise SystemExit(f"uploaded size mismatch: s3://{bucket}/{key}")
        print(f"uploaded=s3://{bucket}/{key} bytes={path.stat().st_size}")


if __name__ == "__main__":
    main()
