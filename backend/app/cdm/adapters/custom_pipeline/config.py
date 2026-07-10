"""Configs for the custom pipeline tools and the pipeline itself.

The pipeline is a set of capability slots, each filled by at most one named
tool instance. One instance runs once, however many slots reference it, and is
told which capabilities to `emit` (masking).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Literal, Optional, Set

from pydantic import BaseModel

from app.cdm.adapters.custom_pipeline.capabilities import BLOCK_PRODUCING, Capability
from app.cdm.adapters.custom_pipeline.page_flags import PageFlagsConfig
from app.cdm.adapters.custom_pipeline.tools.base import PipelineTool


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


@dataclass(frozen=True)
class ToolSpec:
    config_cls: type[BaseModel]
    provides: frozenset[Capability]
    factory: Callable[[Any], PipelineTool]


def _tool_registry() -> Dict[str, ToolSpec]:
    from app.cdm.adapters.custom_pipeline.tools.camelot_tool import CamelotTool
    from app.cdm.adapters.custom_pipeline.tools.fitz_tables_tool import FitzTablesTool
    from app.cdm.adapters.custom_pipeline.tools.fitz_tool import FitzTool

    return {
        "fitz": ToolSpec(FitzConfig, FitzTool.provides,
                         lambda c: FitzTool(config=c)),
        "camelot": ToolSpec(CamelotConfig, CamelotTool.provides,
                            lambda c: CamelotTool(config=c)),
        "fitz_tables": ToolSpec(FitzTablesConfig, FitzTablesTool.provides,
                                lambda c: FitzTablesTool(config=c)),
    }


@dataclass(frozen=True)
class ResolvedInstance:
    key: str
    tool: PipelineTool
    emit: frozenset[Capability]


@dataclass(frozen=True)
class ResolvedPipeline:
    instances: List[ResolvedInstance]
    page_flags: PageFlagsConfig
    eviction_overlap_threshold: float
    ocr_eviction_threshold: float

    def for_capability(self, cap: Capability) -> Optional[ResolvedInstance]:
        return next((i for i in self.instances if cap in i.emit), None)


def build_pipeline_config(config: Dict[str, Any]) -> ResolvedPipeline:
    registry = _tool_registry()
    tools_cfg: Dict[str, Any] = config.get("tools", {}) or {}
    caps_cfg: Dict[str, str] = config.get("capabilities", {}) or {}

    # capability key -> Capability, validating the enum
    slots: Dict[Capability, str] = {}
    for raw_cap, instance_key in caps_cfg.items():
        try:
            cap = Capability(raw_cap)
        except ValueError:
            raise ValueError(f"unknown capability: {raw_cap!r}")
        if cap not in BLOCK_PRODUCING:
            raise ValueError(f"no tool provides staging capability {cap.value!r}")
        slots[cap] = instance_key

    if Capability.TEXT_EXTRACTION not in slots:
        raise ValueError("capability 'text_extraction' is required")

    # instance key -> assigned capabilities (this is the masking set)
    assigned: Dict[str, Set[Capability]] = {}
    for cap, key in slots.items():
        if key not in tools_cfg:
            raise ValueError(
                f"capability {cap.value!r} references unknown instance {key!r}"
            )
        assigned.setdefault(key, set()).add(cap)

    instances: List[ResolvedInstance] = []
    for key in sorted(assigned):  # deterministic order
        entry = tools_cfg[key]
        tool_id = entry.get("tool")
        spec = registry.get(tool_id)
        if spec is None:
            raise ValueError(f"unknown tool: {tool_id!r}")
        emit = frozenset(assigned[key])
        if not emit <= spec.provides:
            missing = {c.value for c in emit - spec.provides}
            raise ValueError(f"tool {tool_id!r} does not provide {missing}")
        tool_cfg = spec.config_cls.model_validate(entry.get("config", {}) or {})
        instances.append(
            ResolvedInstance(key=key, tool=spec.factory(tool_cfg), emit=emit)
        )

    return ResolvedPipeline(
        instances=instances,
        page_flags=PageFlagsConfig.model_validate(config.get("page_flags", {}) or {}),
        eviction_overlap_threshold=config.get("eviction_overlap_threshold", 0.5),
        ocr_eviction_threshold=config.get("ocr_eviction_threshold", 0.3),
    )
