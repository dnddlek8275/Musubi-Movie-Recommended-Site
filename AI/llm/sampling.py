"""Task-specific, side-effect-free LLM sampling configuration."""

DEFAULT_PARAMS = {
    "temperature": 0.75,
    "top_p": 0.92,
    "top_k": 50,
    "min_p": 0.05,
    "repeat_penalty": 1.1,
    "stop": ["<turn|>", "<|turn>"],
}

SAMPLING_PROFILES = {
    "character_chat": {
        "temperature": 0.6,
        "top_p": 0.9,
        "top_k": 40,
        "min_p": 0.05,
        "repeat_penalty": 1.1,
    },
    "grounded_recommendation": {
        "temperature": 0.25,
        "top_p": 0.8,
        "top_k": 30,
        "min_p": 0.02,
        "repeat_penalty": 1.1,
    },
    "character_recommendation": {
        "temperature": 0.45,
        "top_p": 0.85,
        "top_k": 40,
        "min_p": 0.03,
        "repeat_penalty": 1.1,
    },
    "structured": {
        "temperature": 0.0,
        "top_p": 1.0,
        "top_k": 1,
        "min_p": 0.0,
        "repeat_penalty": 1.0,
    },
}


def sampling_params(profile: str | None = None, **overrides) -> dict:
    params = dict(DEFAULT_PARAMS)
    if profile is not None:
        if profile not in SAMPLING_PROFILES:
            raise ValueError(f"알 수 없는 sampling profile: {profile}")
        params.update(SAMPLING_PROFILES[profile])
    params.update(overrides)
    return params
