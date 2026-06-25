"""Configs for the local pipeline tools and the pipeline itself.

The per-tool configs are Pydantic models (serializable → ParseRun.config).
LocalPipelineConfig is a runtime object holding instantiated tools; it is NOT
persisted — the runner persists the raw config dict it received.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel

from app.cdm.adapters.local_pipeline.tools.base import LocalTool, PageMeta


class FitzConfig(BaseModel):
    min_chars_threshold: int = 10   # pages below → emit warning
    include_images: bool = True      # emit FIGURE blocks for image blocks
    span_detail: bool = False        # store full span list in parser_extras


class CamelotConfig(BaseModel):
    flavor: Literal["lattice", "stream"] = "lattice"
    edge_tol: int = 50
    row_tol: int = 2
    copy_text: List[str] = []


# tool_id -> the Pydantic config class that validates its per-tool config dict.
TOOL_REGISTRY: Dict[str, type[BaseModel]] = {
    "fitz": FitzConfig,
    "camelot": CamelotConfig,
}


@dataclass
class LocalPipelineConfig:
    """Runtime pipeline config — ordered tools (later = higher priority)."""
    tools: List[LocalTool]
    eviction_overlap_threshold: float = 0.5


def build_pipeline_config(
    config: Dict[str, Any],
    page_meta: Optional[Dict[int, PageMeta]] = None,
) -> LocalPipelineConfig:
    """Build a runtime LocalPipelineConfig from a serialized config dict.

    `page_meta` is passed to CamelotTool for bbox y-flip (the runner supplies
    FitzTool's page_meta after FitzTool completes; for fitz-only configs it is
    unused).
    """
    # Imported here to avoid a circular import (tools import nothing from config).
    from app.cdm.adapters.local_pipeline.tools.camelot_tool import CamelotTool
    from app.cdm.adapters.local_pipeline.tools.fitz_tool import FitzTool

    tools: List[LocalTool] = []
    for entry in config.get("tools", []):
        tool_id = entry.get("tool_id")
        raw_cfg = entry.get("config", {}) or {}
        cfg_cls = TOOL_REGISTRY.get(tool_id)
        if cfg_cls is None:
            raise ValueError(f"unknown tool: {tool_id!r}")
        tool_cfg = cfg_cls.model_validate(raw_cfg)
        if tool_id == "fitz":
            tools.append(FitzTool(config=tool_cfg))  # type: ignore[arg-type]
        elif tool_id == "camelot":
            tools.append(CamelotTool(config=tool_cfg, page_meta=page_meta or {}))  # type: ignore[arg-type]

    threshold = config.get("eviction_overlap_threshold", 0.5)
    return LocalPipelineConfig(tools=tools, eviction_overlap_threshold=threshold)
