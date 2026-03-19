"""Data extraction port interface."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExtractionOutput:
    """Extractor-agnostic output contract."""
    structured_data: dict[str, Any]
    extraction_metadata: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class DataExtractor(ABC):
    """Port: Extract structured data from documents using a JSON Schema."""

    @abstractmethod
    async def extract(
        self,
        file_path: str,
        schema: dict[str, Any],
        config: dict[str, Any] | None = None,
    ) -> ExtractionOutput:
        """Extract structured data from a document file."""
        ...

    @property
    @abstractmethod
    def extractor_type(self) -> str:
        """Unique identifier for this extractor (e.g. 'llamaextract')."""
        ...
