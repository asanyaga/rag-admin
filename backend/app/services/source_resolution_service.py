"""Source resolution: parsed-doc handle + segment -> chunkable source.

Single shared seam used by both chunk preview and index processing so that
a preview always reflects the same bytes the save path will chunk.

The seam carries only the bytes/blocks. Metadata (source_document_id,
source_filename) flows through the dispatcher's call site so that the save
path's chunk metadata stays byte-identical with the pre-refactor behaviour
(which sourced filename from `Document.source_metadata.filename`).
"""
from dataclasses import dataclass
from typing import Literal, Union
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.parsed_document_repository import ParsedDocumentRepository
from app.services.exceptions import NotFoundError, ValidationError


SourceRepresentation = Literal["full_text", "full_markdown", "block"]


@dataclass(frozen=True)
class TextSource:
    """Text-shaped source (full_text or full_markdown)."""
    text: str


@dataclass(frozen=True)
class BlocksSource:
    """Block-shaped source. Block chunking is not yet implemented."""
    blocks: list[dict]


ChunkSource = Union[TextSource, BlocksSource]


class SourceResolutionService:
    """Resolve a parsed-document handle + segment into a ChunkSource."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def resolve(
        self,
        *,
        parsed_document_id: UUID,
        source_representation: SourceRepresentation,
    ) -> ChunkSource:
        parsed_doc_repo = ParsedDocumentRepository(self.session)

        # Under the current 1:1 schema, parsed_documents.parse_run_id is the PK.
        parsed_doc = await parsed_doc_repo.get_by_run(parsed_document_id)
        if parsed_doc is None:
            raise NotFoundError(
                f"Parsed document {parsed_document_id} not found"
            )

        if source_representation == "full_text":
            if parsed_doc.full_text is None:
                raise ValidationError(
                    f"Parsed document {parsed_document_id} has no full_text"
                )
            return TextSource(text=parsed_doc.full_text)

        if source_representation == "full_markdown":
            if parsed_doc.full_markdown is None:
                raise ValidationError(
                    f"Parsed document {parsed_document_id} has no full_markdown. "
                    "Re-parse with a configuration that outputs markdown."
                )
            return TextSource(text=parsed_doc.full_markdown)

        # block
        blocks = (parsed_doc.content or {}).get("blocks") or []
        if not blocks:
            raise ValidationError(
                f"Parsed document {parsed_document_id} has no blocks"
            )
        return BlocksSource(blocks=blocks)
