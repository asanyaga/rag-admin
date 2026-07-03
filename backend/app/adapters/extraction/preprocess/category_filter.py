"""Preprocess stage: reconstruct a whole ParsedDocument scoped to a keep-set.

Config is produced by resolve_category_filter_stages (services.classification):
it carries the original selection (classificationRunId, categories, granularity)
plus the resolved keepPages / keepBlockIds. This function is pure — no DB access.
"""
from __future__ import annotations

from typing import Any

from app.cdm.models import Label, ParsedDocument


def category_filter(doc: ParsedDocument, config: dict[str, Any]) -> ParsedDocument:
    keep_pages = {int(p) for p in (config.get("keepPages") or [])}
    keep_block_ids = {str(b) for b in (config.get("keepBlockIds") or [])}

    kept = [
        b for b in doc.blocks
        if b.page_index in keep_pages or str(b.id) in keep_block_ids
    ]
    kept_ids = {str(b.id) for b in kept}
    kept_page_indices = {b.page_index for b in kept}

    pages = [
        p.model_copy(update={"block_ids": [bid for bid in p.block_ids if bid in kept_ids]})
        for p in doc.pages
        if p.index in kept_page_indices
    ]

    full_markdown = "\n\n".join(
        (b.markdown if b.markdown else b.text) for b in kept if (b.markdown or b.text)
    ) or None
    full_text = "\n\n".join(b.text for b in kept if b.text) or None

    categories = config.get("categories") or []
    labels = list(doc.labels) + [
        Label(name=c, scope="document", source="classifier") for c in categories
    ]

    return doc.model_copy(update={
        "blocks": kept,
        "pages": pages,
        "page_count": len(pages),
        "full_markdown": full_markdown,
        "full_text": full_text,
        "labels": labels,
        "derived_from": doc.parse_run_id,
        "derivation": "preprocess:category_filter",
    })
