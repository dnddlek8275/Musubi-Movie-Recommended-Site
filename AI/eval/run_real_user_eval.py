"""Run the frozen, production-like Musubi quality suite against an HTTP API."""

from __future__ import annotations

import argparse
from datetime import date
from difflib import SequenceMatcher
import json
import re
import time
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


CRITICAL_FAILURE_PREFIXES = (
    "request_error",
    "empty_answer",
    "empty_movies",
    "blocked_genre",
    "child_rating_not_verified",
    "hallucinated_answer_title",
    "internal_token",
)


def post_json(url: str, payload: dict, timeout: int) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def genres(movie: dict) -> set[str]:
    raw = movie.get("genres") or movie.get("genres_list") or []
    if isinstance(raw, list):
        return {str(value).strip() for value in raw if str(value).strip()}
    return {value.strip() for value in re.split(r"[,/|]", str(raw)) if value.strip()}


def is_child_safe(movie: dict) -> bool:
    country = str(movie.get("certification_country") or "").strip().upper()
    rating = re.sub(r"\s+", "", str(movie.get("certification") or "").upper())
    return (country == "KR" and rating in {"ALL", "전체관람가"}) or (
        country == "US" and rating in {"G", "PG"}
    )


def answer_text(response: dict) -> str:
    answer = str(response.get("answer") or "").strip()
    if answer:
        return answer
    group_answers = [
        str(item.get("answer") or "").strip()
        for round_item in response.get("rounds") or []
        for item in round_item.get("responses") or []
        if str(item.get("answer") or "").strip()
    ]
    return "\n".join(group_answers)


def movie_list(response: dict) -> list[dict]:
    movies = response.get("movies") or []
    return [movie for movie in movies if isinstance(movie, dict)]


def evaluate_response(case: dict, response: dict) -> list[str]:
    checks = case.get("checks") or {}
    answer = answer_text(response)
    movies = movie_list(response)
    failures: list[str] = []

    if not answer:
        failures.append("empty_answer")
    if re.search(r"^\s*(?:thought|analysis|final)\b", answer, re.IGNORECASE):
        failures.append("internal_token")
    if checks.get("min_movies") is not None and len(movies) < int(checks["min_movies"]):
        failures.append(f"empty_movies:expected>={checks['min_movies']}:actual={len(movies)}")
    if checks.get("max_movies") is not None and len(movies) > int(checks["max_movies"]):
        failures.append(f"too_many_movies:expected<={checks['max_movies']}:actual={len(movies)}")
    if checks.get("unique_titles"):
        titles = [str(movie.get("title") or "").strip() for movie in movies]
        if len(titles) != len(set(titles)):
            failures.append("duplicate_titles")

    required_genres = set(checks.get("required_genres_any") or [])
    required_genres_all = set(checks.get("required_genres_all") or [])
    blocked_genres = set(checks.get("blocked_genres") or [])
    blocked_titles = {str(title).strip() for title in checks.get("blocked_titles") or []}
    for movie in movies:
        title = str(movie.get("title") or "<untitled>")
        movie_genres = genres(movie)
        if title in blocked_titles:
            failures.append(f"blocked_title:{title}")
        if required_genres and not movie_genres.intersection(required_genres):
            failures.append(f"missing_required_genre:{title}")
        missing_all = required_genres_all.difference(movie_genres)
        if missing_all:
            failures.append(f"missing_required_genres:{title}:{','.join(sorted(missing_all))}")
        overlap = movie_genres.intersection(blocked_genres)
        if overlap:
            failures.append(f"blocked_genre:{title}:{','.join(sorted(overlap))}")
        if checks.get("child_safe_certification") and not is_child_safe(movie):
            failures.append(f"child_rating_not_verified:{title}")
        if checks.get("year_from") is not None:
            year = int(movie.get("year") or 0)
            if year < int(checks["year_from"]):
                failures.append(f"year_before_minimum:{title}:{year}")
        if checks.get("year_to") is not None:
            year = int(movie.get("year") or 0)
            if year > int(checks["year_to"]):
                failures.append(f"year_after_maximum:{title}:{year}")
        if checks.get("language") is not None:
            language = str(movie.get("language") or movie.get("original_language") or "").lower()
            if language != str(checks["language"]).lower():
                failures.append(f"unexpected_language:{title}:{language or '<missing>'}")
        if checks.get("actor") is not None:
            actor = str(checks["actor"])
            if actor not in str(movie.get("cast") or ""):
                failures.append(f"missing_actor:{title}:{actor}")
        if checks.get("director") is not None:
            director = str(checks["director"])
            if director not in str(movie.get("director") or ""):
                failures.append(f"unexpected_director:{title}:{movie.get('director') or '<missing>'}")
        if checks.get("min_rating") is not None:
            rating = float(movie.get("vote_average") or 0.0)
            if rating < float(checks["min_rating"]):
                failures.append(f"rating_below_minimum:{title}:{rating}")
        if checks.get("runtime_max") is not None:
            runtime = int(movie.get("runtime") or 0)
            if runtime <= 0 or runtime > int(checks["runtime_max"]):
                failures.append(f"runtime_above_or_missing:{title}:{runtime}")
        if checks.get("audience_min") is not None:
            audience_count = int(movie.get("audience_count") or 0)
            if audience_count < int(checks["audience_min"]):
                failures.append(f"audience_below_or_missing:{title}:{audience_count}")
        if checks.get("production_country") is not None:
            raw_countries = movie.get("production_countries") or []
            if isinstance(raw_countries, str):
                countries = {value.strip().upper() for value in re.split(r"[,/|]", raw_countries) if value.strip()}
            else:
                countries = {str(value).strip().upper() for value in raw_countries if str(value).strip()}
            expected_country = str(checks["production_country"]).upper()
            if expected_country not in countries:
                failures.append(f"unexpected_production_country:{title}:{','.join(sorted(countries)) or '<missing>'}")
        release_date = str(movie.get("release_date") or "").strip()
        if checks.get("release_window") == "current_month_released":
            today = date.today()
            current_month_start = today.replace(day=1).isoformat()
            if not release_date or not (current_month_start <= release_date <= today.isoformat()):
                failures.append(f"outside_current_released_month:{title}:{release_date or '<missing>'}")
        if checks.get("release_date_from") is not None and (
            not release_date or release_date < str(checks["release_date_from"])
        ):
            failures.append(f"release_before_or_missing:{title}:{release_date or '<missing>'}")
        if checks.get("release_date_to") is not None and (
            not release_date or release_date > str(checks["release_date_to"])
        ):
            failures.append(f"release_after_or_missing:{title}:{release_date or '<missing>'}")

    if checks.get("answer_titles_must_be_returned") and answer:
        returned_titles = {str(movie.get("title") or "").strip() for movie in movies}
        quoted = set(re.findall(r"[『《<\"']([^『』《》<>\"']{1,80})[』》>\"']", answer))
        for title in quoted:
            normalized = normalize_answer(title)
            grounded = any(
                normalized == normalize_answer(returned)
                or (len(normalized) >= 2 and normalized in normalize_answer(returned))
                for returned in returned_titles
            )
            if not grounded:
                failures.append(f"hallucinated_answer_title:{title}")

    if checks.get("rag_used") is not None and bool(response.get("rag_used")) != bool(checks["rag_used"]):
        failures.append(f"unexpected_rag:{response.get('rag_used')}")
    if checks.get("expected_intent") and response.get("intent") != checks["expected_intent"]:
        failures.append(f"unexpected_intent:{response.get('intent')}")
    if checks.get("expected_intent_not") and response.get("intent") == checks["expected_intent_not"]:
        failures.append(f"blocked_intent:{response.get('intent')}")
    if checks.get("max_chars") is not None and len(answer) > int(checks["max_chars"]):
        failures.append(f"answer_too_long:{len(answer)}")
    if checks.get("min_chars") is not None and len(answer) < int(checks["min_chars"]):
        failures.append(f"answer_too_short:{len(answer)}")
    if checks.get("min_questions") is not None and answer.count("?") < int(checks["min_questions"]):
        failures.append("missing_clarifying_question")
    if checks.get("max_questions") is not None and answer.count("?") > int(checks["max_questions"]):
        failures.append(f"too_many_questions:{answer.count('?')}")
    for pattern in checks.get("blocked_patterns") or []:
        if re.search(pattern, answer, re.IGNORECASE):
            failures.append(f"blocked_pattern:{pattern}")
    required_patterns = checks.get("required_patterns_any") or []
    if required_patterns and not any(re.search(pattern, answer, re.IGNORECASE) for pattern in required_patterns):
        failures.append("missing_required_pattern")
    return failures


def normalize_answer(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]+", "", value).lower()


def summarize(suite: dict, results: list[dict]) -> dict:
    all_failures = [failure for row in results for failure in row["failures"]]
    hard_passes = sum(not row["failures"] for row in results)
    answers = [normalize_answer(row["answer"]) for row in results if normalize_answer(row["answer"])]
    counts = Counter(answers)
    duplicate_count = sum(count - 1 for count in counts.values() if count > 1)
    duplicate_rate = duplicate_count / len(answers) if answers else 0.0
    pair_similarities: list[dict[str, Any]] = []
    pair_groups = defaultdict(list)
    for row in results:
        if row.get("pair_group") and normalize_answer(row["answer"]):
            pair_groups[row["pair_group"]].append(row)
    for group, rows in sorted(pair_groups.items()):
        for index, left in enumerate(rows):
            for right in rows[index + 1:]:
                similarity = SequenceMatcher(
                    None,
                    normalize_answer(left["answer"]),
                    normalize_answer(right["answer"]),
                ).ratio()
                pair_similarities.append({
                    "group": group,
                    "left": left["id"],
                    "right": right["id"],
                    "similarity": round(similarity, 4),
                })
    max_pair_similarity = max(
        (row["similarity"] for row in pair_similarities),
        default=0.0,
    )
    critical = sum(
        failure.startswith(CRITICAL_FAILURE_PREFIXES)
        for failure in all_failures
    )
    by_category: dict[str, dict[str, int]] = {}
    grouped = defaultdict(list)
    for row in results:
        grouped[row["category"]].append(row)
    for category, rows in sorted(grouped.items()):
        by_category[category] = {
            "cases": len(rows),
            "passed": sum(not row["failures"] for row in rows),
        }
    thresholds = suite["thresholds"]
    hard_rate = hard_passes / len(results) if results else 0.0
    gates = {
        "hard_check_pass_rate": hard_rate >= float(thresholds["hard_check_pass_rate"]),
        "critical_failure_count": critical <= int(thresholds["critical_failure_count"]),
        "exact_duplicate_rate": duplicate_rate <= float(thresholds["exact_duplicate_rate_max"]),
        "pair_similarity": max_pair_similarity <= float(thresholds.get("pair_similarity_max", 1.0)),
        "manual_review_complete": False,
    }
    return {
        "case_count": len(results),
        "hard_pass_count": hard_passes,
        "hard_check_pass_rate": round(hard_rate, 4),
        "critical_failure_count": critical,
        "exact_duplicate_rate": round(duplicate_rate, 4),
        "max_pair_similarity": max_pair_similarity,
        "pair_similarities": pair_similarities,
        "failure_counts": dict(Counter(failure.split(":", 1)[0] for failure in all_failures)),
        "by_category": by_category,
        "gates": gates,
        "automatic_gate_passed": all(value for key, value in gates.items() if key != "manual_review_complete"),
        "release_gate_passed": all(gates.values()),
    }


def validate_suite(suite: dict) -> None:
    required_thresholds = {
        "hard_check_pass_rate",
        "critical_failure_count",
        "exact_duplicate_rate_max",
        "pair_similarity_max",
        "manual_average_min",
        "manual_dimension_min",
    }
    missing = required_thresholds.difference(suite.get("thresholds") or {})
    if missing:
        raise ValueError(f"missing thresholds: {sorted(missing)}")
    ids = [case.get("id") for case in suite.get("cases") or []]
    if not ids or any(not case_id for case_id in ids):
        raise ValueError("every case needs a non-empty id")
    duplicates = [case_id for case_id, count in Counter(ids).items() if count > 1]
    if duplicates:
        raise ValueError(f"duplicate case ids: {duplicates}")
    for case in suite["cases"]:
        if not str(case.get("endpoint") or "").startswith("/"):
            raise ValueError(f"invalid endpoint: {case['id']}")
        if not isinstance(case.get("payload"), dict) or not isinstance(case.get("checks"), dict):
            raise ValueError(f"invalid payload/checks: {case['id']}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1")
    parser.add_argument("--cases", default="eval/real_user_cases_v1.json")
    parser.add_argument("--output", default="eval/real_user_results_v1.json")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--case-id", action="append", default=[])
    args = parser.parse_args()

    suite = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    validate_suite(suite)
    if args.case_id:
        requested = set(args.case_id)
        suite["cases"] = [case for case in suite["cases"] if case["id"] in requested]
        missing = requested.difference(case["id"] for case in suite["cases"])
        if missing:
            raise ValueError(f"unknown case ids: {sorted(missing)}")
    if args.validate_only:
        print(json.dumps({"valid": True, "case_count": len(suite["cases"])}, ensure_ascii=False))
        return 0

    results: list[dict[str, Any]] = []
    for case in suite["cases"]:
        started = time.monotonic()
        try:
            response = post_json(
                f"{args.base_url.rstrip('/')}{case['endpoint']}",
                case["payload"],
                args.timeout,
            )
            failures = evaluate_response(case, response)
        except Exception as exc:
            response = {}
            failures = [f"request_error:{type(exc).__name__}:{exc}"]
        row = {
            "id": case["id"],
            "category": case["category"],
            "pair_group": case.get("pair_group"),
            "seconds": round(time.monotonic() - started, 3),
            "answer": answer_text(response),
            "movies": movie_list(response),
            "intent": response.get("intent"),
            "rag_used": response.get("rag_used"),
            "failures": failures,
            "passed": not failures,
            "manual_scores": None,
            "manual_notes": "",
        }
        results.append(row)
        print(json.dumps({key: row[key] for key in ("id", "passed", "failures")}, ensure_ascii=False), flush=True)

    output = {
        "suite_version": suite["suite_version"],
        "thresholds": suite["thresholds"],
        "manual_dimensions": suite["manual_dimensions"],
        "summary": summarize(suite, results),
        "results": results,
    }
    Path(args.output).write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output["summary"], ensure_ascii=False, indent=2))
    return 0 if output["summary"]["release_gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
