"""Drives the custom tool pipeline end-to-end: tools → merge → CDM + ParseRun."""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from app.cdm.adapters.base import SourceMeta
from app.cdm.adapters.custom_pipeline.adapter import CustomPipelineAdapter
from app.cdm.adapters.custom_pipeline.capabilities import Capability
from app.cdm.adapters.custom_pipeline.config import build_pipeline_config
from app.cdm.adapters.custom_pipeline.merger import merge
from app.cdm.adapters.custom_pipeline.page_flags import compute_page_flags
from app.cdm.models import ParsedDocument, ParserKind
from app.cdm.source import ParseRun, ParseRunStatus, SourceDocument
from app.services.parsing.errors import CustomPipelineRunError


async def run_custom_pipeline(
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

    def _fail(exc: Exception) -> CustomPipelineRunError:
        finished_at = datetime.now(timezone.utc)
        duration_ms = int((time.perf_counter() - t0) * 1000)
        failed = ParseRun(
            id=run_id,
            source_document_id=source.id,
            parser=ParserKind.CUSTOM_PIPELINE,
            representation_kind=representation_kind,
            config=config,
            status=ParseRunStatus.FAILED,
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=duration_ms,
            error=f"{type(exc).__name__}: {exc}",
        )
        return CustomPipelineRunError(f"Custom pipeline failed: {exc}", run=failed)

    try:
        pdf_path = Path(file_path)

        pipeline = build_pipeline_config(config)
        flags = compute_page_flags(pdf_path, pipeline.page_flags)

        structure_instance = pipeline.for_capability(Capability.LAYOUT_ANALYSIS)
        # build_pipeline_config guarantees this, but fail loudly if it ever does not.
        if structure_instance is None:
            raise ValueError("capability 'layout_analysis' is required")

        structure_result = structure_instance.tool.run(pdf_path, emit=structure_instance.emit)
        results = [structure_result]
        warnings = list(structure_result.warnings)

        # Remaining instances run once each, in the deterministic order
        # build_pipeline_config established, and receive page geometry from the
        # structure (layout_analysis) tool.
        for inst in pipeline.instances:
            if inst is structure_instance:
                continue
            pages = None
            if Capability.TEXT_OCR in inst.emit:
                # OCR is the one capability whose page selection depends on
                # per-page facts; every other tool runs over the whole document.
                pages = inst.tool.select_pages(flags)
            r = inst.tool.run(
                pdf_path, pages=pages, page_meta=structure_result.page_meta, emit=inst.emit)
            results.append(r)
            warnings.extend(r.warnings)

        merge_result = merge(
            results,
            source_document_id=source.id,
            page_flags=flags,
            ocr_prefer=pipeline.ocr_prefer,
            eviction_overlap_threshold=pipeline.eviction_overlap_threshold,
            ocr_eviction_threshold=pipeline.ocr_eviction_threshold,
        )
    except Exception as exc:  # noqa: BLE001
        raise _fail(exc) from exc

    finished_at = datetime.now(timezone.utc)
    duration_ms = int((time.perf_counter() - t0) * 1000)

    run = ParseRun(
        id=run_id,
        source_document_id=source.id,
        parser=ParserKind.CUSTOM_PIPELINE,
        representation_kind=representation_kind,
        config=config,
        status=ParseRunStatus.SUCCEEDED,
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=duration_ms,
        warnings=warnings,
        raw_payload=merge_result.raw_output,
    )

    adapter = CustomPipelineAdapter()
    doc = adapter.adapt(
        {"page_meta": structure_result.page_meta, "blocks": merge_result.blocks},
        SourceMeta(
            source_document_id=source.id,
            parse_run_id=run.id,
            filename=source.filename,
            sha256=source.sha256,
        ),
    )
    return run, doc
