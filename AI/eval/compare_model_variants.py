"""Compare BF16/Q8/Q4 result files using quality metrics only."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from eval.select_checkpoint import manual_averages


def load_variant(spec: str) -> dict:
    if "=" not in spec:
        raise ValueError("variant must use NAME=RESULT_JSON")
    name, raw_path = spec.split("=", 1)
    path = Path(raw_path)
    result = json.loads(path.read_text(encoding="utf-8"))
    ids = [row.get("id") for row in result.get("results") or []]
    manual_average, dimensions = manual_averages(result)
    summary = result.get("summary") or {}
    duplicate_rate = summary.get("exact_duplicate_rate")
    return {
        "name": name,
        "path": str(path),
        "suite_version": result.get("suite_version"),
        "case_ids": ids,
        "hard_check_pass_rate": float(summary.get("hard_check_pass_rate") or 0.0),
        "critical_failure_count": int(summary.get("critical_failure_count") or 0),
        "exact_duplicate_rate": float(1.0 if duplicate_rate is None else duplicate_rate),
        "automatic_gate_passed": bool(summary.get("automatic_gate_passed")),
        "manual_average": manual_average,
        "manual_dimensions": dimensions,
    }


def compare(specs: list[str], reference: str) -> dict:
    variants = [load_variant(spec) for spec in specs]
    versions = {variant["suite_version"] for variant in variants}
    case_sets = {tuple(variant["case_ids"]) for variant in variants}
    if len(versions) != 1 or len(case_sets) != 1:
        raise ValueError("all variants must use the same suite version and ordered case ids")
    by_name = {variant["name"]: variant for variant in variants}
    if reference not in by_name:
        raise ValueError(f"missing reference variant: {reference}")
    baseline = by_name[reference]
    rows = []
    for variant in variants:
        manual_delta = None
        if baseline["manual_average"] is not None and variant["manual_average"] is not None:
            manual_delta = round(variant["manual_average"] - baseline["manual_average"], 4)
        rows.append({
            **{key: value for key, value in variant.items() if key not in {"case_ids"}},
            "hard_pass_delta": round(variant["hard_check_pass_rate"] - baseline["hard_check_pass_rate"], 4),
            "manual_average_delta": manual_delta,
        })
    return {
        "reference": reference,
        "suite_version": next(iter(versions)),
        "case_count": len(next(iter(case_sets))),
        "quality_only": True,
        "variants": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("variants", nargs="+", help="NAME=RESULT_JSON")
    parser.add_argument("--reference", default="bf16")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = compare(args.variants, args.reference)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
