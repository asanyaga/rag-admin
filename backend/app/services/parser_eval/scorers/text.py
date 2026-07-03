"""Text-faithfulness scorer — compares parsed per-page text to a page-segmented reference.

Content-oriented and parser-agnostic: it flattens each page to text and never inspects
block structure, so parsers that segment blocks differently are scored fairly.
"""
from __future__ import annotations

import difflib
import re
from typing import Any

from app.cdm.models import ParsedDocument

_WS = re.compile(r"\s+")


def _normalize(text: str) -> str:
    return _WS.sub(" ", (text or "").strip().lower())


def _tokens(text: str) -> list[str]:
    return _normalize(text).split()


def _parsed_page_texts(cdm: ParsedDocument) -> list[str]:
    """Per-page text via Page.start_char/end_char slices of full_text.

    Falls back to concatenating each page's block text when offsets are absent.
    """
    full = cdm.full_text or ""
    pages: list[str] = []
    for page in sorted(cdm.pages, key=lambda p: p.index):
        if full and page.start_char is not None and page.end_char is not None:
            pages.append(full[page.start_char:page.end_char])
        else:
            pages.append(
                " ".join(b.text for b in cdm.blocks if b.page_index == page.index)
            )
    return pages


def _score_page(reference: str, parsed: str) -> dict[str, float]:
    ref_norm, par_norm = _normalize(reference), _normalize(parsed)
    similarity = difflib.SequenceMatcher(None, ref_norm, par_norm).ratio()

    ref_toks, par_toks = set(_tokens(reference)), set(_tokens(parsed))
    omission = 0.0 if not ref_toks else len(ref_toks - par_toks) / len(ref_toks)
    hallucination = 0.0 if not par_toks else len(par_toks - ref_toks) / len(par_toks)
    return {"similarity": similarity, "omission": omission, "hallucination": hallucination}


def score_text(cdm: ParsedDocument, expected: dict[str, Any]) -> tuple[float, dict[str, Any]]:
    reference_pages: list[str] = expected["pages"]
    parsed_pages = _parsed_page_texts(cdm)

    per_page: list[dict[str, Any]] = []
    n = max(len(reference_pages), len(parsed_pages))
    for i in range(n):
        ref = reference_pages[i] if i < len(reference_pages) else ""
        par = parsed_pages[i] if i < len(parsed_pages) else ""
        page_scores = _score_page(ref, par)
        per_page.append({"page": i, **page_scores})

    # Length-weighted aggregate by reference character count (empty ref pages weight 0,
    # but an unmatched *parsed* page still contributes hallucination via a min weight of 1).
    def _weight(i: int) -> int:
        return max(len(reference_pages[i]) if i < len(reference_pages) else 0, 1)

    total_w = sum(_weight(i) for i in range(n)) or 1
    similarity = sum(p["similarity"] * _weight(p["page"]) for p in per_page) / total_w
    omission = sum(p["omission"] * _weight(p["page"]) for p in per_page) / total_w
    hallucination = sum(p["hallucination"] * _weight(p["page"]) for p in per_page) / total_w

    details = {
        "per_page": per_page,
        "omission": omission,
        "hallucination": hallucination,
        "page_count_expected": len(reference_pages),
        "page_count_parsed": len(parsed_pages),
    }
    return similarity, details
