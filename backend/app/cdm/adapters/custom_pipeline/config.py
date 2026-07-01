"""Configs for the local pipeline tools and the pipeline itself."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel

from app.cdm.adapters.local_pipeline.tools.base import LocalTool, PageMeta


class FitzConfig(BaseModel):
    min_chars_threshold: int = 10
    include_images: bool = True
    span_detail: bool = False


class CamelotConfig(BaseModel):
    flavor: Literal["lattice", "stream"] = "lattice"
    edge_tol: int = 50
    row_tol: int = 2
    copy_text: List[str] = []


class FitzTablesConfig(BaseModel):
    vertical_strategy: str = "lines_strict"
    horizontal_strategy: str = "lines_strict"
    snap_tolerance: float = 3.0
    snap_x_tolerance: Optional[float] = None
    snap_y_tolerance: Optional[float] = None
    join_tolerance: float = 3.0
    join_x_tolerance: Optional[float] = None
    join_y_tolerance: Optional[float] = None
    edge_min_length: float = 3.0
    min_words_vertical: int = 3
    min_words_horizontal: int = 1
    intersection_tolerance: float = 3.0
    intersection_x_tolerance: Optional[float] = None
    intersection_y_tolerance: Optional[float] = None
    text_tolerance: float = 3.0
    text_x_tolerance: Optional[float] = None
    text_y_tolerance: Optional[float] = None


TABLE_TOOL_IDS: frozenset[str] = frozenset({"camelot", "fitz_tables"})

TOOL_REGISTRY: Dict[str, type[BaseModel]] = {
    "fitz": FitzConfig,
    "camelot": CamelotConfig,
    "fitz_tables": FitzTablesConfig,
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
    from app.cdm.adapters.local_pipeline.tools.camelot_tool import CamelotTool
    from app.cdm.adapters.local_pipeline.tools.fitz_tables_tool import FitzTablesTool
    from app.cdm.adapters.local_pipeline.tools.fitz_tool import FitzTool

    tools_cfg = config.get("tools", [])

    table_ids_present = [
        e.get("tool_id") for e in tools_cfg
        if e.get("tool_id") in TABLE_TOOL_IDS
    ]
    if len(table_ids_present) > 1:
        raise ValueError(
            f"only one table tool allowed per pipeline, got: {table_ids_present}"
        )

    tools: List[LocalTool] = []
    for entry in tools_cfg:
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
        elif tool_id == "fitz_tables":
            tools.append(FitzTablesTool(config=tool_cfg, page_meta=page_meta or {}))  # type: ignore[arg-type]

    threshold = config.get("eviction_overlap_threshold", 0.5)
    return LocalPipelineConfig(tools=tools, eviction_overlap_threshold=threshold)
