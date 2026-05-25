"""LlamaExtract adapter — stub for CDM port signature.

Full refactor: docs/superpowers/specs/2026-05-06-llamaextract-adapter-refactor-design.md
"""
from typing import Any
from app.ports.data_extraction import DataExtractor, ExtractionOutput


class LlamaExtractAdapter(DataExtractor):
    """LlamaExtract adapter (pending CDM refactor)."""

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key

    @property
    def extractor_type(self) -> str:
        return "llamaextract"

    @property
    def display_name(self) -> str:
        return "LlamaExtract"

    async def extract(
        self,
        parsed_document: Any,
        schema: dict[str, Any],
        config: dict[str, Any] | None = None,
    ) -> ExtractionOutput:
        raise NotImplementedError(
            "LlamaExtractAdapter.extract() requires the CDM refactor. "
            "See docs/superpowers/specs/2026-05-06-llamaextract-adapter-refactor-design.md"
        )
