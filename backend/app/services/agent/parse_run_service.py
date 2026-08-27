"""Parse run service — resolves a source document into a generic agent run."""
import logging
from uuid import UUID

from app.schemas.agent import AgentRunResponse
from app.services.agent.agent_run_service import AgentRunService
from app.services.agent.parsing_bridge import parser_provider
from app.services.exceptions import NotFoundError
from app.services.provider_key_service import resolve_api_key

logger = logging.getLogger(__name__)


class ParseRunService:
    """Thin service that resolves parse inputs into a generic initial state."""

    def __init__(self, agent_run_service: AgentRunService, source_doc_repo, provider_key_repo):
        self.agent_run_service = agent_run_service
        self.source_doc_repo = source_doc_repo
        self.provider_key_repo = provider_key_repo

    async def start_parse_run(
        self, *, project_id: UUID, agent_definition_id: UUID,
        source_document_id: UUID, parser: str, representation_kind: str,
        parse_config: dict, user_id: UUID,
    ) -> AgentRunResponse:
        source = await self.source_doc_repo.get(source_document_id)
        if source is None:
            raise NotFoundError(f"Source document {source_document_id} not found")

        # Pre-validate BYOK key presence so a missing key is a clean 400, not a
        # failed run. The key is discarded here; the node re-resolves for real.
        provider = parser_provider(parser)
        if provider:
            key = await resolve_api_key(self.provider_key_repo, user_id, provider)
            if not key:
                raise ValueError(
                    f"No API key configured for parser '{parser}'. "
                    "Add one in Settings → API Keys."
                )

        config = dict(parse_config or {})
        config["parser"] = parser
        initial_state = {
            "source_document_id": str(source_document_id),
            "project_id": str(project_id),
            "user_id": str(user_id),
            "representation_kind": representation_kind,
            "parse_config": config,
            "current_step": "parse",
        }
        return await self.agent_run_service.start_run(
            project_id=project_id,
            agent_definition_id=agent_definition_id,
            initial_state=initial_state,
            user_id=user_id,
        )
