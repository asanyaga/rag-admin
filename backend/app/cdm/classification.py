"""Classification types for the Common Data Model."""
from __future__ import annotations

from enum import Enum
from typing import List, Literal, Optional

from app.cdm.models import _Frozen


class ClassifiedRegion(_Frozen):
    label: str
    page_start: int
    page_end: int
    block_ids: List[str]
    confidence: Optional[float] = None
    reasoning: Optional[str] = None
    source: Literal["llm", "human"] = "llm"


class ClassificationRunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
