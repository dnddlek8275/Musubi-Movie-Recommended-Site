"""Run multi-turn movie recommendation checks through the live API."""

from __future__ import annotations

import argparse
import json
import time
import urllib.request
from datetime import date
from pathlib import Path


def post_json(url: str, payload: dict, timeout: int) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def genre_set(movie: dict) -> set[str]:
    return {genre.strip() for genre in str(movie.get("genres") or "").split(",") if genre.strip()}


def evaluate(case: dict, response: dict) -> list[str]:
    failures = []
    movies = response.get("movies") or []
    if response.get("intent") != "movie_recommend":
        failures.append(f"wrong_intent:{response.get('intent')}")
    if not movies:
        return failures + ["empty_result"]

    required = set(case.get("required_genres_any") or [])
    blocked = set(case.get("blocked_genres") or [])
    excluded_titles = set(case.get("excluded_titles") or [])
    expected_roles = ("가장 잘 맞는 선택", "다른 결의 대안", "취향 확장 선택")
    answer = str(response.get("answer") or "")
    reasons = []
    for index, movie in enumerate(movies):
        title = str(movie.get("title") or "")
        genres = genre_set(movie)
        if required and not genres.intersection(required):
            failures.append(f"missing_required_genre:{title}")
        if genres.intersection(blocked):
            failures.append(f"blocked_genre:{title}")
        if title in excluded_titles:
            failures.append(f"previous_title_repeated:{title}")
        if title and title not in answer:
            failures.append(f"answer_missing_title:{title}")
        if index < len(expected_roles) and movie.get("recommendation_role") != expected_roles[index]:
            failures.append(f"wrong_recommendation_role:{title}")
        reason = str(movie.get("recommendation_reason") or "").strip()
        if not reason:
            failures.append(f"missing_recommendation_reason:{title}")
        reasons.append(reason)

    if len(movies) >= 3 and len(set(reasons[:3])) < 2:
        failures.append("recommendation_reasons_not_distinct")

    if case.get("release_date_desc"):
        dates = [str(movie.get("release_date") or "") for movie in movies]
        populated = [value for value in dates if value]
        if populated != sorted(populated, reverse=True):
            failures.append("release_date_not_desc")
        if any(value > date.today().isoformat() for value in populated):
            failures.append("future_release_returned")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1")
    parser.add_argument("--cases", default="eval/movie_followup_cases_v1.json")
    parser.add_argument("--output", default="eval/movie_followup_results_v1.json")
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()

    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    results = []
    for case in cases:
        started = time.monotonic()
        try:
            response = post_json(
                f"{args.base_url.rstrip('/')}/chat/auto",
                {
                    "character": None,
                    "message": case["message"],
                    "history": case.get("history") or [],
                },
                args.timeout,
            )
            movies = response.get("movies") or []
            failures = evaluate(case, response)
        except Exception as exc:
            response = {}
            movies = []
            failures = [f"request_error:{type(exc).__name__}:{exc}"]
        result = {
            "id": case["id"],
            "message": case["message"],
            "seconds": round(time.monotonic() - started, 3),
            "intent": response.get("intent"),
            "titles": [movie.get("title") for movie in movies],
            "failures": failures,
            "passed": not failures,
        }
        results.append(result)
        print(json.dumps(result, ensure_ascii=False), flush=True)

    Path(args.output).write_text(
        json.dumps(results, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return 0 if all(result["passed"] for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
