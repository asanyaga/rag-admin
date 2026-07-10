"""Contracts shared by all custom-pipeline tools.

A PipelineTool reads a PDF and returns CDM Blocks (normalized bboxes) keyed by
the capability that produced them, plus the native records behind them.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

from app.cdm.adapters.custom_pipeline.capabilities import Capability
from app.cdm.models import Block


def clamp01(v: float) -> float:
    """Clamp a coordinate fraction into the [0, 1] range."""
    return max(0.0, min(1.0, v))


class PageMeta(BaseModel):
    """Authoritative page geometry, sourced from the text_extraction tool."""
    index: int
    width: float       # PDF points
    height: float      # PDF points
    unit: str = "points"
    rotation: int = 0  # degrees


class ToolResult(BaseModel):
    """Output of one PipelineTool.run() invocation."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tool_id: str
    blocks_by_capability: Dict[Capability, List[Block]] = {}
    page_meta: Dict[int, PageMeta] = {}
    raw: Any = None
    native_by_block: Dict[str, Any] = {}
    warnings: List[str] = []
    duration_ms: int = 0


@runtime_checkable
class PipelineTool(Protocol):
    tool_id: str
    provides: frozenset[Capability]

    def run(
        self,
        pdf_path: Path,
        *,
        pages: Optional[List[int]] = None,
        page_meta: Optional[Dict[int, PageMeta]] = None,
        emit: frozenset[Capability],
    ) -> ToolResult: ...
