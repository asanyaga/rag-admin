"""Orchestrate one parser-eval run: capture per variant, score the case's dimension, persist."""
from __future__ import annotations

import logging
from typing import Any, Callable

from app.models.parser_eval import ParserEvalRunStatus
from app.services.parser_eval.capture import capture
from app.services.parser_eval.scorers import get_scorer
from app.services.parser_eval.variants import variant_key

logger = logging.getLogger(__name__)


def _default_case_source(case: Any) -> tuple[str, str, str, str]:
    raise NotImplementedError


async def run_evaluation(
    repo: Any,
    parsing_service: Any,
    storage: Any,
    *,
    run_id: Any,
    cases: list[Any],
    variants: list[dict],
    project_id: Any,
    _case_source: Callable[[Any], tuple[str, str, str, str]] = _default_case_source,
) -> None:
    await repo.set_run_status(run_id, ParserEvalRunStatus.running)
    try:
        for case in cases:
            source_document_id, storage_uri, filename, mime_type = _case_source(case)
            spec = get_scorer(case.dimension.value)
            for variant in variants:
                adapter = variant["adapter"]
                config = variant.get("config") or {}
                cdm, cost, latency = await capture(
                    parsing_service, storage,
                    source_document_id=source_document_id, storage_uri=storage_uri,
                    filename=filename, mime_type=mime_type, parser=adapter,
                    project_id=project_id, config=config)
                if cdm is None:
                    metrics, details = {spec.primary: 0.0}, {"capture_failed": True}
                else:
                    metrics, details = spec.fn(cdm, case.expected)
                await repo.insert_result(
                    run_id, case.id, adapter, config, variant_key(adapter, config),
                    metrics, spec.primary, details, cost, latency)
        await repo.set_run_status(run_id, ParserEvalRunStatus.completed)
    except Exception as err:                            # noqa: BLE001 — record and surface
        logger.exception("parser-eval run %s failed", run_id)
        await repo.set_run_status(run_id, ParserEvalRunStatus.failed, error_message=str(err))
        raise
