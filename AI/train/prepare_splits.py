"""Create leakage-resistant train/dev/test JSONL splits.

The source is never modified. Near-duplicate user prompts are grouped before a
deterministic hash split so variants cannot cross split boundaries.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path


def normalize(text: str) -> str:
    value = unicodedata.normalize("NFKC", str(text or "")).lower()
    return re.sub(r"[^0-9a-z가-힣]+", "", value)


def user_text(record: dict) -> str:
    if "input" in record:
        return str(record.get("input") or "")
    for turn in record.get("conversations") or []:
        if turn.get("role") == "user":
            return str(turn.get("content") or "")
    return ""


def assistant_text(record: dict) -> str:
    if "output" in record:
        return str(record.get("output") or "")
    for turn in record.get("conversations") or []:
        if turn.get("role") == "assistant":
            return str(turn.get("content") or "")
    return ""


def ngrams(text: str, size: int = 3) -> set[str]:
    value = normalize(text)
    if len(value) <= size:
        return {value} if value else set()
    return {value[index : index + size] for index in range(len(value) - size + 1)}


def jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def blocking_keys(text: str) -> set[str]:
    grams = sorted(ngrams(text))
    if not grams:
        return {"empty"}
    digest = hashlib.sha256("|".join(grams).encode("utf-8")).hexdigest()
    # Exact gram-set hash plus four stable sampled grams keep candidate search bounded.
    sampled = {grams[index * (len(grams) - 1) // 3] for index in range(4)}
    return {f"h:{digest}"} | {f"g:{gram}" for gram in sampled}


class DisjointSet:
    def __init__(self, size: int):
        self.parent = list(range(size))

    def find(self, value: int) -> int:
        while self.parent[value] != value:
            self.parent[value] = self.parent[self.parent[value]]
            value = self.parent[value]
        return value

    def union(self, left: int, right: int) -> None:
        left_root, right_root = self.find(left), self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root


def duplicate_groups(records: list[dict], threshold: float) -> list[list[int]]:
    groups = DisjointSet(len(records))
    gram_sets = [ngrams(user_text(record)) for record in records]
    buckets: dict[str, list[int]] = defaultdict(list)
    compared: set[tuple[int, int]] = set()
    for index, record in enumerate(records):
        for key in blocking_keys(user_text(record)):
            for other in buckets[key]:
                pair = (other, index)
                if pair in compared:
                    continue
                compared.add(pair)
                if jaccard(gram_sets[other], gram_sets[index]) >= threshold:
                    groups.union(other, index)
            buckets[key].append(index)
    output: dict[int, list[int]] = defaultdict(list)
    for index in range(len(records)):
        output[groups.find(index)].append(index)
    return list(output.values())


def split_name(group_key: str, seed: int, dev_ratio: float, test_ratio: float) -> str:
    digest = hashlib.sha256(f"{seed}:{group_key}".encode("utf-8")).digest()
    value = int.from_bytes(digest[:8], "big") / 2**64
    if value < test_ratio:
        return "test"
    if value < test_ratio + dev_ratio:
        return "dev"
    return "train"


def prepare(records: list[dict], *, seed: int, dev_ratio: float, test_ratio: float, threshold: float) -> tuple[dict[str, list[dict]], dict]:
    valid = [record for record in records if normalize(user_text(record)) and normalize(assistant_text(record))]
    invalid_count = len(records) - len(valid)
    groups = duplicate_groups(valid, threshold)
    splits: dict[str, list[dict]] = {"train": [], "dev": [], "test": []}
    group_counts = Counter()
    for group in groups:
        key = min(normalize(user_text(valid[index])) for index in group)
        target = split_name(key, seed, dev_ratio, test_ratio)
        group_counts[target] += 1
        splits[target].extend(valid[index] for index in group)

    prompt_sets = {
        name: {normalize(user_text(record)) for record in values}
        for name, values in splits.items()
    }
    exact_overlap = {
        "train_dev": len(prompt_sets["train"] & prompt_sets["dev"]),
        "train_test": len(prompt_sets["train"] & prompt_sets["test"]),
        "dev_test": len(prompt_sets["dev"] & prompt_sets["test"]),
    }
    report = {
        "source_records": len(records),
        "valid_records": len(valid),
        "invalid_records_removed": invalid_count,
        "near_duplicate_threshold": threshold,
        "duplicate_groups": len(groups),
        "multi_record_groups": sum(len(group) > 1 for group in groups),
        "records": {name: len(values) for name, values in splits.items()},
        "groups": dict(group_counts),
        "exact_prompt_overlap": exact_overlap,
    }
    return splits, report


def read_jsonl(paths: list[Path]) -> list[dict]:
    records = []
    for path in paths:
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            value = json.loads(line)
            value["_source"] = {"file": path.name, "line": line_number}
            records.append(value)
    return records


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--dev-ratio", type=float, default=0.10)
    parser.add_argument("--test-ratio", type=float, default=0.10)
    parser.add_argument("--near-duplicate-threshold", type=float, default=0.88)
    args = parser.parse_args()
    if args.dev_ratio < 0 or args.test_ratio < 0 or args.dev_ratio + args.test_ratio >= 1:
        raise ValueError("dev/test ratios must be non-negative and sum to less than 1")
    if not 0 < args.near_duplicate_threshold <= 1:
        raise ValueError("near-duplicate threshold must be in (0, 1]")

    records = read_jsonl(args.inputs)
    splits, report = prepare(
        records,
        seed=args.seed,
        dev_ratio=args.dev_ratio,
        test_ratio=args.test_ratio,
        threshold=args.near_duplicate_threshold,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, values in splits.items():
        write_jsonl(args.output_dir / f"{name}.jsonl", values)
    (args.output_dir / "split_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not any(report["exact_prompt_overlap"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
