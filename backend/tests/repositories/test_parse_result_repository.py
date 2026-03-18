"""Tests for ParseResultRepository."""
import pytest
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.models.parse_result import ParseResult, ParseResultStatus
from app.repositories.parse_result_repository import ParseResultRepository


@pytest.fixture
async def repo(test_db: AsyncSession) -> ParseResultRepository:
    return ParseResultRepository(test_db)


@pytest.fixture
async def user(test_db: AsyncSession) -> User:
    user = User(
        id=uuid4(),
        email="test@example.com",
        full_name="Test User",
        auth_provider="email",
        password_hash="hashed",
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    return user


@pytest.fixture
async def project(test_db: AsyncSession, user: User):
    from app.models import Project
    project = Project(
        id=uuid4(),
        user_id=user.id,
        name="Test Project",
    )
    test_db.add(project)
    await test_db.commit()
    await test_db.refresh(project)
    return project


@pytest.fixture
async def document(test_db: AsyncSession, project, user: User):
    from app.models import Document, DocumentStatus
    doc = Document(
        id=uuid4(),
        project_id=project.id,
        created_by=user.id,
        source_type="upload",
        source_identifier="abc123",
        title="Test Document",
        source_metadata={"file_path": "/tmp/test.pdf", "mime_type": "application/pdf"},
        status=DocumentStatus.ready,
    )
    test_db.add(doc)
    await test_db.commit()
    await test_db.refresh(doc)
    return doc


class TestParseResultRepository:

    async def test_create(self, repo: ParseResultRepository, document, user: User):
        result = await repo.create(
            document_id=document.id,
            parser_type="llamaparse",
            created_by=user.id,
            parser_config={"tier": "agentic"},
        )
        assert result.id is not None
        assert result.document_id == document.id
        assert result.parser_type == "llamaparse"
        assert result.status == ParseResultStatus.pending
        assert result.parser_config == {"tier": "agentic"}

    async def test_get_by_id(self, repo: ParseResultRepository, document, user: User):
        created = await repo.create(
            document_id=document.id,
            parser_type="llamaparse",
            created_by=user.id,
        )
        fetched = await repo.get_by_id(created.id)
        assert fetched is not None
        assert fetched.id == created.id

    async def test_get_by_id_not_found(self, repo: ParseResultRepository):
        result = await repo.get_by_id(uuid4())
        assert result is None

    async def test_list_by_document(self, repo: ParseResultRepository, document, user: User):
        await repo.create(document_id=document.id, parser_type="llamaparse", created_by=user.id)
        await repo.create(document_id=document.id, parser_type="simple", created_by=user.id)

        results = await repo.list_by_document(document.id)
        assert len(results) == 2

    async def test_list_by_document_empty(self, repo: ParseResultRepository):
        results = await repo.list_by_document(uuid4())
        assert len(results) == 0

    async def test_update_status(self, repo: ParseResultRepository, document, user: User):
        created = await repo.create(
            document_id=document.id,
            parser_type="llamaparse",
            created_by=user.id,
        )
        updated = await repo.update_status(
            created.id,
            ParseResultStatus.failed,
            "Something went wrong",
        )
        assert updated.status == ParseResultStatus.failed
        assert updated.status_message == "Something went wrong"

    async def test_update_result(self, repo: ParseResultRepository, document, user: User):
        created = await repo.create(
            document_id=document.id,
            parser_type="llamaparse",
            created_by=user.id,
        )
        updated = await repo.update_result(
            parse_result_id=created.id,
            raw_text="Extracted text content",
            fidelity="markdown",
            markdown="# Heading\n\nParagraph",
            diagnostics={"char_count": 100},
            metadata={"page_count": 2},
        )
        assert updated.status == ParseResultStatus.completed
        assert updated.raw_text == "Extracted text content"
        assert updated.fidelity == "markdown"
        assert updated.markdown == "# Heading\n\nParagraph"
        assert updated.diagnostics == {"char_count": 100}

    async def test_set_started(self, repo: ParseResultRepository, document, user: User):
        created = await repo.create(
            document_id=document.id,
            parser_type="llamaparse",
            created_by=user.id,
        )
        assert created.started_at is None

        updated = await repo.set_started(created.id)
        assert updated.started_at is not None
