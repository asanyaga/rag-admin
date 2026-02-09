"""Service for document chunking.

Supports multiple chunking strategies and provides preview functionality
for the index creation UI.
"""
from dataclasses import dataclass
from typing import Literal
import tiktoken

from langchain_text_splitters import (
    CharacterTextSplitter,
    RecursiveCharacterTextSplitter,
)

from app.schemas.index import IndexConfig, ChunkPreview, ChunkPreviewResponse


@dataclass
class ChunkResult:
    """Result of chunking a document."""
    content: str
    chunk_index: int
    token_count: int
    char_count: int
    start_char: int
    end_char: int
    metadata: dict


class ChunkingService:
    """Service for splitting documents into chunks."""

    def __init__(self):
        # Initialize tiktoken encoder for token counting
        # Using cl100k_base which is used by text-embedding-3-* models
        self._tokenizer = tiktoken.get_encoding("cl100k_base")

    def count_tokens(self, text: str) -> int:
        """Count tokens in a text string using tiktoken."""
        return len(self._tokenizer.encode(text))

    def _create_splitter(
        self,
        strategy: Literal["fixed_size", "recursive_character"],
        chunk_size: int,
        chunk_overlap: int,
        chunk_unit: Literal["tokens", "characters"]
    ):
        """Create a text splitter based on configuration."""
        # For token-based splitting, we need to use a length function
        if chunk_unit == "tokens":
            length_function = self.count_tokens
        else:
            length_function = len

        if strategy == "fixed_size":
            return CharacterTextSplitter(
                separator="",  # Split on any character
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                length_function=length_function,
                is_separator_regex=False,
            )
        else:  # recursive_character (default)
            return RecursiveCharacterTextSplitter(
                separators=["\n\n", "\n", ". ", " ", ""],
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                length_function=length_function,
                is_separator_regex=False,
            )

    def chunk_text(
        self,
        text: str,
        config: IndexConfig,
        source_document_id: str | None = None,
        source_filename: str | None = None,
        page_numbers: list[int] | None = None
    ) -> list[ChunkResult]:
        """Split text into chunks based on configuration.

        Args:
            text: The document text to chunk
            config: Index configuration with chunking parameters
            source_document_id: Optional document ID for metadata
            source_filename: Optional filename for metadata
            page_numbers: Optional list of page numbers (for PDFs)

        Returns:
            List of ChunkResult objects
        """
        if not text or not text.strip():
            return []

        splitter = self._create_splitter(
            strategy=config.chunking_strategy,
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap,
            chunk_unit=config.chunk_unit
        )

        # Split the text
        chunks = splitter.split_text(text)

        # Build results with metadata
        results = []
        current_pos = 0

        for i, chunk_content in enumerate(chunks):
            # Find the actual position in the original text
            # This is approximate due to how text splitters work
            start_char = text.find(chunk_content, current_pos)
            if start_char == -1:
                start_char = current_pos
            end_char = start_char + len(chunk_content)
            current_pos = max(current_pos, start_char + 1)

            # Build metadata
            metadata = {
                "chunk_index": i,
                "start_char": start_char,
                "end_char": end_char,
            }
            if source_document_id:
                metadata["source_document_id"] = source_document_id
            if source_filename:
                metadata["source_filename"] = source_filename
            if page_numbers:
                metadata["page_numbers"] = page_numbers

            results.append(ChunkResult(
                content=chunk_content,
                chunk_index=i,
                token_count=self.count_tokens(chunk_content),
                char_count=len(chunk_content),
                start_char=start_char,
                end_char=end_char,
                metadata=metadata
            ))

        return results

    def preview_chunks(
        self,
        text: str,
        config: IndexConfig,
        max_chunks: int = 5
    ) -> ChunkPreviewResponse:
        """Generate a chunk preview for the UI.

        This runs the chunker in memory and returns preview data
        without persisting anything to the database.

        Args:
            text: Document text to preview
            config: Chunking configuration
            max_chunks: Maximum number of chunks to return in preview

        Returns:
            ChunkPreviewResponse with statistics and sample chunks
        """
        # Get all chunks for statistics
        all_chunks = self.chunk_text(text, config)

        if not all_chunks:
            return ChunkPreviewResponse(
                total_chunks_estimate=0,
                avg_chunk_size_chars=0,
                avg_chunk_size_tokens=0,
                min_chunk_size_chars=0,
                max_chunk_size_chars=0,
                preview_chunks=[]
            )

        # Calculate statistics
        char_counts = [c.char_count for c in all_chunks]
        token_counts = [c.token_count for c in all_chunks]

        avg_chars = sum(char_counts) / len(char_counts)
        avg_tokens = sum(token_counts) / len(token_counts)
        min_chars = min(char_counts)
        max_chars = max(char_counts)

        # Build preview chunks (first N)
        preview_chunks = []
        for i, chunk in enumerate(all_chunks[:max_chunks]):
            # Calculate overlap regions
            # Start overlap: if not first chunk, overlap from previous chunk
            overlap_start = 0
            if i > 0 and config.chunk_overlap > 0:
                overlap_start = min(config.chunk_overlap, chunk.char_count // 2)

            # End overlap: if not last chunk, overlap into next chunk
            overlap_end = 0
            if i < len(all_chunks) - 1 and config.chunk_overlap > 0:
                overlap_end = min(config.chunk_overlap, chunk.char_count // 2)

            preview_chunks.append(ChunkPreview(
                index=chunk.chunk_index,
                content=chunk.content,
                char_count=chunk.char_count,
                token_count=chunk.token_count,
                overlap_start_chars=overlap_start,
                overlap_end_chars=overlap_end,
            ))

        return ChunkPreviewResponse(
            total_chunks_estimate=len(all_chunks),
            avg_chunk_size_chars=round(avg_chars, 1),
            avg_chunk_size_tokens=round(avg_tokens, 1),
            min_chunk_size_chars=min_chars,
            max_chunk_size_chars=max_chars,
            preview_chunks=preview_chunks,
        )


# Singleton instance
_chunking_service: ChunkingService | None = None


def get_chunking_service() -> ChunkingService:
    """Get or create the chunking service singleton."""
    global _chunking_service
    if _chunking_service is None:
        _chunking_service = ChunkingService()
    return _chunking_service
