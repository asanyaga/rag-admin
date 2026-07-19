"""End-to-end docling via ParserKind.DOCLING. Skipped where docling is absent.

These invoke the real models and are slow (tens of seconds per test); the
stubbed behaviour lives in test_docling_runner.py.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

docling = pytest.importorskip("docling")  # skip whole module if not installed

import fitz

from app.cdm.source import ParseRunStatus, SourceDocument
from app.services.parsing.docling_runner import run_docling

pytestmark = pytest.mark.slow


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


async def _parse(pdf, config=None):
    return await run_docling(
        source=_source(), file_path=str(pdf), representation_kind="extract_rich",
        config=config or {}, client=None)


@pytest.mark.asyncio
async def test_docling_reading_order_is_column_aware(tmp_path):
    """The reason docling exists as a rung: a naive (y0, x0) sort interleaves
    the columns, docling's own reading order does not."""
    pdf = tmp_path / "cols.pdf"; _two_column_pdf(pdf)
    _, parsed = await _parse(pdf)
    text = parsed.full_text
    assert text.index("Left line 0") < text.index("Right line 0")
    assert text.index("Left line 3") < text.index("Right line 0")


@pytest.mark.asyncio
async def test_docling_run_succeeds_and_populates_blocks(tmp_path):
    pdf = tmp_path / "cols.pdf"; _two_column_pdf(pdf)
    run, parsed = await _parse(pdf)
    assert run.status == ParseRunStatus.SUCCEEDED
    assert len(parsed.blocks) > 0
    assert all(b.id.startswith("src-1:") for b in parsed.blocks)
    assert parsed.full_markdown


@pytest.mark.asyncio
async def test_table_mode_changes_the_config_without_breaking_the_run(tmp_path):
    """FAST and ACCURATE must both parse. They are distinct configs, so they
    hash differently and stay separately comparable in the eval harness."""
    from app.services.parsing.parsing_service import _compute_config_hash

    pdf = tmp_path / "cols.pdf"; _two_column_pdf(pdf)
    fast = {"table_structure_options": {"mode": "fast"}}
    accurate = {"table_structure_options": {"mode": "accurate"}}

    run_fast, _ = await _parse(pdf, fast)
    run_accurate, _ = await _parse(pdf, accurate)

    assert run_fast.status == ParseRunStatus.SUCCEEDED
    assert run_accurate.status == ParseRunStatus.SUCCEEDED
    assert _compute_config_hash(fast) != _compute_config_hash(accurate)


@pytest.mark.asyncio
async def test_disabling_ocr_and_tables_still_parses(tmp_path):
    """The cheapest docling config — layout only — must remain a valid rung."""
    pdf = tmp_path / "cols.pdf"; _two_column_pdf(pdf)
    run, parsed = await _parse(pdf, {"do_ocr": False, "do_table_structure": False})
    assert run.status == ParseRunStatus.SUCCEEDED
    assert parsed.blocks
