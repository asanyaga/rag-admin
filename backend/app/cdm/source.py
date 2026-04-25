"""SourceDocument and ParseRun — identity and execution records.

A SourceDocument is the content-addressable representation of input bytes.
A ParseRun is one execution of a parser against a SourceDocument, identified
separately so that a single source can have multiple parsed representations
(e.g. vector_light vs. extract_rich) each with their own metrics.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict

from app.cdm.models import ParserKind


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ParseRunStatus(str, Enum):
    PENDING   = "pending"
    RUNNING   = "running"
    SUCCEEDED = "succeeded"
    FAILED    = "failed"
    PARTIAL   = "partial"


class SourceDocument(_Frozen):
    id: str
    sha256: str
    filename: Optional[str] = None
    mime_type: Optional[str] = None
    byte_size: Optional[int] = None
    storage_uri: Optional[str] = None
    created_at: datetime


class ParseRun(_Frozen):
    id: str
    source_document_id: str
    parser: ParserKind
    parser_version: Optional[str] = None
    representation_kind: str  # open string: "vector_light" | "extract_rich" | ...
    config: Dict[str, Any] = {}
    status: ParseRunStatus
    started_at: datetime
    finished_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    cost: Dict[str, Any] = {}
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    warnings: List[str] = []
    failed_pages: List[int] = []
    provider_refs: Dict[str, Any] = {}
    raw_payload: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
