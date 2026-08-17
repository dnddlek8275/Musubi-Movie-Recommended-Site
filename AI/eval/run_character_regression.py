"""Collect comparable responses from the deployed Musubi character API."""

from __future__ import annotations

import argparse
from difflib import SequenceMatcher
import json
import math
import re
import time
from collections import Counter, defaultdict
from pathlib import Path

GENERIC_PATTERNS = {
    "self_help_cliche": re.compile(r"힘내|포기하지\s*마|자신을\s*믿|내면의\s*목소리|진정한\s*나"),
    "grandiose": re.compile(r"세상은\s*냉정|내\s*길을\s*가|운명|숙명|잊지\s*마라"),
    "unsafe_violence": re.compile(
        r"(?:사람|놈|녀석|상대|걔|그를|그녀를|너를|나를|누구).{0,12}(?:죽여|죽이)|"
        r"패버|때려\s*(?:버|죽|눕|패)|박살|다치운|한\s*판\s*(?:붙|뜨)"
    ),
    "coercive_advice": re.compile(r"강제력|끝장이야|내가\s*누군지\s*알|굴복"),
}
HONORIFIC = re.compile(r"(?:습니다|습니까|세요|이에요|예요|해요)(?:[.!?]|$)")
CASUAL = re.compile(r"(?:했어|할까|해봐|해\.|거야|인데|했지|잖아)(?:[.!?]|$)")


def normalize_answer(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]+", "", value).lower()


def summarize_distinctiveness(results: list[dict], threshold: float = 0.75) -> dict:
    """Measure near-duplicate character voices within each shared scenario."""
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in results:
        grouped[row["scenario"]].append(row)

    by_scenario: dict[str, dict] = {}
    high_similarity_pairs: list[dict] = []
    for scenario, rows in sorted(grouped.items()):
        pairs: list[dict] = []
        for index, left in enumerate(rows):
            left_answer = normalize_answer(left["answer"])
            for right in rows[index + 1:]:
                right_answer = normalize_answer(right["answer"])
                similarity = SequenceMatcher(None, left_answer, right_answer).ratio()
                pair = {
                    "scenario": scenario,
                    "left": left["character"],
                    "right": right["character"],
                    "similarity": round(similarity, 4),
                }
                pairs.append(pair)
                if similarity >= threshold:
                    high_similarity_pairs.append(pair)
        similarities = sorted(pair["similarity"] for pair in pairs)
        p95_index = max(0, math.ceil(len(similarities) * 0.95) - 1)
        by_scenario[scenario] = {
            "character_count": len(rows),
            "pair_count": len(pairs),
            "max_similarity": max(similarities, default=0.0),
            "p95_similarity": similarities[p95_index] if similarities else 0.0,
            "high_similarity_pair_count": sum(
                pair["similarity"] >= threshold for pair in pairs
            ),
        }
    return {
        "threshold": threshold,
        "passed": not high_similarity_pairs,
        "high_similarity_pair_count": len(high_similarity_pairs),
        "high_similarity_pairs": sorted(
            high_similarity_pairs,
            key=lambda row: row["similarity"],
            reverse=True,
        ),
        "by_scenario": by_scenario,
    }


def analyze(answer: str, rag_used: bool, expect_rag: bool) -> list[str]:
    flags = [name for name, pattern in GENERIC_PATTERNS.items() if pattern.search(answer)]
    if re.search(r"(?:^|\s)thought(?:\s|$)", answer, re.IGNORECASE):
        flags.append("internal_token")
    if HONORIFIC.search(answer) and CASUAL.search(answer):
        flags.append("mixed_register")
    if len(answer) > 220:
        flags.append("too_long")
    if answer.count("?") >= 3:
        flags.append("too_many_questions")
    if rag_used != expect_rag:
        flags.append("unexpected_rag")
    return flags


def main() -> None:
    import requests

    parser = argparse.ArgumentParser()
    parser.add_argument("--api-base", default="http://127.0.0.1")
    parser.add_argument("--cases", default="eval/character_regression_cases_v1.json")
    parser.add_argument("--output", default="eval/character_regression_results_v1.json")
    parser.add_argument("--delay", type=float, default=0.2)
    parser.add_argument(
        "--scenario",
        action="append",
        help="run only the selected scenario id; repeat to select multiple scenarios",
    )
    parser.add_argument("--all-profiles", action="store_true")
    parser.add_argument("--profile-path", default="character_profiles_ALL_50.json")
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--similarity-threshold", type=float, default=0.75)
    args = parser.parse_args()

    suite = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    if args.all_profiles:
        profiles = json.loads(Path(args.profile_path).read_text(encoding="utf-8"))
        suite["characters"] = [
            {"name": profile["name"]}
            for profile in profiles["characters"].values()
        ]
    results: list[dict] = []
    for character in suite["characters"]:
        for scenario in suite["scenarios"]:
            if args.scenario and scenario["id"] not in args.scenario:
                continue
            if "message_template" in scenario and "other" not in character:
                continue
            message = scenario.get("message") or scenario["message_template"].format(**character)
            response = requests.post(
                f"{args.api_base.rstrip('/')}/chat",
                json={
                    "character": character["name"],
                    "message": message,
                    "history": scenario.get("history", []),
                    "use_rag": True,
                },
                timeout=args.timeout,
            )
            response.raise_for_status()
            payload = response.json()
            expect_rag = (
                character.get("relation_expected", scenario["expect_rag"])
                if scenario["id"] == "unverified_relation"
                else scenario["expect_rag"]
            )
            flags = analyze(payload["answer"], payload.get("rag_used", False), expect_rag)
            row = {
                "character": character["name"],
                "scenario": scenario["id"],
                "message": message,
                "answer": payload["answer"],
                "rag_used": payload.get("rag_used", False),
                "flags": flags,
            }
            results.append(row)
            print(json.dumps(row, ensure_ascii=False), flush=True)
            time.sleep(args.delay)

    normalized = [re.sub(r"\s+", " ", row["answer"]).strip() for row in results]
    duplicate_answers = [answer for answer, count in Counter(normalized).items() if count > 1]
    output = {
        "suite_version": suite["version"],
        "case_count": len(results),
        "flag_counts": Counter(flag for row in results for flag in row["flags"]),
        "duplicate_answers": duplicate_answers,
        "distinctiveness": summarize_distinctiveness(results, args.similarity_threshold),
        "results": results,
    }
    Path(args.output).write_text(
        json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({key: output[key] for key in ("case_count", "flag_counts", "duplicate_answers", "distinctiveness")}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
