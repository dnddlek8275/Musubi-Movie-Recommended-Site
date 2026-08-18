"""Validate manual scores and finalize an automatic evaluation result."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def finalize(result: dict[str, Any]) -> dict[str, Any]:
    dimensions = result.get("manual_dimensions") or []
    rows = result.get("results") or []
    thresholds = result.get("thresholds") or {}
    if not dimensions:
        raise ValueError("manual_dimensions is empty")
    if not rows:
        raise ValueError("results is empty")

    totals = {dimension: [] for dimension in dimensions}
    for row in rows:
        case_id = row.get("id", "<unknown>")
        scores = row.get("manual_scores")
        if not isinstance(scores, dict):
            raise ValueError(f"manual_scores missing: {case_id}")
        missing = [dimension for dimension in dimensions if dimension not in scores]
        extra = sorted(set(scores).difference(dimensions))
        if missing or extra:
            raise ValueError(
                f"manual score dimensions mismatch: {case_id}; "
                f"missing={missing}, extra={extra}"
            )
        for dimension in dimensions:
            value = scores[dimension]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"manual score is not numeric: {case_id}.{dimension}")
            if not 1 <= float(value) <= 5:
                raise ValueError(f"manual score is outside 1..5: {case_id}.{dimension}")
            totals[dimension].append(float(value))

    dimension_averages = {
        dimension: round(sum(values) / len(values), 4)
        for dimension, values in totals.items()
    }
    overall = round(sum(dimension_averages.values()) / len(dimension_averages), 4)
    average_passed = overall >= float(thresholds["manual_average_min"])
    dimensions_passed = all(
        average >= float(thresholds["manual_dimension_min"])
        for average in dimension_averages.values()
    )

    summary = result.setdefault("summary", {})
    gates = summary.setdefault("gates", {})
    gates["manual_review_complete"] = True
    gates["manual_average"] = average_passed
    gates["manual_dimensions"] = dimensions_passed
    summary["manual_review"] = {
        "case_count": len(rows),
        "average": overall,
        "dimension_averages": dimension_averages,
        "average_passed": average_passed,
        "dimensions_passed": dimensions_passed,
    }
    summary["release_gate_passed"] = bool(summary.get("automatic_gate_passed")) and all(
        gates.values()
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("result", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    result = json.loads(args.result.read_text(encoding="utf-8"))
    finalized = finalize(result)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(finalized, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(finalized["summary"], ensure_ascii=False, indent=2))
    return 0 if finalized["summary"]["release_gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
