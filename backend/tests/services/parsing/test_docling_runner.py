"""Tests for docling_runner — batching, converter caching, offload, failures.

Docling itself is stubbed throughout; the real conversion is exercised in
test_docling_pipeline_integration.py.
"""
from __future__ import annotations

import asyncio
import json
import threading
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.cdm.models import ParserKind
from app.cdm.source import ParseRunStatus, SourceDocument
from app.services.parsing.errors import DoclingRunError

FIXTURE = (Path(__file__).parents[2] / "cdm" / "adapters" / "fixtures"
           / "docling_simple_text.json")


@pytest.fixture
def source():
    return SourceDocument(
        id="src-1", sha256="abc123", filename="simple_text.pdf",
        mime_type="application/pdf", byte_size=1024,
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def pdf_path():
    return str(Path(__file__).parents[1].parent / "cdm" / "adapters"
               / "custom_pipeline" / "fixtures" / "simple_text.pdf")


@pytest.fixture
def docling_doc():
    from docling_core.types.doc import DoclingDocument
    return DoclingDocument.model_validate(json.loads(FIXTURE.read_text(encoding="utf-8")))


@pytest.fixture(autouse=True)
def clear_converter_cache():
    from app.services.parsing import docling_runner
    docling_runner.clear_converter_cache()
    yield
    docling_runner.clear_converter_cache()


async def _run(source, pdf_path, config=None, **kw):
    from app.services.parsing.docling_runner import run_docling
    return await run_docling(
        source=source, file_path=pdf_path, representation_kind="cdm",
        config=config or {}, **kw,
    )


# ── Happy path ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_successful_run_produces_run_and_document(
    monkeypatch, source, pdf_path, docling_doc):
    from app.services.parsing import docling_runner
    monkeypatch.setattr(docling_runner, "_convert_batch",
                        lambda converter, path: docling_doc)

    run, doc = await _run(source, pdf_path, parse_run_id="run-1")

    assert run.id == "run-1"
    assert run.parser is ParserKind.DOCLING
    assert run.status is ParseRunStatus.SUCCEEDED
    assert run.source_document_id == "src-1"
    assert run.duration_ms is not None and run.duration_ms >= 0
    assert doc.parse_run_id == "run-1"
    assert doc.page_count == 2


@pytest.mark.asyncio
async def test_config_is_recorded_on_the_run(monkeypatch, source, pdf_path, docling_doc):
    from app.services.parsing import docling_runner
    monkeypatch.setattr(docling_runner, "_convert_batch",
                        lambda converter, path: docling_doc)

    config = {"do_ocr": False, "do_table_structure": False}
    run, _ = await _run(source, pdf_path, config=config)
    assert run.config == config


@pytest.mark.asyncio
async def test_raw_payload_is_serializable(monkeypatch, source, pdf_path, docling_doc):
    from app.services.parsing import docling_runner
    monkeypatch.setattr(docling_runner, "_convert_batch",
                        lambda converter, path: docling_doc)

    run, _ = await _run(source, pdf_path)
    assert run.raw_payload is not None
    json.dumps(run.raw_payload)  # must not raise


# ── Batching ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_single_batch_passes_the_original_file(
    monkeypatch, source, pdf_path, docling_doc):
    """A document under the batch size must not be rewritten to a temp file."""
    from app.services.parsing import docling_runner
    seen = []

    def _fake(converter, path):
        seen.append(str(path))
        return docling_doc

    monkeypatch.setattr(docling_runner, "_convert_batch", _fake)
    await _run(source, pdf_path, config={"page_batch_size": 500})
    assert seen == [pdf_path]


@pytest.mark.asyncio
async def test_batches_are_offset_and_temp_files_cleaned(
    monkeypatch, source, pdf_path, docling_doc):
    from app.services.parsing import docling_runner
    seen = []

    def _fake(converter, path):
        seen.append(Path(path))
        return docling_doc

    monkeypatch.setattr(docling_runner, "_convert_batch", _fake)
    run, doc = await _run(source, pdf_path, config={"page_batch_size": 1})

    assert len(seen) == 2, "2-page fixture at batch size 1 should convert twice"
    assert not any(p.exists() for p in seen), "temp batch files must be cleaned up"
    # each stubbed batch returns the whole 2-page doc, offset by its start page
    assert [p.index for p in doc.pages] == [0, 1, 2]


# ── Converter caching ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_converter_is_reused_across_runs_with_identical_options(
    monkeypatch, source, pdf_path, docling_doc):
    from app.services.parsing import docling_runner
    built = []

    monkeypatch.setattr(docling_runner, "_build_converter",
                        lambda opts, backend: built.append(1) or object())
    monkeypatch.setattr(docling_runner, "_convert_batch",
                        lambda converter, path: docling_doc)

    await _run(source, pdf_path, config={"do_ocr": False})
    await _run(source, pdf_path, config={"do_ocr": False})
    assert len(built) == 1


@pytest.mark.asyncio
async def test_differing_options_build_separate_converters(
    monkeypatch, source, pdf_path, docling_doc):
    from app.services.parsing import docling_runner
    built = []

    monkeypatch.setattr(docling_runner, "_build_converter",
                        lambda opts, backend: built.append(1) or object())
    monkeypatch.setattr(docling_runner, "_convert_batch",
                        lambda converter, path: docling_doc)

    await _run(source, pdf_path, config={"do_ocr": False})
    await _run(source, pdf_path, config={"do_ocr": True})
    assert len(built) == 2


@pytest.mark.asyncio
async def test_page_batch_size_does_not_affect_converter_identity(
    monkeypatch, source, pdf_path, docling_doc):
    """page_batch_size is ours, not docling's — it must not fragment the cache."""
    from app.services.parsing import docling_runner
    built = []

    monkeypatch.setattr(docling_runner, "_build_converter",
                        lambda opts, backend: built.append(1) or object())
    monkeypatch.setattr(docling_runner, "_convert_batch",
                        lambda converter, path: docling_doc)

    await _run(source, pdf_path, config={"page_batch_size": 5})
    await _run(source, pdf_path, config={"page_batch_size": 50})
    assert len(built) == 1


# ── Concurrency ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_conversion_runs_off_the_event_loop(
    monkeypatch, source, pdf_path, docling_doc):
    from app.services.parsing import docling_runner
    threads = []

    def _fake(converter, path):
        threads.append(threading.current_thread().name)
        return docling_doc

    monkeypatch.setattr(docling_runner, "_convert_batch", _fake)
    await _run(source, pdf_path)
    assert threads and all(t != threading.main_thread().name for t in threads)


@pytest.mark.asyncio
async def test_concurrent_runs_serialize(monkeypatch, source, pdf_path, docling_doc):
    """docling is memory-hungry; conversions must not overlap."""
    from app.services.parsing import docling_runner
    active = 0
    peak = 0
    lock = threading.Lock()

    def _fake(converter, path):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        try:
            threading.Event().wait(0.05)
            return docling_doc
        finally:
            with lock:
                active -= 1

    monkeypatch.setattr(docling_runner, "_convert_batch", _fake)
    await asyncio.gather(*(_run(source, pdf_path) for _ in range(3)))
    assert peak == 1


# ── Failure handling ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_one_failed_batch_degrades_to_warnings(
    monkeypatch, source, pdf_path, docling_doc):
    from app.services.parsing import docling_runner
    calls = {"n": 0}

    def _flaky(converter, path):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("page exploded")
        return docling_doc

    monkeypatch.setattr(docling_runner, "_convert_batch", _flaky)
    run, doc = await _run(source, pdf_path, config={"page_batch_size": 1})

    assert run.status is ParseRunStatus.SUCCEEDED
    assert run.warnings and any("exploded" in w for w in run.warnings)
    assert doc.blocks, "the surviving batch must still produce content"


@pytest.mark.asyncio
async def test_every_batch_failing_fails_the_run(monkeypatch, source, pdf_path):
    from app.services.parsing import docling_runner

    def _boom(converter, path):
        raise RuntimeError("docling died")

    monkeypatch.setattr(docling_runner, "_convert_batch", _boom)

    with pytest.raises(DoclingRunError) as exc:
        await _run(source, pdf_path, parse_run_id="run-x")

    failed = exc.value.run
    assert failed.id == "run-x"
    assert failed.status is ParseRunStatus.FAILED
    assert failed.parser is ParserKind.DOCLING
    assert "docling died" in failed.error


@pytest.mark.asyncio
async def test_invalid_config_fails_the_run_with_a_parse_run(source, pdf_path):
    with pytest.raises(DoclingRunError) as exc:
        await _run(source, pdf_path, config={"ocr_options": {"kind": "nope"}})
    assert exc.value.run.status is ParseRunStatus.FAILED


@pytest.mark.asyncio
async def test_missing_docling_install_is_reported_clearly(
    monkeypatch, source, pdf_path):
    from app.services.parsing import docling_runner

    def _no_docling(opts, backend):
        raise ImportError("No module named 'docling'")

    monkeypatch.setattr(docling_runner, "_build_converter", _no_docling)

    with pytest.raises(DoclingRunError, match="docling is not installed"):
        await _run(source, pdf_path)


@pytest.mark.asyncio
async def test_failed_pages_records_the_pages_actually_covered(
    monkeypatch, source, pdf_path, docling_doc):
    """The batch is a page range, so a failure must report that range — not the
    batch offset alone, and not a full-size range when the batch is short."""
    from app.services.parsing import docling_runner

    def _boom_on_first(converter, path):
        if not getattr(_boom_on_first, "seen", False):
            _boom_on_first.seen = True
            raise RuntimeError("page exploded")
        return docling_doc

    monkeypatch.setattr(docling_runner, "_convert_batch", _boom_on_first)
    run, _ = await _run(source, pdf_path, config={"page_batch_size": 1})

    assert run.status is ParseRunStatus.SUCCEEDED
    assert run.failed_pages == [0]
    assert "pages 0-0" in run.warnings[0]


def test_docling_is_registered_as_a_runner():
    from app.services.parsing.parsing_service import _RUNNERS
    from app.services.parsing.docling_runner import run_docling

    assert _RUNNERS[ParserKind.DOCLING] is run_docling


def test_every_parser_kind_has_a_runner():
    """A ParserKind with no runner fails only at parse time, deep in a task."""
    from app.services.parsing.parsing_service import _RUNNERS

    unregistered = {k.value for k in ParserKind} - {k.value for k in _RUNNERS}
    assert unregistered <= {"liteparse", "unstructured"}, (
        f"unexpected parser kinds without a runner: {unregistered}")


@pytest.mark.asyncio
async def test_runner_accepts_the_config_shape_the_router_actually_sends(
    monkeypatch, source, pdf_path, docling_doc):
    """The router injects `parser` into parse_cfg before dispatch, so the runner
    receives it whether it wants it or not. Validating the raw dict against a
    model with extra="forbid" rejected every real parse run.
    """
    from app.services.parsing import docling_runner
    monkeypatch.setattr(docling_runner, "_convert_batch",
                        lambda converter, path: docling_doc)

    router_config = {"parser": "docling", "do_ocr": False}
    run, doc = await _run(source, pdf_path, config=router_config)

    assert run.status is ParseRunStatus.SUCCEEDED
    # the routing key stays on the persisted run — config_hash depends on it
    assert run.config == router_config


@pytest.mark.asyncio
async def test_representation_kind_in_config_is_also_tolerated(
    monkeypatch, source, pdf_path, docling_doc):
    from app.services.parsing import docling_runner
    monkeypatch.setattr(docling_runner, "_convert_batch",
                        lambda converter, path: docling_doc)

    run, _ = await _run(source, pdf_path,
                        config={"parser": "docling", "representation_kind": "extract_rich"})
    assert run.status is ParseRunStatus.SUCCEEDED


@pytest.mark.asyncio
async def test_a_genuine_typo_is_still_rejected(monkeypatch, source, pdf_path):
    """Tolerating routing keys must not turn into tolerating everything."""
    with pytest.raises(DoclingRunError, match="Invalid docling config"):
        await _run(source, pdf_path, config={"parser": "docling", "do_ocrr": True})
