from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol

from app.cdm.classification import ClassifiedRegion
from app.cdm.models import ParsedDocument


@dataclass
class ClassificationResult:
    regions: list[ClassifiedRegion]
    input_tokens: int = 0
    output_tokens: int = 0


class ClassificationPort(Protocol):
    async def classify(
        self,
        doc: ParsedDocument,
        labels: list[str],
    ) -> ClassificationResult: ...
