"""Minimal OpenAI-compatible endpoint for isolated candidate evaluation."""

from __future__ import annotations

import argparse
import time
from threading import Lock

import torch
import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict
from unsloth import FastLanguageModel


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="allow")
    model: str = "candidate"
    messages: list[dict]
    max_tokens: int = 512
    temperature: float = 0.7
    top_p: float = 0.9
    top_k: int = 40
    repeat_penalty: float = 1.0
    stop: list[str] | str | None = None


def build_app(adapter: str) -> FastAPI:
    model, processor = FastLanguageModel.from_pretrained(
        model_name=adapter,
        max_seq_length=2048,
        dtype=None,
        load_in_4bit=True,
    )
    FastLanguageModel.for_inference(model)
    tokenizer = getattr(processor, "tokenizer", processor)
    lock = Lock()
    app = FastAPI()

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "model": adapter}

    @app.post("/v1/chat/completions")
    def chat(request: ChatRequest) -> dict:
        prompt = tokenizer.apply_chat_template(
            request.messages, tokenize=False, add_generation_prompt=True
        )
        inputs = tokenizer(prompt, return_tensors="pt").to("cuda")
        do_sample = request.temperature > 0
        generation = {
            "max_new_tokens": request.max_tokens,
            "do_sample": do_sample,
            "repetition_penalty": request.repeat_penalty,
            "pad_token_id": tokenizer.eos_token_id,
        }
        if do_sample:
            generation.update(
                temperature=request.temperature,
                top_p=request.top_p,
                top_k=request.top_k,
            )
        with lock, torch.inference_mode():
            output = model.generate(**inputs, **generation)
        generated = output[0][inputs["input_ids"].shape[1]:]
        content = tokenizer.decode(generated, skip_special_tokens=True).strip()
        stops = [request.stop] if isinstance(request.stop, str) else (request.stop or [])
        for marker in stops:
            content = content.split(marker, 1)[0].rstrip()
        return {
            "id": f"candidate-{time.time_ns()}",
            "object": "chat.completion",
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }],
        }

    return app


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--adapter", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8081)
    args = parser.parse_args()
    uvicorn.run(build_app(args.adapter), host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
