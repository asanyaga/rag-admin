# backend/tests/services/parse_agent/test_engine.py
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.parse_agent_run import ParseAgentRunStatus
from app.repositories.parse_agent_run_repository import ParseAgentRunRepository
from app.services.parse_agent.engine import execute_parse_agent


class _FakeRun:
    id = "run-xyz"
    failed_pages = []


class _FakeDoc:
    page_count = 1
    full_text = "hi"
    blocks = []


class _FakeParsingService:
    async def parse_and_persist(self, **kwargs):
        return _FakeRun(), _FakeDoc()


@pytest.mark.asyncio
async def test_execute_projects_two_steps_and_completes(seed_project_user_source, test_db: AsyncSession):
    project_id, _user_id, source_id = seed_project_user_source
    repo = ParseAgentRunRepository(test_db)
    run = await repo.create_run(
        project_id=project_id, source_document_id=source_id,
        started_at=datetime.now(timezone.utc),
    )

    await execute_parse_agent(
        test_db,
        run_id=run.id,
        initial_state={
            "file_path": "local://x.pdf", "source_document_id": str(source_id),
            "project_id": str(project_id), "representation_kind": "extract_rich",
            "config": {"parser": "simple"},
        },
        parsing_service=_FakeParsingService(),
        source=object(),
    )

    got = await repo.get_run(run.id)
    assert got.status == ParseAgentRunStatus.completed.value
    assert got.finished_at is not None

    steps = await repo.list_steps(run.id)
    assert [s.node for s in steps] == ["parse", "health_check"]
    assert steps[0].output_keys == ["parse_run_id", "page_count", "text_len", "failed_page_count", "block_count"]
    assert steps[0].input_keys == ["file_path", "config", "representation_kind", "project_id", "source_document_id"]
    assert steps[0].state_delta["parse_run_id"] == "run-xyz"
    assert steps[1].state_delta["quality_signal"]["ok"] is True


@pytest.mark.asyncio
async def test_execute_marks_failed_on_error(seed_project_user_source, test_db: AsyncSession):
    project_id, _user_id, source_id = seed_project_user_source
    repo = ParseAgentRunRepository(test_db)
    run = await repo.create_run(
        project_id=project_id, source_document_id=source_id,
        started_at=datetime.now(timezone.utc),
    )

    class _Boom:
        async def parse_and_persist(self, **kwargs):
            raise RuntimeError("parser exploded")

    await execute_parse_agent(
        test_db, run_id=run.id,
        initial_state={
            "file_path": "local://x.pdf", "source_document_id": str(source_id),
            "project_id": str(project_id), "representation_kind": "extract_rich",
            "config": {"parser": "simple"},
        },
        parsing_service=_Boom(), source=object(),
    )

    got = await repo.get_run(run.id)
    assert got.status == ParseAgentRunStatus.failed.value
    assert "parser exploded" in (got.error or "")
