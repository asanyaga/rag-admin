# backend/app/services/parse_agent/engine.py
"""Parse-agent execution engine: run the graph, project each step into our trace."""
import json
import logging
import time
from datetime import datetime, timezone
from uuid import UUID

from app.models.parse_agent_run import ParseAgentRunStatus
from app.repositories.parse_agent_run_repository import ParseAgentRunRepository, StepCreate
from app.services.parse_agent.graph import build_parse_graph
from app.services.parse_agent.nodes import NODE_SPECS

logger = logging.getLogger(__name__)


def _json_safe(delta: dict) -> dict:
    safe = {}
    for k, v in delta.items():
        try:
            json.dumps(v)
            safe[k] = v
        except (TypeError, ValueError):
            safe[k] = str(v)
    return safe


async def execute_parse_agent(
    session, *, run_id: UUID, initial_state: dict, parsing_service, source,
) -> None:
    """Stream the graph and project each node's output into parse_agent_run_steps."""
    repo = ParseAgentRunRepository(session)
    compiled = build_parse_graph(parsing_service, source)

    seq = 0
    last = time.monotonic()
    try:
        async for chunk in compiled.astream(initial_state, stream_mode="updates"):
            for node_name, delta in chunk.items():
                now = time.monotonic()
                duration_ms = int((now - last) * 1000)
                last = now
                spec = NODE_SPECS.get(node_name)
                await repo.append_step(StepCreate(
                    run_id=run_id, seq=seq, node=node_name, phase="end", status="succeeded",
                    input_keys=list(spec.input_keys) if spec else [],
                    output_keys=list(delta.keys()),
                    state_delta=_json_safe(delta), duration_ms=duration_ms,
                ))
                seq += 1
        await repo.finish_run(
            run_id, status=ParseAgentRunStatus.completed.value,
            finished_at=datetime.now(timezone.utc),
        )
    except Exception as exc:  # noqa: BLE001 — engine boundary; failure is recorded, not raised
        logger.exception("parse-agent run %s failed", run_id)
        await repo.finish_run(
            run_id, status=ParseAgentRunStatus.failed.value,
            finished_at=datetime.now(timezone.utc), error=str(exc),
        )


async def run_parse_agent(
    *, run_id: UUID, source_document_id: UUID, file_path: str, project_id: UUID,
    config: dict, representation_kind: str, storage_service,
    llamaparse_api_key: str | None = None, landingai_api_key: str | None = None,
) -> None:
    """Background-task entry point. Opens its own DB session (mirrors process_cdm_parsing)."""
    from app.cdm.models import ParserKind
    from app.cdm.source import SourceDocument as SourceDocumentCDM
    from app.database import AsyncSessionLocal
    from app.dependencies.documents import get_document_extractor
    from app.repositories.parsed_document_repository import ParsedDocumentRepository
    from app.repositories.parse_run_repository import ParseRunRepository
    from app.repositories.source_document_repository import SourceDocumentRepository
    from app.services.parsing.parsing_service import ParsingService

    llamaparse_client = None
    if llamaparse_api_key:
        from llama_cloud import AsyncLlamaCloud
        llamaparse_client = AsyncLlamaCloud(api_key=llamaparse_api_key)
    landingai_client = None
    if landingai_api_key:
        from landingai_ade import LandingAIADE
        landingai_client = LandingAIADE(apikey=landingai_api_key)

    async with AsyncSessionLocal() as session:
        source_orm = await SourceDocumentRepository(session).get(source_document_id)
        if source_orm is None:
            await ParseAgentRunRepository(session).finish_run(
                run_id, status=ParseAgentRunStatus.failed.value,
                finished_at=datetime.now(timezone.utc), error="SourceDocument not found",
            )
            return

        source_cdm = SourceDocumentCDM(
            id=str(source_orm.id), sha256=source_orm.sha256, filename=source_orm.filename,
            mime_type=source_orm.mime_type, byte_size=source_orm.byte_size,
            storage_uri=source_orm.storage_uri, created_at=source_orm.created_at,
        )
        parsing_service = ParsingService(
            source_doc_repo=SourceDocumentRepository(session),
            parse_run_repo=ParseRunRepository(session),
            parsed_doc_repo=ParsedDocumentRepository(session),
            storage=storage_service,
            clients={
                ParserKind.LLAMAPARSE: llamaparse_client,
                ParserKind.LANDING_AI: landingai_client,
                ParserKind.SIMPLE: get_document_extractor(),
            },
        )
        await execute_parse_agent(
            session, run_id=run_id,
            initial_state={
                "file_path": file_path, "source_document_id": str(source_document_id),
                "project_id": str(project_id), "representation_kind": representation_kind,
                "config": config,
            },
            parsing_service=parsing_service, source=source_cdm,
        )
