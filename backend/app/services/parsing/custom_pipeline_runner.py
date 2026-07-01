"""Drives the local tool pipeline end-to-end: tools → merge → CDM + ParseRun."""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from app.cdm.adapters.base import SourceMeta
from app.cdm.adapters.local_pipeline.adapter import LocalPipelineAdapter
from app.cdm.adapters.local_pipeline.config import TABLE_TOOL_IDS, build_pipeline_config
from app.cdm.adapters.local_pipeline.merger import merge
from app.cdm.adapters.local_pipeline.tools.base import ToolResult
from app.cdm.models import ParsedDocument, ParserKind
from app.cdm.source import ParseRun, ParseRunStatus, SourceDocument
from app.services.parsing.errors import LocalPipelineRunError


async def run_local_pipeline(
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

    def _fail(exc: Exception) -> LocalPipelineRunError:
        finished_at = datetime.now(timezone.utc)
        duration_ms = int((time.perf_counter() - t0) * 1000)
        failed = ParseRun(
            id=run_id,
            source_document_id=source.id,
            parser=ParserKind.LOCAL_PIPELINE,
            representation_kind=representation_kind,
            config=config,
            status=ParseRunStatus.FAILED,
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=duration_ms,
            error=f"{type(exc).__name__}: {exc}",
        )
        return LocalPipelineRunError(f"Local pipeline failed: {exc}", run=failed)

    try:
        pdf_path = Path(file_path)

        pipeline = build_pipeline_config(config)

        fitz_tool = next((t for t in pipeline.tools if t.tool_id == "fitz"), None)
        if fitz_tool is None:
            raise ValueError("local pipeline requires a 'fitz' tool")

        fitz_result: ToolResult = fitz_tool.run(pdf_path)
        warnings = list(fitz_result.warnings)

        table_entry = next(
            (e for e in config.get("tools", []) if e.get("tool_id") in TABLE_TOOL_IDS),
            None,
        )
        if table_entry is not None:
            table_pipeline = build_pipeline_config(
                {"tools": [table_entry]}, page_meta=fitz_result.page_meta
            )
            table_tool = table_pipeline.tools[0]
            table_result = table_tool.run(pdf_path)
            warnings.extend(table_result.warnings)
        else:
            table_result = ToolResult(tool_id="none", blocks=[], page_meta={}, raw={})

        merge_result = merge(
            fitz_result,
            table_result,
            source_document_id=source.id,
            eviction_overlap_threshold=pipeline.eviction_overlap_threshold,
        )
    except Exception as exc:  # noqa: BLE001
        raise _fail(exc) from exc

    finished_at = datetime.now(timezone.utc)
    duration_ms = int((time.perf_counter() - t0) * 1000)

    run = ParseRun(
        id=run_id,
        source_document_id=source.id,
        parser=ParserKind.LOCAL_PIPELINE,
        representation_kind=representation_kind,
        config=config,
        status=ParseRunStatus.SUCCEEDED,
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=duration_ms,
        warnings=warnings,
        raw_payload=merge_result.raw_output,
    )

    adapter = LocalPipelineAdapter()
    doc = adapter.adapt(
        {"page_meta": fitz_result.page_meta, "blocks": merge_result.blocks},
        SourceMeta(
            source_document_id=source.id,
            parse_run_id=run.id,
            filename=source.filename,
            sha256=source.sha256,
        ),
    )
    return run, doc
