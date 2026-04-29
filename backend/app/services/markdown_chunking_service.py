"""Service for chunking markdown documents by heading structure."""
import re

import tiktoken
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.schemas.index import IndexConfig
from app.services.chunking_service import ChunkResult


class MarkdownChunkingService:
    """Chunks markdown text on heading boundaries with recursive fallback.

    Sections exceeding max_section_chars are further split with
    RecursiveCharacterTextSplitter; sub-chunks inherit the heading path.
    """

    _HEADING = re.compile(r"^(#{1,6})\s+(.+)$")

    def __init__(self) -> None:
        self._tokenizer = tiktoken.get_encoding("cl100k_base")

    def count_tokens(self, text: str) -> int:
        return len(self._tokenizer.encode(text))

    def chunk_markdown(
        self,
        markdown: str,
        config: IndexConfig,
        source_document_id: str | None = None,
        source_filename: str | None = None,
    ) -> list[ChunkResult]:
        if not markdown or not markdown.strip():
            return []

        sections = self._parse_sections(markdown, config.split_heading_level)
        results: list[ChunkResult] = []
        chunk_index = 0

        for section in sections:
            content: str = section["content"]
            heading_path: list[str] = section["heading_path"]
            section_start: int = section["start_char"]

            # Determine sub-chunks: single section or recursive fallback
            if len(content) <= config.max_section_chars:
                sub_chunks: list[tuple[str, int]] = [(content, 0)]
            else:
                splitter = RecursiveCharacterTextSplitter(
                    separators=["\n\n", "\n", ". ", " ", ""],
                    chunk_size=config.max_section_chars,
                    chunk_overlap=0,
                    length_function=len,
                )
                raw = splitter.split_text(content)
                pos = 0
                sub_chunks = []
                for sub in raw:
                    idx = content.find(sub, pos)
                    offset = idx if idx != -1 else pos
                    sub_chunks.append((sub, offset))
                    pos = max(pos, offset + 1)

            for sub_content, offset in sub_chunks:
                start_char = section_start + offset
                end_char = start_char + len(sub_content)
                metadata: dict = {
                    "chunk_index": chunk_index,
                    "start_char": start_char,
                    "end_char": end_char,
                    "heading_path": heading_path,
                    "split_level": config.split_heading_level,
                }
                if source_document_id:
                    metadata["source_document_id"] = source_document_id
                if source_filename:
                    metadata["source_filename"] = source_filename

                results.append(ChunkResult(
                    content=sub_content,
                    chunk_index=chunk_index,
                    token_count=self.count_tokens(sub_content),
                    char_count=len(sub_content),
                    start_char=start_char,
                    end_char=end_char,
                    metadata=metadata,
                ))
                chunk_index += 1

        return results

    def _parse_sections(self, markdown: str, split_heading_level: int) -> list[dict]:
        """Split markdown into sections at headings whose level <= split_heading_level.

        Returns list of dicts: {content, heading_path, start_char}.
        """
        sections: list[dict] = []
        heading_stack: list[tuple[int, str]] = []  # (level, title)
        current_lines: list[str] = []
        current_heading_path: list[str] = []
        current_start_char = 0
        char_pos = 0

        for line in markdown.split("\n"):
            m = self._HEADING.match(line)
            if m and len(m.group(1)) <= split_heading_level:
                level = len(m.group(1))
                title = m.group(2).strip()

                if current_lines:
                    sections.append({
                        "content": "\n".join(current_lines),
                        "heading_path": current_heading_path[:],
                        "start_char": current_start_char,
                    })

                # Pop same-or-deeper levels from the heading stack
                heading_stack = [(l, t) for l, t in heading_stack if l < level]
                heading_stack.append((level, title))
                current_heading_path = [t for _, t in heading_stack]
                current_lines = [line]
                current_start_char = char_pos
            else:
                current_lines.append(line)

            char_pos += len(line) + 1  # +1 for the \n separator

        if current_lines:
            sections.append({
                "content": "\n".join(current_lines),
                "heading_path": current_heading_path[:],
                "start_char": current_start_char,
            })

        return sections


_markdown_chunking_service: MarkdownChunkingService | None = None


def get_markdown_chunking_service() -> MarkdownChunkingService:
    global _markdown_chunking_service
    if _markdown_chunking_service is None:
        _markdown_chunking_service = MarkdownChunkingService()
    return _markdown_chunking_service
