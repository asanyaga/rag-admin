"""LlamaParse adapter — maps llama-cloud parsing output to CDM.

Input is the result of ``client.parsing.parse(...)`` after ``.model_dump()``,
i.e. a plain dict with top-level keys controlled by the ``expand`` parameter
(``text``, ``markdown``, ``items``, ``metadata``, ``job_metadata``).
"""
from __future__ import annotations

from typing import Any, ClassVar, Dict, List, Optional, Tuple

from app.cdm.adapters.base import ParserAdapter, SourceMeta
from app.cdm.models import (
    BBox,
    Block,
    BlockRole,
    Page,
    ParsedDocument,
    ParserKind,
    Quality,
)


_ROLE_MAP: Dict[str, BlockRole] = {
    "heading": BlockRole.HEADING,
    "text":    BlockRole.PARAGRAPH,
    "list":    BlockRole.LIST,
    "table":   BlockRole.TABLE,
    "image":   BlockRole.FIGURE,
    "header":  BlockRole.HEADER,
    "footer":  BlockRole.FOOTER,
    "code":    BlockRole.CODE,
    "link":    BlockRole.LINK,
}


def _map_role(native_type: str) -> BlockRole:
    return _ROLE_MAP.get(native_type, BlockRole.OTHER)


def _clamp(v: float) -> float:
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return v


def _pdf_points_to_normalized(
    *, x: float, y: float, w: float, h: float,
    page_width: float, page_height: float,
) -> BBox:
    x0 = _clamp(x / page_width)
    y0 = _clamp(y / page_height)
    x1 = _clamp((x + w) / page_width)
    y1 = _clamp((y + h) / page_height)
    return BBox(
        x0=x0, y0=y0, x1=x1, y1=y1,
        source_space="pdf_points",
        source_coords=(float(x), float(y), float(w), float(h)),
    )


def _union_bbox(bboxes: List[BBox]) -> Optional[BBox]:
    if not bboxes:
        return None
    if len(bboxes) == 1:
        return bboxes[0]
    x0 = min(b.x0 for b in bboxes)
    y0 = min(b.y0 for b in bboxes)
    x1 = max(b.x1 for b in bboxes)
    y1 = max(b.y1 for b in bboxes)
    return BBox(x0=x0, y0=y0, x1=x1, y1=y1)


import uuid

from app.cdm.models import ParsedDocument


def _mint_block_id(source_document_id: str, page_index: int, reading_order: int) -> str:
    return f"{source_document_id}:p{page_index}:b{reading_order}"


def _flatten_pages(value: Any, *, key: str) -> Optional[str]:
    """LlamaParse returns either a string (legacy) or a dict ``{"pages": [{key: ...}]}``
    (current SDK). Normalize both into a single string, joining pages on blank lines.
    """
    if value is None:
        return None
    if isinstance(value, str):
        return value or None
    if isinstance(value, dict):
        pages = value.get("pages") or []
        parts = [str(p.get(key)) for p in pages if p.get(key)]
        return "\n\n".join(parts) or None
    return None


class LlamaParseAdapter:
    parser: ClassVar[ParserKind] = ParserKind.LLAMAPARSE

    def adapt(self, raw: Dict[str, Any], source_meta: SourceMeta) -> ParsedDocument:
        pages_raw: List[Dict[str, Any]] = (raw.get("items") or {}).get("pages") or []
        page_metadata_list: List[Dict[str, Any]] = (raw.get("metadata") or {}).get("pages") or []
        page_metadata_by_number = {pm.get("page_number"): pm for pm in page_metadata_list}

        all_blocks: List[Block] = []
        pages: List[Page] = []

        for page_raw in pages_raw:
            source_page_number: int = page_raw.get("page_number", 1)
            page_index = source_page_number - 1
            page_width = float(page_raw.get("width") or 1.0)
            page_height = float(page_raw.get("height") or 1.0)
            page_items = page_raw.get("items") or []

            page_blocks: List[Block] = []
            reading_order = 0

            def _walk(items: List[Dict[str, Any]], parent_id: Optional[str],
                      depth: int) -> List[str]:
                nonlocal reading_order
                child_ids_out: List[str] = []
                for item in items:
                    block_id = _mint_block_id(source_meta.source_document_id,
                                              page_index, reading_order)
                    reading_order += 1
                    native_type = str(item.get("type", "other"))
                    role = _map_role(native_type)

                    bboxes = []
                    for bb in item.get("bbox") or []:
                        bboxes.append(_pdf_points_to_normalized(
                            x=float(bb.get("x", 0.0)),
                            y=float(bb.get("y", 0.0)),
                            w=float(bb.get("w", 0.0)),
                            h=float(bb.get("h", 0.0)),
                            page_width=page_width,
                            page_height=page_height,
                        ))
                    block_bbox = _union_bbox(bboxes)

                    confidence: Optional[float] = None
                    native_label: Optional[str] = None
                    for bb in item.get("bbox") or []:
                        if confidence is None and "confidence" in bb:
                            confidence = bb.get("confidence")
                        if native_label is None and bb.get("label"):
                            native_label = bb.get("label")

                    quality = Quality(confidence=confidence) if confidence is not None else None

                    parser_extras: Dict[str, Any] = {}
                    if len(bboxes) > 1:
                        parser_extras["bboxes"] = [b.model_dump() for b in bboxes]
                    for bb in item.get("bbox") or []:
                        if "start_index" in bb or "end_index" in bb:
                            parser_extras.setdefault("char_range", []).append({
                                "start": bb.get("start_index"),
                                "end":   bb.get("end_index"),
                            })

                    child_items = item.get("items") or []
                    children_ids = _walk(child_items, parent_id=block_id, depth=depth + 1) \
                        if child_items else []

                    block = Block(
                        id=block_id,
                        role=role,
                        native_type=native_type,
                        native_label=native_label,
                        text=str(item.get("value") or ""),
                        markdown=item.get("md"),
                        page_index=page_index,
                        bbox=block_bbox,
                        reading_order=reading_order - 1,
                        depth=item.get("level") if native_type == "heading" else depth,
                        parent_id=parent_id,
                        children_ids=children_ids,
                        quality=quality,
                        parser_extras=parser_extras,
                    )
                    page_blocks.append(block)
                    child_ids_out.append(block_id)
                return child_ids_out

            _walk(page_items, parent_id=None, depth=0)
            all_blocks.extend(page_blocks)

            pm = page_metadata_by_number.get(source_page_number, {})
            page_quality = (
                Quality(confidence=pm.get("confidence"))
                if pm.get("confidence") is not None else None
            )
            pages.append(Page(
                index=page_index,
                width=page_width,
                height=page_height,
                unit="points",
                rotation=int(pm.get("original_orientation_angle") or 0),
                block_ids=[b.id for b in page_blocks],
                quality=page_quality,
                parser_extras={"source_page_number": source_page_number},
            ))

        full_text = _flatten_pages(raw.get("text"), key="text") or "\n\n".join(
            b.text for b in all_blocks if b.text
        ) or None
        full_markdown = _flatten_pages(raw.get("markdown"), key="markdown") or "\n\n".join(
            b.markdown for b in all_blocks if b.markdown
        ) or None

        return ParsedDocument(
            id=str(uuid.uuid4()),
            source_document_id=source_meta.source_document_id,
            parse_run_id=source_meta.parse_run_id,
            source_filename=source_meta.filename,
            page_count=len(pages),
            pages=pages,
            blocks=all_blocks,
            full_text=full_text,
            full_markdown=full_markdown,
        )
