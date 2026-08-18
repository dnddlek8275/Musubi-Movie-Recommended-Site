"""Run a second-pass conversation quality probe against the deployed AI API.

This probe complements ``run_conversation_flow_audit.py`` with less scripted,
multi-turn prompts modeled after messages a user may actually send. It calls
the AI API directly and does not create Backend chat rooms or DB records.
"""

from __future__ import annotations

import argparse
import json
import re
import urllib.request
from collections import Counter
from pathlib import Path


ROLE_LEAK = re.compile(r"<start_of_turn>|<end_of_turn>|<\|assistant\|>|assistant:", re.I)
CLICHE = re.compile(
    r"너\s*자신을\s*믿|포기하지\s*마|희망을\s*잃|내면의\s*목소리|"
    r"과정의\s*일부|모든\s*게\s*끝나는\s*건\s*아니|세상은\s*냉정|"
    r"잘\s*할\s*수\s*있|할\s*수\s*있을\s*거라\s*믿"
)
HUMAN_EXPERIENCE = re.compile(
    r"(?:영화를|작품을).{0,25}(?:봤|보고|느꼈|감동)|"
    r"(?:인상\s*깊|맘에\s*와닿|마음에\s*와닿)"
)


def post(url: str, payload: dict) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.load(response)


def answer_flags(answer: str) -> list[str]:
    flags: list[str] = []
    if not answer.strip():
        flags.append("empty_answer")
    if len(answer) > 360:
        flags.append("too_long")
    if ROLE_LEAK.search(answer):
        flags.append("role_token_leak")
    if CLICHE.search(answer):
        flags.append("self_help_cliche")
    if answer.count("'") % 2 or answer.count("“") != answer.count("”"):
        flags.append("unbalanced_quote")
    return flags


def normalized_answer(answer: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]+", "", answer).casefold()


def add_history(history: list[dict], message: str, payload: dict) -> None:
    history.extend(
        [
            {"role": "user", "content": message},
            {
                "role": "assistant",
                "content": str(payload.get("answer") or ""),
                "character": payload.get("character") or "무무",
                **(
                    {"recommended_movies": payload.get("movies")}
                    if payload.get("movies")
                    else {}
                ),
            },
        ]
    )


def probe_general(base: str, selected: set[str] | None = None) -> list[dict]:
    dialogues = [
        ("work_failure", ["오늘 발표를 완전히 망쳤어", "내일 다시 발표해야 해", "지금 뭘 먼저 준비할까?"]),
        ("truth_boundary", ["너는 실제로 영화를 보고 감동한 적 있어?", "그럼 어떻게 내 취향을 알아?"]),
        ("natural_short", ["아 진짜", "상사가 또 일을 줬어", "하..."]),
    ]
    rows: list[dict] = []
    for dialogue, messages in dialogues:
        if selected and dialogue not in selected:
            continue
        history: list[dict] = []
        for turn, message in enumerate(messages, 1):
            payload = post(f"{base}/chat/auto", {"message": message, "history": history})
            answer = str(payload.get("answer") or "")
            flags = answer_flags(answer)
            if payload.get("intent") == "movie_recommend":
                flags.append("unrequested_movie_recommendation")
            if dialogue == "truth_boundary" and turn == 1 and HUMAN_EXPERIENCE.search(answer):
                flags.append("invented_human_experience")
            row = {
                "stage": "general_v2",
                "dialogue": dialogue,
                "turn": turn,
                "message": message,
                "intent": payload.get("intent"),
                "answer": answer,
                "flags": flags,
            }
            rows.append(row)
            print(json.dumps(row, ensure_ascii=False), flush=True)
            add_history(history, message, payload)
    return rows


def probe_single(base: str, selected: set[str] | None = None) -> list[dict]:
    dialogues = [
        ("maseokdo_opinion", "마석도", ["장첸이 너무 잘생겨 보여. 어떡해?", "그래도 네 생각은 어때?"]),
        ("tony_practical", "토니 스타크", ["오늘 발표를 망쳤어.", "상사한테 뭐라고 말하면 좋을까?"]),
        ("hermione_constraint", "헤르미온느", ["시험 공부가 하나도 안 됐어.", "잔소리 말고 오늘 할 것만 짧게 말해줘."]),
        ("gollum_paraphrase", "골룸", ["프로도를 믿어?", "왜 같이 모르도르로 갔어?"]),
    ]
    rows: list[dict] = []
    for dialogue, character, messages in dialogues:
        if selected and dialogue not in selected:
            continue
        history: list[dict] = []
        previous_answer = ""
        for turn, message in enumerate(messages, 1):
            payload = post(
                f"{base}/chat",
                {"character": character, "message": message, "history": history, "use_rag": True},
            )
            answer = str(payload.get("answer") or "")
            flags = answer_flags(answer)
            if payload.get("character") != character:
                flags.append("identity_bleed")
            if dialogue == "gollum_paraphrase" and not payload.get("rag_used"):
                flags.append("missing_relation_grounding")
            if dialogue == "tony_practical" and turn == 2 and re.search(r"슈트|아이언맨", answer):
                flags.append("irrelevant_roleplay_metaphor")
            if previous_answer and normalized_answer(answer) == normalized_answer(previous_answer):
                flags.append("repeated_previous_answer")
            row = {
                "stage": "single_v2",
                "dialogue": dialogue,
                "turn": turn,
                "message": message,
                "character": payload.get("character"),
                "answer": answer,
                "rag_used": payload.get("rag_used", False),
                "flags": flags,
            }
            rows.append(row)
            print(json.dumps(row, ensure_ascii=False), flush=True)
            history.extend(
                [
                    {"role": "user", "content": message},
                    {"role": "assistant", "content": answer, "character": character},
                ]
            )
            previous_answer = answer
    return rows


def probe_group(base: str, selected: set[str] | None = None) -> list[dict]:
    cases = [
        ("crime_user_opinion", ["마석도", "장첸"], "장첸이 잘생겼다는 말에 둘은 어떻게 생각해?", "character_chat"),
        ("marvel_interview", ["토니 스타크", "피터 파커", "스티브 로저스"], "내일 면접이라 긴장돼. 각자 짧게 한마디만 해줘.", "character_chat"),
        ("crossworld_disagreement", ["엘사", "데드풀"], "친구랑 다퉜는데 먼저 연락할지 고민이야. 둘의 의견이 궁금해.", "character_chat"),
        ("group_movie", ["슈렉", "데드풀"], "둘이 주말 밤에 볼 유쾌한 영화 세 편 골라줘.", "movie_recommend"),
    ]
    rows: list[dict] = []
    for dialogue, characters, message, expected_intent in cases:
        if selected and dialogue not in selected:
            continue
        payload = post(
            f"{base}/chat/group/auto",
            {"characters": characters, "message": message, "history": []},
        )
        responses = [
            response
            for round_item in payload.get("rounds") or []
            for response in round_item.get("responses") or []
        ]
        answers = [str(response.get("answer") or "") for response in responses]
        titles = [str(movie.get("title") or "") for movie in payload.get("movies") or []]
        flags = [flag for answer in answers for flag in answer_flags(answer)]
        if len(answers) != len(set(answers)):
            flags.append("duplicate_group_answer")
        if len(titles) != len(set(titles)):
            flags.append("duplicate_group_movie")
        if any(response.get("character") not in characters for response in responses):
            flags.append("unknown_group_speaker")
        if payload.get("intent") != expected_intent:
            flags.append(f"wrong_intent:{payload.get('intent')}")
        if dialogue == "group_movie" and len(titles) < 3:
            flags.append("missing_group_movies")
        if dialogue == "group_movie" and any(
            not any(title and title in answer for title in titles)
            for answer in answers[1:]
        ):
            flags.append("generic_group_movie_reaction")
        if dialogue == "crossworld_disagreement" and any(
            "확인된 관계" in answer for answer in answers
        ):
            flags.append("ordinary_friend_problem_misclassified")
        if dialogue == "crossworld_disagreement" and any(
            re.search(r"내가\s+[^.!?]{0,30}(?:와|과).{0,20}(?:다퉜|갈등|싸웠)", answer)
            for answer in answers
        ):
            flags.append("invented_character_experience")
        if dialogue == "marvel_interview" and any(
            re.search(r"슈트|거미줄|전투", answer) for answer in answers
        ):
            flags.append("irrelevant_roleplay_metaphor")
        row = {
            "stage": "group_v2",
            "dialogue": dialogue,
            "message": message,
            "intent": payload.get("intent"),
            "movie_titles": titles,
            "responses": responses,
            "flags": sorted(set(flags)),
        }
        rows.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-base", default="http://127.0.0.1")
    parser.add_argument("--output", default="eval/conversation_quality_probe_v2.json")
    parser.add_argument(
        "--dialogue",
        action="append",
        default=[],
        help="Run only the named dialogue; repeat this option to select multiple dialogues.",
    )
    args = parser.parse_args()
    base = args.api_base.rstrip("/")
    selected = set(args.dialogue) or None
    rows: list[dict] = []
    for probe in (probe_general, probe_single, probe_group):
        rows.extend(probe(base, selected))
    report = {
        "case_count": len(rows),
        "stage_counts": Counter(row["stage"] for row in rows),
        "flag_counts": Counter(flag for row in rows for flag in row.get("flags", [])),
        "results": rows,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {key: report[key] for key in ("case_count", "stage_counts", "flag_counts")},
            ensure_ascii=False,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
