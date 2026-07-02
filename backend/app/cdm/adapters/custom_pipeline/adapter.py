"""CustomPipelineAdapter — pure assembler: merged blocks + page geometry → CDM.

All heavy lifting (eviction, id minting, bbox normalization) happens upstream
in the tools and the merger. This adapter only assembles the ParsedDocument.
"""
from __future__ import annotations

from typing import Any, ClassVar, Dict, List
from uuid import uuid4

from app.cdm.adapters.base import SourceMeta
from app.cdm.adapters.custom_pipeline.tools.base import PageMeta
from app.cdm.models import Block, Page, ParsedDocument, ParserKind


class CustomPipelineAdapter:
    parser: ClassVar[ParserKind] = ParserKind.CUSTOM_PIPELINE

    def adapt(self, raw: Any, source_meta: SourceMeta) -> ParsedDocument:
        page_meta: Dict[int, PageMeta] = raw["page_meta"]
        blocks: List[Block] = list(raw["blocks"])

        blocks_by_page: Dict[int, List[Block]] = {}
        for b in blocks:
            blocks_by_page.setdefault(b.page_index, []).append(b)

        page_indices = sorted(set(page_meta.keys()) | set(blocks_by_page.keys()))
        pages: List[Page] = []
        for idx in page_indices:
            pm = page_meta.get(idx)
            page_blocks = sorted(
                blocks_by_page.get(idx, []),
                key=lambda b: (b.reading_order if b.reading_order is not None else 1e9),
            )
            pages.append(Page(
                index=idx,
                width=pm.width if pm else None,
                height=pm.height if pm else None,
                unit=pm.unit if pm else None,
                rotation=pm.rotation if pm else 0,
                block_ids=[b.id for b in page_blocks],
            ))

        ordered_blocks = sorted(
            blocks,
            key=lambda b: (b.page_index, b.reading_order if b.reading_order is not None else 1e9),
        )
        full_text = "\n\n".join(b.text for b in ordered_blocks if b.text)
        full_markdown = "\n\n".join(b.markdown for b in ordered_blocks if b.markdown)

        return ParsedDocument(
            id=str(uuid4()),
            source_document_id=source_meta.source_document_id,
            parse_run_id=source_meta.parse_run_id,
            source_filename=source_meta.filename,
            page_count=len(pages),
            pages=pages,
            blocks=ordered_blocks,
            full_text=full_text or None,
            full_markdown=full_markdown or None,
        )
