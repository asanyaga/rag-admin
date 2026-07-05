"""Orchestrate one parser-eval run: capture per parser, score each asserted target, persist."""
from __future__ import annotations

import logging
from typing import Any, Callable

from app.models.parser_eval import ParserEvalRunStatus
from app.services.parser_eval.capture import capture
from app.services.parser_eval.scorers import get_scorer

logger = logging.getLogger(__name__)


def _default_case_source(case: Any) -> tuple[str, str, str, str]:
    # Overridden in tests; the service passes a resolver that reads SourceDocument fields.
    raise NotImplementedError


async def run_evaluation(
    repo: Any,
    parsing_service: Any,
    storage: Any,
    *,
    run_id: Any,
    cases: list[Any],
    parsers: list[str],
    project_id: Any,
    _case_source: Callable[[Any], tuple[str, str, str, str]] = _default_case_source,
) -> None:
    await repo.set_run_status(run_id, ParserEvalRunStatus.running)
    try:
        for case in cases:
            source_document_id, storage_uri, filename, mime_type = _case_source(case)
            for parser in parsers:
                cdm, cost, latency = await capture(
                    parsing_service, storage,
                    source_document_id=source_document_id, storage_uri=storage_uri,
                    filename=filename, mime_type=mime_type, parser=parser,
                    project_id=project_id)
                for target in case.targets:            # only asserted dimensions
                    if cdm is None:
                        score, details = 0.0, {"capture_failed": True}
                    else:
                        score, details = get_scorer(target.dimension.value)(cdm, target.expected)
                    await repo.upsert_result(run_id, case.id, parser, target.dimension,
                                             score, details, cost, latency)
        await repo.set_run_status(run_id, ParserEvalRunStatus.completed)
    except Exception as err:                            # noqa: BLE001 — record and surface
        logger.exception("parser-eval run %s failed", run_id)
        await repo.set_run_status(run_id, ParserEvalRunStatus.failed, error_message=str(err))
        raise
