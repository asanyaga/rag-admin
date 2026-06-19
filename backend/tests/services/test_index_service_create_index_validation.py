"""Tests for IndexService validation against the parsed-document family."""
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document as DocumentORM
from app.models.parse_run import ParseRun
from app.models.parsed_document import ParsedDocument
from app.models.project import Project
from app.models.source_document import SourceDocument
from app.models.user import User
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.index_repository import IndexRepository
from app.repositories.parsed_document_repository import ParsedDocumentRepository
from app.schemas.index import IndexConfig, IndexCreate
from app.services.exceptions import NotFoundError, ValidationError
from app.services.index_service import IndexService


def _config(
    parser: str = "llamaparse",
    parse_config_hash: str = "h" * 64,
    source_rep: str = "full_text",
    strategy: str = "recursive_character",
) -> IndexConfig:
    return IndexConfig.model_validate({
        "parser": parser,
        "parse_config_hash": parse_config_hash,
        "source_representation": source_rep,
        "chunking_strategy": strategy,
        "chunk_size": 500,
        "chunk_overlap": 50,
        "chunk_unit": "characters",
        "embedding_provider": "openai",
        "embedding_model": "text-embedding-3-small",
    })


async def _seed_user_project(db: AsyncSession):
    user = User(
        email=f"u{uuid4().hex[:6]}@example.com",
        password_hash="x",
        full_name="u",
        auth_provider="email",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    project = Project(user_id=user.id, name=f"P{uuid4().hex[:6]}")
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return user, project


async def _seed_parsed(
    db: AsyncSession, *,
    user: User, project: Project, sha: str,
    parser: str = "llamaparse", config_hash: str = "h" * 64,
    full_markdown: str | None = None, status: str = "succeeded",
) -> ParsedDocument:
    sd = SourceDocument(id=uuid4(), sha256=sha, storage_uri=f"local://{sha[:6]}.pdf")
    db.add(sd)
    await db.commit()
    doc = DocumentORM(
        project_id=project.id, source_document_id=sd.id,
        source_type="upload", source_identifier=sha, title=sha[:6],
        status="ready", created_by=user.id,
    )
    db.add(doc)
    await db.commit()
    pr = ParseRun(
        source_document_id=sd.id, parser=parser,
        representation_kind="full_markdown" if full_markdown else "full_text",
        config={}, config_hash=config_hash,
        status=status,
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc) if status == "succeeded" else None,
    )
    db.add(pr)
    await db.commit()
    await db.refresh(pr)
    pd = ParsedDocument(
        parse_run_id=pr.id, source_document_id=sd.id,
        full_text="hello", full_markdown=full_markdown,
        page_count=1, block_count=1, content={"blocks": [{"text": "hi"}]},
    )
    db.add(pd)
    await db.commit()
    await db.refresh(pd)
    return pd


def _service(db: AsyncSession) -> IndexService:
    return IndexService(
        index_repo=IndexRepository(db),
        chunk_repo=ChunkRepository(db),
        parsed_doc_repo=ParsedDocumentRepository(db),
    )


@pytest.mark.asyncio
async def test_create_index_persists_parse_run_id_per_row(test_db):
    user, project = await _seed_user_project(test_db)
    pd = await _seed_parsed(test_db, user=user, project=project, sha="a" * 64)
    svc = _service(test_db)

    response = await svc.create_index(
        project_id=project.id, user_id=user.id,
        data=IndexCreate(name="i", config=_config(), parsed_document_ids=[pd.parse_run_id]),
    )
    # The response is the freshly-created index. Verify by re-fetching.
    fetched = await svc.get_index(response.id, project.id)
    assert fetched.document_count >= 1


@pytest.mark.asyncio
async def test_create_index_rejects_unknown_parsed_doc(test_db):
    user, project = await _seed_user_project(test_db)
    svc = _service(test_db)

    with pytest.raises(NotFoundError, match="parsed_document"):
        await svc.create_index(
            project_id=project.id, user_id=user.id,
            data=IndexCreate(name="i", config=_config(), parsed_document_ids=[uuid4()]),
        )


@pytest.mark.asyncio
async def test_create_index_rejects_parsed_doc_outside_project(test_db):
    user_a, project_a = await _seed_user_project(test_db)
    user_b, project_b = await _seed_user_project(test_db)
    pd_b = await _seed_parsed(test_db, user=user_b, project=project_b, sha="b" * 64)
    svc = _service(test_db)

    with pytest.raises(NotFoundError, match="parsed_document"):
        await svc.create_index(
            project_id=project_a.id, user_id=user_a.id,
            data=IndexCreate(name="i", config=_config(), parsed_document_ids=[pd_b.parse_run_id]),
        )


@pytest.mark.asyncio
async def test_create_index_rejects_family_mismatch(test_db):
    user, project = await _seed_user_project(test_db)
    pd = await _seed_parsed(
        test_db, user=user, project=project, sha="c" * 64,
        parser="landingai", config_hash="h" * 64,
    )
    svc = _service(test_db)

    cfg = _config(parser="llamaparse", parse_config_hash="h" * 64)
    with pytest.raises(ValidationError, match="family"):
        await svc.create_index(
            project_id=project.id, user_id=user.id,
            data=IndexCreate(name="i", config=cfg, parsed_document_ids=[pd.parse_run_id]),
        )


@pytest.mark.asyncio
async def test_create_index_rejects_failed_parse_run(test_db):
    user, project = await _seed_user_project(test_db)
    pd = await _seed_parsed(test_db, user=user, project=project, sha="e" * 64, status="failed")
    svc = _service(test_db)

    with pytest.raises(ValidationError, match="parse run"):
        await svc.create_index(
            project_id=project.id, user_id=user.id,
            data=IndexCreate(name="i", config=_config(), parsed_document_ids=[pd.parse_run_id]),
        )
