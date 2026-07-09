from __future__ import annotations
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel

ObservationLabel = Literal[
    "text_image", "decorative_image", "text_covered_image", "uncertain", "table_grid",
]
PageType = Literal["text", "scanned", "mixed", "empty"]


class BBox(BaseModel):
    x0: float
    y0: float
    x1: float
    y1: float


class Signal(BaseModel):
    name: str
    value: Union[float, str]
    unit: Optional[str] = None
    strength: Optional[float] = None   # normalized 0..1
    detail: Optional[str] = None


class Observation(BaseModel):
    label: ObservationLabel
    confidence: float


class RegionFinding(BaseModel):
    id: str
    page_index: int
    kind: Literal["image", "table"]
    bbox: BBox
    signals: List[Signal] = []
    observation: Observation


class PageProfile(BaseModel):
    index: int
    page_type: PageType
    signals: List[Signal] = []
    regions: List[RegionFinding] = []


class ParserSuggestion(BaseModel):
    authoritative: bool = False
    tools: List[str] = []
    ocr_pages: List[int] = []
    overall_confidence: float = 0.0
    rationale: List[str] = []


class ProbeReport(BaseModel):
    document_id: str
    filename: Optional[str]
    page_count: int
    inspection: Dict[str, Any]
    pages: List[PageProfile]
    suggestion: Optional[ParserSuggestion]
    duration_ms: int
    probed_at: str
