"""Data extraction port interface."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class FieldCitation:
    """Provenance link from an extracted field value back to the CDM."""
    field_path: str               # dot/bracket path: "total", "line_items[0].sku"
    page_index: int | None        # always attempted; None only when truly unavailable
    block_ids: list[str] | None   # CDM Block.id values; None in phase 1
    text_spans: list[str] | None  # verbatim text drawn from; optional


@dataclass(frozen=True)
class ExtractionOutput:
    """Extractor-agnostic output contract."""
    structured_data: dict[str, Any]           # always — clean extracted values
    source_parse_run_id: UUID                  # always — minimum provenance anchor
    citations: list[FieldCitation] | None      # LLM adapters only
    provider_response_raw: dict | None         # provider adapters only
    extraction_metadata: dict[str, Any] | None # timing, tokens, cost


class DataExtractor(ABC):
    """Port: extract structured data from a CDM ParsedDocument using a JSON Schema."""

    @property
    @abstractmethod
    def extractor_type(self) -> str:
        """Registry key, e.g. 'ollama', 'llamaextract'."""
        ...

    @property
    def display_name(self) -> str:
        return self.extractor_type

    @abstractmethod
    async def extract(
        self,
        parsed_document: Any,   # app.cdm.models.ParsedDocument — Any avoids circular import
        schema: dict[str, Any],
        config: dict[str, Any] | None = None,
    ) -> ExtractionOutput:
        """Extract structured data from a CDM ParsedDocument."""
        ...
