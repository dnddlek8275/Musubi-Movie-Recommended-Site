"""Select a checkpoint from frozen real-user evaluation result files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def manual_averages(result: dict) -> tuple[float | None, dict[str, float]]:
    dimensions = result.get("manual_dimensions") or []
    totals = {name: [] for name in dimensions}
    for row in result.get("results") or []:
        scores = row.get("manual_scores")
        if not isinstance(scores, dict):
            continue
        for name in dimensions:
            if scores.get(name) is not None:
                totals[name].append(float(scores[name]))
    averages = {
        name: sum(values) / len(values)
        for name, values in totals.items()
        if values
    }
    if len(averages) != len(dimensions):
        return None, averages
    return sum(averages.values()) / len(averages), averages


def score_candidate(path: Path) -> dict:
    result = json.loads(path.read_text(encoding="utf-8"))
    summary = result.get("summary") or {}
    thresholds = result.get("thresholds") or {}
    manual_average, dimensions = manual_averages(result)
    manual_complete = manual_average is not None
    manual_pass = manual_complete and manual_average >= float(thresholds["manual_average_min"])
    dimensions_pass = manual_complete and all(
        value >= float(thresholds["manual_dimension_min"])
        for value in dimensions.values()
    )
    eligible = bool(summary.get("automatic_gate_passed")) and manual_pass and dimensions_pass
    exact_duplicate_rate = summary.get("exact_duplicate_rate")
    return {
        "checkpoint": path.stem,
        "result_file": str(path),
        "eligible": eligible,
        "automatic_gate_passed": bool(summary.get("automatic_gate_passed")),
        "hard_check_pass_rate": float(summary.get("hard_check_pass_rate") or 0.0),
        "critical_failure_count": int(summary.get("critical_failure_count") or 0),
        "exact_duplicate_rate": float(
            1.0 if exact_duplicate_rate is None else exact_duplicate_rate
        ),
        "manual_average": manual_average,
        "manual_dimensions": dimensions,
    }


def ranking_key(candidate: dict) -> tuple:
    return (
        candidate["eligible"],
        candidate["manual_average"] if candidate["manual_average"] is not None else -1.0,
        candidate["hard_check_pass_rate"],
        -candidate["critical_failure_count"],
        -candidate["exact_duplicate_rate"],
    )


def select(paths: list[Path]) -> dict:
    candidates = [score_candidate(path) for path in paths]
    ranked = sorted(candidates, key=ranking_key, reverse=True)
    selected = ranked[0] if ranked and ranked[0]["eligible"] else None
    return {"selected": selected, "candidates": ranked}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("results", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    decision = select(args.results)
    args.output.write_text(json.dumps(decision, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    return 0 if decision["selected"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
