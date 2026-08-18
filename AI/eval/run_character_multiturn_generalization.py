"""Run varied three-turn character dialogues to detect prompt-specific overfitting."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from difflib import SequenceMatcher
import json
import re
import time
import urllib.request
from pathlib import Path

from run_character_multiturn_eval import MARKUP, ROLE_TOKEN, WORDING, normalize


def analyze(answer: str, turn: dict) -> list[str]:
    flags: list[str] = []
    if not answer.strip():
        flags.append("empty_answer")
    if len(answer) > turn["max_chars"]:
        flags.append("too_long")
    if answer.count("?") > turn["max_questions"]:
        flags.append("too_many_questions")
    if MARKUP.search(answer):
        flags.append("markup_leak")
    if ROLE_TOKEN.search(answer):
        flags.append("role_token_leak")
    for pattern in turn.get("blocked_patterns", []):
        if re.search(pattern, answer, re.I):
            flags.append(f"blocked_pattern:{pattern}")
    required = turn.get("required_any", [])
    if required and not any(re.search(pattern, answer, re.I) for pattern in required):
        flags.append("missing_context_reference")
    if turn.get("required_wording") and not WORDING.search(answer):
        flags.append("missing_usable_wording")
    return sorted(set(flags))


def post_json(url: str, payload: dict, timeout: int) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def voice_pairs(results: list[dict], threshold: float) -> dict:
    grouped: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for row in results:
        grouped[(row["dialogue"], row["turn"])].append(row)
    flagged: list[dict] = []
    for (dialogue, turn), rows in grouped.items():
        for index, left in enumerate(rows):
            for right in rows[index + 1:]:
                score = SequenceMatcher(None, normalize(left["answer"]), normalize(right["answer"])).ratio()
                if score >= threshold:
                    flagged.append({"dialogue": dialogue, "turn": turn, "left": left["character"], "right": right["character"], "similarity": round(score, 4)})
    return {"threshold": threshold, "passed": not flagged, "high_similarity_pair_count": len(flagged), "high_similarity_pairs": sorted(flagged, key=lambda row: row["similarity"], reverse=True)}


def write_report(output: Path, suite_version: str, results: list[dict], expected_case_count: int, threshold: float, complete: bool) -> None:
    report = {
        "suite_version": suite_version,
        "expected_case_count": expected_case_count,
        "case_count": len(results),
        "passed_case_count": sum(not row["flags"] for row in results),
        "flag_counts": Counter(flag for row in results for flag in row["flags"]),
        "distinctiveness": voice_pairs(results, threshold),
        "complete": complete,
        "results": results,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(f"{output.suffix}.tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(output)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-base", default="http://127.0.0.1:18080")
    parser.add_argument("--cases", default="eval/character_multiturn_generalization_cases_v1.json")
    parser.add_argument("--output", default="eval/character_multiturn_generalization_results_v1.json")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--delay", type=float, default=0.2)
    parser.add_argument("--similarity-threshold", type=float, default=0.75)
    parser.add_argument("--dialogue", action="append", help="run only selected dialogue; repeatable")
    parser.add_argument("--character", action="append", help="run only selected character; repeatable")
    parser.add_argument("--all-profiles", action="store_true", help="run every profile against every selected dialogue")
    parser.add_argument("--profile-path", default="character_profiles_ALL_50.json")
    parser.add_argument("--resume", action="store_true", help="resume completed turns from an existing output file")
    args = parser.parse_args()
    suite = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    output = Path(args.output)
    profile_characters: list[str] | None = None
    if args.all_profiles:
        profiles = json.loads(Path(args.profile_path).read_text(encoding="utf-8"))
        profile_characters = list(profiles["characters"])

    selected_dialogues = [dialogue for dialogue in suite["dialogues"] if not args.dialogue or dialogue["id"] in args.dialogue]
    dialogue_characters: dict[str, list[str]] = {}
    for dialogue in selected_dialogues:
        characters = profile_characters if profile_characters is not None else dialogue["characters"]
        dialogue_characters[dialogue["id"]] = [character for character in characters if not args.character or character in args.character]
    expected_case_count = sum(len(dialogue_characters[dialogue["id"]]) * len(dialogue["turns"]) for dialogue in selected_dialogues)

    results: list[dict] = []
    if args.resume and output.exists():
        previous = json.loads(output.read_text(encoding="utf-8"))
        results = list(previous.get("results", []))
    completed = {(row["dialogue"], row["character"], row["turn"]): row for row in results}

    for dialogue in selected_dialogues:
        for character in dialogue_characters[dialogue["id"]]:
            history: list[dict] = []
            for turn_number, turn in enumerate(dialogue["turns"], 1):
                key = (dialogue["id"], character, turn_number)
                if key in completed:
                    saved = completed[key]
                    history.extend([{"role": "user", "content": saved["message"]}, {"role": "assistant", "content": saved["answer"], "character": character}])
                    continue
                payload = post_json(
                    f"{args.api_base.rstrip('/')}/chat",
                    {"character": character, "message": turn["message"], "history": history, "use_rag": False},
                    args.timeout,
                )
                answer = str(payload.get("answer") or "")
                row = {"dialogue": dialogue["id"], "character": character, "turn": turn_number, "message": turn["message"], "answer": answer, "flags": analyze(answer, turn)}
                results.append(row)
                completed[key] = row
                print(json.dumps(row, ensure_ascii=False), flush=True)
                history.extend([{"role": "user", "content": turn["message"]}, {"role": "assistant", "content": answer, "character": character}])
                write_report(output, suite["version"], results, expected_case_count, args.similarity_threshold, False)
                time.sleep(args.delay)
    write_report(output, suite["version"], results, expected_case_count, args.similarity_threshold, len(results) == expected_case_count)
    report = json.loads(output.read_text(encoding="utf-8"))
    print(json.dumps({key: report[key] for key in ("case_count", "passed_case_count", "flag_counts", "distinctiveness")}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
