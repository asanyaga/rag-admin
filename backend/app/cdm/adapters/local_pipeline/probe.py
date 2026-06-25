"""DocumentProbe — standalone PDF classifier using PyMuPDF."""
from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Literal, Optional

import fitz  # pymupdf
from pydantic import BaseModel, ConfigDict


class PageProfile(BaseModel):
    model_config = ConfigDict(frozen=True)

    index: int
    char_count: int
    has_text_layer: bool
    image_count: int
    font_health: Literal["clean", "cid_corrupt", "mixed", "unknown"]
    table_signal: bool
    page_type: Literal["text", "scanned", "mixed", "empty"]


class DocumentProfile(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_document_id: str
    filename: Optional[str]
    page_count: int
    pages: List[PageProfile]
    has_text_layer: bool
    has_scanned_pages: bool
    has_cid_corruption: bool
    table_signal: bool
    recommended_tools: List[str]
    duration_ms: int
    probed_at: datetime


class DocumentProbe:
    """Inspects a PDF and returns a DocumentProfile.

    Uses only PyMuPDF — no network calls, no side effects.
    """

    # Pages below this char count are considered to lack a usable text layer.
    _MIN_TEXT_CHARS = 10
    # Ratio of Unicode private-use area chars that triggers CID corruption flag.
    _CID_THRESHOLD = 0.3
    _CID_WARN_THRESHOLD = 0.05
    # Minimum axis-aligned line/rect drawing items to flag table_signal.
    # A rectangle + at least 2 internal dividers (= a true grid) is the threshold;
    # a single bounding rectangle alone should not signal a table.
    _TABLE_LINE_MIN = 3

    def run(self, pdf_path: Path, source_document_id: str = "") -> DocumentProfile:
        t0 = time.monotonic()
        doc = fitz.open(str(pdf_path))
        try:
            pages = [self._profile_page(doc[i], i) for i in range(len(doc))]
        finally:
            doc.close()

        has_text_layer = any(p.has_text_layer for p in pages)
        has_scanned_pages = any(p.page_type == "scanned" for p in pages)
        has_cid = any(p.font_health in ("cid_corrupt", "mixed") for p in pages)
        table_sig = any(p.table_signal for p in pages)

        return DocumentProfile(
            source_document_id=source_document_id,
            filename=pdf_path.name,
            page_count=len(pages),
            pages=pages,
            has_text_layer=has_text_layer,
            has_scanned_pages=has_scanned_pages,
            has_cid_corruption=has_cid,
            table_signal=table_sig,
            recommended_tools=self._recommend(has_cid, has_scanned_pages, table_sig),
            duration_ms=int((time.monotonic() - t0) * 1000),
            probed_at=datetime.now(tz=timezone.utc),
        )

    def _profile_page(self, page: fitz.Page, index: int) -> PageProfile:
        text = page.get_text("text")
        char_count = len(text.strip())
        has_text = char_count >= self._MIN_TEXT_CHARS
        image_count = len(page.get_images(full=True))
        font_health = self._font_health(text)
        table_signal = self._table_signal(page)

        if not has_text and image_count > 0:
            page_type: Literal["text", "scanned", "mixed", "empty"] = "scanned"
        elif has_text and image_count > 0:
            page_type = "mixed"
        elif has_text:
            page_type = "text"
        else:
            page_type = "empty"

        return PageProfile(
            index=index,
            char_count=char_count,
            has_text_layer=has_text,
            image_count=image_count,
            font_health=font_health,
            table_signal=table_signal,
            page_type=page_type,
        )

    def _font_health(self, text: str) -> Literal["clean", "cid_corrupt", "mixed", "unknown"]:
        if not text.strip():
            return "unknown"
        total = len(text)
        pua = sum(1 for c in text if 0xe000 <= ord(c) <= 0xf8ff)
        ratio = pua / total
        if ratio > self._CID_THRESHOLD:
            return "cid_corrupt"
        if ratio > self._CID_WARN_THRESHOLD:
            return "mixed"
        return "clean"

    def _table_signal(self, page: fitz.Page) -> bool:
        drawings = page.get_drawings()
        line_count = 0
        for path in drawings:
            for item in path.get("items", []):
                if item[0] in ("l", "re"):  # line or rectangle
                    line_count += 1
        return line_count >= self._TABLE_LINE_MIN

    def _recommend(self, has_cid: bool, has_scanned: bool, has_tables: bool) -> List[str]:
        if has_cid or has_scanned:
            tools = ["paddleocr"]
            if has_tables:
                tools.append("paddleocr_pp_structure")
        else:
            tools = ["fitz"]
            if has_tables:
                tools.append("camelot")
        return tools
