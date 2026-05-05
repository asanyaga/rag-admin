from __future__ import annotations
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

from app.cdm.classification import ClassifiedRegion
from app.cdm.models import ParsedDocument

logger = logging.getLogger(__name__)


@dataclass
class BatchPageResult:
    page: int
    label_statuses: Dict[str, str]  # label -> "start"|"continue"|"none"
    batch_start: int
    batch_end: int


def resolve_page_statuses(
    batch_results: List[List[BatchPageResult]],
) -> Dict[int, Dict[str, str]]:
    """For overlapping pages, prefer results from the middle 50% of each batch window."""
    best: Dict[int, tuple[int, Dict[str, str]]] = {}

    for batch_pages in batch_results:
        if not batch_pages:
            continue
        batch_start = batch_pages[0].batch_start
        batch_end = batch_pages[0].batch_end
        batch_len = batch_end - batch_start + 1
        quarter = max(1, batch_len // 4)

        for page_result in batch_pages:
            page = page_result.page
            in_middle = (batch_start + quarter) <= page < (batch_end - quarter)
            priority = 0 if in_middle else 1
            if page not in best or priority < best[page][0]:
                best[page] = (priority, page_result.label_statuses)

    return {page: statuses for page, (_, statuses) in best.items()}


def assemble_regions(
    resolved: Dict[int, Dict[str, str]],
    labels: List[str],
    doc: ParsedDocument,
) -> List[ClassifiedRegion]:
    """Walk sorted pages per label and build ClassifiedRegion objects."""
    regions: List[ClassifiedRegion] = []

    for label in labels:
        current_start: Optional[int] = None
        current_end: Optional[int] = None

        for page in sorted(resolved.keys()):
            status = resolved[page].get(label, "none")

            if status == "start":
                if current_start is not None:
                    regions.append(_make_region(label, current_start, current_end, doc))
                current_start = page
                current_end = page
            elif status == "continue" and current_start is not None:
                current_end = page
            elif status == "continue" and current_start is None:
                logger.warning(
                    "Ignoring 'continue' status for label %r on page %d: no preceding 'start'",
                    label, page,
                )
            elif status == "none" and current_start is not None:
                regions.append(_make_region(label, current_start, current_end, doc))
                current_start = None
                current_end = None

        if current_start is not None:
            regions.append(_make_region(label, current_start, current_end, doc))

    return regions


def _make_region(
    label: str,
    page_start: int,
    page_end: int,
    doc: ParsedDocument,
) -> ClassifiedRegion:
    block_ids = [
        b.id
        for b in sorted(
            (b for b in doc.blocks if page_start <= b.page_index <= page_end),
            key=lambda b: (b.page_index, b.reading_order or 0),
        )
    ]
    return ClassifiedRegion(
        label=label,
        page_start=page_start,
        page_end=page_end,
        block_ids=block_ids,
    )
