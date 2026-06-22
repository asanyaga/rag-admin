"""ParsingService — orchestrates source-document dedup, parse-run reuse, and persistence."""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Callable, Dict
from uuid import UUID

from app.cdm.models import ParsedDocument as ParsedDocumentCDM, ParserKind
from app.cdm.source import (
    ParseRun as ParseRunCDM,
    ParseRunStatus,
    SourceDocument as SourceDocumentCDM,
)
from app.models.parse_run import ParseRun as ParseRunORM
from app.models.parsed_document import ParsedDocument as ParsedDocumentORM
from app.models.source_document import SourceDocument as SourceDocumentORM
from app.ports.storage import StorageService
from app.repositories.parse_run_repository import ParseRunCreate, ParseRunRepository
from app.repositories.parsed_document_repository import ParsedDocumentCreate, ParsedDocumentRepository
from app.repositories.source_document_repository import SourceDocumentRepository
from app.services.parsing.docling_runner import run_docling
from app.services.parsing.errors import ParseFailedError, ParseRunError
from app.services.parsing.landingai_runner import run_landingai
from app.services.parsing.llamaparse_runner import run_llamaparse
from app.services.parsing.simple_runner import run_simple


logger = logging.getLogger(__name__)

_RUNNERS: Dict[ParserKind, Callable] = {
    ParserKind.LLAMAPARSE: run_llamaparse,
    ParserKind.LANDING_AI: run_landingai,
    ParserKind.SIMPLE:     run_simple,
    ParserKind.DOCLING:    run_docling,
}


def _compute_config_hash(config: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(config, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _run_orm_to_cdm(orm: ParseRunORM) -> ParseRunCDM:
    return ParseRunCDM(
        id=str(orm.id),
        source_document_id=str(orm.source_document_id),
        parser=ParserKind(orm.parser),
        parser_version=orm.parser_version,
        representation_kind=orm.representation_kind,
        config=orm.config or {},
        status=ParseRunStatus(orm.status),
        started_at=orm.started_at,
        finished_at=orm.finished_at,
        duration_ms=orm.duration_ms,
        cost=orm.cost or {},
        input_tokens=orm.input_tokens,
        output_tokens=orm.output_tokens,
        warnings=orm.warnings or [],
        failed_pages=orm.failed_pages or [],
        provider_refs=orm.provider_refs or {},
        error=orm.error,
    )


def _doc_orm_to_cdm(orm: ParsedDocumentORM) -> ParsedDocumentCDM:
    return ParsedDocumentCDM.model_validate(orm.content)


def _source_orm_to_cdm(orm: SourceDocumentORM) -> SourceDocumentCDM:
    return SourceDocumentCDM(
        id=str(orm.id),
        sha256=orm.sha256,
        filename=orm.filename,
        mime_type=orm.mime_type,
        byte_size=orm.byte_size,
        storage_uri=orm.storage_uri,
        created_at=orm.created_at,
    )


class ParsingService:
    def __init__(
        self,
        source_doc_repo: SourceDocumentRepository,
        parse_run_repo: ParseRunRepository,
        parsed_doc_repo: ParsedDocumentRepository,
        storage: StorageService,
        clients: Dict[ParserKind, Any],
    ) -> None:
        self._source_doc_repo = source_doc_repo
        self._parse_run_repo = parse_run_repo
        self._parsed_doc_repo = parsed_doc_repo
        self._storage = storage
        self._clients = clients

    async def ensure_source_document(
        self,
        *,
        bytes_: bytes,
        filename: str,
        mime_type: str,
    ) -> SourceDocumentCDM:
        """Store bytes (idempotent on sha256) and return a CDM SourceDocument."""
        from app.utils.file_validation import compute_checksum
        sha256 = compute_checksum(bytes_)
        storage_uri = await self._storage.save(bytes_, f"uploads/{sha256}/{filename}")
        orm, created = await self._source_doc_repo.get_or_create_by_sha256(
            sha256=sha256,
            storage_uri=storage_uri,
            filename=filename,
            mime_type=mime_type,
            byte_size=len(bytes_),
        )
        # If an existing SourceDocument was returned but the file was just saved
        # to a different path (e.g. re-upload with a different filename after the
        # original file was deleted), update storage_uri so future parses find it.
        if not created and orm.storage_uri != storage_uri:
            await self._source_doc_repo.update_storage_uri(orm.id, storage_uri)
            orm.storage_uri = storage_uri
        return _source_orm_to_cdm(orm)

    async def parse_and_persist(
        self,
        *,
        source: SourceDocumentCDM,
        file_path: str,
        representation_kind: str,
        config: dict[str, Any],
        project_id: UUID,
        force: bool = False,
    ) -> tuple[ParseRunCDM, ParsedDocumentCDM | None]:
        """Run parse with same-project reuse. Persists success, partial, and failure runs.

        The parser is read from ``config["parser"]`` (default: ``"llamaparse"``).
        Returns (run, parsed_doc-or-None).
          - parsed_doc is not None when run.status is SUCCEEDED or PARTIAL.
          - parsed_doc is None when run.status is FAILED.
        Raises ParseFailedError on terminal failure after the failed ParseRun is persisted.

        Pass ``force=True`` to bypass the same-config reuse check and always run a fresh
        parse. Used by the explicit re-parse endpoint.
        """
        parser = ParserKind(config.get("parser", ParserKind.LLAMAPARSE.value))
        config_hash = _compute_config_hash(config)
        source_uuid = UUID(source.id)

        if not force:
            existing = await self._parse_run_repo.get_latest_for_project(
                source_document_id=source_uuid,
                representation_kind=representation_kind,
                config_hash=config_hash,
                project_id=project_id,
            )
            if existing is not None and existing.status in ("succeeded", "partial"):
                cdm_run = _run_orm_to_cdm(existing)
                doc_orm = await self._parsed_doc_repo.get_by_run(existing.id)
                return cdm_run, _doc_orm_to_cdm(doc_orm) if doc_orm else None

        runner = _RUNNERS.get(parser)
        if runner is None:
            raise ValueError(f"No runner registered for parser: {parser}")
        client = self._clients.get(parser)

        try:
            cdm_run, cdm_doc = await runner(
                source=source,
                file_path=file_path,
                representation_kind=representation_kind,
                config=config,
                client=client,
            )
        except ParseRunError as err:
            await self._persist_run(err.run, config_hash, source_uuid)
            raise ParseFailedError(str(err)) from err

        orm_run = await self._persist_run(cdm_run, config_hash, source_uuid)
        orm_doc = await self._parsed_doc_repo.create(ParsedDocumentCreate(
            parse_run_id=orm_run.id,
            source_document_id=source_uuid,
            full_text=cdm_doc.full_text,
            full_markdown=cdm_doc.full_markdown,
            page_count=cdm_doc.page_count,
            block_count=len(cdm_doc.blocks),
            content=cdm_doc.model_dump(),
        ))
        return _run_orm_to_cdm(orm_run), _doc_orm_to_cdm(orm_doc)

    async def _persist_run(
        self,
        cdm_run: ParseRunCDM,
        config_hash: str,
        source_uuid: UUID,
    ) -> ParseRunORM:
        return await self._parse_run_repo.create(ParseRunCreate(
            id=UUID(cdm_run.id),
            source_document_id=source_uuid,
            parser=cdm_run.parser.value,
            parser_version=cdm_run.parser_version,
            representation_kind=cdm_run.representation_kind,
            config=dict(cdm_run.config),
            config_hash=config_hash,
            status=cdm_run.status.value,
            started_at=cdm_run.started_at,
            finished_at=cdm_run.finished_at,
            duration_ms=cdm_run.duration_ms,
            cost=dict(cdm_run.cost),
            input_tokens=cdm_run.input_tokens,
            output_tokens=cdm_run.output_tokens,
            warnings=list(cdm_run.warnings),
            failed_pages=list(cdm_run.failed_pages),
            provider_refs=dict(cdm_run.provider_refs),
            raw_payload=cdm_run.raw_payload,
            error=cdm_run.error,
        ))
