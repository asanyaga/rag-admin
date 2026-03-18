"""Tests for ParseService."""
import pytest
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, Document, DocumentStatus
from app.models.parse_result import ParseResultStatus
from app.repositories.document_repository import DocumentRepository
from app.repositories.parse_result_repository import ParseResultRepository
from app.services.parse_service import ParseService
from app.services.exceptions import NotFoundError


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
    project = Project(id=uuid4(), user_id=user.id, name="Test Project")
    test_db.add(project)
    await test_db.commit()
    await test_db.refresh(project)
    return project


@pytest.fixture
async def document(test_db: AsyncSession, project, user: User):
    doc = Document(
        id=uuid4(),
        project_id=project.id,
        created_by=user.id,
        source_type="upload",
        source_identifier="abc123",
        title="Test Document",
        source_metadata={"file_path": "/tmp/test.pdf"},
        status=DocumentStatus.ready,
    )
    test_db.add(doc)
    await test_db.commit()
    await test_db.refresh(doc)
    return doc


@pytest.fixture
async def parse_service(test_db: AsyncSession) -> ParseService:
    return ParseService(
        parse_result_repo=ParseResultRepository(test_db),
        document_repo=DocumentRepository(test_db),
    )


class TestParseService:

    async def test_create_parse_result(self, parse_service: ParseService, document, user: User):
        result = await parse_service.create_parse_result(
            document_id=document.id,
            user_id=user.id,
            parser_type="llamaparse",
            parser_config={"tier": "agentic"},
        )
        assert result.status == ParseResultStatus.pending
        assert result.parser_type == "llamaparse"

    async def test_create_parse_result_document_not_found(self, parse_service: ParseService, user: User):
        with pytest.raises(NotFoundError):
            await parse_service.create_parse_result(
                document_id=uuid4(),
                user_id=user.id,
                parser_type="llamaparse",
            )

    async def test_get_parse_result(self, parse_service: ParseService, document, user: User):
        created = await parse_service.create_parse_result(
            document_id=document.id,
            user_id=user.id,
            parser_type="llamaparse",
        )
        fetched = await parse_service.get_parse_result(created.id)
        assert fetched.id == created.id

    async def test_get_parse_result_not_found(self, parse_service: ParseService):
        with pytest.raises(NotFoundError):
            await parse_service.get_parse_result(uuid4())

    async def test_list_parse_results(self, parse_service: ParseService, document, user: User):
        await parse_service.create_parse_result(
            document_id=document.id, user_id=user.id, parser_type="llamaparse"
        )
        await parse_service.create_parse_result(
            document_id=document.id, user_id=user.id, parser_type="simple"
        )

        results = await parse_service.list_parse_results(document.id)
        assert len(results) == 2

    async def test_list_parse_results_empty(self, parse_service: ParseService):
        results = await parse_service.list_parse_results(uuid4())
        assert len(results) == 0

    async def test_get_parsers(self, parse_service: ParseService):
        parsers = await parse_service.get_parsers()
        assert len(parsers) >= 1
        parser_types = [p.parser_type for p in parsers]
        assert "simple" in parser_types
