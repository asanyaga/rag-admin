"""Adapter protocol — each parser implementation adapts raw output to CDM."""
from __future__ import annotations

from typing import Any, ClassVar, Optional, Protocol

from pydantic import BaseModel

from app.cdm.models import ParsedDocument, ParserKind


class SourceMeta(BaseModel):
    """Identity passed into an adapter so it can wire up foreign references."""
    source_document_id: str
    parse_run_id: str
    filename: Optional[str] = None
    sha256: Optional[str] = None


class ParserAdapter(Protocol):
    parser: ClassVar[ParserKind]

    def adapt(self, raw: Any, source_meta: SourceMeta) -> ParsedDocument: ...
