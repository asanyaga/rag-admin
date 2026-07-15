from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.parse_agent_run import ParseAgentRun, ParseAgentRunStep, ParseAgentRunStatus


@pytest.mark.asyncio
async def test_can_persist_run_and_step(seed_project_user_source, test_db: AsyncSession):
    project_id, _user_id, source_id = seed_project_user_source

    run = ParseAgentRun(
        id=uuid4(),
        project_id=project_id,
        source_document_id=source_id,
        status=ParseAgentRunStatus.running.value,
        started_at=datetime.now(timezone.utc),
    )
    test_db.add(run)
    await test_db.commit()

    step = ParseAgentRunStep(
        id=uuid4(),
        run_id=run.id,
        seq=0,
        node="parse",
        phase="end",
        status="succeeded",
        input_keys=["file_path"],
        output_keys=["parse_run_id"],
        state_delta={"parse_run_id": "abc"},
        message=None,
        duration_ms=42,
    )
    test_db.add(step)
    await test_db.commit()

    rows = (await test_db.execute(select(ParseAgentRunStep).where(ParseAgentRunStep.run_id == run.id))).scalars().all()
    assert len(rows) == 1
    assert rows[0].output_keys == ["parse_run_id"]
    assert rows[0].state_delta == {"parse_run_id": "abc"}
