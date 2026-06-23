"""Tests for docling_runner: _split_pdf, _merge_fragments, run_docling."""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.cdm.adapters.base import SourceMeta
from app.cdm.adapters.docling import DoclingAdapter
from app.cdm.models import ParserKind
from app.cdm.source import ParseRunStatus, SourceDocument


# ── Shared helpers ────────────────────────────────────────────────────────────

def _make_minimal_pdf(path: Path, num_pages: int) -> None:
    from pypdf import PdfWriter
    writer = PdfWriter()
    for _ in range(num_pages):
        writer.add_blank_page(width=595, height=842)
    with open(path, "wb") as f:
        writer.write(f)


def _source() -> SourceDocument:
    return SourceDocument(
        id=str(uuid.uuid4()),
        sha256="c" * 64,
        filename="test.pdf",
        storage_uri="local://test.pdf",
        created_at=datetime.now(timezone.utc),
    )


def _fake_conversion_result(page_count: int = 1):
    def _fake_page_item():
        return SimpleNamespace(size=SimpleNamespace(width=595.0, height=842.0))

    def _fake_text(text, page_no):
        bbox = SimpleNamespace(l=0.0, t=800.0, r=595.0, b=750.0, coord_origin="BOTTOMLEFT")
        prov = SimpleNamespace(page_no=page_no, bbox=bbox)
        return SimpleNamespace(
            label=SimpleNamespace(value="text"),
            text=text,
            prov=[prov],
            export_to_markdown=lambda: text,
        )

    pages = {i + 1: _fake_page_item() for i in range(page_count)}
    items = [_fake_text(f"Content page {i + 1}", i + 1) for i in range(page_count)]
    items_with_level = [(item, 0) for item in items]
    full_md = "\n\n".join(f"Content page {i + 1}" for i in range(page_count))

    doc = SimpleNamespace(
        pages=pages,
        iterate_items=lambda: iter(items_with_level),
        export_to_markdown=lambda: full_md,
    )
    return SimpleNamespace(document=doc)


def _make_fragment(page_offset: int, page_count: int):
    """Build a minimal ParsedDocument fragment via DoclingAdapter."""
    def _fake_page_item():
        return SimpleNamespace(size=SimpleNamespace(width=595.0, height=842.0))

    def _fake_text(text, page_no):
        bbox = SimpleNamespace(l=0.0, t=800.0, r=595.0, b=750.0, coord_origin="BOTTOMLEFT")
        prov = SimpleNamespace(page_no=page_no, bbox=bbox)
        return SimpleNamespace(
            label=SimpleNamespace(value="text"),
            text=text,
            prov=[prov],
            export_to_markdown=lambda: text,
        )

    # page_no is batch-relative (docling always starts at 1 within a batch file)
    pages = {i + 1: _fake_page_item() for i in range(page_count)}
    items = [_fake_text(f"Page {page_offset + i}", i + 1) for i in range(page_count)]
    items_with_level = [(item, 0) for item in items]
    full_md = "\n\n".join(f"Page {page_offset + i}" for i in range(page_count))

    raw = SimpleNamespace(
        pages=pages,
        iterate_items=lambda: iter(items_with_level),
        export_to_markdown=lambda: full_md,
    )
    meta = SourceMeta(
        source_document_id="merge-test-src",
        parse_run_id="merge-test-run",
        filename="test.pdf",
        sha256="0" * 64,
    )
    return DoclingAdapter().adapt(raw, meta, page_offset=page_offset)


# ── _split_pdf tests ──────────────────────────────────────────────────────────

def test_split_pdf_no_split_when_under_batch_size(tmp_path):
    from app.services.parsing.docling_runner import _split_pdf
    pdf = tmp_path / "small.pdf"
    _make_minimal_pdf(pdf, num_pages=5)
    paths, is_temp = _split_pdf(str(pdf), batch_size=20)
    assert len(paths) == 1
    assert str(paths[0]) == str(pdf)
    assert is_temp is False


def test_split_pdf_exact_batch_size_no_split(tmp_path):
    from app.services.parsing.docling_runner import _split_pdf
    pdf = tmp_path / "exact.pdf"
    _make_minimal_pdf(pdf, num_pages=20)
    paths, is_temp = _split_pdf(str(pdf), batch_size=20)
    assert len(paths) == 1
    assert is_temp is False


def test_split_pdf_creates_correct_batch_count(tmp_path):
    from app.services.parsing.docling_runner import _split_pdf
    pdf = tmp_path / "large.pdf"
    _make_minimal_pdf(pdf, num_pages=45)
    paths, is_temp = _split_pdf(str(pdf), batch_size=20)
    assert len(paths) == 3  # 20 + 20 + 5
    assert is_temp is True
    assert all(p.exists() for p in paths)
    for p in paths:
        p.unlink(missing_ok=True)


def test_split_pdf_batch_page_counts(tmp_path):
    from pypdf import PdfReader
    from app.services.parsing.docling_runner import _split_pdf
    pdf = tmp_path / "counted.pdf"
    _make_minimal_pdf(pdf, num_pages=45)
    paths, _ = _split_pdf(str(pdf), batch_size=20)
    page_counts = [len(PdfReader(str(p)).pages) for p in paths]
    assert page_counts == [20, 20, 5]
    for p in paths:
        p.unlink(missing_ok=True)


def test_split_pdf_temp_files_are_valid_pdfs(tmp_path):
    from pypdf import PdfReader
    from app.services.parsing.docling_runner import _split_pdf
    pdf = tmp_path / "multi.pdf"
    _make_minimal_pdf(pdf, num_pages=25)
    paths, is_temp = _split_pdf(str(pdf), batch_size=20)
    assert is_temp is True
    for p in paths:
        reader = PdfReader(str(p))
        assert len(reader.pages) > 0
        p.unlink(missing_ok=True)


# ── _merge_fragments tests ────────────────────────────────────────────────────

def test_merge_single_fragment_returns_it():
    from app.services.parsing.docling_runner import _merge_fragments
    frag = _make_fragment(page_offset=0, page_count=3)
    merged = _merge_fragments([frag])
    assert merged is frag


def test_merge_two_fragments_total_page_count():
    from app.services.parsing.docling_runner import _merge_fragments
    f1 = _make_fragment(page_offset=0, page_count=20)
    f2 = _make_fragment(page_offset=20, page_count=5)
    merged = _merge_fragments([f1, f2])
    assert merged.page_count == 25


def test_merge_page_indexes_are_continuous():
    from app.services.parsing.docling_runner import _merge_fragments
    f1 = _make_fragment(page_offset=0, page_count=3)
    f2 = _make_fragment(page_offset=3, page_count=3)
    merged = _merge_fragments([f1, f2])
    page_indexes = [p.index for p in merged.pages]
    assert page_indexes == list(range(6))


def test_merge_block_count_is_sum():
    from app.services.parsing.docling_runner import _merge_fragments
    f1 = _make_fragment(page_offset=0, page_count=2)
    f2 = _make_fragment(page_offset=2, page_count=2)
    merged = _merge_fragments([f1, f2])
    assert len(merged.blocks) == len(f1.blocks) + len(f2.blocks)


def test_merge_full_text_concatenated():
    from app.services.parsing.docling_runner import _merge_fragments
    f1 = _make_fragment(page_offset=0, page_count=1)
    f2 = _make_fragment(page_offset=1, page_count=1)
    merged = _merge_fragments([f1, f2])
    assert f1.full_text in merged.full_text
    assert f2.full_text in merged.full_text


# ── run_docling tests ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_docling_success(tmp_path):
    from app.services.parsing.docling_runner import run_docling
    pdf = tmp_path / "test.pdf"
    _make_minimal_pdf(pdf, num_pages=3)
    src = _source()

    with patch(
        "app.services.parsing.docling_runner._convert",
        return_value=_fake_conversion_result(page_count=3),
    ):
        run, doc = await run_docling(
            source=src,
            file_path=str(pdf),
            representation_kind="extract_rich",
            config={"parser": "docling"},
            client=None,
        )

    assert run.status == ParseRunStatus.SUCCEEDED
    assert run.parser == ParserKind.DOCLING
    assert run.duration_ms is not None and run.duration_ms >= 0
    assert doc is not None
    assert doc.source_document_id == src.id
    assert doc.page_count == 3


@pytest.mark.asyncio
async def test_run_docling_failure_raises_docling_run_error(tmp_path):
    from app.services.parsing.errors import DoclingRunError
    from app.services.parsing.docling_runner import run_docling
    pdf = tmp_path / "test.pdf"
    _make_minimal_pdf(pdf, num_pages=1)
    src = _source()

    with patch(
        "app.services.parsing.docling_runner._convert",
        side_effect=RuntimeError("docling crashed"),
    ):
        with pytest.raises(DoclingRunError) as exc_info:
            await run_docling(
                source=src,
                file_path=str(pdf),
                representation_kind="extract_rich",
                config={"parser": "docling"},
                client=None,
            )

    err = exc_info.value
    assert err.run.status == ParseRunStatus.FAILED
    assert err.run.parser == ParserKind.DOCLING
    assert "docling crashed" in err.run.error


@pytest.mark.asyncio
async def test_run_docling_temp_files_cleaned_up_on_error(tmp_path):
    from app.services.parsing.errors import DoclingRunError
    from app.services.parsing.docling_runner import run_docling
    pdf = tmp_path / "large.pdf"
    _make_minimal_pdf(pdf, num_pages=25)
    src = _source()

    created_temp_paths: list[Path] = []
    import app.services.parsing.docling_runner as runner_mod
    original_split = runner_mod._split_pdf

    def capturing_split(file_path, batch_size):
        paths, is_temp = original_split(file_path, batch_size)
        if is_temp:
            created_temp_paths.extend(paths)
        return paths, is_temp

    with patch("app.services.parsing.docling_runner._split_pdf", side_effect=capturing_split):
        with patch(
            "app.services.parsing.docling_runner._convert",
            side_effect=RuntimeError("crash"),
        ):
            with pytest.raises(DoclingRunError):
                await run_docling(
                    source=src,
                    file_path=str(pdf),
                    representation_kind="extract_rich",
                    config={"parser": "docling", "page_batch_size": 20},
                    client=None,
                )

    for p in created_temp_paths:
        assert not p.exists(), f"Temp file not cleaned up: {p}"


def test_docling_semaphore_initialized_with_one_slot():
    from app.services.parsing.docling_runner import _DOCLING_SEMAPHORE
    assert not _DOCLING_SEMAPHORE.locked()


def test_docling_registered_in_runners():
    from app.services.parsing import parsing_service
    assert ParserKind.DOCLING in parsing_service._RUNNERS
