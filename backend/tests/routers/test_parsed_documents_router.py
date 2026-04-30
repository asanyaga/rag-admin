"""Tests for GET /projects/{project_id}/parsed-documents."""
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


async def _seed_run_with_pdoc(
    test_db: AsyncSession,
    *,
    user: User,
    project: Project,
    sha: str,
    parser: str = "llamaparse",
    config_hash: str = "h" * 64,
    full_markdown: str | None = "# md",
    full_text: str | None = "hello",
    finished_at: datetime | None = None,
    filename: str | None = None,
    status: str = "succeeded",
) -> ParsedDocumentORM | None:
    sd = SourceDocument(
        id=uuid4(), sha256=sha, storage_uri=f"local://{sha[:6]}.pdf", filename=filename,
    )
    test_db.add(sd)
    await test_db.commit()
    doc = DocumentORM(
        project_id=project.id, source_document_id=sd.id,
        source_type="upload", source_identifier=sha, title=filename or sha[:6],
        status="ready", created_by=user.id,
    )
    test_db.add(doc)
    finished_at = finished_at or datetime.now(timezone.utc)
    run = ParseRunORM(
        source_document_id=sd.id, parser=parser,
        representation_kind="full_markdown" if full_markdown else "full_text",
        config={"k": 1}, config_hash=config_hash,
        status=status, started_at=finished_at,
        finished_at=finished_at if status == "succeeded" else None,
    )
    test_db.add(run)
    await test_db.commit()
    if status != "succeeded":
        return None
    pdoc = ParsedDocumentORM(
        parse_run_id=run.id, source_document_id=sd.id,
        full_text=full_text, full_markdown=full_markdown,
        page_count=1, block_count=1, content={},
    )
    test_db.add(pdoc)
    await test_db.commit()
    return pdoc


@pytest.mark.asyncio
async def test_no_filter_returns_project_set(client: AsyncClient, test_db: AsyncSession):
    token = await _signup(client, "list1@example.com")
    user = await _user_by_email(test_db, "list1@example.com")
    project = await _make_project(test_db, user)

    await _seed_run_with_pdoc(
        test_db, user=user, project=project, sha="a" * 64, filename="a.pdf",
    )
    await _seed_run_with_pdoc(
        test_db, user=user, project=project, sha="b" * 64, filename="b.pdf",
    )

    resp = await client.get(
        f"/api/v1/projects/{project.id}/parsed-documents",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    filenames = {item["sourceFilename"] for item in body}
    assert filenames == {"a.pdf", "b.pdf"}


@pytest.mark.asyncio
async def test_filters_by_family(client: AsyncClient, test_db: AsyncSession):
    token = await _signup(client, "list2@example.com")
    user = await _user_by_email(test_db, "list2@example.com")
    project = await _make_project(test_db, user)

    await _seed_run_with_pdoc(
        test_db, user=user, project=project, sha="a" * 64,
        parser="llamaparse", config_hash="x" * 64,
    )
    await _seed_run_with_pdoc(
        test_db, user=user, project=project, sha="b" * 64,
        parser="landingai", config_hash="y" * 64,
    )

    resp = await client.get(
        f"/api/v1/projects/{project.id}/parsed-documents",
        params={"parser": "llamaparse", "parseConfigHash": "x" * 64},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["parser"] == "llamaparse"
    assert body[0]["parseConfigHash"] == "x" * 64


@pytest.mark.asyncio
async def test_representation_full_markdown_filters_to_populated(
    client: AsyncClient, test_db: AsyncSession
):
    token = await _signup(client, "list3@example.com")
    user = await _user_by_email(test_db, "list3@example.com")
    project = await _make_project(test_db, user)

    await _seed_run_with_pdoc(
        test_db, user=user, project=project, sha="m" * 64, full_markdown="# yes",
    )
    await _seed_run_with_pdoc(
        test_db, user=user, project=project, sha="t" * 64, full_markdown=None,
    )

    resp = await client.get(
        f"/api/v1/projects/{project.id}/parsed-documents",
        params={"representation": "full_markdown"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["hasFullMarkdown"] is True


@pytest.mark.asyncio
async def test_latest_per_source_default_true(client: AsyncClient, test_db: AsyncSession):
    token = await _signup(client, "list4@example.com")
    user = await _user_by_email(test_db, "list4@example.com")
    project = await _make_project(test_db, user)

    sd = SourceDocument(id=uuid4(), sha256="s" * 64, storage_uri="local://s.pdf")
    test_db.add(sd)
    await test_db.commit()
    doc = DocumentORM(
        project_id=project.id, source_document_id=sd.id,
        source_type="upload", source_identifier="s", title="S",
        status="ready", created_by=user.id,
    )
    test_db.add(doc)
    await test_db.commit()

    earlier = datetime(2026, 1, 1, tzinfo=timezone.utc)
    later = datetime(2026, 4, 1, tzinfo=timezone.utc)
    for ts, hash_ in ((earlier, "1" * 64), (later, "2" * 64)):
        run = ParseRunORM(
            source_document_id=sd.id, parser="llamaparse",
            representation_kind="full_markdown",
            config={}, config_hash=hash_, status="succeeded",
            started_at=ts, finished_at=ts,
        )
        test_db.add(run)
        await test_db.commit()
        test_db.add(ParsedDocumentORM(
            parse_run_id=run.id, source_document_id=sd.id,
            full_text="x", full_markdown="# x", page_count=1, block_count=1, content={},
        ))
        await test_db.commit()

    resp = await client.get(
        f"/api/v1/projects/{project.id}/parsed-documents",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_latest_per_source_false_returns_all_runs(
    client: AsyncClient, test_db: AsyncSession
):
    token = await _signup(client, "list5@example.com")
    user = await _user_by_email(test_db, "list5@example.com")
    project = await _make_project(test_db, user)

    sd = SourceDocument(id=uuid4(), sha256="z" * 64, storage_uri="local://z.pdf")
    test_db.add(sd)
    await test_db.commit()
    doc = DocumentORM(
        project_id=project.id, source_document_id=sd.id,
        source_type="upload", source_identifier="z", title="Z",
        status="ready", created_by=user.id,
    )
    test_db.add(doc)
    await test_db.commit()

    for hash_ in ("1" * 64, "2" * 64):
        run = ParseRunORM(
            source_document_id=sd.id, parser="llamaparse",
            representation_kind="full_markdown",
            config={}, config_hash=hash_, status="succeeded",
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
        )
        test_db.add(run)
        await test_db.commit()
        test_db.add(ParsedDocumentORM(
            parse_run_id=run.id, source_document_id=sd.id,
            full_text="x", full_markdown="# x", page_count=1, block_count=1, content={},
        ))
        await test_db.commit()

    resp = await client.get(
        f"/api/v1/projects/{project.id}/parsed-documents",
        params={"latestPerSource": "false"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_rejects_other_users_project(client: AsyncClient, test_db: AsyncSession):
    await _signup(client, "owner2@example.com")
    owner = await _user_by_email(test_db, "owner2@example.com")
    project = await _make_project(test_db, owner)
    await _seed_run_with_pdoc(
        test_db, user=owner, project=project, sha="o" * 64,
    )

    other_token = await _signup(client, "other2@example.com")
    resp = await client.get(
        f"/api/v1/projects/{project.id}/parsed-documents",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_validates_partial_family_query(client: AsyncClient, test_db: AsyncSession):
    """Supplying parser without parseConfigHash should be rejected."""
    token = await _signup(client, "validate@example.com")
    user = await _user_by_email(test_db, "validate@example.com")
    project = await _make_project(test_db, user)
    resp = await client.get(
        f"/api/v1/projects/{project.id}/parsed-documents",
        params={"parser": "llamaparse"},  # missing parseConfigHash
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422
