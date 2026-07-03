import asyncio
from typing import AsyncGenerator, Generator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
)

TestSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def test_db() -> AsyncGenerator[AsyncSession, None]:
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="function")
async def client(test_db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield test_db

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def sync_client() -> TestClient:
    return TestClient(app)


@pytest.fixture(scope="function")
async def seed_project_user_source(test_db: AsyncSession):
    """Insert a Project + User + SourceDocument; return (project_id, user_id, source_id)."""
    from app.models import User
    from app.models.project import Project
    from app.models.source_document import SourceDocument

    user = User(
        id=uuid4(),
        email=f"{uuid4()}@example.com",
        full_name="Test User",
        auth_provider="email",
        password_hash="hashed",
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)

    project = Project(id=uuid4(), user_id=user.id, name="Test Project")
    test_db.add(project)
    await test_db.commit()
    await test_db.refresh(project)

    source = SourceDocument(id=uuid4(), sha256="a" * 64, storage_uri="local://a.pdf")
    test_db.add(source)
    await test_db.commit()
    await test_db.refresh(source)

    return project.id, user.id, source.id
