"""Drives docling's own pipelines: convert → DoclingAdapter → ParseRun + CDM.

Docling is opinionated end-to-end — layout, OCR, and table structure all come
out of one conversion pass — so this runner configures it and gets out of the
way. Composition of independent engines is the custom pipeline's job.

Two constraints shape the code:

* **Memory.** Conversions are serialized by a module-level semaphore and large PDFs
  are split into page batches, because docling holds whole-page renderings and
  model state for the pages in flight.
* **The event loop.** Conversion is CPU-bound and multi-second; every call is
  offloaded via `asyncio.to_thread` so a parse never blocks the API.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import tempfile
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.cdm.adapters.base import SourceMeta
from app.cdm.adapters.docling import DoclingAdapter
from app.cdm.models import ParsedDocument, ParserKind
from app.cdm.source import ParseRun, ParseRunStatus, SourceDocument
from app.services.parsing.docling_config import DoclingConfig
from app.services.parsing.errors import DoclingRunError

logger = logging.getLogger(__name__)

#: Docling is memory-hungry; only one conversion at a time. This is held around
#: the offload rather than inside `_convert_batch`, so the guarantee belongs to
#: the runner's orchestration and does not depend on the leaf call's internals.
#: A semaphore, not a threading lock: the waiters are coroutines, and blocking
#: the event loop to wait for a multi-second conversion is exactly the failure
#: mode the offload exists to prevent. Fixed at 1 for now — it becomes a real
#: global constraint once parsing moves to worker processes behind the queue.
_CONVERT_SEMAPHORE = asyncio.Semaphore(1)

#: Built converters keyed by their options hash. Building one initializes the
#: layout/OCR/table models, so rebuilding per batch (as the old runner did) is
#: pure waste.
_CONVERTERS: Dict[str, Any] = {}
_CONVERTERS_LOCK = threading.Lock()


def clear_converter_cache() -> None:
    """Drop cached converters. Exposed for tests."""
    with _CONVERTERS_LOCK:
        _CONVERTERS.clear()


def _build_converter(pipeline_options: Any, backend: str) -> Any:
    """Construct docling's DocumentConverter. Separate for cacheability and so
    tests can stub the expensive part."""
    from docling.backend.image_backend import ImageDocumentBackend
    from docling.datamodel.base_models import InputFormat
    from docling.document_converter import (
        DocumentConverter,
        ImageFormatOption,
        PdfFormatOption,
    )

    return DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_options=pipeline_options, backend=_pdf_backend(backend)),
            # Images run the same pipeline but need their own backend — the PDF
            # backends do not decode bitmaps.
            InputFormat.IMAGE: ImageFormatOption(
                pipeline_options=pipeline_options, backend=ImageDocumentBackend),
        }
    )


def _pdf_backend(name: str) -> Any:
    from docling.backend.docling_parse_v2_backend import DoclingParseV2DocumentBackend
    from docling.backend.docling_parse_v4_backend import DoclingParseV4DocumentBackend
    from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend

    return {
        "docling_parse_v4": DoclingParseV4DocumentBackend,
        "docling_parse_v2": DoclingParseV2DocumentBackend,
        "pypdfium2": PyPdfiumDocumentBackend,
    }[name]


def _converter_for(cfg: DoclingConfig) -> Any:
    """Cache key covers everything docling sees — deliberately not
    page_batch_size, which is ours and must not fragment the cache."""
    identity = cfg.model_dump(mode="json", exclude={"page_batch_size"})
    key = hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()

    with _CONVERTERS_LOCK:
        converter = _CONVERTERS.get(key)
        if converter is None:
            converter = _build_converter(cfg.to_pipeline_options(), cfg.backend.value)
            _CONVERTERS[key] = converter
        return converter


def _convert_batch(converter: Any, path: Path) -> Any:
    """The heavy call. Returns a DoclingDocument."""
    return converter.convert(str(path)).document


def _split_pages(pdf_path: Path, batch_size: int) -> List[Tuple[Path, int, int]]:
    """Split into (batch_path, page_offset, page_count).

    One batch => the original file, so the common case writes nothing to disk.
    page_count is carried so a failed batch can report the pages it actually
    covered rather than assuming every batch is full-size.
    """
    from pypdf import PdfReader, PdfWriter

    try:
        reader = PdfReader(str(pdf_path))
        total = len(reader.pages)
    except Exception:  # noqa: BLE001 — images and unreadable PDFs convert whole
        return [(pdf_path, 0, 0)]

    if total <= batch_size:
        return [(pdf_path, 0, total)]

    batches: List[Tuple[Path, int, int]] = []
    for start in range(0, total, batch_size):
        end = min(start + batch_size, total)
        writer = PdfWriter()
        for i in range(start, end):
            writer.add_page(reader.pages[i])
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            writer.write(tmp)
        batches.append((Path(tmp.name), start, end - start))
    return batches


async def run_docling(
    *,
    source: SourceDocument,
    file_path: str,
    representation_kind: str,
    config: Dict[str, Any],
    client: Any = None,
    parse_run_id: Optional[str] = None,
) -> Tuple[ParseRun, ParsedDocument]:
    run_id = parse_run_id or str(uuid.uuid4())
    started_at = datetime.now(timezone.utc)
    t0 = time.perf_counter()

    def _fail(exc: Exception, message: Optional[str] = None) -> DoclingRunError:
        failed = ParseRun(
            id=run_id,
            source_document_id=source.id,
            parser=ParserKind.DOCLING,
            representation_kind=representation_kind,
            config=config,
            status=ParseRunStatus.FAILED,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
            duration_ms=int((time.perf_counter() - t0) * 1000),
            error=message or f"{type(exc).__name__}: {exc}",
        )
        return DoclingRunError(message or f"Docling parse failed: {exc}", run=failed)

    try:
        cfg = DoclingConfig.from_parse_config(config)
    except Exception as exc:  # noqa: BLE001
        raise _fail(exc, f"Invalid docling config: {exc}") from exc

    try:
        converter = _converter_for(cfg)
    except ImportError as exc:
        raise _fail(exc, "docling is not installed or failed to load") from exc
    except Exception as exc:  # noqa: BLE001
        raise _fail(exc) from exc

    pdf_path = Path(file_path)
    batches = _split_pages(pdf_path, cfg.page_batch_size)
    made_temp = any(path != pdf_path for path, _, _ in batches)

    converted: List[Tuple[Any, int]] = []
    warnings: List[str] = []
    failed_pages: List[int] = []

    try:
        for batch_path, page_offset, page_count in batches:
            try:
                async with _CONVERT_SEMAPHORE:
                    doc = await asyncio.to_thread(_convert_batch, converter, batch_path)
            except Exception as exc:  # noqa: BLE001 — one bad batch must not
                # lose the rest of the document; record it and carry on.
                logger.warning("docling: batch at page %s failed: %s", page_offset, exc)
                covered = list(range(page_offset, page_offset + max(page_count, 1)))
                warnings.append(
                    f"pages {covered[0]}-{covered[-1]}: {type(exc).__name__}: {exc}"
                )
                failed_pages.extend(covered)
                continue
            converted.append((doc, page_offset))
    finally:
        if made_temp:
            for batch_path, _, _ in batches:
                if batch_path != pdf_path:
                    Path(batch_path).unlink(missing_ok=True)

    if not converted:
        raise _fail(
            RuntimeError("all batches failed"),
            "Docling parse failed: " + ("; ".join(warnings) or "no pages converted"),
        )

    try:
        raw_payload = _serialize(converted)
    except Exception as exc:  # noqa: BLE001 — provenance is nice to have, not
        # worth failing a good parse over.
        logger.warning("docling: raw serialization failed: %s", exc)
        raw_payload = None
        warnings.append(f"raw payload unavailable: {type(exc).__name__}: {exc}")

    run = ParseRun(
        id=run_id,
        source_document_id=source.id,
        parser=ParserKind.DOCLING,
        representation_kind=representation_kind,
        config=config,
        status=ParseRunStatus.SUCCEEDED,
        started_at=started_at,
        finished_at=datetime.now(timezone.utc),
        duration_ms=int((time.perf_counter() - t0) * 1000),
        warnings=warnings,
        failed_pages=failed_pages,
        raw_payload=raw_payload,
    )

    doc = DoclingAdapter().adapt(
        converted,
        SourceMeta(
            source_document_id=source.id,
            parse_run_id=run.id,
            filename=source.filename,
            sha256=source.sha256,
        ),
    )
    return run, doc


def _serialize(converted: List[Tuple[Any, int]]) -> Dict[str, Any]:
    """ParseRun.raw_payload is a dict, so batches are wrapped rather than
    stored as a bare list."""
    return {
        "batches": [
            {"page_offset": offset, "document": json.loads(doc.model_dump_json())}
            for doc, offset in converted
        ]
    }
