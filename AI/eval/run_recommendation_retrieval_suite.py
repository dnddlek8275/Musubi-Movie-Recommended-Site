"""Evaluate frozen recommendation cases at the retrieval/presentation boundary."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pipeline.query_rewriter import rewrite
from pipeline.recommendation_context import build_recommendation_context
from pipeline.recommendation_presenter import filter_movies_by_requested_genre, prepare_recommendations
from rag.movie_retriever import MovieFilter, retrieve


def _genres(movie: dict) -> set[str]:
    return {value.strip() for value in str(movie.get("genres") or "").split(",") if value.strip()}


def _child_safe(movie: dict) -> bool:
    country = str(movie.get("certification_country") or "").strip().upper()
    rating = "".join(str(movie.get("certification") or "").upper().split())
    return (country == "KR" and rating in {"ALL", "전체관람가"}) or (
        country == "US" and rating in {"G", "PG"}
    )


def _failures(checks: dict, movies: list[dict]) -> list[str]:
    failures: list[str] = []
    if len(movies) < int(checks.get("min_movies", 0)):
        failures.append(f"min_movies:{len(movies)}")
    titles = [str(movie.get("title") or "") for movie in movies]
    if checks.get("unique_titles") and len(titles) != len(set(titles)):
        failures.append("duplicate_titles")
    required = set(checks.get("required_genres_any") or [])
    required_all = set(checks.get("required_genres_all") or [])
    blocked = set(checks.get("blocked_genres") or [])
    for movie in movies:
        title = str(movie.get("title") or "")
        genres = _genres(movie)
        if required and not genres.intersection(required):
            failures.append(f"missing_required_genre:{title}")
        if required_all and not required_all.issubset(genres):
            failures.append(f"missing_required_genres:{title}")
        if genres.intersection(blocked):
            failures.append(f"blocked_genre:{title}")
        if checks.get("child_safe_certification") and not _child_safe(movie):
            failures.append(f"child_rating_not_verified:{title}")
        if checks.get("year_from") is not None and int(movie.get("year") or 0) < int(checks["year_from"]):
            failures.append(f"year_before_minimum:{title}")
        if checks.get("year_to") is not None and int(movie.get("year") or 0) > int(checks["year_to"]):
            failures.append(f"year_after_maximum:{title}")
        if checks.get("language") and str(movie.get("language") or "") != str(checks["language"]):
            failures.append(f"language_mismatch:{title}")
        if checks.get("min_rating") is not None and float(movie.get("vote_average") or 0) < float(checks["min_rating"]):
            failures.append(f"rating_below_minimum:{title}")
        if checks.get("overview_required") and not str(movie.get("overview") or "").strip():
            failures.append(f"missing_overview:{title}")
    return failures


def retrieve_case(message: str, top_k: int = 3, history: list[dict] | None = None) -> list[dict]:
    context = build_recommendation_context(message, history or [])
    rewritten = rewrite(context.search_message)
    required_genres = [
        genre for genre in rewritten.get("required_genres") or []
        if genre not in context.excluded_genres
    ]
    rewritten["required_genres"] = required_genres
    if rewritten.get("genre") in context.excluded_genres:
        rewritten["genre"] = required_genres[0] if required_genres else None
    filters = MovieFilter(
        genre=rewritten.get("genre"), actor=rewritten.get("actor"),
        director=rewritten.get("director"), language=rewritten.get("language"),
        year_from=rewritten.get("year_from"), year_to=rewritten.get("year_to"),
        min_rating=rewritten.get("min_rating"), exclude_genres=context.excluded_genres,
        required_genres=rewritten.get("required_genres") or [],
    )
    quality_weight = {"generic": 0.70, "mood": 0.55}.get(rewritten.get("quality_priority"), 0.30)
    movies = retrieve(
        rewritten.get("search_query") or message,
        top_k=top_k * 3,
        movie_filter=filters,
        sort_latest=bool(rewritten.get("sort_latest")),
        required_count=top_k,
        quality_weight=quality_weight,
        topic=rewritten.get("topic"),
        exclude_titles=set(context.excluded_titles),
    )
    for genre in rewritten.get("required_genres") or [rewritten.get("genre")]:
        movies = filter_movies_by_requested_genre(movies, genre)
    return prepare_recommendations(movies, context.search_message, rewritten, limit=top_k)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", default="eval/real_user_cases_v1.json")
    parser.add_argument("--output", default="eval/recommendation_retrieval_results.json")
    args = parser.parse_args()
    suite = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    cases = [case for case in suite["cases"] if case.get("category") == "recommendation"]
    results = []
    for case in cases:
        movies = retrieve_case(case["payload"]["message"])
        failures = _failures(case.get("checks") or {}, movies)
        row = {
            "id": case["id"],
            "titles": [movie.get("title") for movie in movies],
            "movies": [
                {
                    field: movie.get(field)
                    for field in (
                        "title", "genres", "overview", "vote_average", "vote_count",
                        "audience_count", "year", "release_date", "language",
                        "certification", "certification_country",
                    )
                }
                for movie in movies
            ],
            "failures": failures,
            "passed": not failures,
        }
        results.append(row)
        print(json.dumps(
            {key: row[key] for key in ("id", "titles", "failures", "passed")},
            ensure_ascii=False,
        ), flush=True)
    summary = {"cases": len(results), "passed": sum(row["passed"] for row in results)}
    payload = {"summary": summary, "results": results}
    Path(args.output).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if summary["passed"] == summary["cases"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
