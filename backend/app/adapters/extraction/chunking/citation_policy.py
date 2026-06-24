"""Resolve citation granularity, including size-based `auto`."""
from __future__ import annotations

from typing import Literal

CitationLevel = Literal["full", "page_only", "off"]

# Above this estimated document size, `auto` degrades to page-only provenance.
AUTO_PAGE_ONLY_THRESHOLD_TOKENS = 6000


def resolve_level(level: str, estimated_tokens: int) -> CitationLevel:
    """Map a requested level (incl. `auto`) to a concrete level.

    `auto` never selects `off`: provenance is only fully dropped on request.
    """
    if level in ("full", "page_only", "off"):
        return level  # type: ignore[return-value]
    if level == "auto":
        return "page_only" if estimated_tokens >= AUTO_PAGE_ONLY_THRESHOLD_TOKENS else "full"
    raise ValueError(f"Unknown citation level: {level!r}")
