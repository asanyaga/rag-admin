"""Docling runner — local PDF parsing with semaphore-bounded concurrency."""
from __future__ import annotations

import asyncio
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.cdm.adapters.base import SourceMeta
from app.cdm.adapters.docling import DoclingAdapter
from app.cdm.models import ParsedDocument, ParserKind
from app.cdm.source import ParseRun, ParseRunStatus, SourceDocument
from app.services.parsing.errors import DoclingRunError

# Cap concurrent docling jobs to 1 — docling is memory-intensive and will
# freeze the process if multiple heavy documents run simultaneously.
_DOCLING_SEMAPHORE = asyncio.Semaphore(1)


def _split_pdf(file_path: str, batch_size: int) -> Tuple[List[Path], bool]:
    """Split a PDF into page-range batches.

    Returns (paths, created_temp_files). If the PDF fits in one batch,
    returns ([Path(file_path)], False) — no temp files created.
    """
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(file_path)
    total_pages = len(reader.pages)

    if total_pages <= batch_size:
        return [Path(file_path)], False

    batch_paths: List[Path] = []
    for start in range(0, total_pages, batch_size):
        end = min(start + batch_size, total_pages)
        writer = PdfWriter()
        for page_num in range(start, end):
            writer.add_page(reader.pages[page_num])

        tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        with open(tmp.name, "wb") as f:
            writer.write(f)
        batch_paths.append(Path(tmp.name))

    return batch_paths, True


def _merge_fragments(fragments: List[ParsedDocument]) -> ParsedDocument:
    """Merge CDM fragments from page batches into one ParsedDocument."""
    if len(fragments) == 1:
        return fragments[0]

    pages = [p for f in fragments for p in f.pages]
    blocks = [b for f in fragments for b in f.blocks]
    text_parts = [f.full_text for f in fragments if f.full_text]
    md_parts = [f.full_markdown for f in fragments if f.full_markdown]

    first = fragments[0]
    return ParsedDocument(
        id=first.id,
        source_document_id=first.source_document_id,
        parse_run_id=first.parse_run_id,
        source_filename=first.source_filename,
        page_count=len(pages),
        pages=pages,
        blocks=blocks,
        full_text="\n\n".join(text_parts) or None,
        full_markdown="\n\n".join(md_parts) or None,
    )


def _convert(file_path: Path, config: Dict[str, Any]) -> Any:
    """Synchronous docling conversion — runs in a thread via asyncio.to_thread."""
    from docling.document_converter import DocumentConverter
    converter = DocumentConverter()
    return converter.convert(str(file_path))


async def run_docling(
    *,
    source: SourceDocument,
    file_path: str,
    representation_kind: str,
    config: Dict[str, Any],
    client: Any,  # unused — docling is in-process
    parse_run_id: Optional[str] = None,
) -> Tuple[ParseRun, ParsedDocument]:
    run_id = parse_run_id or str(uuid.uuid4())
    started_at = datetime.now(timezone.utc)
    t0 = time.perf_counter()
    batch_size = config.get("page_batch_size", 20)

    try:
        batch_paths, is_temp = _split_pdf(file_path, batch_size)
    except Exception as exc:
        finished_at = datetime.now(timezone.utc)
        duration_ms = int((time.perf_counter() - t0) * 1000)
        failed = ParseRun(
            id=run_id,
            source_document_id=source.id,
            parser=ParserKind.DOCLING,
            representation_kind=representation_kind,
            config=config,
            status=ParseRunStatus.FAILED,
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=duration_ms,
            error=f"PDF split failed: {exc}",
        )
        raise DoclingRunError(f"PDF split failed: {exc}", run=failed) from exc

    adapter = DoclingAdapter()
    fragments: List[ParsedDocument] = []
    raw_docs: List[Any] = []

    try:
        for i, batch_path in enumerate(batch_paths):
            page_offset = i * batch_size
            source_meta = SourceMeta(
                source_document_id=source.id,
                parse_run_id=run_id,
                filename=source.filename,
                sha256=source.sha256,
            )
            async with _DOCLING_SEMAPHORE:
                result = await asyncio.to_thread(_convert, batch_path, config)
            raw_docs.append(result.document)
            fragment = adapter.adapt(result.document, source_meta, page_offset=page_offset)
            fragments.append(fragment)
    except Exception as exc:
        finished_at = datetime.now(timezone.utc)
        duration_ms = int((time.perf_counter() - t0) * 1000)
        failed = ParseRun(
            id=run_id,
            source_document_id=source.id,
            parser=ParserKind.DOCLING,
            representation_kind=representation_kind,
            config=config,
            status=ParseRunStatus.FAILED,
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=duration_ms,
            error=f"{type(exc).__name__}: {exc}",
        )
        raise DoclingRunError(str(exc), run=failed) from exc
    finally:
        if is_temp:
            for tmp_path in batch_paths:
                tmp_path.unlink(missing_ok=True)

    finished_at = datetime.now(timezone.utc)
    duration_ms = int((time.perf_counter() - t0) * 1000)
    merged = _merge_fragments(fragments)

    raw_payload: Optional[Dict[str, Any]] = None
    try:
        if len(raw_docs) == 1:
            raw_payload = raw_docs[0].model_dump(mode="json")
        else:
            raw_payload = {
                "batch_count": len(raw_docs),
                "batches": [doc.model_dump(mode="json") for doc in raw_docs],
            }
    except Exception:
        pass

    run = ParseRun(
        id=run_id,
        source_document_id=source.id,
        parser=ParserKind.DOCLING,
        representation_kind=representation_kind,
        config=config,
        status=ParseRunStatus.SUCCEEDED,
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=duration_ms,
        raw_payload=raw_payload,
    )
    return run, merged
