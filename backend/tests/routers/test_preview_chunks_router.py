"""Tests for POST /projects/{project_id}/indexes/preview-chunks."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document as DocumentORM
from app.models.parse_run import ParseRun as ParseRunORM
from app.models.parsed_document import ParsedDocument as ParsedDocumentORM
from app.models.project import Project
from app.models.source_document import SourceDocument
from app.models.user import User


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _signup(client: AsyncClient, email: str) -> str:
    await client.post(
        "/api/v1/auth/signup",
        json={
            "email": email,
            "password": "ValidPass123!",
            "password_confirm": "ValidPass123!",
            "full_name": "T",
        },
    )
    resp = await client.post(
        "/api/v1/auth/signin",
        json={"email": email, "password": "ValidPass123!"},
    )
    return resp.json()["access_token"]


async def _user_by_email(test_db: AsyncSession, email: str) -> User:
    result = await test_db.execute(select(User).where(User.email == email))
    return result.scalar_one()


async def _make_project(test_db: AsyncSession, user: User, name: str = "P") -> Project:
    project = Project(user_id=user.id, name=name)
    test_db.add(project)
    await test_db.commit()
    await test_db.refresh(project)
    return project


async def _seed_run_with_pdoc(
    test_db: AsyncSession,
    *,
    user: User,
    project: Project,
    sha: str,
    parser: str = "llamaparse",
    config_hash: str = "h" * 64,
    full_markdown: str | None = "# heading\n\nsome markdown content",
    full_text: str | None = "hello world text",
    extracted_text: str | None = None,
    status: str = "succeeded",
) -> tuple[DocumentORM, ParsedDocumentORM | None]:
    """Seed a SourceDocument + Document + ParseRun + ParsedDocument.

    Returns the Document and the ParsedDocument (None if status != 'succeeded').
    """
    sd = SourceDocument(
        id=uuid4(),
        sha256=sha,
        storage_uri=f"local://{sha[:6]}.pdf",
        filename=f"{sha[:6]}.pdf",
    )
    test_db.add(sd)
    await test_db.commit()

    doc = DocumentORM(
        project_id=project.id,
        source_document_id=sd.id,
        source_type="upload",
        source_identifier=sha,
        title=sha[:6],
        status="ready",
        created_by=user.id,
        extracted_text=extracted_text,
    )
    test_db.add(doc)
    await test_db.commit()

    now = datetime.now(timezone.utc)
    run = ParseRunORM(
        source_document_id=sd.id,
        parser=parser,
        representation_kind="full_markdown" if full_markdown else "full_text",
        config={"k": 1},
        config_hash=config_hash,
        status=status,
        started_at=now,
        finished_at=now if status == "succeeded" else None,
    )
    test_db.add(run)
    await test_db.commit()

    if status != "succeeded":
        return doc, None

    pdoc = ParsedDocumentORM(
        parse_run_id=run.id,
        source_document_id=sd.id,
        full_text=full_text,
        full_markdown=full_markdown,
        page_count=1,
        block_count=1,
        content={},
    )
    test_db.add(pdoc)
    await test_db.commit()
    return doc, pdoc


def _full_markdown_config() -> dict:
    return {
        "parser": "llamaparse",
        "parseConfigHash": "h" * 64,
        "sourceRepresentation": "full_markdown",
        "chunkingStrategy": "markdown_heading",
        "chunkSize": 512,
        "chunkOverlap": 0,
        "splitHeadingLevel": 2,
        "maxSectionChars": 4000,
        "embeddingProvider": "openai",
        "embeddingModel": "text-embedding-3-small",
    }


def _full_text_config() -> dict:
    return {
        "parser": "llamaparse",
        "parseConfigHash": "h" * 64,
        "sourceRepresentation": "full_text",
        "chunkingStrategy": "recursive_character",
        "chunkSize": 512,
        "chunkOverlap": 0,
        "embeddingProvider": "openai",
        "embeddingModel": "text-embedding-3-small",
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_preview_chunks_validates_exactly_one_handle(
    client: AsyncClient, test_db: AsyncSession
):
    """Body with neither documentId nor parsedDocumentId → 422."""
    token = await _signup(client, "preview_neither@example.com")
    user = await _user_by_email(test_db, "preview_neither@example.com")
    project = await _make_project(test_db, user)

    resp = await client.post(
        f"/api/v1/projects/{project.id}/indexes/preview-chunks",
        json={"config": _full_markdown_config()},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_preview_chunks_validates_both_handles_supplied(
    client: AsyncClient, test_db: AsyncSession
):
    """Body with BOTH documentId and parsedDocumentId → 422."""
    token = await _signup(client, "preview_both@example.com")
    user = await _user_by_email(test_db, "preview_both@example.com")
    project = await _make_project(test_db, user)

    resp = await client.post(
        f"/api/v1/projects/{project.id}/indexes/preview-chunks",
        json={
            "documentId": str(uuid4()),
            "parsedDocumentId": str(uuid4()),
            "config": _full_markdown_config(),
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_preview_chunks_with_parsed_document_id_full_markdown(
    client: AsyncClient, test_db: AsyncSession
):
    """Happy path through the seam using parsedDocumentId → 200 with chunks."""
    token = await _signup(client, "preview_pdoc@example.com")
    user = await _user_by_email(test_db, "preview_pdoc@example.com")
    project = await _make_project(test_db, user)

    _doc, pdoc = await _seed_run_with_pdoc(
        test_db,
        user=user,
        project=project,
        sha="a" * 64,
        full_markdown="# Heading\n\nSome content for the preview.",
    )
    assert pdoc is not None

    resp = await client.post(
        f"/api/v1/projects/{project.id}/indexes/preview-chunks",
        json={
            "parsedDocumentId": str(pdoc.parse_run_id),
            "config": _full_markdown_config(),
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["totalChunksEstimate"] >= 1
    assert isinstance(body["previewChunks"], list)
    assert len(body["previewChunks"]) >= 1
    assert body["previewChunks"][0]["content"] != ""


@pytest.mark.asyncio
async def test_preview_chunks_bridge_document_id_full_markdown(
    client: AsyncClient, test_db: AsyncSession
):
    """Bridge path: documentId + CDM config → resolves latest parse run → 200."""
    token = await _signup(client, "preview_bridge@example.com")
    user = await _user_by_email(test_db, "preview_bridge@example.com")
    project = await _make_project(test_db, user)

    doc, _pdoc = await _seed_run_with_pdoc(
        test_db,
        user=user,
        project=project,
        sha="b" * 64,
        full_markdown="# Bridge\n\nBridge content for preview test.",
    )

    resp = await client.post(
        f"/api/v1/projects/{project.id}/indexes/preview-chunks",
        json={
            "documentId": str(doc.id),
            "config": _full_markdown_config(),
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["totalChunksEstimate"] >= 1
    assert len(body["previewChunks"]) >= 1


@pytest.mark.asyncio
async def test_preview_chunks_bridge_document_id_no_parse_run_returns_400(
    client: AsyncClient, test_db: AsyncSession
):
    """documentId with no succeeded parse runs + CDM config → 400 mentioning 'parse'."""
    token = await _signup(client, "preview_norun@example.com")
    user = await _user_by_email(test_db, "preview_norun@example.com")
    project = await _make_project(test_db, user)

    # Seed document with a failed (non-succeeded) parse run only.
    doc, _pdoc = await _seed_run_with_pdoc(
        test_db,
        user=user,
        project=project,
        sha="c" * 64,
        status="failed",
    )

    resp = await client.post(
        f"/api/v1/projects/{project.id}/indexes/preview-chunks",
        json={
            "documentId": str(doc.id),
            "config": _full_markdown_config(),
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
    assert "parse" in resp.json()["detail"].lower()



@pytest.mark.asyncio
async def test_preview_chunks_parsed_document_outside_project_returns_404(
    client: AsyncClient, test_db: AsyncSession
):
    """parsedDocumentId from a different user's project → 404."""
    # Owner B creates their own project + parsed-doc.
    await _signup(client, "preview_owner_b@example.com")
    user_b = await _user_by_email(test_db, "preview_owner_b@example.com")
    project_b = await _make_project(test_db, user_b, name="B-project")
    _doc_b, pdoc_b = await _seed_run_with_pdoc(
        test_db,
        user=user_b,
        project=project_b,
        sha="e" * 64,
        full_markdown="# B content\n\nOwner B's document.",
    )
    assert pdoc_b is not None

    # User A signs up and creates their own project.
    token_a = await _signup(client, "preview_owner_a@example.com")
    user_a = await _user_by_email(test_db, "preview_owner_a@example.com")
    project_a = await _make_project(test_db, user_a, name="A-project")

    # User A requests preview using user B's parsedDocumentId scoped to A's project.
    resp = await client.post(
        f"/api/v1/projects/{project_a.id}/indexes/preview-chunks",
        json={
            "parsedDocumentId": str(pdoc_b.parse_run_id),
            "config": _full_markdown_config(),
        },
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_preview_chunks_seam_overlap_matches_config(
    client: AsyncClient, test_db: AsyncSession
):
    """Seam path computes overlap from config.chunk_overlap, matching the raw_text path.

    Seeds a parsed-doc with full_text long enough to produce >= 2 chunks at
    chunk_size=200. Submits chunk_overlap=50 and asserts the second chunk's
    overlapStartChars > 0 (i.e. the fix propagates config to the helper).
    """
    token = await _signup(client, "preview_overlap@example.com")
    user = await _user_by_email(test_db, "preview_overlap@example.com")
    project = await _make_project(test_db, user)

    # "alpha " * 200 = 1200 chars — well over two 200-char chunks.
    long_text = "alpha " * 200
    _doc, pdoc = await _seed_run_with_pdoc(
        test_db,
        user=user,
        project=project,
        sha="f" * 64,
        full_text=long_text,
        full_markdown=None,
    )
    assert pdoc is not None

    config = {
        "parser": "llamaparse",
        "parseConfigHash": "h" * 64,
        "sourceRepresentation": "full_text",
        "chunkingStrategy": "recursive_character",
        "chunkSize": 200,
        "chunkOverlap": 50,
        "embeddingProvider": "openai",
        "embeddingModel": "text-embedding-3-small",
    }

    resp = await client.post(
        f"/api/v1/projects/{project.id}/indexes/preview-chunks",
        json={
            "parsedDocumentId": str(pdoc.parse_run_id),
            "config": config,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    chunks = body["previewChunks"]
    assert len(chunks) >= 2, "Need at least 2 chunks to test overlap"
    # The second chunk (index 1) must have a non-zero overlapStartChars because
    # chunk_overlap=50 and all chunks are well over 100 chars (50 * 2).
    assert chunks[1]["overlapStartChars"] > 0, (
        f"Expected overlapStartChars > 0 for second chunk, got {chunks[1]['overlapStartChars']}"
    )
