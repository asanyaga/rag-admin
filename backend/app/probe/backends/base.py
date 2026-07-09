from __future__ import annotations
from pathlib import Path
from typing import List, Protocol, runtime_checkable
import numpy as np
from pydantic import BaseModel
from app.probe.report import BBox


class TextSpan(BaseModel):
    text: str
    bbox: BBox            # normalized


class ImagePrimitive(BaseModel):
    xref: int
    bbox: BBox            # normalized position on the page
    width_px: int         # native pixel dimensions of the embedded image
    height_px: int


class DrawingPrimitive(BaseModel):
    kind: str             # 'l' (line) or 're' (rect)
    bbox: BBox


class PagePrimitives(BaseModel):
    index: int
    width_pt: float
    height_pt: float
    text: str
    text_spans: List[TextSpan]
    images: List[ImagePrimitive]
    drawings: List[DrawingPrimitive]


class DocumentPrimitives(BaseModel):
    page_count: int
    copy_restricted: bool
    pages: List[PagePrimitives]


@runtime_checkable
class InspectionBackend(Protocol):
    name: str
    version: str
    def inspect(self, pdf_path: Path) -> DocumentPrimitives: ...
    def render_gray(self, pdf_path: Path, page_index: int, bbox: BBox, target_px: int = 256) -> np.ndarray: ...
