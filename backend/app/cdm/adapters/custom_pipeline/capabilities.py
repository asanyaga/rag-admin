"""IDP capabilities and their precedence.

One tool fills at most one capability slot. Blocks are tagged with the
capability that produced them; the merger ranks blocks by that tag.
"""
from __future__ import annotations

from enum import Enum
from typing import Dict


class Capability(str, Enum):
    TEXT_EXTRACTION = "text_extraction"
    TABLE_DETECTION = "table_detection"
    TEXT_OCR = "text_ocr"
    LAYOUT_ANALYSIS = "layout_analysis"


#: Capabilities whose blocks compete for page area (governed by precedence).
BLOCK_PRODUCING = frozenset({
    Capability.TEXT_EXTRACTION,
    Capability.TABLE_DETECTION,
    Capability.TEXT_OCR,
})

#: Capabilities that order/route rather than compete. No tools yet.
STAGING = frozenset({Capability.LAYOUT_ANALYSIS})


def resolve_precedence(*, cid_corrupt: bool, ocr_prefer: bool) -> Dict[Capability, int]:
    """Rank block-producing capabilities for one page. Higher wins.

    Structure always beats loose text. The only variable is whether OCR sits
    above or below native text — the CID flip and `prefer` are the same
    mechanism, applied per-page vs per-run.
    """
    ocr_outranks_text = ocr_prefer or cid_corrupt
    if ocr_outranks_text:
        return {
            Capability.TABLE_DETECTION: 3,
            Capability.TEXT_OCR: 2,
            Capability.TEXT_EXTRACTION: 1,
        }
    return {
        Capability.TABLE_DETECTION: 3,
        Capability.TEXT_EXTRACTION: 2,
        Capability.TEXT_OCR: 1,
    }
