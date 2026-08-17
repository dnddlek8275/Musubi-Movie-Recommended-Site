"""Gemma chat tokenization with assistant-only supervision."""

from __future__ import annotations


def tokenize_conversation(record: dict, tokenizer, max_length: int) -> dict:
    input_ids: list[int] = []
    labels: list[int] = []
    assistant_tokens = 0
    turns = record.get("conversations") or []
    if not turns and ("input" in record or "output" in record):
        turns = [
            {"role": "user", "content": record.get("input") or ""},
            {"role": "assistant", "content": record.get("output") or ""},
        ]
    for turn in turns:
        role = turn.get("role")
        if role not in {"user", "assistant"}:
            raise ValueError(f"unsupported conversation role: {role}")
        template_role = "model" if role == "assistant" else "user"
        text = f"<start_of_turn>{template_role}\n{turn.get('content', '')}<end_of_turn>\n"
        ids = tokenizer(text, add_special_tokens=False, padding=False)["input_ids"]
        input_ids.extend(ids)
        if role == "assistant":
            labels.extend(ids)
            assistant_tokens += len(ids)
        else:
            labels.extend([-100] * len(ids))

    eos_text = tokenizer.eos_token or "<eos>"
    eos_ids = tokenizer(eos_text, add_special_tokens=False, padding=False)["input_ids"]
    input_ids.extend(eos_ids)
    labels.extend(eos_ids)
    assistant_tokens += len(eos_ids)
    input_ids = input_ids[:max_length]
    labels = labels[:max_length]
    supervised_tokens = sum(label != -100 for label in labels)
    # EOS 하나만 감독하는 빈 대화도 허용하지 않는다.
    if not input_ids or supervised_tokens <= len(eos_ids) or assistant_tokens <= len(eos_ids):
        raise ValueError("conversation has no supervised assistant tokens")
    return {
        "input_ids": input_ids,
        "labels": labels,
        "attention_mask": [1] * len(input_ids),
    }
