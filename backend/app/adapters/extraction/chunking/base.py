"""Chunking primitives: DocumentChunk view + strategy protocol."""
from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict

from app.cdm.models import ParsedDocument


class DocumentChunk(BaseModel):
    """A derived, non-destructive view over a slice of a ParsedDocument.

    `document` is built via ParsedDocument.model_copy; the source is never mutated.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    document: ParsedDocument
    chunk_index: int
    page_indices: list[int]


class ChunkStrategy(Protocol):
    """Splits a ParsedDocument into ordered DocumentChunks."""

    def split(
        self,
        parsed_doc: ParsedDocument,
        schema: dict[str, Any],
        config: dict[str, Any],
    ) -> list[DocumentChunk]:
        ...
