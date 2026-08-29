"""Bridge between the agents engine and the extraction subsystem.

Resolves the document/schema ids a run form supplies into the file_path +
schema_definition extract_node needs, so extract composes generically.
"""
from __future__ import annotations
from uuid import UUID

from app.services.exceptions import NotFoundError


async def resolve_document_file_path(session, document_id: UUID | str) -> str:
    from app.repositories.document_repository import DocumentRepository
    doc = await DocumentRepository(session).get_by_id_unscoped(UUID(str(document_id)))
    if doc is None:
        raise NotFoundError(f"Document {document_id} not found")
    file_path = (doc.source_metadata or {}).get("file_path")
    if not file_path:
        raise NotFoundError(f"Document {document_id} has no file path")
    return file_path


async def resolve_schema_definition(session, schema_id: UUID | str) -> dict:
    from app.repositories.extraction_schema_repository import ExtractionSchemaRepository
    schema = await ExtractionSchemaRepository(session).get_by_id(UUID(str(schema_id)))
    if schema is None:
        raise NotFoundError(f"Extraction schema {schema_id} not found")
    return schema.schema_definition
