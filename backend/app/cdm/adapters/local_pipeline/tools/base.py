"""Contracts shared by all local parsing tools.

A LocalTool reads a PDF and returns CDM Blocks (with normalized bboxes) plus
the native records that produced them, for the audit trail.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

from app.cdm.models import Block


def clamp01(v: float) -> float:
    """Clamp a coordinate fraction into the [0, 1] range."""
    return max(0.0, min(1.0, v))


class PageMeta(BaseModel):
    """Authoritative page geometry, sourced from FitzTool."""
    index: int
    width: float       # PDF points
    height: float      # PDF points
    unit: str = "points"
    rotation: int = 0  # degrees


class ToolResult(BaseModel):
    """Output of one LocalTool.run() invocation."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tool_id: str
    blocks: List[Block]
    page_meta: Dict[int, PageMeta]          # keyed by 0-based page index
    raw: Any = None                          # serializable native dump
    native_by_block: Dict[str, Any] = {}     # provisional block id -> native record
    warnings: List[str] = []
    duration_ms: int = 0


@runtime_checkable
class LocalTool(Protocol):
    tool_id: str

    def run(self, pdf_path: Path, pages: Optional[List[int]] = None) -> ToolResult: ...
