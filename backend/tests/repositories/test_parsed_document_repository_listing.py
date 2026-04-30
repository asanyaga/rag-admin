"""Tests for ParsedDocumentRepository.list_for_project."""
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.models.document import Document as DocumentORM
from app.models.parsed_document import ParsedDocument
from app.models.source_document import SourceDocument
from app.repositories.parse_run_repository import (
    ParseRunCreate,
    ParseRunRepository,
)
from app.repositories.parsed_document_repository import ParsedDocumentRepository


@pytest.fixture
async def user(test_db: AsyncSession) -> User:
    u = User(
        id=uuid4(), email="lst@example.com", full_name="Lst",
        auth_provider="email", password_hash="x",
    )
    test_db.add(u)
    await test_db.commit()
    return u


@pytest.fixture
async def parse_run_repo(test_db: AsyncSession) -> ParseRunRepository:
    return ParseRunRepository(test_db)


@pytest.fixture
async def repo(test_db: AsyncSession) -> ParsedDocumentRepository:
    return ParsedDocumentRepository(test_db)


async def _create_source_in_project(
    test_db: AsyncSession, *, user: User, project_id: UUID, sha: str, filename: str | None = None
) -> SourceDocument:
    sd = SourceDocument(
        id=uuid4(), sha256=sha, storage_uri=f"local://{sha[:6]}.pdf",
        filename=filename,
    )
    test_db.add(sd)
    await test_db.commit()
    doc = DocumentORM(
        id=uuid4(), project_id=project_id, source_document_id=sd.id,
        source_type="upload", source_identifier=sha, title=filename or sha[:6],
        source_metadata={}, status="ready", created_by=user.id,
    )
    test_db.add(doc)
    await test_db.commit()
    return sd


async def _create_run_with_parsed(
    parse_run_repo: ParseRunRepository,
    test_db: AsyncSession,
    *,
    source: SourceDocument,
    parser: str = "llamaparse",
    config_hash: str = "h" * 64,
    finished_at: datetime | None = None,
    status: str = "succeeded",
    full_text: str | None = "hello",
    full_markdown: str | None = None,
    block_count: int = 1,
) -> ParsedDocument | None:
    finished_at = finished_at or datetime.now(timezone.utc)
    run = await parse_run_repo.create(ParseRunCreate(
        source_document_id=source.id, parser=parser,
        representation_kind="full_markdown" if full_markdown else "full_text",
        config={"k": 1}, config_hash=config_hash,
        status=status,
        started_at=finished_at,
        finished_at=finished_at if status == "succeeded" else None,
    ))
    if status != "succeeded":
        return None
    pdoc = ParsedDocument(
        parse_run_id=run.id, source_document_id=source.id,
        full_text=full_text, full_markdown=full_markdown,
        page_count=1, block_count=block_count, content={},
    )
    test_db.add(pdoc)
    await test_db.commit()
    return pdoc


@pytest.mark.asyncio
async def test_list_for_project_returns_only_project_parsed_docs(
    repo, parse_run_repo, test_db, user
):
    p1, p2 = uuid4(), uuid4()
    sd1 = await _create_source_in_project(test_db, user=user, project_id=p1, sha="1" * 64)
    sd2 = await _create_source_in_project(test_db, user=user, project_id=p2, sha="2" * 64)
    await _create_run_with_parsed(parse_run_repo, test_db, source=sd1, full_markdown="# 1")
    await _create_run_with_parsed(parse_run_repo, test_db, source=sd2, full_markdown="# 2")

    rows = await repo.list_for_project(p1)
    assert len(rows) == 1
    assert rows[0].source_document_id == sd1.id


@pytest.mark.asyncio
async def test_list_for_project_filters_by_family(
    repo, parse_run_repo, test_db, user
):
    project_id = uuid4()
    sd = await _create_source_in_project(test_db, user=user, project_id=project_id, sha="a" * 64)
    sd2 = await _create_source_in_project(test_db, user=user, project_id=project_id, sha="b" * 64)
    await _create_run_with_parsed(
        parse_run_repo, test_db, source=sd,
        parser="llamaparse", config_hash="x" * 64, full_markdown="# x",
    )
    await _create_run_with_parsed(
        parse_run_repo, test_db, source=sd2,
        parser="landingai", config_hash="y" * 64, full_markdown="# y",
    )

    rows = await repo.list_for_project(
        project_id, parser="llamaparse", parse_config_hash="x" * 64,
    )
    assert len(rows) == 1
    assert rows[0].parser == "llamaparse"
    assert rows[0].parse_config_hash == "x" * 64


@pytest.mark.asyncio
async def test_list_for_project_filters_by_representation_full_markdown(
    repo, parse_run_repo, test_db, user
):
    project_id = uuid4()
    sd1 = await _create_source_in_project(test_db, user=user, project_id=project_id, sha="m" * 64)
    sd2 = await _create_source_in_project(test_db, user=user, project_id=project_id, sha="t" * 64)
    await _create_run_with_parsed(
        parse_run_repo, test_db, source=sd1,
        config_hash="m" * 64, full_markdown="# md",
    )
    await _create_run_with_parsed(
        parse_run_repo, test_db, source=sd2,
        config_hash="t" * 64, full_markdown=None,
    )

    rows = await repo.list_for_project(project_id, representation="full_markdown")
    assert len(rows) == 1
    assert rows[0].source_document_id == sd1.id


@pytest.mark.asyncio
async def test_list_for_project_filters_by_representation_full_text(
    repo, parse_run_repo, test_db, user
):
    project_id = uuid4()
    sd = await _create_source_in_project(test_db, user=user, project_id=project_id, sha="f" * 64)
    await _create_run_with_parsed(
        parse_run_repo, test_db, source=sd,
        config_hash="f" * 64, full_text="hello", full_markdown=None,
    )

    rows = await repo.list_for_project(project_id, representation="full_text")
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_list_for_project_filters_by_representation_block(
    repo, parse_run_repo, test_db, user
):
    project_id = uuid4()
    sd = await _create_source_in_project(test_db, user=user, project_id=project_id, sha="k" * 64)
    await _create_run_with_parsed(
        parse_run_repo, test_db, source=sd,
        config_hash="k" * 64, block_count=3,
    )

    rows = await repo.list_for_project(project_id, representation="block")
    assert len(rows) == 1
    assert rows[0].block_count == 3


@pytest.mark.asyncio
async def test_list_for_project_latest_per_source_default_returns_one_per_source(
    repo, parse_run_repo, test_db, user
):
    project_id = uuid4()
    sd = await _create_source_in_project(test_db, user=user, project_id=project_id, sha="l" * 64)
    earlier = datetime(2026, 1, 1, tzinfo=timezone.utc)
    later = datetime(2026, 4, 1, tzinfo=timezone.utc)
    await _create_run_with_parsed(
        parse_run_repo, test_db, source=sd,
        config_hash="1" * 64, finished_at=earlier, full_markdown="# e",
    )
    later_doc = await _create_run_with_parsed(
        parse_run_repo, test_db, source=sd,
        config_hash="2" * 64, finished_at=later, full_markdown="# l",
    )

    rows = await repo.list_for_project(project_id)  # default latest_per_source=True
    assert len(rows) == 1
    assert rows[0].parse_run_id == later_doc.parse_run_id


@pytest.mark.asyncio
async def test_list_for_project_latest_per_source_false_returns_all_runs(
    repo, parse_run_repo, test_db, user
):
    project_id = uuid4()
    sd = await _create_source_in_project(test_db, user=user, project_id=project_id, sha="a" * 64)
    earlier = datetime(2026, 1, 1, tzinfo=timezone.utc)
    later = datetime(2026, 4, 1, tzinfo=timezone.utc)
    await _create_run_with_parsed(
        parse_run_repo, test_db, source=sd,
        config_hash="1" * 64, finished_at=earlier, full_markdown="# e",
    )
    await _create_run_with_parsed(
        parse_run_repo, test_db, source=sd,
        config_hash="2" * 64, finished_at=later, full_markdown="# l",
    )

    rows = await repo.list_for_project(project_id, latest_per_source=False)
    assert len(rows) == 2
    # Newest first
    assert rows[0].parsed_at.replace(tzinfo=None) >= rows[1].parsed_at.replace(tzinfo=None)


@pytest.mark.asyncio
async def test_list_for_project_excludes_failed_run_parsed_docs(
    repo, parse_run_repo, test_db, user
):
    project_id = uuid4()
    sd = await _create_source_in_project(test_db, user=user, project_id=project_id, sha="f" * 64)
    await _create_run_with_parsed(
        parse_run_repo, test_db, source=sd, status="failed", full_markdown=None,
    )
    rows = await repo.list_for_project(project_id)
    assert rows == []


@pytest.mark.asyncio
async def test_list_for_project_includes_source_filename(
    repo, parse_run_repo, test_db, user
):
    project_id = uuid4()
    sd = await _create_source_in_project(
        test_db, user=user, project_id=project_id, sha="n" * 64, filename="my-doc.pdf",
    )
    await _create_run_with_parsed(
        parse_run_repo, test_db, source=sd, full_markdown="# name",
    )

    rows = await repo.list_for_project(project_id)
    assert len(rows) == 1
    assert rows[0].source_filename == "my-doc.pdf"
