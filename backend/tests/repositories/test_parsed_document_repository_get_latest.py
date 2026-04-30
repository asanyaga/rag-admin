"""Tests for ParsedDocumentRepository.get_latest_for_document (bridge helper)."""
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.models.document import Document as DocumentORM
from app.models.parsed_document import ParsedDocument
from app.models.source_document import SourceDocument
from app.repositories.parse_run_repository import ParseRunCreate, ParseRunRepository
from app.repositories.parsed_document_repository import ParsedDocumentRepository


# ---------------------------------------------------------------------------
# Local seed helpers (do NOT touch conftest)
# ---------------------------------------------------------------------------


@dataclass
class SeededDocument:
    document: DocumentORM
    source_document: SourceDocument


async def _seed_user(test_db: AsyncSession) -> User:
    u = User(
        id=uuid4(), email=f"bridge-{uuid4().hex[:6]}@example.com",
        full_name="Bridge Test", auth_provider="email", password_hash="x",
    )
    test_db.add(u)
    await test_db.commit()
    return u


async def _seed_document(
    test_db: AsyncSession, *, user: User, sha: str
) -> SeededDocument:
    """Seed a SourceDocument + Document pair. project_id is a bare UUID (FK not enforced in SQLite)."""
    sd = SourceDocument(
        id=uuid4(), sha256=sha, storage_uri=f"local://{sha[:6]}.pdf", filename=f"{sha[:6]}.pdf",
    )
    test_db.add(sd)
    await test_db.commit()

    doc = DocumentORM(
        id=uuid4(),
        project_id=uuid4(),  # bare UUID — FK not enforced in test SQLite
        source_document_id=sd.id,
        source_type="upload",
        source_identifier=sha,
        title=f"doc-{sha[:6]}",
        source_metadata={},
        status="ready",
        created_by=user.id,
    )
    test_db.add(doc)
    await test_db.commit()
    return SeededDocument(document=doc, source_document=sd)


async def _seed_parse_run_with_parsed(
    test_db: AsyncSession,
    parse_run_repo: ParseRunRepository,
    *,
    source_document: SourceDocument,
    status: str = "succeeded",
    finished_at: datetime | None = None,
    config_hash: str | None = None,
) -> ParsedDocument | None:
    """Seed a ParseRun and (if succeeded) a ParsedDocument."""
    ts = finished_at or datetime.now(timezone.utc)
    ch = config_hash or ("h" * 64)
    run = await parse_run_repo.create(ParseRunCreate(
        source_document_id=source_document.id,
        parser="llamaparse",
        representation_kind="full_text",
        config={"k": 1},
        config_hash=ch,
        status=status,
        started_at=ts,
        finished_at=ts if status == "succeeded" else None,
    ))
    if status != "succeeded":
        return None
    pdoc = ParsedDocument(
        parse_run_id=run.id,
        source_document_id=source_document.id,
        full_text="hello",
        full_markdown=None,
        page_count=1,
        block_count=1,
        content={},
    )
    test_db.add(pdoc)
    await test_db.commit()
    return pdoc


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def user(test_db: AsyncSession) -> User:
    return await _seed_user(test_db)


@pytest.fixture
async def parse_run_repo(test_db: AsyncSession) -> ParseRunRepository:
    return ParseRunRepository(test_db)


@pytest.fixture
async def repo(test_db: AsyncSession) -> ParsedDocumentRepository:
    return ParsedDocumentRepository(test_db)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_latest_for_document_returns_newest_succeeded_run(
    repo: ParsedDocumentRepository,
    parse_run_repo: ParseRunRepository,
    test_db: AsyncSession,
    user: User,
) -> None:
    """When two succeeded runs exist for the same Document, return the parsed-doc
    whose parse_run has the later finished_at."""
    seeded = await _seed_document(test_db, user=user, sha="a" * 64)

    earlier = datetime(2026, 1, 1, tzinfo=timezone.utc)
    later = datetime(2026, 4, 1, tzinfo=timezone.utc)

    await _seed_parse_run_with_parsed(
        test_db, parse_run_repo,
        source_document=seeded.source_document,
        finished_at=earlier, config_hash="1" * 64,
    )
    newer_pdoc = await _seed_parse_run_with_parsed(
        test_db, parse_run_repo,
        source_document=seeded.source_document,
        finished_at=later, config_hash="2" * 64,
    )
    assert newer_pdoc is not None

    result = await repo.get_latest_for_document(seeded.document.id)

    assert result is not None
    assert result.parse_run_id == newer_pdoc.parse_run_id


@pytest.mark.asyncio
async def test_get_latest_for_document_skips_failed_runs(
    repo: ParsedDocumentRepository,
    parse_run_repo: ParseRunRepository,
    test_db: AsyncSession,
    user: User,
) -> None:
    """A failed run is ignored; only the succeeded run is returned."""
    seeded = await _seed_document(test_db, user=user, sha="b" * 64)

    ts = datetime(2026, 2, 1, tzinfo=timezone.utc)
    ts_later = datetime(2026, 3, 1, tzinfo=timezone.utc)

    # Seed failed run first, then a succeeded run
    await _seed_parse_run_with_parsed(
        test_db, parse_run_repo,
        source_document=seeded.source_document,
        status="failed", finished_at=ts, config_hash="f" * 64,
    )
    good_pdoc = await _seed_parse_run_with_parsed(
        test_db, parse_run_repo,
        source_document=seeded.source_document,
        status="succeeded", finished_at=ts_later, config_hash="g" * 64,
    )
    assert good_pdoc is not None

    result = await repo.get_latest_for_document(seeded.document.id)

    assert result is not None
    assert result.parse_run_id == good_pdoc.parse_run_id


@pytest.mark.asyncio
async def test_get_latest_for_document_returns_none_when_no_runs(
    repo: ParsedDocumentRepository,
    test_db: AsyncSession,
    user: User,
) -> None:
    """A Document with no parse runs at all returns None."""
    seeded = await _seed_document(test_db, user=user, sha="c" * 64)

    result = await repo.get_latest_for_document(seeded.document.id)

    assert result is None


@pytest.mark.asyncio
async def test_get_latest_for_document_returns_none_for_unknown_document(
    repo: ParsedDocumentRepository,
    parse_run_repo: ParseRunRepository,
    test_db: AsyncSession,
    user: User,
) -> None:
    """Passing an unknown document_id returns None even if other documents have runs."""
    seeded = await _seed_document(test_db, user=user, sha="d" * 64)
    await _seed_parse_run_with_parsed(
        test_db, parse_run_repo,
        source_document=seeded.source_document,
    )

    unknown_id = uuid4()
    result = await repo.get_latest_for_document(unknown_id)

    assert result is None
