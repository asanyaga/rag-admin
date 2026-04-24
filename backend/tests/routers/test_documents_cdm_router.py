"""E2E tests: HTTP upload → CDM rows in source_documents, documents, parse_runs, parsed_documents.

Uses SQLite in-memory DB via the shared conftest `client` fixture.
Patches run_llamaparse to avoid needing a real LlamaParse API key.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cdm.models import Page, ParserKind, ParsedDocument as ParsedDocumentCDM
from app.cdm.source import ParseRun as ParseRunCDM, ParseRunStatus, SourceDocument as SourceDocumentCDM
from app.models.document import Document
from app.models.parse_run import ParseRun as ParseRunORM
from app.models.parsed_document import ParsedDocument as ParsedDocumentORM
from app.models.source_document import SourceDocument as SourceDocumentORM

MINIMAL_PDF = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF"


async def _signup_and_login(client: AsyncClient) -> str:
    await client.post(
        "/api/v1/auth/signup",
        json={
            "email": "cdmtest@example.com",
            "password": "ValidPass123!",
            "password_confirm": "ValidPass123!",
            "full_name": "CDM Test User",
        },
    )
    resp = await client.post(
        "/api/v1/auth/signin",
        json={"email": "cdmtest@example.com", "password": "ValidPass123!"},
    )
    return resp.json()["access_token"]


async def _create_project(client: AsyncClient, token: str) -> str:
    resp = await client.post(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "CDM Upload Test Project"},
    )
    return resp.json()["id"]


def _make_fake_parse_result(source_id: str) -> tuple[ParseRunCDM, ParsedDocumentCDM]:
    """Build a minimal ParseRun + ParsedDocument that ParsingService would return."""
    run_id = str(uuid4())
    run = ParseRunCDM(
        id=run_id,
        source_document_id=source_id,
        parser=ParserKind.LLAMAPARSE,
        representation_kind="extract_rich",
        config={},
        status=ParseRunStatus.SUCCEEDED,
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
        duration_ms=100,
        input_tokens=10,
        output_tokens=5,
    )
    doc = ParsedDocumentCDM(
        id=run_id,
        source_document_id=source_id,
        parse_run_id=run_id,
        page_count=1,
        pages=[
            Page(
                index=0,
                width=100.0,
                height=200.0,
            )
        ],
        blocks=[],
        full_text="Hello world.",
        full_markdown="Hello world.",
    )
    return run, doc


@pytest.mark.asyncio
async def test_upload_cdm_writes_all_four_tables(client: AsyncClient, test_db: AsyncSession):
    """POST /documents with parser_type=llamaparse and USE_CDM_PARSER=True
    must write rows to source_documents, documents, parse_runs, parsed_documents."""
    token = await _signup_and_login(client)
    project_id = await _create_project(client, token)

    async def fake_run_llamaparse(**kwargs: Any):
        source: SourceDocumentCDM = kwargs["source"]
        return _make_fake_parse_result(source.id)

    with (
        patch(
            "app.services.parsing.parsing_service.run_llamaparse",
            new=AsyncMock(side_effect=fake_run_llamaparse),
        ),
        patch(
            "app.dependencies.documents.get_llamaparse_client",
            return_value=MagicMock(),
        ),
    ):
        response = await client.post(
            "/api/v1/documents",
            headers={"Authorization": f"Bearer {token}"},
            data={
                "project_id": project_id,
                "parser_type": "llamaparse",
                "title": "CDM Test Doc",
            },
            files=[("file", ("test.pdf", MINIMAL_PDF, "application/pdf"))],
        )

    assert response.status_code == 202, response.text
    data = response.json()
    assert data["sourceDocumentId"] is not None

    # source_documents row
    sd_result = await test_db.execute(select(SourceDocumentORM))
    source_docs = list(sd_result.scalars().all())
    assert len(source_docs) == 1

    # documents row with source_document_id populated
    doc_result = await test_db.execute(select(Document))
    documents = list(doc_result.scalars().all())
    assert len(documents) == 1
    assert documents[0].source_document_id is not None

    # parse_runs row
    run_result = await test_db.execute(select(ParseRunORM))
    runs = list(run_result.scalars().all())
    assert len(runs) == 1
    assert runs[0].status == "succeeded"

    # parsed_documents row
    pd_result = await test_db.execute(select(ParsedDocumentORM))
    parsed_docs = list(pd_result.scalars().all())
    assert len(parsed_docs) == 1
    assert parsed_docs[0].page_count == 1

    # verify FK chain: documents → source_documents → parse_runs → parsed_documents
    assert documents[0].source_document_id == source_docs[0].id
    assert runs[0].source_document_id == source_docs[0].id
    assert parsed_docs[0].parse_run_id == runs[0].id

    # extracted_text shim written
    doc = documents[0]
    assert doc.extracted_text == "Hello world."
    assert doc.status.value == "ready"


@pytest.mark.asyncio
async def test_upload_cdm_flag_off_skips_cdm_tables(client: AsyncClient, test_db: AsyncSession):
    """With USE_CDM_PARSER=False, even parser_type=llamaparse must use the legacy path (AC#7)."""
    token = await _signup_and_login(client)
    project_id = await _create_project(client, token)

    with patch("app.config.settings.USE_CDM_PARSER", False):
        response = await client.post(
            "/api/v1/documents",
            headers={"Authorization": f"Bearer {token}"},
            data={
                "project_id": project_id,
                "parser_type": "llamaparse",
                "title": "Flag Off Test Doc",
            },
            files=[("file", ("test.pdf", MINIMAL_PDF, "application/pdf"))],
        )

    assert response.status_code == 202
    data = response.json()
    assert data["sourceDocumentId"] is None

    # No source_documents rows — legacy path bypasses CDM tables
    sd_result = await test_db.execute(select(SourceDocumentORM))
    assert len(list(sd_result.scalars().all())) == 0


@pytest.mark.asyncio
async def test_upload_simple_parser_skips_cdm_tables(client: AsyncClient, test_db: AsyncSession):
    """With parser_type=simple, CDM tables should not be populated."""
    token = await _signup_and_login(client)
    project_id = await _create_project(client, token)

    response = await client.post(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {token}"},
        data={
            "project_id": project_id,
            "parser_type": "simple",
            "title": "Simple Test Doc",
        },
        files=[("file", ("test.pdf", MINIMAL_PDF, "application/pdf"))],
    )

    assert response.status_code == 202
    data = response.json()
    # Simple path does not populate source_document_id
    assert data["sourceDocumentId"] is None

    # No source_documents row for simple parser
    sd_result = await test_db.execute(select(SourceDocumentORM))
    assert len(list(sd_result.scalars().all())) == 0
