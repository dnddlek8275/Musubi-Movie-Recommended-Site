"""Audit and filter multi-turn samples for real context dependence."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

try:
    from train.prepare_splits import jaccard, ngrams, normalize, user_text
except ModuleNotFoundError:  # Support: python3 train/filter_multiturn.py
    from prepare_splits import jaccard, ngrams, normalize, user_text


FOLLOWUP_PATTERN = re.compile(
    r"그럼|그러면|그래서|아까|방금|그거|그게|그때|앞에서|말한|그 사람|그 친구|"
    r"그 영화|그 작품|첫 번째|두 번째|대신|말고|더|다른|왜 그렇게|어떻게 답"
)


def audit_record(record: dict, standalone_prompts: set[str]) -> list[str]:
    turns = record.get("conversations") or []
    failures: list[str] = []
    if len(turns) < 4 or len(turns) % 2:
        return ["invalid_turn_count"]
    expected = ["user", "assistant"] * (len(turns) // 2)
    if [turn.get("role") for turn in turns] != expected:
        failures.append("invalid_role_order")

    for index in range(2, len(turns), 2):
        current_user = str(turns[index].get("content") or "")
        previous_answer = str(turns[index - 1].get("content") or "")
        normalized = normalize(current_user)
        has_reference = bool(FOLLOWUP_PATTERN.search(current_user))
        lexical_link = jaccard(ngrams(current_user), ngrams(previous_answer)) >= 0.10
        if not has_reference and not lexical_link:
            failures.append(f"context_independence:turn_{index + 1}")
        if normalized in standalone_prompts and not has_reference:
            failures.append(f"standalone_prompt_reused:turn_{index + 1}")
    return failures


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--standalone", type=Path, required=True)
    parser.add_argument("--multiturn", type=Path, required=True)
    parser.add_argument("--accepted", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    standalone = read_jsonl(args.standalone)
    standalone_prompts = {normalize(user_text(record)) for record in standalone if normalize(user_text(record))}
    candidates = read_jsonl(args.multiturn)
    accepted = []
    rejected = []
    for line_number, record in enumerate(candidates, 1):
        failures = audit_record(record, standalone_prompts)
        if failures:
            rejected.append({"line": line_number, "failures": failures})
        else:
            accepted.append(record)

    args.accepted.parent.mkdir(parents=True, exist_ok=True)
    args.accepted.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in accepted)
        + ("\n" if accepted else ""),
        encoding="utf-8",
    )
    failure_counts = Counter(failure.split(":", 1)[0] for row in rejected for failure in row["failures"])
    report = {
        "candidate_count": len(candidates),
        "accepted_count": len(accepted),
        "rejected_count": len(rejected),
        "acceptance_rate": round(len(accepted) / len(candidates), 4) if candidates else 0.0,
        "failure_counts": dict(failure_counts),
        "rejected": rejected,
    }
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "rejected"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
