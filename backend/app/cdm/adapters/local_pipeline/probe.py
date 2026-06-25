"""DocumentProbe — standalone PDF classifier using PyMuPDF."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict


class PageProfile(BaseModel):
    model_config = ConfigDict(frozen=True)

    index: int
    char_count: int
    has_text_layer: bool
    image_count: int
    font_health: Literal["clean", "cid_corrupt", "mixed", "unknown"]
    table_signal: bool
    page_type: Literal["text", "scanned", "mixed", "empty"]


class DocumentProfile(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_document_id: str
    filename: Optional[str]
    page_count: int
    pages: List[PageProfile]
    has_text_layer: bool
    has_scanned_pages: bool
    has_cid_corruption: bool
    table_signal: bool
    recommended_tools: List[str]
    duration_ms: int
    probed_at: datetime


class DocumentProbe:
    """Inspects a PDF and returns a DocumentProfile.

    Uses only PyMuPDF — no network calls, no side effects.
    """

    def run(self, pdf_path: Path, source_document_id: str = "") -> DocumentProfile:
        raise NotImplementedError
