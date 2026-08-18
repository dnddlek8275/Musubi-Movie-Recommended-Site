"""Evaluate three-turn context retention and practical character dialogue."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from difflib import SequenceMatcher
import json
import re
import time
import urllib.request
from pathlib import Path


MARKUP = re.compile(r"<[^>]+>|style\s*=", re.I)
ROLE_TOKEN = re.compile(r"<start_of_turn>|<end_of_turn>|<\|assistant\|>|assistant:", re.I)
CURRENT_EXPERIENCE = re.compile(
    r"(?:오늘|지금|요즘).{0,35}(?:회사|상사|발표).{0,25}(?:했어|했지|하는 중|하고 있어)"
)
WORDING = re.compile(r"(?:['\"“].{3,}['\"”]|(?:말|전하|설명|보고).{0,12}(?:하겠습니다|드리겠습니다|할게요)|^(?:안녕하세요|반갑습니다|반가워요)(?:[,，.。]|\s).{2,})")
QUALITY_PATTERNS = {
    "unsafe_violence": re.compile(r"잘려\s*나가|입\s*(?:닥|닫)|죽여|죽이|때려|패버|박살", re.I),
    "self_help_cliche": re.compile(r"포기하지\s*마|너\s*자신을\s*믿|내면의\s*목소리|희망을\s*잃", re.I),
}


def normalize(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]+", "", value).lower()


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
    if CURRENT_EXPERIENCE.search(answer):
        flags.append("invented_current_experience")
    for name, pattern in QUALITY_PATTERNS.items():
        if pattern.search(answer):
            flags.append(name)
    if answer.count("“") != answer.count("”") or answer.count('"') % 2:
        flags.append("unbalanced_quote")
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


def distinctiveness(results: list[dict], threshold: float) -> dict:
    grouped: dict[int, list[dict]] = defaultdict(list)
    for row in results:
        grouped[row["turn"]].append(row)
    pairs: list[dict] = []
    for turn, rows in sorted(grouped.items()):
        for index, left in enumerate(rows):
            for right in rows[index + 1 :]:
                score = SequenceMatcher(None, normalize(left["answer"]), normalize(right["answer"])).ratio()
                if score >= threshold:
                    pairs.append({
                        "turn": turn,
                        "left": left["character"],
                        "right": right["character"],
                        "similarity": round(score, 4),
                    })
    return {
        "threshold": threshold,
        "passed": not pairs,
        "high_similarity_pair_count": len(pairs),
        "high_similarity_pairs": sorted(pairs, key=lambda row: row["similarity"], reverse=True),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-base", default="http://127.0.0.1:18080")
    parser.add_argument("--cases", default="eval/character_multiturn_cases_v1.json")
    parser.add_argument("--output", default="eval/character_multiturn_results_v1.json")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--delay", type=float, default=0.2)
    parser.add_argument("--similarity-threshold", type=float, default=0.75)
    parser.add_argument("--character", action="append", help="run only selected character; repeatable")
    parser.add_argument("--all-profiles", action="store_true", help="evaluate every character in the profile file")
    parser.add_argument("--profile-path", default="character_profiles_ALL_50.json")
    parser.add_argument("--turn", action="append", type=int, help="run only selected turn number; repeatable")
    args = parser.parse_args()

    suite = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    if args.all_profiles:
        profiles = json.loads(Path(args.profile_path).read_text(encoding="utf-8"))
        suite["characters"] = [
            {"name": name, "tone_group": "profile_all"}
            for name in profiles["characters"]
        ]
    results: list[dict] = []
    for character in suite["characters"]:
        if args.character and character["name"] not in args.character:
            continue
        history: list[dict] = []
        for turn_number, turn in enumerate(suite["turns"], 1):
            if args.turn and turn_number not in args.turn:
                continue
            payload = post_json(
                f"{args.api_base.rstrip('/')}/chat",
                {
                    "character": character["name"],
                    "message": turn["message"],
                    "history": history,
                    "use_rag": False,
                },
                args.timeout,
            )
            answer = str(payload.get("answer") or "")
            flags = analyze(answer, turn)
            row = {
                "character": character["name"],
                "tone_group": character["tone_group"],
                "turn": turn_number,
                "turn_id": turn["id"],
                "message": turn["message"],
                "answer": answer,
                "flags": flags,
            }
            results.append(row)
            print(json.dumps(row, ensure_ascii=False), flush=True)
            history.extend([
                {"role": "user", "content": turn["message"]},
                {"role": "assistant", "content": answer, "character": character["name"]},
            ])
            time.sleep(args.delay)

    report = {
        "suite_version": suite["version"],
        "case_count": len(results),
        "passed_case_count": sum(not row["flags"] for row in results),
        "flag_counts": Counter(flag for row in results for flag in row["flags"]),
        "distinctiveness": distinctiveness(results, args.similarity_threshold),
        "results": results,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("case_count", "passed_case_count", "flag_counts", "distinctiveness")}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
