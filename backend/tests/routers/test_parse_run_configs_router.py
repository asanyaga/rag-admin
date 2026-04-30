"""Tests for GET /projects/{project_id}/parse-runs/configs."""
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


async def _signup(client: AsyncClient, email: str) -> str:
    await client.post(
        "/api/v1/auth/signup",
        json={
            "email": email, "password": "ValidPass123!",
            "password_confirm": "ValidPass123!", "full_name": "T",
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


async def _seed_succeeded_run(
    test_db: AsyncSession,
    *,
    user: User,
    project: Project,
    sha: str,
    parser: str,
    config_hash: str,
    config: dict | None = None,
    full_markdown: str | None = "# md",
    finished_at: datetime | None = None,
) -> ParsedDocumentORM:
    sd = SourceDocument(id=uuid4(), sha256=sha, storage_uri=f"local://{sha[:6]}.pdf")
    test_db.add(sd)
    await test_db.commit()
    doc = DocumentORM(
        project_id=project.id, source_document_id=sd.id,
        source_type="upload", source_identifier=sha, title=sha[:6],
        status="ready", created_by=user.id,
    )
    test_db.add(doc)
    finished_at = finished_at or datetime.now(timezone.utc)
    run = ParseRunORM(
        source_document_id=sd.id, parser=parser,
        representation_kind="full_markdown" if full_markdown else "full_text",
        config=config or {"k": 1}, config_hash=config_hash,
        status="succeeded", started_at=finished_at, finished_at=finished_at,
    )
    test_db.add(run)
    await test_db.commit()
    pdoc = ParsedDocumentORM(
        parse_run_id=run.id, source_document_id=sd.id,
        full_text="hello", full_markdown=full_markdown,
        page_count=1, block_count=1, content={},
    )
    test_db.add(pdoc)
    await test_db.commit()
    return pdoc


@pytest.mark.asyncio
async def test_returns_distinct_families_for_project(client: AsyncClient, test_db: AsyncSession):
    token = await _signup(client, "configs1@example.com")
    user = await _user_by_email(test_db, "configs1@example.com")
    project = await _make_project(test_db, user)

    await _seed_succeeded_run(
        test_db, user=user, project=project, sha="a" * 64,
        parser="llamaparse", config_hash="h" * 64, config={"tier": "premium"},
    )
    await _seed_succeeded_run(
        test_db, user=user, project=project, sha="b" * 64,
        parser="landingai", config_hash="z" * 64, config={"mode": "fast"},
        full_markdown=None,
    )

    resp = await client.get(
        f"/api/v1/projects/{project.id}/parse-runs/configs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    families = {(o["parser"], o["parseConfigHash"]) for o in body}
    assert families == {("llamaparse", "h" * 64), ("landingai", "z" * 64)}
    llama = next(o for o in body if o["parser"] == "llamaparse")
    assert llama["hasFullMarkdown"] is True
    assert llama["parsedDocumentCount"] == 1
    assert llama["config"] == {"tier": "premium"}


@pytest.mark.asyncio
async def test_requires_authentication(client: AsyncClient):
    resp = await client.get(f"/api/v1/projects/{uuid4()}/parse-runs/configs")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_rejects_other_users_project(client: AsyncClient, test_db: AsyncSession):
    # User A owns project; user B tries to read configs.
    await _signup(client, "owner@example.com")
    owner = await _user_by_email(test_db, "owner@example.com")
    project = await _make_project(test_db, owner)
    await _seed_succeeded_run(
        test_db, user=owner, project=project, sha="o" * 64,
        parser="llamaparse", config_hash="o" * 64,
    )

    other_token = await _signup(client, "other@example.com")
    resp = await client.get(
        f"/api/v1/projects/{project.id}/parse-runs/configs",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_returns_empty_list(client: AsyncClient, test_db: AsyncSession):
    token = await _signup(client, "empty@example.com")
    user = await _user_by_email(test_db, "empty@example.com")
    project = await _make_project(test_db, user)

    resp = await client.get(
        f"/api/v1/projects/{project.id}/parse-runs/configs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == []
