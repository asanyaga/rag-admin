# backend/tests/repositories/test_parse_agent_run_repository.py
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.parse_agent_run import ParseAgentRunStatus
from app.repositories.parse_agent_run_repository import ParseAgentRunRepository, StepCreate


@pytest.mark.asyncio
async def test_create_append_finish_and_read(seed_project_user_source, test_db: AsyncSession):
    project_id, _user_id, source_id = seed_project_user_source
    repo = ParseAgentRunRepository(test_db)

    run = await repo.create_run(
        project_id=project_id, source_document_id=source_id,
        started_at=datetime.now(timezone.utc),
    )
    assert run.status == ParseAgentRunStatus.running.value

    await repo.append_step(StepCreate(
        run_id=run.id, seq=0, node="parse", phase="end", status="succeeded",
        input_keys=["file_path"], output_keys=["parse_run_id"],
        state_delta={"parse_run_id": "abc"}, duration_ms=10,
    ))
    await repo.append_step(StepCreate(
        run_id=run.id, seq=1, node="health_check", phase="end", status="succeeded",
        input_keys=["text_len"], output_keys=["quality_signal"],
        state_delta={"quality_signal": {"ok": True}}, duration_ms=2,
    ))
    await repo.finish_run(run.id, status=ParseAgentRunStatus.completed.value,
                          finished_at=datetime.now(timezone.utc))

    got = await repo.get_run(run.id)
    assert got.status == ParseAgentRunStatus.completed.value
    assert got.finished_at is not None

    steps = await repo.list_steps(run.id)
    assert [s.node for s in steps] == ["parse", "health_check"]
    assert steps[0].seq == 0 and steps[1].seq == 1
