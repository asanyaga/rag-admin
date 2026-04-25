"""Tests for GET /parse-runs/{id}/parsed-document."""
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


async def _signup_and_login(client: AsyncClient, email: str) -> str:
    await client.post(
        "/api/v1/auth/signup",
        json={
            "email": email,
            "password": "ValidPass123!",
            "password_confirm": "ValidPass123!",
            "full_name": "Test User",
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


async def _seed(
    test_db: AsyncSession,
    user: User,
    *,
    with_parsed_doc: bool = True,
) -> ParseRunORM:
    project = Project(user_id=user.id, name="P")
    test_db.add(project)
    await test_db.commit()
    await test_db.refresh(project)

    sd = SourceDocument(id=uuid4(), sha256="a" * 64, storage_uri="local://a.pdf")
    test_db.add(sd)
    await test_db.commit()
    await test_db.refresh(sd)

    doc = DocumentORM(
        project_id=project.id,
        source_document_id=sd.id,
        source_type="upload",
        source_identifier="a.pdf",
        title="A",
        status="ready",
        created_by=user.id,
    )
    test_db.add(doc)

    run = ParseRunORM(
        source_document_id=sd.id,
        parser="llamaparse",
        representation_kind="vector_light",
        config={},
        config_hash="c" * 64,
        status="succeeded",
        started_at=datetime.now(timezone.utc),
    )
    test_db.add(run)
    await test_db.commit()
    await test_db.refresh(run)

    if with_parsed_doc:
        parsed = ParsedDocumentORM(
            parse_run_id=run.id,
            source_document_id=sd.id,
            full_text="hello",
            full_markdown="# hello",
            page_count=1,
            block_count=2,
            content={"schema_version": "1", "pages": [], "blocks": []},
        )
        test_db.add(parsed)
        await test_db.commit()

    return run


@pytest.mark.asyncio
async def test_200_returns_parsed_document_with_camel_case(
    client: AsyncClient, test_db: AsyncSession
):
    token = await _signup_and_login(client, "u1@example.com")
    user = await _user_by_email(test_db, "u1@example.com")
    run = await _seed(test_db, user)

    resp = await client.get(
        f"/api/v1/parse-runs/{run.id}/parsed-document",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["parseRunId"] == str(run.id)
    assert body["sourceDocumentId"] == str(run.source_document_id)
    assert body["pageCount"] == 1
    assert body["blockCount"] == 2
    assert body["fullText"] == "hello"
    assert body["fullMarkdown"] == "# hello"
    assert body["content"]["schema_version"] == "1"


@pytest.mark.asyncio
async def test_404_when_run_does_not_exist(client: AsyncClient):
    token = await _signup_and_login(client, "u1@example.com")
    resp = await client.get(
        f"/api/v1/parse-runs/{uuid4()}/parsed-document",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_404_when_run_has_no_parsed_document(
    client: AsyncClient, test_db: AsyncSession
):
    token = await _signup_and_login(client, "u1@example.com")
    user = await _user_by_email(test_db, "u1@example.com")
    run = await _seed(test_db, user, with_parsed_doc=False)

    resp = await client.get(
        f"/api/v1/parse-runs/{run.id}/parsed-document",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_403_when_user_does_not_own_source(
    client: AsyncClient, test_db: AsyncSession
):
    # User A seeds a run; User B calls the endpoint.
    await _signup_and_login(client, "a@example.com")
    user_a = await _user_by_email(test_db, "a@example.com")
    run = await _seed(test_db, user_a)

    token_b = await _signup_and_login(client, "b@example.com")
    resp = await client.get(
        f"/api/v1/parse-runs/{run.id}/parsed-document",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_raw_payload_200_returns_dict(
    client: AsyncClient, test_db: AsyncSession
):
    token = await _signup_and_login(client, "rp1@example.com")
    user = await _user_by_email(test_db, "rp1@example.com")
    run = await _seed(test_db, user)
    run.raw_payload = {"job_metadata": {"job_id": "j1"}, "pages": []}
    await test_db.commit()

    resp = await client.get(
        f"/api/v1/parse-runs/{run.id}/raw-payload",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["rawPayload"] == {"job_metadata": {"job_id": "j1"}, "pages": []}


@pytest.mark.asyncio
async def test_raw_payload_200_returns_null_when_absent(
    client: AsyncClient, test_db: AsyncSession
):
    token = await _signup_and_login(client, "rp2@example.com")
    user = await _user_by_email(test_db, "rp2@example.com")
    run = await _seed(test_db, user)  # raw_payload defaults to NULL

    resp = await client.get(
        f"/api/v1/parse-runs/{run.id}/raw-payload",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["rawPayload"] is None


@pytest.mark.asyncio
async def test_raw_payload_404_when_run_does_not_exist(
    client: AsyncClient,
):
    token = await _signup_and_login(client, "rp3@example.com")
    resp = await client.get(
        f"/api/v1/parse-runs/{uuid4()}/raw-payload",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_raw_payload_403_when_user_does_not_own_source(
    client: AsyncClient, test_db: AsyncSession
):
    await _signup_and_login(client, "rpA@example.com")
    user_a = await _user_by_email(test_db, "rpA@example.com")
    run = await _seed(test_db, user_a)

    token_b = await _signup_and_login(client, "rpB@example.com")
    resp = await client.get(
        f"/api/v1/parse-runs/{run.id}/raw-payload",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_raw_payload_401_when_unauthenticated(
    client: AsyncClient, test_db: AsyncSession
):
    await _signup_and_login(client, "rpC@example.com")
    user = await _user_by_email(test_db, "rpC@example.com")
    run = await _seed(test_db, user)

    resp = await client.get(f"/api/v1/parse-runs/{run.id}/raw-payload")
    assert resp.status_code == 401
