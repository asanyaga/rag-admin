"""Acceptance test for OCR reconciliation.

On a page with a native text layer plus an image containing text, OCR runs
wholesale; the merger keeps native text and OCR-over-image, and drops OCR that
duplicates native text.
"""
import shutil
from datetime import datetime, timezone

import fitz
import pytest

from app.cdm.source import ParseRunStatus, SourceDocument
from app.services.parsing.custom_pipeline_runner import run_custom_pipeline


def _tesseract_available() -> bool:
    return shutil.which("tesseract") is not None


def _source() -> SourceDocument:
    return SourceDocument(id="src-ocr", sha256="c" * 64, filename="mixed.pdf",
                          mime_type="application/pdf", byte_size=1,
                          created_at=datetime.now(timezone.utc))


def _mixed_pdf(tmp_path):
    """Native text at the top; an image of text (rendered separately) at the
    bottom with no native text under it."""
    label = fitz.open(); lp = label.new_page(width=300, height=100)
    lp.insert_text((20, 70), "LOGO", fontsize=64)
    img_bytes = lp.get_pixmap(matrix=fitz.Matrix(2, 2)).tobytes("png")
    label.close()

    doc = fitz.open(); page = doc.new_page(width=612, height=400)
    page.insert_text((40, 60), "Native invoice heading", fontsize=18)
    page.insert_image(fitz.Rect(40, 200, 340, 300), stream=img_bytes)
    p = tmp_path / "mixed.pdf"; doc.save(str(p)); doc.close()
    return p


@pytest.mark.skipif(not _tesseract_available(), reason="tesseract binary not installed")
@pytest.mark.asyncio
async def test_ocr_keeps_image_text_and_drops_ocr_over_native(tmp_path):
    config = {
        "tools": {"fitz": {"tool": "fitz", "config": {}},
                  "ocr": {"tool": "tesseract", "config": {"pages": "all", "dpi": 200}}},
        "capabilities": {"text_extraction": "fitz", "text_ocr": "ocr"},
    }
    run, parsed = await run_custom_pipeline(
        source=_source(), file_path=str(_mixed_pdf(tmp_path)),
        representation_kind="extract_rich", config=config, client=None)

    assert run.status == ParseRunStatus.SUCCEEDED
    all_text = " ".join(b.text for b in parsed.blocks if b.text)
    # Native heading survives (exact), and the image's text is recovered by OCR.
    assert "Native invoice heading" in all_text
    assert "LOGO" in all_text.upper()

    # The surviving native heading is a native block, not an OCR block.
    heading = next(b for b in parsed.blocks if "Native invoice heading" in (b.text or ""))
    assert heading.native_type != "ocr_text"

    # Any OCR block that duplicated native text was evicted, not deleted silently.
    for rec in run.raw_payload["evicted"]:
        assert rec["reason"] == "covered_by"
