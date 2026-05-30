"""Canonical Document Model types — core content representation.

All models are frozen Pydantic v2 BaseModels. Mutations return new instances
via `model_copy(update=...)`.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Tuple, Union

from pydantic import BaseModel, ConfigDict


class ParserKind(str, Enum):
    SIMPLE       = "simple"      # local text extraction via LlamaIndexExtractor
    LITEPARSE    = "liteparse"   # reserved — LlamaIndex LiteParse cloud product (future)
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


class Block(_Frozen):
    id: str
    role: BlockRole
    native_type: str
    native_label: Optional[str] = None
    text: str = ""
    markdown: Optional[str] = None
    html: Optional[str] = None
    page_index: int
    bbox: Optional[BBox] = None
    reading_order: Optional[int] = None
    depth: Optional[int] = None
    parent_id: Optional[str] = None
    children_ids: List[str] = []
    spans: List[Span] = []
    table: Optional[Table] = None
    image_ref: Optional[str] = None
    style: Optional[Style] = None
    quality: Optional[Quality] = None
    language: Optional[str] = None
    is_continuation: bool = False
    parser_extras: Dict[str, Any] = {}


class Page(_Frozen):
    index: int
    start_char: Optional[int] = None
    end_char: Optional[int] = None
    width: Optional[float] = None
    height: Optional[float] = None
    unit: Optional[str] = None
    rotation: int = 0
    block_ids: List[str] = []
    quality: Optional[Quality] = None
    parser_extras: Dict[str, Any] = {}


class Label(_Frozen):
    name: str
    confidence: Optional[float] = None
    scope: Literal["document", "page", "block"] = "document"
    scope_ref: Optional[Union[int, str]] = None
    source: Literal["parser", "classifier", "human"] = "classifier"


class ParsedDocument(_Frozen):
    id: str
    source_document_id: str
    parse_run_id: str
    source_filename: Optional[str] = None
    page_count: int
    pages: List[Page]
    blocks: List[Block]
    full_text: Optional[str] = None
    full_markdown: Optional[str] = None
    labels: List[Label] = []
    # Lineage for future split() outputs — set when this is a derived document.
    derived_from: Optional[str] = None
    derivation: Optional[str] = None
    parser_extras: Dict[str, Any] = {}
    schema_version: str = "1.0"
