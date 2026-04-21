"""Canonical Document Model types — core content representation.

All models are frozen Pydantic v2 BaseModels. Mutations return new instances
via `model_copy(update=...)`.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional, Tuple

from pydantic import BaseModel, ConfigDict


class ParserKind(str, Enum):
    LITEPARSE    = "liteparse"
    UNSTRUCTURED = "unstructured"
    LLAMAPARSE   = "llamaparse"
    LANDING_AI   = "landing_ai"


class BlockRole(str, Enum):
    TITLE      = "title"
    HEADING    = "heading"
    PARAGRAPH  = "paragraph"
    LIST       = "list"
    TABLE      = "table"
    FIGURE     = "figure"
    CAPTION    = "caption"
    HEADER     = "header"
    FOOTER     = "footer"
    MARGINALIA = "marginalia"
    CODE       = "code"
    FORMULA    = "formula"
    LINK       = "link"
    OTHER      = "other"


class CoordSpace(str, Enum):
    NORMALIZED = "normalized"


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class BBox(_Frozen):
    """Normalized bounding box — origin top-left, fractions of page size."""
    x0: float
    y0: float
    x1: float
    y1: float
    space: CoordSpace = CoordSpace.NORMALIZED
    source_space: Optional[str] = None                              # "pdf_points" | "pixels" | "fraction"
    source_coords: Optional[Tuple[float, float, float, float]] = None
