"""Tests for GET /documents/{id}/parse-runs."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document as DocumentORM
from app.models.parse_run import ParseRun as ParseRunORM
from app.models.project import Project
from app.models.source_document import SourceDocument
from app.models.user import User


async def _signup_and_login(client: AsyncClient, email: str = "u1@example.com") -> str:
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


async def _get_user_by_email(test_db: AsyncSession, email: str) -> User:
    from sqlalchemy import select

    result = await test_db.execute(select(User).where(User.email == email))
    return result.scalar_one()


def _make_run(source_id, *, config_hash: str, started_at=None) -> ParseRunORM:
    return ParseRunORM(
        source_document_id=source_id,
        parser="llamaparse",
        representation_kind="vector_light",
        config={"k": "v"},
        config_hash=config_hash,
        status="succeeded",
        started_at=started_at or datetime.now(timezone.utc),
    )


async def _seed_doc_with_runs(
    test_db: AsyncSession,
    user: User,
    *,
    with_source: bool = True,
    n_runs: int = 0,
) -> tuple[DocumentORM, list[ParseRunORM]]:
    project = Project(user_id=user.id, name="P")
    test_db.add(project)
    await test_db.commit()
    await test_db.refresh(project)

    source_id = None
    if with_source:
        sd = SourceDocument(
            id=uuid4(), sha256="a" * 64, storage_uri="local://a.pdf"
        )
        test_db.add(sd)
        await test_db.commit()
        await test_db.refresh(sd)
        source_id = sd.id

    doc = DocumentORM(
        project_id=project.id,
        source_document_id=source_id,
        source_type="upload",
        source_identifier="a.pdf",
        title="A",
        status="ready",
        created_by=user.id,
    )
    test_db.add(doc)
    await test_db.commit()
    await test_db.refresh(doc)

    runs: list[ParseRunORM] = []
    if source_id is not None:
        for i in range(n_runs):
            run = _make_run(source_id, config_hash=str(i) * 64)
            test_db.add(run)
            runs.append(run)
        if runs:
            await test_db.commit()
            for r in runs:
                await test_db.refresh(r)
            # Deterministic ordering: index 0 = oldest, last = newest
            for i, r in enumerate(runs):
                r.created_at = datetime(2026, 1, i + 1, tzinfo=timezone.utc)
            await test_db.commit()
    return doc, runs


@pytest.mark.asyncio
async def test_404_for_unknown_document(client: AsyncClient):
    token = await _signup_and_login(client)
    resp = await client.get(
        f"/api/v1/documents/{uuid4()}/parse-runs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_404_for_other_users_document(
    client: AsyncClient, test_db: AsyncSession
):
    # User A owns the doc, User B tries to access it.
    token_a = await _signup_and_login(client, "a@example.com")
    user_a = await _get_user_by_email(test_db, "a@example.com")
    doc, _ = await _seed_doc_with_runs(test_db, user_a, n_runs=1)

    token_b = await _signup_and_login(client, "b@example.com")
    resp = await client.get(
        f"/api/v1/documents/{doc.id}/parse-runs",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.status_code == 404
    # Owner can see it
    resp = await client.get(
        f"/api/v1/documents/{doc.id}/parse-runs",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_empty_list_when_no_source_document(
    client: AsyncClient, test_db: AsyncSession
):
    token = await _signup_and_login(client)
    user = await _get_user_by_email(test_db, "u1@example.com")
    doc, _ = await _seed_doc_with_runs(test_db, user, with_source=False)

    resp = await client.get(
        f"/api/v1/documents/{doc.id}/parse-runs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_returns_runs_newest_first_with_camel_case(
    client: AsyncClient, test_db: AsyncSession
):
    token = await _signup_and_login(client)
    user = await _get_user_by_email(test_db, "u1@example.com")
    doc, runs = await _seed_doc_with_runs(test_db, user, n_runs=3)

    resp = await client.get(
        f"/api/v1/documents/{doc.id}/parse-runs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert len(payload) == 3
    # Newest first: runs created in order 0,1,2 with created_at jan 1,2,3 → order 2,1,0
    expected_ids = [str(runs[2].id), str(runs[1].id), str(runs[0].id)]
    assert [r["id"] for r in payload] == expected_ids

    first = payload[0]
    for key in (
        "sourceDocumentId",
        "representationKind",
        "startedAt",
        "failedPages",
        "providerRefs",
        "createdAt",
    ):
        assert key in first, f"missing camelCase key {key}"
    assert first["parser"] == "llamaparse"
