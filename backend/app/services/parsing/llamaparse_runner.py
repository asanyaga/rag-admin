"""Drives LlamaParse end-to-end: SDK call → ParseRun + ParsedDocument."""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from app.cdm.adapters.base import SourceMeta
from app.cdm.adapters.llamaparse import LlamaParseAdapter
from app.cdm.models import ParsedDocument, ParserKind
from app.cdm.source import ParseRun, ParseRunStatus, SourceDocument
from app.services.parsing.errors import LlamaParseRunError


async def run_llamaparse(
    *,
    source: SourceDocument,
    file_path: str,
    representation_kind: str,
    config: Dict[str, Any],
    client: Any,
    parse_run_id: Optional[str] = None,
) -> Tuple[ParseRun, ParsedDocument]:
    """Parse `file_path` via LlamaParse and adapt to CDM.

    Raises on SDK failure. On success returns (ParseRun, ParsedDocument).
    """
    run_id = parse_run_id or str(uuid.uuid4())
    started_at = datetime.now(timezone.utc)
    t0 = time.perf_counter()

    tier = config.get("tier", "agentic")
    expand = config.get("expand", ["markdown", "text", "items", "metadata"])

    try:
        result = await client.parsing.parse(
            upload_file=file_path,
            tier=tier,
            expand=expand,
        )
    except Exception as exc:
        finished_at = datetime.now(timezone.utc)
        duration_ms = int((time.perf_counter() - t0) * 1000)
        failed = ParseRun(
            id=run_id,
            source_document_id=source.id,
            parser=ParserKind.LLAMAPARSE,
            representation_kind=representation_kind,
            config=config,
            status=ParseRunStatus.FAILED,
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=duration_ms,
            error=f"{type(exc).__name__}: {exc}",
        )
        raise LlamaParseRunError(f"LlamaParse failed: {exc}", run=failed) from exc

    raw = result.model_dump()
    finished_at = datetime.now(timezone.utc)
    duration_ms = int((time.perf_counter() - t0) * 1000)

    jm = raw.get("job_metadata") or {}
    run = ParseRun(
        id=run_id,
        source_document_id=source.id,
        parser=ParserKind.LLAMAPARSE,
        representation_kind=representation_kind,
        config=config,
        status=ParseRunStatus.SUCCEEDED,
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=duration_ms,
        input_tokens=jm.get("pdf-inputTokens"),
        output_tokens=jm.get("pdf-outputTokens"),
        provider_refs={"llamaparse_job_id": jm.get("job_id")} if jm.get("job_id") else {},
    )

    adapter = LlamaParseAdapter()
    doc = adapter.adapt(raw, SourceMeta(
        source_document_id=source.id,
        parse_run_id=run.id,
        filename=source.filename,
        sha256=source.sha256,
    ))
    return run, doc
