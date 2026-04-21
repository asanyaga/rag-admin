"""Canonical Document Model types — core content representation.

All models are frozen Pydantic v2 BaseModels. Mutations return new instances
via `model_copy(update=...)`.
"""
from __future__ import annotations

from enum import Enum
from typing import List, Optional, Tuple

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


class Quality(_Frozen):
    confidence: Optional[float] = None
    low_confidence_spans: List[Tuple[int, int]] = []
    notes: Optional[str] = None


class Style(_Frozen):
    font_name: Optional[str] = None
    font_size: Optional[float] = None
    bold: Optional[bool] = None
    italic: Optional[bool] = None


class Span(_Frozen):
    text: str
    bbox: Optional[BBox] = None
    style: Optional[Style] = None


class Cell(_Frozen):
    row: int
    col: int
    rowspan: int = 1
    colspan: int = 1
    text: str
    bbox: Optional[BBox] = None
    quality: Optional[Quality] = None
    is_header: bool = False


class Table(_Frozen):
    rows: int
    cols: int
    cells: List[Cell]
    html: Optional[str] = None
    markdown: Optional[str] = None
    caption: Optional[str] = None
