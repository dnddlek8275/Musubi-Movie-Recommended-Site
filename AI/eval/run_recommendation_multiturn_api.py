"""Run chained recommendation scenarios through the real /chat/auto boundary."""

from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path

from eval.run_movie_followup_regression import evaluate


def post(url: str, payload: dict, timeout: int) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:18080")
    parser.add_argument("--cases", default="eval/recommendation_multiturn_cases_v1.json")
    parser.add_argument("--output", default="eval/recommendation_multiturn_api_results.json")
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()

    suite = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    rows = []
    for scenario in suite["scenarios"]:
        history: list[dict] = []
        previous_titles: set[str] = set()
        for number, turn in enumerate(scenario["turns"], start=1):
            response = post(
                f"{args.base_url.rstrip('/')}/chat/auto",
                {"message": turn["message"], "history": history},
                args.timeout,
            )
            checks = dict(turn.get("checks") or {})
            if turn.get("exclude_previous_turn"):
                checks["excluded_titles"] = sorted(previous_titles)
            failures = evaluate(checks, response)
            movies = response.get("movies") or []
            titles = [str(movie.get("title") or "") for movie in movies]
            row = {
                "scenario": scenario["id"], "turn": number,
                "message": turn["message"], "intent": response.get("intent"),
                "titles": titles, "answer": response.get("answer"),
                "movies": movies,
                "failures": failures, "passed": not failures,
            }
            rows.append(row)
            print(json.dumps({k: row[k] for k in ("scenario", "turn", "titles", "failures", "passed")}, ensure_ascii=False), flush=True)
            history.extend([
                {"role": "user", "content": turn["message"]},
                {"role": "assistant", "content": str(response.get("answer") or ""), "recommended_movies": movies},
            ])
            previous_titles = set(titles)

    summary = {"turns": len(rows), "passed": sum(row["passed"] for row in rows)}
    Path(args.output).write_text(json.dumps({"summary": summary, "results": rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if summary["turns"] == summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
