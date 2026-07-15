"""End-to-end docling via the custom pipeline. Skipped where docling is absent."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

docling = pytest.importorskip("docling")  # skip whole module if not installed

import fitz

from app.cdm.source import ParseRunStatus, SourceDocument
from app.services.parsing.custom_pipeline_runner import run_custom_pipeline


def _two_column_pdf(path):
    d = fitz.open()
    page = d.new_page(width=595, height=842)
    # Left column then right column — reading order must be L-col then R-col,
    # which a naive (y0, x0) sort interleaves incorrectly.
    for i, y in enumerate(range(120, 400, 40)):
        page.insert_text(fitz.Point(72, y), f"Left line {i}", fontsize=11)
    for i, y in enumerate(range(120, 400, 40)):
        page.insert_text(fitz.Point(340, y), f"Right line {i}", fontsize=11)
    d.save(str(path)); d.close()


def _source():
    return SourceDocument(id="src-1", sha256="b" * 64, filename="cols.pdf",
                          mime_type="application/pdf", byte_size=1,
                          created_at=datetime.now(timezone.utc))


_DOCLING_CONFIG = {"tools": {"docling": {"tool": "docling", "config": {}}},
                   "capabilities": {"layout_analysis": "docling"}}


@pytest.mark.asyncio
async def test_docling_reading_order_is_column_aware(tmp_path):
    pdf = tmp_path / "cols.pdf"; _two_column_pdf(pdf)
    _, parsed = await run_custom_pipeline(
        source=_source(), file_path=str(pdf), representation_kind="extract_rich",
        config=_DOCLING_CONFIG, client=None)
    text = parsed.full_text
    # All left-column lines precede all right-column lines in reading order.
    assert text.index("Left line 0") < text.index("Right line 0")
    assert text.index("Left line 3") < text.index("Right line 0")


@pytest.mark.asyncio
async def test_docling_run_succeeds_and_populates_blocks(tmp_path):
    pdf = tmp_path / "cols.pdf"; _two_column_pdf(pdf)
    run, parsed = await run_custom_pipeline(
        source=_source(), file_path=str(pdf), representation_kind="extract_rich",
        config=_DOCLING_CONFIG, client=None)
    assert run.status == ParseRunStatus.SUCCEEDED
    assert len(parsed.blocks) > 0
    assert all(b.id.startswith("src-1:") for b in parsed.blocks)
