"""SimpleText adapter — maps LlamaIndexExtractor output to CDM.

Input is a plain dict with optional keys:
  ``text``            — full document text
  ``page_count``      — number of pages
  ``page_boundaries`` — list of dicts with ``page``, ``start_char``, ``end_char``
"""
from __future__ import annotations

import uuid
from typing import Any, ClassVar, Dict, List

from app.cdm.adapters.base import ParserAdapter, SourceMeta
from app.cdm.models import Block, BlockRole, Page, ParsedDocument, ParserKind


class SimpleTextAdapter:
    parser: ClassVar[ParserKind] = ParserKind.SIMPLE

    def adapt(self, raw: Dict[str, Any], source_meta: SourceMeta) -> ParsedDocument:
        full_text: str = raw.get("text") or ""
        boundaries: List[Dict[str, Any]] = raw.get("page_boundaries") or []

        if boundaries:
            blocks: List[Block] = []
            pages: List[Page] = []
            for pb in boundaries:
                page_number: int = pb.get("page", 1)
                page_index = page_number - 1
                start_char: int = pb.get("start_char", 0)
                end_char: int = pb.get("end_char", len(full_text))
                page_text = full_text[start_char:end_char].strip()
                block_id = f"{source_meta.source_document_id}:p{page_index}:b0"
                block = Block(
                    id=block_id,
                    role=BlockRole.TEXT,
                    native_type="text",
                    text=page_text,
                    page_index=page_index,
                )
                blocks.append(block)
                pages.append(Page(
                    index=page_index,
                    block_ids=[block_id],
                    start_char=start_char,
                    end_char=end_char,
                ))
        else:
            # Fallback: single page/block containing all text
            block_id = f"{source_meta.source_document_id}:p0:b0"
            blocks = [Block(
                id=block_id,
                role=BlockRole.TEXT,
                native_type="text",
                text=full_text.strip(),
                page_index=0,
            )]
            pages = [Page(
                index=0,
                block_ids=[block_id],
                start_char=0,
                end_char=len(full_text),
            )]

        return ParsedDocument(
            id=str(uuid.uuid4()),
            source_document_id=source_meta.source_document_id,
            parse_run_id=source_meta.parse_run_id,
            source_filename=source_meta.filename,
            page_count=len(pages),
            pages=pages,
            blocks=blocks,
            full_text=full_text or None,
        )
