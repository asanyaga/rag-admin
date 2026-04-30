"""Tests for SourceResolutionService."""
import pytest
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.parse_run import ParseRun
from app.models.parsed_document import ParsedDocument as ParsedDocumentORM
from app.models.source_document import SourceDocument

from app.services.source_resolution_service import (
    SourceResolutionService,
    TextSource,
    BlocksSource,
)
from app.services.exceptions import NotFoundError, ValidationError


# ---------------------------------------------------------------------------
# Local fixtures — seed a minimal SourceDocument → ParseRun → ParsedDocument
# chain.  SQLite in-memory (from conftest.test_db) does not enforce FKs so we
# don't need User/Project rows.
# ---------------------------------------------------------------------------


async def _seed_source_and_run(session: AsyncSession) -> tuple[SourceDocument, ParseRun]:
    src = SourceDocument(
        id=uuid4(),
        sha256=uuid4().hex + uuid4().hex,
        storage_uri="local://test.pdf",
    )
    session.add(src)
    await session.commit()

    run = ParseRun(
        id=uuid4(),
        source_document_id=src.id,
        parser="llamaparse",
        representation_kind="vector_light",
        config_hash="a" * 64,
        status="succeeded",
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
    )
    session.add(run)
    await session.commit()
    return src, run


@pytest.fixture
async def seeded_parsed_document(test_db: AsyncSession) -> ParsedDocumentORM:
    """ParsedDocument with full_text and blocks populated; full_markdown=None."""
    src, run = await _seed_source_and_run(test_db)

    blocks = [{"id": "b1", "role": "paragraph", "text": "hello world"}]
    pd = ParsedDocumentORM(
        parse_run_id=run.id,
        source_document_id=src.id,
        full_text="clean parsed text",
        full_markdown=None,
        page_count=1,
        block_count=1,
        content={"blocks": blocks},
    )
    test_db.add(pd)
    await test_db.commit()
    await test_db.refresh(pd)
    return pd


@pytest.fixture
async def seeded_parsed_document_with_markdown(test_db: AsyncSession) -> ParsedDocumentORM:
    """ParsedDocument with both full_text and full_markdown populated."""
    src, run = await _seed_source_and_run(test_db)

    blocks = [{"id": "b1", "role": "paragraph", "text": "# Section\nSome markdown content."}]
    pd = ParsedDocumentORM(
        parse_run_id=run.id,
        source_document_id=src.id,
        full_text="Some markdown content.",
        full_markdown="# Section\nSome markdown content.",
        page_count=1,
        block_count=1,
        content={"blocks": blocks},
    )
    test_db.add(pd)
    await test_db.commit()
    await test_db.refresh(pd)
    return pd


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_full_text_returns_text_source(seeded_parsed_document, test_db):
    svc = SourceResolutionService(test_db)
    result = await svc.resolve(
        parsed_document_id=seeded_parsed_document.parse_run_id,
        source_representation="full_text",
    )
    assert isinstance(result, TextSource)
    assert result.text == seeded_parsed_document.full_text


@pytest.mark.asyncio
async def test_resolve_full_markdown_returns_text_source(seeded_parsed_document_with_markdown, test_db):
    svc = SourceResolutionService(test_db)
    result = await svc.resolve(
        parsed_document_id=seeded_parsed_document_with_markdown.parse_run_id,
        source_representation="full_markdown",
    )
    assert isinstance(result, TextSource)
    assert result.text == seeded_parsed_document_with_markdown.full_markdown


@pytest.mark.asyncio
async def test_resolve_block_returns_blocks_source(seeded_parsed_document, test_db):
    svc = SourceResolutionService(test_db)
    result = await svc.resolve(
        parsed_document_id=seeded_parsed_document.parse_run_id,
        source_representation="block",
    )
    assert isinstance(result, BlocksSource)
    assert len(result.blocks) >= 1


@pytest.mark.asyncio
async def test_resolve_missing_parsed_document_raises_not_found(test_db):
    svc = SourceResolutionService(test_db)
    with pytest.raises(NotFoundError, match="Parsed document"):
        await svc.resolve(
            parsed_document_id=uuid4(),
            source_representation="full_text",
        )


@pytest.mark.asyncio
async def test_resolve_full_markdown_missing_segment_raises_validation(seeded_parsed_document, test_db):
    """seeded_parsed_document fixture has full_markdown=None."""
    svc = SourceResolutionService(test_db)
    with pytest.raises(ValidationError, match="full_markdown"):
        await svc.resolve(
            parsed_document_id=seeded_parsed_document.parse_run_id,
            source_representation="full_markdown",
        )


@pytest.mark.asyncio
async def test_resolve_full_text_missing_segment_raises_validation(test_db: AsyncSession):
    """ParsedDocument with full_text=None raises ValidationError for full_text."""
    src, run = await _seed_source_and_run(test_db)
    pd = ParsedDocumentORM(
        parse_run_id=run.id,
        source_document_id=src.id,
        full_text=None,
        full_markdown=None,
        page_count=1,
        block_count=0,
        content={},
    )
    test_db.add(pd)
    await test_db.commit()

    svc = SourceResolutionService(test_db)
    with pytest.raises(ValidationError, match="full_text"):
        await svc.resolve(
            parsed_document_id=run.id,
            source_representation="full_text",
        )
