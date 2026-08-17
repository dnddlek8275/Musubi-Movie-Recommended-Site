"""Evaluate chained recommendation refinements without deploying the API."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from eval.run_recommendation_retrieval_suite import _failures, retrieve_case
from pipeline.intent import Intent, classify
from pipeline.recommendation_context import build_recommendation_context


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", default="eval/recommendation_multiturn_cases_v1.json")
    parser.add_argument("--output", default="eval/recommendation_multiturn_results.json")
    args = parser.parse_args()

    suite = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    rows = []
    for scenario in suite["scenarios"]:
        history: list[dict] = []
        seen_titles: set[str] = set()
        for turn_number, turn in enumerate(scenario["turns"], start=1):
            message = turn["message"]
            context = build_recommendation_context(message, history)
            intent = classify(message, history=history)
            movies = retrieve_case(message, top_k=int(turn.get("top_k", 3)), history=history)
            failures = _failures(turn.get("checks") or {}, movies)
            if intent != Intent.MOVIE_RECOMMEND:
                failures.append(f"wrong_intent:{intent}")
            if turn.get("expect_followup") is not None and context.is_followup != turn["expect_followup"]:
                failures.append(f"followup_mismatch:{context.is_followup}")
            search_message = context.search_message
            for term in turn.get("required_context_terms") or []:
                if term not in search_message:
                    failures.append(f"missing_context_term:{term}")
            previous_only = set(turn.get("excluded_titles") or [])
            if turn.get("exclude_previous_turn"):
                previous_only.update(
                    str(movie.get("title") or "")
                    for movie in (history[-1].get("recommended_movies") if history and history[-1].get("role") == "assistant" else [])
                )
            for movie in movies:
                title = str(movie.get("title") or "")
                if title in previous_only:
                    failures.append(f"previous_title_repeated:{title}")
                overview = str(movie.get("overview") or "")
                for pattern in turn.get("blocked_overview_patterns") or []:
                    if re.search(pattern, overview):
                        failures.append(f"blocked_overview:{title}:{pattern}")

            titles = [str(movie.get("title") or "") for movie in movies]
            row = {
                "scenario": scenario["id"],
                "turn": turn_number,
                "message": message,
                "search_message": search_message,
                "titles": titles,
                "movies": movies,
                "failures": failures,
                "passed": not failures,
            }
            rows.append(row)
            print(json.dumps({k: row[k] for k in ("scenario", "turn", "titles", "failures", "passed")}, ensure_ascii=False), flush=True)
            history.extend([
                {"role": "user", "content": message},
                {"role": "assistant", "content": " / ".join(titles), "recommended_movies": movies},
            ])
            seen_titles.update(titles)

    summary = {"turns": len(rows), "passed": sum(row["passed"] for row in rows)}
    Path(args.output).write_text(
        json.dumps({"summary": summary, "results": rows}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if summary["turns"] == summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
