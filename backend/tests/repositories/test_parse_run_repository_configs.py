"""Tests for ParseRunRepository.list_distinct_configs_for_project."""
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


@pytest.fixture
async def user(test_db: AsyncSession) -> User:
    u = User(
        id=uuid4(), email="cfg@example.com", full_name="Cfg",
        auth_provider="email", password_hash="x",
    )
    test_db.add(u)
    await test_db.commit()
    await test_db.refresh(u)
    return u


@pytest.fixture
async def repo(test_db: AsyncSession) -> ParseRunRepository:
    return ParseRunRepository(test_db)


async def _attach_doc_to_project(
    test_db: AsyncSession,
    *,
    user: User,
    project_id: UUID,
    sha: str,
) -> SourceDocument:
    """Create a SourceDocument and a Document in the given project pointing to it."""
    sd = SourceDocument(id=uuid4(), sha256=sha, storage_uri=f"local://{sha[:6]}.pdf")
    test_db.add(sd)
    await test_db.commit()
    await test_db.refresh(sd)
    doc = DocumentORM(
        id=uuid4(), project_id=project_id, source_document_id=sd.id,
        source_type="upload", source_identifier=sha, title=sha[:6],
        source_metadata={}, status="ready", created_by=user.id,
    )
    test_db.add(doc)
    await test_db.commit()
    return sd


async def _create_parsed_run(
    repo: ParseRunRepository,
    test_db: AsyncSession,
    *,
    source: SourceDocument,
    parser: str,
    config_hash: str,
    config: dict,
    status: str = "succeeded",
    finished_at: datetime | None = None,
    full_markdown: str | None = None,
    full_text: str | None = "hello",
) -> tuple[UUID, UUID]:
    """Create a ParseRun and (when succeeded) its ParsedDocument. Returns (run_id, sd_id)."""
    finished_at = finished_at or datetime.now(timezone.utc)
    started_at = finished_at
    run = await repo.create(ParseRunCreate(
        source_document_id=source.id, parser=parser,
        representation_kind="full_markdown" if full_markdown else "full_text",
        config=config, config_hash=config_hash,
        status=status,
        started_at=started_at, finished_at=finished_at if status == "succeeded" else None,
    ))
    if status == "succeeded":
        pdoc = ParsedDocument(
            parse_run_id=run.id, source_document_id=source.id,
            full_text=full_text, full_markdown=full_markdown,
            page_count=1, block_count=1, content={},
        )
        test_db.add(pdoc)
        await test_db.commit()
    return run.id, source.id


@pytest.mark.asyncio
async def test_list_distinct_configs_for_project_groups_by_parser_and_hash(
    repo, test_db, user
):
    project_id = uuid4()
    sd = await _attach_doc_to_project(test_db, user=user, project_id=project_id, sha="a" * 64)
    sd2 = await _attach_doc_to_project(test_db, user=user, project_id=project_id, sha="b" * 64)

    # Two runs, same family on two different source docs
    await _create_parsed_run(
        repo, test_db, source=sd, parser="llamaparse",
        config_hash="h" * 64, config={"tier": "premium"},
        full_markdown="# md",
    )
    await _create_parsed_run(
        repo, test_db, source=sd2, parser="llamaparse",
        config_hash="h" * 64, config={"tier": "premium"},
        full_markdown=None,
    )
    # One run, different family
    await _create_parsed_run(
        repo, test_db, source=sd, parser="landingai",
        config_hash="z" * 64, config={"mode": "fast"},
        full_markdown="# md",
    )

    rows = await repo.list_distinct_configs_for_project(project_id)
    assert len(rows) == 2
    families = {(r.parser, r.parse_config_hash) for r in rows}
    assert families == {("llamaparse", "h" * 64), ("landingai", "z" * 64)}

    llama = next(r for r in rows if r.parser == "llamaparse")
    assert llama.parsed_document_count == 2
    assert llama.has_full_markdown is True
    assert llama.config == {"tier": "premium"}


@pytest.mark.asyncio
async def test_list_distinct_configs_for_project_excludes_other_projects(
    repo, test_db, user
):
    p1, p2 = uuid4(), uuid4()
    sd1 = await _attach_doc_to_project(test_db, user=user, project_id=p1, sha="1" * 64)
    sd2 = await _attach_doc_to_project(test_db, user=user, project_id=p2, sha="2" * 64)

    await _create_parsed_run(
        repo, test_db, source=sd1, parser="llamaparse",
        config_hash="x" * 64, config={"a": 1}, full_markdown="# x",
    )
    await _create_parsed_run(
        repo, test_db, source=sd2, parser="llamaparse",
        config_hash="y" * 64, config={"a": 2}, full_markdown="# y",
    )

    p1_rows = await repo.list_distinct_configs_for_project(p1)
    assert len(p1_rows) == 1
    assert p1_rows[0].parse_config_hash == "x" * 64


@pytest.mark.asyncio
async def test_list_distinct_configs_for_project_excludes_failed_runs(
    repo, test_db, user
):
    project_id = uuid4()
    sd = await _attach_doc_to_project(test_db, user=user, project_id=project_id, sha="f" * 64)
    await _create_parsed_run(
        repo, test_db, source=sd, parser="llamaparse",
        config_hash="o" * 64, config={"ok": 1},
        full_markdown="# ok",
    )
    await _create_parsed_run(
        repo, test_db, source=sd, parser="llamaparse",
        config_hash="f" * 64, config={"failed": 1},
        status="failed",
    )

    rows = await repo.list_distinct_configs_for_project(project_id)
    assert len(rows) == 1
    assert rows[0].parse_config_hash == "o" * 64


@pytest.mark.asyncio
async def test_list_distinct_configs_for_project_has_full_markdown_when_at_least_one_populated(
    repo, test_db, user
):
    project_id = uuid4()
    sd1 = await _attach_doc_to_project(test_db, user=user, project_id=project_id, sha="1" * 64)
    sd2 = await _attach_doc_to_project(test_db, user=user, project_id=project_id, sha="2" * 64)
    # Both runs same family, only the second populated full_markdown
    await _create_parsed_run(
        repo, test_db, source=sd1, parser="llamaparse",
        config_hash="m" * 64, config={"x": 1}, full_markdown=None,
    )
    await _create_parsed_run(
        repo, test_db, source=sd2, parser="llamaparse",
        config_hash="m" * 64, config={"x": 1}, full_markdown="# present",
    )

    rows = await repo.list_distinct_configs_for_project(project_id)
    assert len(rows) == 1
    assert rows[0].has_full_markdown is True


@pytest.mark.asyncio
async def test_list_distinct_configs_for_project_returns_latest_parsed_at(
    repo, test_db, user
):
    project_id = uuid4()
    # Two source docs so the (source, representation_kind, config_hash) unique allows
    # two runs in the same family.
    sd1 = await _attach_doc_to_project(test_db, user=user, project_id=project_id, sha="t" * 64)
    sd2 = await _attach_doc_to_project(test_db, user=user, project_id=project_id, sha="u" * 64)
    earlier = datetime(2026, 1, 1, tzinfo=timezone.utc)
    later = datetime(2026, 4, 1, tzinfo=timezone.utc)
    await _create_parsed_run(
        repo, test_db, source=sd1, parser="llamaparse",
        config_hash="t" * 64, config={"k": 1}, finished_at=earlier,
        full_markdown="# e",
    )
    await _create_parsed_run(
        repo, test_db, source=sd2, parser="llamaparse",
        config_hash="t" * 64, config={"k": 1}, finished_at=later,
        full_markdown="# l",
    )

    rows = await repo.list_distinct_configs_for_project(project_id)
    assert len(rows) == 1
    # SQLite drops tzinfo; compare on the wall-clock value.
    assert rows[0].latest_parsed_at.replace(tzinfo=None) == later.replace(tzinfo=None)


@pytest.mark.asyncio
async def test_list_distinct_configs_for_project_empty_when_no_runs(repo):
    rows = await repo.list_distinct_configs_for_project(uuid4())
    assert rows == []
