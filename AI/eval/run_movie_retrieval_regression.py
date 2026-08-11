"""Run movie recommendation retrieval checks through the live API process."""

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


def child_safe_certification(movie: dict) -> bool:
    country = str(movie.get("certification_country") or "").strip().upper()
    certification = "".join(str(movie.get("certification") or "").upper().split())
    return (
        (country == "US" and certification in {"G", "PG"})
        or (country == "KR" and certification in {"ALL", "전체관람가"})
    )


def evaluate(case: dict, movies: list[dict]) -> list[str]:
    failures = []
    if not movies:
        return ["empty_result"]

    required = set(case.get("required_genres_any") or [])
    blocked = set(case.get("blocked_genres") or [])
    for movie in movies:
        genres = genre_set(movie)
        if required and not genres.intersection(required):
            failures.append(f"missing_required_genre:{movie.get('title')}")
        if genres.intersection(blocked):
            failures.append(f"blocked_genre:{movie.get('title')}")
        if case.get("min_rating") is not None:
            if float(movie.get("vote_average") or 0.0) < float(case["min_rating"]):
                failures.append(f"rating_below_minimum:{movie.get('title')}")
        if case.get("child_safe_certification") and not child_safe_certification(movie):
            failures.append(f"child_rating_not_verified:{movie.get('title')}")

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
    parser.add_argument("--cases", default="eval/movie_retrieval_cases_v1.json")
    parser.add_argument("--output", default="eval/movie_retrieval_results_v1.json")
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()

    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    results = []
    for case in cases:
        started = time.monotonic()
        try:
            response = post_json(
                f"{args.base_url.rstrip('/')}/recommend",
                {"message": case["message"]},
                args.timeout,
            )
            movies = response.get("movies") or []
            failures = evaluate(case, movies)
        except Exception as exc:
            movies = []
            failures = [f"request_error:{type(exc).__name__}:{exc}"]
        result = {
            "id": case["id"],
            "message": case["message"],
            "seconds": round(time.monotonic() - started, 3),
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
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0 if all(result["passed"] for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
