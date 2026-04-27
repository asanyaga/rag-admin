"""Drives Landing AI ADE end-to-end: parse_jobs API → ParseRun + ParsedDocument.

Always uses the async parse_jobs path (supports documents of any size).
SDK calls are sync; wrapped in asyncio.to_thread to avoid blocking the event loop.
"""
from __future__ import annotations

import asyncio
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from app.cdm.adapters.base import SourceMeta
from app.cdm.adapters.landing_ai import LandingAIAdapter
from app.cdm.models import ParsedDocument, ParserKind
from app.cdm.source import ParseRun, ParseRunStatus, SourceDocument
from app.services.parsing.errors import LandingAIRunError


async def run_landingai(
    *,
    source: SourceDocument,
    file_path: str,
    representation_kind: str,
    config: Dict[str, Any],
    client: Any,
    parse_run_id: Optional[str] = None,
) -> Tuple[ParseRun, ParsedDocument]:
    """Submit a Landing AI parse job, poll to completion, and adapt to CDM.

    Raises LandingAIRunError (carrying the failed ParseRun) on SDK failure,
    job failure, or timeout.
    """
    run_id = parse_run_id or str(uuid.uuid4())
    started_at = datetime.now(timezone.utc)
    t0 = time.perf_counter()

    model = config.get("model", "dpt-2-latest")
    poll_interval: float = float(config.get("poll_interval_s", 5))
    poll_timeout: float = float(config.get("poll_timeout_s", 600))

    def _create_job() -> Any:
        return client.parse_jobs.create(document=Path(file_path), model=model)

    def _get_job(job_id: str) -> Any:
        return client.parse_jobs.get(job_id)

    job_id: Optional[str] = None
    try:
        job = await asyncio.to_thread(_create_job)
        job_id = job.job_id

        elapsed = 0.0
        response = None
        while elapsed < poll_timeout:
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval
            response = await asyncio.to_thread(_get_job, job_id)
            if response.status == "completed":
                break
            if response.status == "failed":
                raise RuntimeError(f"Landing AI job {job_id} reported status=failed")
        else:
            raise TimeoutError(
                f"Landing AI job {job_id} did not complete within {poll_timeout}s"
            )

    except Exception as exc:
        finished_at = datetime.now(timezone.utc)
        duration_ms = int((time.perf_counter() - t0) * 1000)
        provider_refs = {"landingai_job_id": job_id} if job_id else {}
        failed = ParseRun(
            id=run_id,
            source_document_id=source.id,
            parser=ParserKind.LANDING_AI,
            representation_kind=representation_kind,
            config=config,
            status=ParseRunStatus.FAILED,
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=duration_ms,
            provider_refs=provider_refs,
            error=f"{type(exc).__name__}: {exc}",
        )
        raise LandingAIRunError(f"Landing AI run failed: {exc}", run=failed) from exc

    finished_at = datetime.now(timezone.utc)
    duration_ms = int((time.perf_counter() - t0) * 1000)

    raw = response.data.model_dump(mode="json")
    meta: Dict[str, Any] = raw.get("metadata") or {}

    api_duration_ms = meta.get("duration_ms") or duration_ms

    run = ParseRun(
        id=run_id,
        source_document_id=source.id,
        parser=ParserKind.LANDING_AI,
        parser_version=meta.get("version"),
        representation_kind=representation_kind,
        config=config,
        status=ParseRunStatus.SUCCEEDED,
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=api_duration_ms,
        cost={"credits": meta["credit_usage"]} if meta.get("credit_usage") is not None else {},
        failed_pages=list(meta.get("failed_pages") or []),
        provider_refs={"landingai_job_id": job_id},
        raw_payload=raw,
    )

    adapter = LandingAIAdapter()
    doc = adapter.adapt(raw, SourceMeta(
        source_document_id=source.id,
        parse_run_id=run.id,
        filename=source.filename,
        sha256=source.sha256,
    ))
    return run, doc
