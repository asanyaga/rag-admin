"""Chunking strategy catalogue + factory (mirrors the extractor registry)."""
from __future__ import annotations

from typing import Any

from app.adapters.extraction.chunking.base import ChunkStrategy
from app.adapters.extraction.chunking.token_budget import TokenBudgetPagesStrategy

_DEFAULT_MAX_INPUT_TOKENS = 8000


def get_chunk_strategies() -> list[dict]:
    return [
        {"strategy": "none", "name": "None (single-shot)",
         "description": "Send the whole document in one request.",
         "config_schema": {"type": "object", "properties": {}}},
        {"strategy": "token_budget_pages", "name": "Token-budgeted pages",
         "description": "Pack whole pages until an input-token budget is reached.",
         "config_schema": {
             "type": "object",
             "properties": {
                 "maxInputTokens": {"type": "integer", "default": _DEFAULT_MAX_INPUT_TOKENS},
                 "pageOverlap": {"type": "integer", "default": 0},
                 "dedupeKey": {"type": "string"},
             },
         }},
    ]


def build_strategy(name: str, config: dict[str, Any]) -> ChunkStrategy | None:
    if name == "none":
        return None
    if name == "token_budget_pages":
        return TokenBudgetPagesStrategy(
            max_input_tokens=int(config.get("maxInputTokens", _DEFAULT_MAX_INPUT_TOKENS)),
            page_overlap=int(config.get("pageOverlap", 0)),
        )
    raise ValueError(f"Unknown chunking strategy: {name!r}")
