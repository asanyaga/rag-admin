from __future__ import annotations
from typing import List, Literal
from pydantic import BaseModel, Field

ALL_SIGNALS = [
    "text_layer", "font_health", "copy_restricted",
    "coverage", "dpi", "text_overlap", "table_grid", "edge_density",
]


class Thresholds(BaseModel):
    min_text_chars: int = 10
    cid_ratio: float = 0.3
    edge_density_min: float = 0.15   # >= is text-like
    coverage_min: float = 0.10       # image must cover >= 10% of page to matter
    table_line_min: int = 3
    overlap_covered: float = 0.6     # >= means text already sits over the image


class ProbeConfig(BaseModel):
    enabled_signals: List[str] = Field(default_factory=lambda: list(ALL_SIGNALS))
    thresholds: Thresholds = Field(default_factory=Thresholds)
    backend: Literal["fitz"] = "fitz"


DEFAULT_CONFIG = ProbeConfig()
