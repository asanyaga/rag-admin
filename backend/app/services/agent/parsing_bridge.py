"""Bridge between the agents engine and the parsing subsystem.

Isolates all parse-subsystem wiring (BYOK key resolution, ParsingService
construction, parse execution + result shaping) so agent nodes stay thin and
tests can substitute these functions.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.cdm.models import ParserKind
from app.cdm.source import SourceDocument as SourceDocumentCDM
from app.services.exceptions import NotFoundError

PARSER_PROVIDER: dict[str, str] = {
    "llamaparse": "llama_cloud",
    "landing_ai": "landing_ai",
}


def parser_provider(parser_type: str) -> str | None:
    """Return the provider-key name for a parser, or None if it needs no key."""
    return PARSER_PROVIDER.get(parser_type)


async def resolve_source_cdm(session, source_document_id: UUID) -> tuple[SourceDocumentCDM, str]:
    """Load a SourceDocument ORM row and project it to a CDM + its storage path."""
    from app.repositories.source_document_repository import SourceDocumentRepository

    orm = await SourceDocumentRepository(session).get(source_document_id)
    if orm is None:
        raise NotFoundError(f"Source document {source_document_id} not found")
    cdm = SourceDocumentCDM(
        id=str(orm.id), sha256=orm.sha256, filename=orm.filename,
        mime_type=orm.mime_type, byte_size=orm.byte_size,
        storage_uri=orm.storage_uri, created_at=orm.created_at,
    )
    return cdm, orm.storage_uri


async def build_parsing_service(session, user_id: UUID, parser_type: str):
    """Construct a ParsingService with the client needed for `parser_type`.

    Resolves the parser's BYOK key from the user's provider keys (env fallback
    inside resolve_api_key). The key is used to build the client and is never
    returned or stored.
    """
    from app.dependencies.documents import get_document_extractor, get_storage_service
    from app.repositories.parse_run_repository import ParseRunRepository
    from app.repositories.parsed_document_repository import ParsedDocumentRepository
    from app.repositories.provider_key_repository import ProviderKeyRepository
    from app.repositories.source_document_repository import SourceDocumentRepository
    from app.services.parsing.parsing_service import ParsingService
    from app.services.provider_key_service import resolve_api_key

    clients: dict[ParserKind, Any] = {ParserKind.SIMPLE: get_document_extractor()}

    provider = parser_provider(parser_type)
    key = None
    if provider:
        key = await resolve_api_key(ProviderKeyRepository(session), user_id, provider)

    if parser_type == "llamaparse" and key:
        from llama_cloud import AsyncLlamaCloud
        clients[ParserKind.LLAMAPARSE] = AsyncLlamaCloud(api_key=key)
    elif parser_type == "landing_ai" and key:
        from landingai_ade import LandingAIADE
        clients[ParserKind.LANDING_AI] = LandingAIADE(apikey=key)

    return ParsingService(
        source_doc_repo=SourceDocumentRepository(session),
        parse_run_repo=ParseRunRepository(session),
        parsed_doc_repo=ParsedDocumentRepository(session),
        storage=get_storage_service(),
        clients=clients,
    )


@dataclass
class ParseOutcome:
    parse_run_id: str
    parsed_document_id: str | None
    page_count: int
    text_len: int
    failed_page_count: int
    block_count: int

    def as_state(self) -> dict:
        return {
            "parse_run_id": self.parse_run_id,
            "parsed_document_id": self.parsed_document_id,
            "page_count": self.page_count,
            "text_len": self.text_len,
            "failed_page_count": self.failed_page_count,
            "block_count": self.block_count,
        }


async def run_parse(
    session, service, source, *,
    file_path: str, representation_kind: str, config: dict, project_id,
) -> ParseOutcome:
    """Run parse_and_persist and shape the result into a ParseOutcome."""
    from app.repositories.parsed_document_repository import ParsedDocumentRepository

    run, doc = await service.parse_and_persist(
        source=source, file_path=file_path,
        representation_kind=representation_kind, config=config,
        project_id=UUID(str(project_id)),
    )
    if doc is None:
        raise RuntimeError(f"parse produced no document for parse_run {run.id}")

    parsed_row = await ParsedDocumentRepository(session).get_by_run(run.id)
    full_text = getattr(doc, "full_text", "") or ""
    return ParseOutcome(
        parse_run_id=str(run.id),
        # ParsedDocument's primary key is parse_run_id (1:1 with the run); it has
        # no `id` column, so parse_run_id IS the parsed-document handle.
        parsed_document_id=str(parsed_row.parse_run_id) if parsed_row else None,
        page_count=doc.page_count,
        text_len=len(full_text),
        failed_page_count=len(run.failed_pages),
        block_count=len(doc.blocks),
    )
