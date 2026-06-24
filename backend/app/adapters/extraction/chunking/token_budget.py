"""Token-budgeted page-packing chunk strategy."""
from __future__ import annotations

from typing import Any

from app.adapters.extraction.chunking.base import DocumentChunk
from app.cdm.models import ParsedDocument

_CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    """Cheap heuristic token estimate."""
    return len(text) // _CHARS_PER_TOKEN


def _page_tokens(doc: ParsedDocument, page_index: int) -> int:
    total = 0
    for block in doc.blocks:
        if block.page_index == page_index:
            total += estimate_tokens(block.markdown or block.text or "")
    return total


class TokenBudgetPagesStrategy:
    """Pack whole pages into chunks until an input-token budget is reached."""

    def __init__(self, max_input_tokens: int, page_overlap: int = 0) -> None:
        self.max_input_tokens = max_input_tokens
        self.page_overlap = page_overlap

    def split(
        self,
        parsed_doc: ParsedDocument,
        schema: dict[str, Any],
        config: dict[str, Any],
    ) -> list[DocumentChunk]:
        page_indices = sorted({p.index for p in parsed_doc.pages}) or \
            sorted({b.page_index for b in parsed_doc.blocks})
        if not page_indices:
            return [DocumentChunk(document=parsed_doc, chunk_index=0, page_indices=[])]

        groups: list[list[int]] = []
        current: list[int] = []
        current_tokens = 0
        for idx in page_indices:
            pt = _page_tokens(parsed_doc, idx)
            if current and current_tokens + pt > self.max_input_tokens:
                groups.append(current)
                overlap = current[-self.page_overlap:] if self.page_overlap else []
                current = list(overlap)
                current_tokens = sum(_page_tokens(parsed_doc, i) for i in current)
            current.append(idx)
            current_tokens += pt
        if current:
            groups.append(current)

        return [
            DocumentChunk(
                document=self._derive(parsed_doc, group),
                chunk_index=i,
                page_indices=group,
            )
            for i, group in enumerate(groups)
        ]

    @staticmethod
    def _derive(doc: ParsedDocument, page_group: list[int]) -> ParsedDocument:
        keep = set(page_group)
        pages = [p for p in doc.pages if p.index in keep]
        blocks = [b for b in doc.blocks if b.page_index in keep]
        return doc.model_copy(update={
            "pages": pages,
            "blocks": blocks,
            "page_count": len(pages) or len(keep),
            "derived_from": doc.parse_run_id,
            "derivation": f"chunk:pages={page_group[0]}-{page_group[-1]}",
        })
