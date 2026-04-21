"""CitationRef — references from downstream outputs back to CDM blocks.

Block IDs are only unique within a ParseRun, so parse_run_id is required.
bbox is denormalized for UI overlay rendering without a lookup.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.cdm.models import BBox


class CitationRef(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source_document_id: str
    parse_run_id: str
    block_id: str
    page_index: int
    char_start: Optional[int] = None
    char_end: Optional[int] = None
    cell_id: Optional[str] = None
    bbox: Optional[BBox] = None
