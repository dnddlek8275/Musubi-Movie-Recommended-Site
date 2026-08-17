"""Choose the cheapest safe movie reranking path for a parsed request."""

from __future__ import annotations

from typing import Literal


RerankMode = Literal["skip", "standard", "complex"]


def choose_rerank_mode(
    *,
    has_metadata_filter: bool,
    quality_priority: str | None,
    has_topic: bool,
    has_personalization: bool,
) -> RerankMode:
    """Return a conservative reranking mode from already verified request signals.

    Metadata filters are hard constraints backed by Milvus fields, so an additional
    semantic CrossEncoder pass adds GPU cost without improving constraint matching.
    Mood, free-form topic, and personalized requests still need semantic comparison.
    Unknown free-form requests use the current standard path rather than guessing a
    confidence threshold that has not yet been calibrated from evaluation data.
    """
    if has_topic or quality_priority == "mood" or has_personalization:
        return "complex"
    if has_metadata_filter:
        return "skip"
    return "standard"
