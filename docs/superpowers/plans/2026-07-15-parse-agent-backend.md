# Parse Agent — Backend Spine Implementation Plan

> **⚠️ Superseded (2026-08-26):** The parse-agent stack has been retired. Parsing
> is now a tool in the agents feature — see
> `docs/superpowers/specs/2026-08-26-parse-tool-design.md`. This document is kept
> for historical context only.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A file upload starts a background parse-agent run whose every step is persisted to an append-only trace, readable via a polling API.

**Architecture:** A new, purpose-built engine runs a hand-wired 2-node LangGraph graph (`parse` → `health_check`) in a FastAPI background task. The `parse` node reuses the existing `ParsingService.parse_and_persist` (producing a real CDM `ParseRun`). The engine consumes `astream(stream_mode="updates")` and *projects* each node's output into our own `parse_agent_run_step` table — the frontend never reads LangGraph's internals. This plan is the **backend** subsystem; the frontend trace UI is a follow-on plan.

**Tech Stack:** Python 3.12, FastAPI (async), SQLAlchemy 2.0, LangGraph, Alembic, pytest (SQLite in-memory via `test_db` fixture).

## Global Constraints

- Data flow: router → service/engine → repository → database. Services/engines raise; routers translate to HTTP.
- All DB operations async with type hints.
- New resource is `/parse-agent-runs` — do **NOT** touch or overload the existing read/delete-only `/parse-runs` (CDM) router.
- The `parse` node MUST reuse `ParsingService.parse_and_persist`; do not add a second parse path.
- BYOK: parser API keys are resolved in the router and passed into the background task; never stored in `config` or returned in responses. v1 default parser is `simple` (needs no key).
- API responses use camelCase aliases (existing `CamelModel`/`alias_generator` convention — mirror sibling schemas).
- Tests run on SQLite in-memory; models must be registered in `app/models/__init__.py` so `Base.metadata.create_all` builds their tables.
- Reference spec: `docs/superpowers/specs/2026-07-15-parse-agent-design.md`.

---

## File Structure

- `backend/app/models/parse_agent_run.py` — `ParseAgentRun`, `ParseAgentRunStep`, `ParseAgentRunStatus` (they change together).
- `backend/app/models/__init__.py` — register the new models.
- `backend/alembic/versions/<rev>_create_parse_agent_run_tables.py` — migration.
- `backend/app/repositories/parse_agent_run_repository.py` — `ParseAgentRunRepository` + `StepCreate` DTO.
- `backend/app/services/parse_agent/__init__.py`
- `backend/app/services/parse_agent/nodes.py` — `NodeSpec`, `NODE_SPECS`, `GRAPH_NODES`, `health_check_node`, `make_parse_node`.
- `backend/app/services/parse_agent/graph.py` — `build_parse_graph`.
- `backend/app/services/parse_agent/engine.py` — `execute_parse_agent` (session-injected, testable) + `run_parse_agent` (opens `AsyncSessionLocal`, for the background task).
- `backend/app/schemas/parse_agent_run.py` — response schemas.
- `backend/app/routers/parse_agent_runs.py` — `POST` + `GET`.
- `backend/app/main.py` — include the router.
- Tests under `backend/tests/…` mirroring the above.

---

### Task 1: Models + registration + migration

**Files:**
- Create: `backend/app/models/parse_agent_run.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/<rev>_create_parse_agent_run_tables.py`
- Test: `backend/tests/models/test_parse_agent_run_model.py`

**Interfaces:**
- Produces: `ParseAgentRun` (cols: `id`, `project_id`, `source_document_id`, `status`, `started_at`, `finished_at`, `error`, `created_at`), `ParseAgentRunStep` (cols: `id`, `run_id`, `seq`, `node`, `phase`, `status`, `input_keys`, `output_keys`, `state_delta`, `message`, `duration_ms`, `created_at`), `ParseAgentRunStatus` enum (`running`, `completed`, `failed`).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/models/test_parse_agent_run_model.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest tests/models/test_parse_agent_run_model.py -o "addopts=" -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.models.parse_agent_run'`.

- [ ] **Step 3: Write the models**

```python
# backend/app/models/parse_agent_run.py
"""ORM models for the parse agent: orchestration run + append-only trace steps."""
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ParseAgentRunStatus(str, Enum):
    running = "running"
    completed = "completed"
    failed = "failed"


class ParseAgentRun(Base):
    __tablename__ = "parse_agent_runs"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4,
        server_default=sa.text("gen_random_uuid()"),
    )
    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False,
    )
    source_document_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("source_documents.id", ondelete="CASCADE"), nullable=False,
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=datetime.utcnow, server_default=sa.text("NOW()"),
    )

    __table_args__ = (
        sa.Index("ix_parse_agent_runs_project_id", "project_id"),
        sa.Index("ix_parse_agent_runs_status", "status"),
    )


class ParseAgentRunStep(Base):
    __tablename__ = "parse_agent_run_steps"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4,
        server_default=sa.text("gen_random_uuid()"),
    )
    run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("parse_agent_runs.id", ondelete="CASCADE"), nullable=False,
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    node: Mapped[str] = mapped_column(Text, nullable=False)
    phase: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    input_keys: Mapped[list] = mapped_column(JSON, nullable=False, default=list, server_default=sa.text("'[]'"))
    output_keys: Mapped[list] = mapped_column(JSON, nullable=False, default=list, server_default=sa.text("'[]'"))
    state_delta: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, server_default=sa.text("'{}'"))
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=datetime.utcnow, server_default=sa.text("NOW()"),
    )

    __table_args__ = (
        sa.Index("ix_parse_agent_run_steps_run_id_seq", "run_id", "seq"),
    )
```

- [ ] **Step 4: Register the models**

In `backend/app/models/__init__.py`, add after the `agent_run` import (line ~28):

```python
from app.models.parse_agent_run import ParseAgentRun, ParseAgentRunStep, ParseAgentRunStatus
```

And add to `__all__`:

```python
    "ParseAgentRun",
    "ParseAgentRunStep",
    "ParseAgentRunStatus",
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && uv run python -m pytest tests/models/test_parse_agent_run_model.py -o "addopts=" -v`
Expected: PASS.

- [ ] **Step 6: Generate the Alembic migration**

Run: `cd backend && alembic revision --autogenerate -m "create parse_agent_run tables"`
Then open the generated file in `backend/alembic/versions/` and confirm `upgrade()` calls `op.create_table("parse_agent_runs", ...)` and `op.create_table("parse_agent_run_steps", ...)` with the indexes, and `downgrade()` drops them. If autogenerate missed the tables (metadata not imported), verify `app.models` is imported in `alembic/env.py`; it is registered in Step 4 so autogenerate should detect them.

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/parse_agent_run.py backend/app/models/__init__.py backend/alembic/versions backend/tests/models/test_parse_agent_run_model.py
git commit -m "feat(parse-agent): parse_agent_run + step models and migration"
```

---

### Task 2: Repository

**Files:**
- Create: `backend/app/repositories/parse_agent_run_repository.py`
- Test: `backend/tests/repositories/test_parse_agent_run_repository.py`

**Interfaces:**
- Consumes: `ParseAgentRun`, `ParseAgentRunStep`, `ParseAgentRunStatus` (Task 1).
- Produces:
  - `StepCreate` dataclass: `run_id: UUID`, `seq: int`, `node: str`, `phase: str`, `status: str`, `input_keys: list[str]`, `output_keys: list[str]`, `state_delta: dict`, `message: str | None = None`, `duration_ms: int | None = None`.
  - `ParseAgentRunRepository(session)` with:
    - `async create_run(*, project_id: UUID, source_document_id: UUID, started_at: datetime) -> ParseAgentRun` (status `running`)
    - `async append_step(dto: StepCreate) -> ParseAgentRunStep`
    - `async finish_run(run_id: UUID, *, status: str, finished_at: datetime, error: str | None = None) -> None`
    - `async get_run(run_id: UUID) -> ParseAgentRun | None`
    - `async list_steps(run_id: UUID) -> list[ParseAgentRunStep]` (ordered by `seq`)

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest tests/repositories/test_parse_agent_run_repository.py -o "addopts=" -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.repositories.parse_agent_run_repository'`.

- [ ] **Step 3: Write the repository**

```python
# backend/app/repositories/parse_agent_run_repository.py
"""Repository for parse-agent runs and their append-only trace steps."""
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.parse_agent_run import ParseAgentRun, ParseAgentRunStatus, ParseAgentRunStep


@dataclass
class StepCreate:
    run_id: UUID
    seq: int
    node: str
    phase: str
    status: str
    input_keys: list[str]
    output_keys: list[str]
    state_delta: dict
    message: str | None = None
    duration_ms: int | None = None


class ParseAgentRunRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_run(
        self, *, project_id: UUID, source_document_id: UUID, started_at: datetime,
    ) -> ParseAgentRun:
        run = ParseAgentRun(
            project_id=project_id,
            source_document_id=source_document_id,
            status=ParseAgentRunStatus.running.value,
            started_at=started_at,
        )
        self.session.add(run)
        await self.session.commit()
        await self.session.refresh(run)
        return run

    async def append_step(self, dto: StepCreate) -> ParseAgentRunStep:
        step = ParseAgentRunStep(
            run_id=dto.run_id, seq=dto.seq, node=dto.node, phase=dto.phase,
            status=dto.status, input_keys=dto.input_keys, output_keys=dto.output_keys,
            state_delta=dto.state_delta, message=dto.message, duration_ms=dto.duration_ms,
        )
        self.session.add(step)
        await self.session.commit()
        await self.session.refresh(step)
        return step

    async def finish_run(
        self, run_id: UUID, *, status: str, finished_at: datetime, error: str | None = None,
    ) -> None:
        run = await self.get_run(run_id)
        if run is None:
            raise ValueError(f"ParseAgentRun {run_id} not found")
        run.status = status
        run.finished_at = finished_at
        if error is not None:
            run.error = error
        await self.session.commit()

    async def get_run(self, run_id: UUID) -> ParseAgentRun | None:
        result = await self.session.execute(
            select(ParseAgentRun).where(ParseAgentRun.id == run_id)
        )
        return result.scalar_one_or_none()

    async def list_steps(self, run_id: UUID) -> list[ParseAgentRunStep]:
        result = await self.session.execute(
            select(ParseAgentRunStep)
            .where(ParseAgentRunStep.run_id == run_id)
            .order_by(ParseAgentRunStep.seq)
        )
        return list(result.scalars().all())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run python -m pytest tests/repositories/test_parse_agent_run_repository.py -o "addopts=" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/repositories/parse_agent_run_repository.py backend/tests/repositories/test_parse_agent_run_repository.py
git commit -m "feat(parse-agent): ParseAgentRunRepository"
```

---

### Task 3: Node specs + nodes

**Files:**
- Create: `backend/app/services/parse_agent/__init__.py` (empty)
- Create: `backend/app/services/parse_agent/nodes.py`
- Test: `backend/tests/services/parse_agent/test_nodes.py`

**Interfaces:**
- Consumes: `ParsingService` (`app.services.parsing.parsing_service`), `SourceDocument` CDM (`app.cdm.source.SourceDocument`).
- Produces:
  - `NodeSpec(slug: str, input_keys: list[str], output_keys: list[str])`
  - `NODE_SPECS: dict[str, NodeSpec]`, `GRAPH_NODES: list[str]` (order `["parse", "health_check"]`)
  - `async health_check_node(state: dict) -> dict` — returns `{"quality_signal": {...}}`
  - `make_parse_node(parsing_service, source) -> async callable(state) -> dict` — returns `{"parse_run_id", "page_count", "text_len", "failed_page_count", "block_count"}`

Notes: nodes return **partial deltas** (only their own keys). The graph uses a `TypedDict` state schema (Task 4) so LangGraph gives each key its own channel and the deltas merge per-key. (A bare `StateGraph(dict)` in langgraph 1.1.6 is a single whole-state channel that would drop accumulated keys — the POC only avoids this by spreading `{**state}`.) `parse_run_id` is the link the trace uses for the results-viewer handoff.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/services/parse_agent/test_nodes.py
import pytest

from app.services.parse_agent.nodes import GRAPH_NODES, NODE_SPECS, health_check_node, make_parse_node


@pytest.mark.asyncio
async def test_health_check_ok_when_text_present_and_no_failed_pages():
    state = {"text_len": 12, "failed_page_count": 0, "block_count": 3}
    out = await health_check_node(state)
    assert out["quality_signal"]["text_non_empty"] is True
    assert out["quality_signal"]["ok"] is True


@pytest.mark.asyncio
async def test_health_check_not_ok_when_empty_text():
    state = {"text_len": 0, "failed_page_count": 0, "block_count": 0}
    out = await health_check_node(state)
    assert out["quality_signal"]["ok"] is False


@pytest.mark.asyncio
async def test_make_parse_node_calls_parsing_service_and_returns_delta():
    class FakeRun:
        id = "run-123"
        failed_pages = []

    class FakeDoc:
        page_count = 2
        full_text = "hello"
        blocks = [1, 2, 3]

    class FakeParsingService:
        def __init__(self):
            self.called_with = None

        async def parse_and_persist(self, **kwargs):
            self.called_with = kwargs
            return FakeRun(), FakeDoc()

    svc = FakeParsingService()
    source = object()  # closed over; not inspected by the node
    node = make_parse_node(svc, source)

    state = {
        "file_path": "local://x.pdf", "project_id": "proj-1",
        "representation_kind": "extract_rich", "config": {"parser": "simple"},
    }
    out = await node(state)

    assert out["parse_run_id"] == "run-123"
    assert out["page_count"] == 2
    assert out["text_len"] == 5
    assert out["failed_page_count"] == 0
    assert out["block_count"] == 3
    assert svc.called_with["file_path"] == "local://x.pdf"
    assert svc.called_with["source"] is source


def test_graph_nodes_order_and_specs():
    assert GRAPH_NODES == ["parse", "health_check"]
    assert set(NODE_SPECS) == {"parse", "health_check"}
    assert "file_path" in NODE_SPECS["parse"].input_keys
    assert "quality_signal" in NODE_SPECS["health_check"].output_keys
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest tests/services/parse_agent/test_nodes.py -o "addopts=" -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.parse_agent'`.

- [ ] **Step 3: Write the nodes**

Create empty `backend/app/services/parse_agent/__init__.py`, then:

```python
# backend/app/services/parse_agent/nodes.py
"""Parse-agent graph nodes and their static contracts.

Nodes return PARTIAL deltas (only the keys they own). The graph uses a TypedDict
state schema (see graph.py) so LangGraph gives each key its own channel and the
deltas merge per-key across nodes.
"""
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class NodeSpec:
    slug: str
    input_keys: list[str]
    output_keys: list[str]


PARSE_SPEC = NodeSpec(
    slug="parse",
    input_keys=["file_path", "config", "representation_kind", "project_id", "source_document_id"],
    output_keys=["parse_run_id", "page_count", "text_len", "failed_page_count", "block_count"],
)
HEALTH_SPEC = NodeSpec(
    slug="health_check",
    input_keys=["text_len", "failed_page_count", "block_count"],
    output_keys=["quality_signal"],
)

NODE_SPECS: dict[str, NodeSpec] = {PARSE_SPEC.slug: PARSE_SPEC, HEALTH_SPEC.slug: HEALTH_SPEC}
GRAPH_NODES: list[str] = ["parse", "health_check"]


def make_parse_node(parsing_service, source):
    """Factory: returns a `parse` node closing over the parsing service + source CDM."""
    async def parse_node(state: dict) -> dict:
        run, doc = await parsing_service.parse_and_persist(
            source=source,
            file_path=state["file_path"],
            representation_kind=state["representation_kind"],
            config=state["config"],
            project_id=UUID(str(state["project_id"])),
        )
        full_text = doc.full_text or ""
        return {
            "parse_run_id": str(run.id),
            "page_count": doc.page_count,
            "text_len": len(full_text),
            "failed_page_count": len(run.failed_pages),
            "block_count": len(doc.blocks),
        }
    return parse_node


async def health_check_node(state: dict) -> dict:
    """Reference-free quality signal. Pure function of accumulated state."""
    text_len = int(state.get("text_len", 0) or 0)
    failed_pages = int(state.get("failed_page_count", 0) or 0)
    block_count = int(state.get("block_count", 0) or 0)
    return {
        "quality_signal": {
            "text_non_empty": text_len > 0,
            "failed_pages": failed_pages,
            "block_count": block_count,
            "ok": text_len > 0 and failed_pages == 0,
        }
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run python -m pytest tests/services/parse_agent/test_nodes.py -o "addopts=" -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/parse_agent/__init__.py backend/app/services/parse_agent/nodes.py backend/tests/services/parse_agent/test_nodes.py
git commit -m "feat(parse-agent): graph node contracts (parse, health_check)"
```

---

### Task 4: Graph builder

**Files:**
- Create: `backend/app/services/parse_agent/graph.py`
- Test: `backend/tests/services/parse_agent/test_graph.py`

**Interfaces:**
- Consumes: `make_parse_node`, `health_check_node` (Task 3).
- Produces: `build_parse_graph(parsing_service, source)` → a **compiled** LangGraph graph. Hand-wired with raw primitives (`add_node` / `add_edge`), state schema = a `TypedDict(total=False)` (`ParseAgentState`) so partial-delta node returns merge per-key (a bare `dict` schema would not), no checkpointer (v1 has no interrupt).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/services/parse_agent/test_graph.py
import pytest

from app.services.parse_agent.graph import build_parse_graph


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
async def test_graph_streams_two_node_updates_in_order():
    compiled = build_parse_graph(_FakeParsingService(), source=object())
    initial = {
        "file_path": "local://x.pdf", "project_id": "proj-1",
        "representation_kind": "extract_rich", "config": {"parser": "simple"},
    }

    seen: list[str] = []
    async for chunk in compiled.astream(initial, stream_mode="updates"):
        seen.extend(chunk.keys())

    assert seen == ["parse", "health_check"]


@pytest.mark.asyncio
async def test_graph_accumulates_state_to_final():
    compiled = build_parse_graph(_FakeParsingService(), source=object())
    initial = {
        "file_path": "local://x.pdf", "project_id": "proj-1",
        "representation_kind": "extract_rich", "config": {"parser": "simple"},
    }
    final = await compiled.ainvoke(initial)
    assert final["parse_run_id"] == "run-xyz"
    assert final["quality_signal"]["ok"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest tests/services/parse_agent/test_graph.py -o "addopts=" -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.parse_agent.graph'`.

- [ ] **Step 3: Write the graph builder**

```python
# backend/app/services/parse_agent/graph.py
"""Hand-wired parse-agent graph: START -> parse -> health_check -> END.

Raw LangGraph primitives on purpose (pedagogy). No checkpointer in v1 — there is
no interrupt/human-review yet; durability comes from the persisted step log.

State schema is a TypedDict, NOT a bare dict: in langgraph 1.1.6 StateGraph(dict)
is a single whole-state LastValue channel, so partial-delta node returns overwrite
the whole state and accumulated keys are lost. A TypedDict gives per-key channels
so partial deltas merge.
"""
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app.services.parse_agent.nodes import health_check_node, make_parse_node


class ParseAgentState(TypedDict, total=False):
    file_path: str
    source_document_id: str
    project_id: str
    representation_kind: str
    config: dict
    parse_run_id: str
    page_count: int
    text_len: int
    failed_page_count: int
    block_count: int
    quality_signal: dict


def build_parse_graph(parsing_service, source):
    graph = StateGraph(ParseAgentState)
    graph.add_node("parse", make_parse_node(parsing_service, source))
    graph.add_node("health_check", health_check_node)
    graph.add_edge(START, "parse")
    graph.add_edge("parse", "health_check")
    graph.add_edge("health_check", END)
    return graph.compile()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run python -m pytest tests/services/parse_agent/test_graph.py -o "addopts=" -v`
Expected: PASS. If `test_graph_streams_two_node_updates_in_order` shows merged state instead of per-node deltas, that means the installed LangGraph treats a bare `dict` schema differently than the POC — stop and report (the POC at `app/services/agent/state.py` relies on this behavior, so it should hold).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/parse_agent/graph.py backend/tests/services/parse_agent/test_graph.py
git commit -m "feat(parse-agent): hand-wired parse graph builder"
```

---

### Task 5: Execution engine

**Files:**
- Create: `backend/app/services/parse_agent/engine.py`
- Test: `backend/tests/services/parse_agent/test_engine.py`

**Interfaces:**
- Consumes: `build_parse_graph` (Task 4), `ParseAgentRunRepository` + `StepCreate` (Task 2), `NODE_SPECS` (Task 3), `ParseAgentRunStatus` (Task 1), `ParsingService`, `SourceDocument` CDM.
- Produces:
  - `async execute_parse_agent(session, *, run_id, initial_state, parsing_service, source) -> None` — session-injected core; streams the graph and projects steps; finalizes run status. **Testable with `test_db`.**
  - `async run_parse_agent(*, run_id, source_document_id, file_path, project_id, config, representation_kind, storage_service, llamaparse_api_key=None, landingai_api_key=None) -> None` — background-task entry: opens `AsyncSessionLocal`, builds `ParsingService` + source CDM (mirrors `process_cdm_parsing`), calls `execute_parse_agent`.

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest tests/services/parse_agent/test_engine.py -o "addopts=" -v`
Expected: FAIL with `ImportError: cannot import name 'execute_parse_agent'`.

- [ ] **Step 3: Write the engine**

```python
# backend/app/services/parse_agent/engine.py
"""Parse-agent execution engine: run the graph, project each step into our trace."""
import json
import logging
import time
from datetime import datetime, timezone
from uuid import UUID

from app.models.parse_agent_run import ParseAgentRunStatus
from app.repositories.parse_agent_run_repository import ParseAgentRunRepository, StepCreate
from app.services.parse_agent.graph import build_parse_graph
from app.services.parse_agent.nodes import NODE_SPECS

logger = logging.getLogger(__name__)


def _json_safe(delta: dict) -> dict:
    safe = {}
    for k, v in delta.items():
        try:
            json.dumps(v)
            safe[k] = v
        except (TypeError, ValueError):
            safe[k] = str(v)
    return safe


async def execute_parse_agent(
    session, *, run_id: UUID, initial_state: dict, parsing_service, source,
) -> None:
    """Stream the graph and project each node's output into parse_agent_run_steps."""
    repo = ParseAgentRunRepository(session)
    compiled = build_parse_graph(parsing_service, source)

    seq = 0
    last = time.monotonic()
    try:
        async for chunk in compiled.astream(initial_state, stream_mode="updates"):
            for node_name, delta in chunk.items():
                now = time.monotonic()
                duration_ms = int((now - last) * 1000)
                last = now
                spec = NODE_SPECS.get(node_name)
                await repo.append_step(StepCreate(
                    run_id=run_id, seq=seq, node=node_name, phase="end", status="succeeded",
                    input_keys=list(spec.input_keys) if spec else [],
                    output_keys=list(delta.keys()),
                    state_delta=_json_safe(delta), duration_ms=duration_ms,
                ))
                seq += 1
        await repo.finish_run(
            run_id, status=ParseAgentRunStatus.completed.value,
            finished_at=datetime.now(timezone.utc),
        )
    except Exception as exc:  # noqa: BLE001 — engine boundary; failure is recorded, not raised
        logger.exception("parse-agent run %s failed", run_id)
        await repo.finish_run(
            run_id, status=ParseAgentRunStatus.failed.value,
            finished_at=datetime.now(timezone.utc), error=str(exc),
        )


async def run_parse_agent(
    *, run_id: UUID, source_document_id: UUID, file_path: str, project_id: UUID,
    config: dict, representation_kind: str, storage_service,
    llamaparse_api_key: str | None = None, landingai_api_key: str | None = None,
) -> None:
    """Background-task entry point. Opens its own DB session (mirrors process_cdm_parsing)."""
    from app.cdm.models import ParserKind
    from app.cdm.source import SourceDocument as SourceDocumentCDM
    from app.database import AsyncSessionLocal
    from app.dependencies.documents import get_document_extractor
    from app.repositories.parsed_document_repository import ParsedDocumentRepository
    from app.repositories.parse_run_repository import ParseRunRepository
    from app.repositories.source_document_repository import SourceDocumentRepository
    from app.services.parsing.parsing_service import ParsingService

    llamaparse_client = None
    if llamaparse_api_key:
        from llama_cloud import AsyncLlamaCloud
        llamaparse_client = AsyncLlamaCloud(api_key=llamaparse_api_key)
    landingai_client = None
    if landingai_api_key:
        from landingai_ade import LandingAIADE
        landingai_client = LandingAIADE(apikey=landingai_api_key)

    async with AsyncSessionLocal() as session:
        source_orm = await SourceDocumentRepository(session).get(source_document_id)
        if source_orm is None:
            await ParseAgentRunRepository(session).finish_run(
                run_id, status=ParseAgentRunStatus.failed.value,
                finished_at=datetime.now(timezone.utc), error="SourceDocument not found",
            )
            return

        source_cdm = SourceDocumentCDM(
            id=str(source_orm.id), sha256=source_orm.sha256, filename=source_orm.filename,
            mime_type=source_orm.mime_type, byte_size=source_orm.byte_size,
            storage_uri=source_orm.storage_uri, created_at=source_orm.created_at,
        )
        parsing_service = ParsingService(
            source_doc_repo=SourceDocumentRepository(session),
            parse_run_repo=ParseRunRepository(session),
            parsed_doc_repo=ParsedDocumentRepository(session),
            storage=storage_service,
            clients={
                ParserKind.LLAMAPARSE: llamaparse_client,
                ParserKind.LANDING_AI: landingai_client,
                ParserKind.SIMPLE: get_document_extractor(),
            },
        )
        await execute_parse_agent(
            session, run_id=run_id,
            initial_state={
                "file_path": file_path, "source_document_id": str(source_document_id),
                "project_id": str(project_id), "representation_kind": representation_kind,
                "config": config,
            },
            parsing_service=parsing_service, source=source_cdm,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run python -m pytest tests/services/parse_agent/test_engine.py -o "addopts=" -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/parse_agent/engine.py backend/tests/services/parse_agent/test_engine.py
git commit -m "feat(parse-agent): execution engine with step-log projection"
```

---

### Task 6: Schemas + router + wiring

**Files:**
- Create: `backend/app/schemas/parse_agent_run.py`
- Create: `backend/app/routers/parse_agent_runs.py`
- Modify: `backend/app/main.py` (include router)
- Test: `backend/tests/routers/test_parse_agent_runs_router.py`

**Interfaces:**
- Consumes: `run_parse_agent` (Task 5), `ParseAgentRunRepository` (Task 2), `get_parsing_service` / `get_storage_service` (`app.dependencies.documents`), `get_current_active_user` (`app.dependencies.auth`), `get_db` (`app.database`), `ProjectRepository`.
- Produces: `POST /api/v1/parse-agent-runs` → `202 {"runId": ...}`; `GET /api/v1/parse-agent-runs/{run_id}` → `{ run, steps[], graphNodes[] }`.

Look first at `backend/app/schemas/parse_run.py` for the camelCase base model (`CamelModel` or `model_config` with `alias_generator=to_camel, populate_by_name=True`) and copy that exact base. Look at `backend/app/routers/documents.py:110-185` for the upload/BYOK/background-task pattern and at `backend/app/routers/parse_runs.py` for the auth style; mirror them.

- [ ] **Step 1: Write the failing E2E test**

```python
# backend/tests/routers/test_parse_agent_runs_router.py
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

MINIMAL_PDF = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF"


async def _signup_and_login(client: AsyncClient) -> str:
    await client.post("/api/v1/auth/signup", json={
        "email": "pa@example.com", "password": "ValidPass123!",
        "password_confirm": "ValidPass123!", "full_name": "PA User",
    })
    resp = await client.post("/api/v1/auth/signin",
                             json={"email": "pa@example.com", "password": "ValidPass123!"})
    return resp.json()["access_token"]


async def _create_project(client: AsyncClient, token: str) -> str:
    resp = await client.post("/api/v1/projects", headers={"Authorization": f"Bearer {token}"},
                             json={"name": "PA Project"})
    return resp.json()["id"]


def _fake_parse_result(source_id: str):
    class _Run:
        id = uuid4()
        failed_pages: list[int] = []

    class _Doc:
        page_count = 1
        full_text = "Hello world."
        blocks: list[Any] = []

    return _Run(), _Doc()


@pytest.mark.asyncio
async def test_upload_creates_run_and_trace(client: AsyncClient, test_db: AsyncSession):
    token = await _signup_and_login(client)
    project_id = await _create_project(client, token)

    # Redirect the background task's own session to the SQLite test session.
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=test_db)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

    async def fake_parse_and_persist(**kwargs):
        return _fake_parse_result(str(kwargs["source"].id))

    with (
        patch("app.database.AsyncSessionLocal", mock_session_factory),
        patch("app.services.parsing.parsing_service.ParsingService.parse_and_persist",
              new=AsyncMock(side_effect=fake_parse_and_persist)),
    ):
        resp = await client.post(
            "/api/v1/parse-agent-runs",
            headers={"Authorization": f"Bearer {token}"},
            data={"project_id": project_id, "parser_type": "simple", "title": "PA Doc"},
            files=[("file", ("test.pdf", MINIMAL_PDF, "application/pdf"))],
        )
        assert resp.status_code == 202, resp.text
        run_id = resp.json()["runId"]

        got = await client.get(f"/api/v1/parse-agent-runs/{run_id}",
                               headers={"Authorization": f"Bearer {token}"})

    assert got.status_code == 200, got.text
    body = got.json()
    assert body["run"]["status"] == "completed"
    assert body["graphNodes"] == ["parse", "health_check"]
    assert [s["node"] for s in body["steps"]] == ["parse", "health_check"]


@pytest.mark.asyncio
async def test_get_run_requires_ownership(client: AsyncClient, test_db: AsyncSession):
    token = await _signup_and_login(client)
    resp = await client.get(f"/api/v1/parse-agent-runs/{uuid4()}",
                            headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest tests/routers/test_parse_agent_runs_router.py -o "addopts=" -v`
Expected: FAIL with 404 on the POST (route not registered) / import error.

- [ ] **Step 3: Write the schemas**

Mirror the camelCase base from `app/schemas/parse_run.py`. Assuming it exposes `CamelModel`:

```python
# backend/app/schemas/parse_agent_run.py
"""Response schemas for parse-agent runs (camelCase, mirrors parse_run schemas)."""
from datetime import datetime
from uuid import UUID

from app.schemas.parse_run import CamelModel  # reuse the project's camelCase base


class ParseAgentRunStepResponse(CamelModel):
    id: UUID
    seq: int
    node: str
    phase: str
    status: str
    input_keys: list[str]
    output_keys: list[str]
    state_delta: dict
    message: str | None
    duration_ms: int | None
    created_at: datetime


class ParseAgentRunSummary(CamelModel):
    id: UUID
    project_id: UUID
    source_document_id: UUID
    status: str
    started_at: datetime
    finished_at: datetime | None
    error: str | None


class ParseAgentRunDetailResponse(CamelModel):
    run: ParseAgentRunSummary
    steps: list[ParseAgentRunStepResponse]
    graph_nodes: list[str]


class ParseAgentRunCreatedResponse(CamelModel):
    run_id: UUID
```

> If `app/schemas/parse_run.py` does not export a shared `CamelModel`, copy its `model_config`/base class definition verbatim into a local base in this file instead of importing.

- [ ] **Step 4: Write the router**

```python
# backend/app/routers/parse_agent_runs.py
"""Parse-agent runs API: start a run from an upload, read its trace."""
import json
import logging
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_active_user
from app.dependencies.documents import get_parsing_service, get_storage_service
from app.models import User
from app.ports import StorageService
from app.repositories.parse_agent_run_repository import ParseAgentRunRepository
from app.repositories.project_repository import ProjectRepository
from app.routers.documents import _resolve_parser_key  # reuse BYOK key resolution
from app.schemas.parse_agent_run import (
    ParseAgentRunCreatedResponse,
    ParseAgentRunDetailResponse,
    ParseAgentRunStepResponse,
    ParseAgentRunSummary,
)
from app.services.parse_agent.engine import run_parse_agent

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/parse-agent-runs", tags=["parse-agent-runs"])


@router.post("", response_model=ParseAgentRunCreatedResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_run(
    background_tasks: BackgroundTasks,
    project_id: UUID = Form(...),
    parser_type: str = Form("simple"),
    parse_config: str | None = Form(None),
    file: UploadFile = ...,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    storage_service: StorageService = Depends(get_storage_service),
):
    project = await ProjectRepository(db).get_by_id(project_id, current_user.id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    llamaparse_api_key, landingai_api_key = await _resolve_parser_key(
        db, current_user.id, parser_type
    )

    config_dict = json.loads(parse_config) if parse_config else {}
    representation_kind = config_dict.pop("representation_kind", "extract_rich")
    config_dict["parser"] = parser_type

    file_content = await file.read()
    filename = file.filename or "upload.pdf"

    parsing_service = get_parsing_service(db)
    source = await parsing_service.ensure_source_document(
        bytes_=file_content, filename=filename, mime_type=file.content_type or "application/pdf",
    )

    from datetime import datetime, timezone
    run = await ParseAgentRunRepository(db).create_run(
        project_id=project_id, source_document_id=UUID(source.id),
        started_at=datetime.now(timezone.utc),
    )

    background_tasks.add_task(
        run_parse_agent,
        run_id=run.id, source_document_id=UUID(source.id), file_path=source.storage_uri,
        project_id=project_id, config=config_dict, representation_kind=representation_kind,
        storage_service=storage_service,
        llamaparse_api_key=llamaparse_api_key, landingai_api_key=landingai_api_key,
    )
    return ParseAgentRunCreatedResponse(run_id=run.id)


@router.get("/{run_id}", response_model=ParseAgentRunDetailResponse)
async def get_run(
    run_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    repo = ParseAgentRunRepository(db)
    run = await repo.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    project = await ProjectRepository(db).get_by_id(run.project_id, current_user.id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    steps = await repo.list_steps(run_id)
    from app.services.parse_agent.nodes import GRAPH_NODES
    return ParseAgentRunDetailResponse(
        run=ParseAgentRunSummary.model_validate(run),
        steps=[ParseAgentRunStepResponse.model_validate(s) for s in steps],
        graph_nodes=GRAPH_NODES,
    )
```

> Confirm `_resolve_parser_key(db, user_id, parser_type)` exists in `app/routers/documents.py` and returns `(llamaparse_key, landingai_key)`. If it is named differently, use the actual helper (grep `def _resolve_parser_key` / `resolve_api_key` in that file). Confirm `ProjectRepository.get_by_id(project_id, user_id)` is the ownership-scoped signature (it is used across routers).

- [ ] **Step 5: Register the router**

In `backend/app/main.py`, mirror the other `app.include_router(...)` lines:

```python
from app.routers import parse_agent_runs
app.include_router(parse_agent_runs.router, prefix="/api/v1")
```

(Match the exact prefix/style used by the sibling `parse_runs` router registration in that file.)

- [ ] **Step 6: Run the test to verify it passes**

Run: `cd backend && uv run python -m pytest tests/routers/test_parse_agent_runs_router.py -o "addopts=" -v`
Expected: PASS (2 tests). If the POST returns 200 with an empty trace, the background task didn't run against `test_db` — recheck the `patch("app.database.AsyncSessionLocal", ...)` block matches the engine's import path.

- [ ] **Step 7: Run the full parse-agent suite + commit**

Run: `cd backend && uv run python -m pytest tests/models/test_parse_agent_run_model.py tests/repositories/test_parse_agent_run_repository.py tests/services/parse_agent tests/routers/test_parse_agent_runs_router.py -o "addopts=" -v`
Expected: all PASS.

```bash
git add backend/app/schemas/parse_agent_run.py backend/app/routers/parse_agent_runs.py backend/app/main.py backend/tests/routers/test_parse_agent_runs_router.py
git commit -m "feat(parse-agent): POST/GET parse-agent-runs router + schemas"
```

---

## Self-Review

**Spec coverage:**
- Trigger entry point / upload → run → 202 → Task 6 (router) + Task 5 (`run_parse_agent`). ✓
- Hand-wired 2-node graph (parse, health_check) → Task 4 + Task 3. ✓
- Parse node reuses `ParsingService.parse_and_persist`, produces `ParseRun` → Task 3 (`make_parse_node`). ✓
- health_check reference-free, trace-only → Task 3 (`health_check_node`), never persisted to the artifact. ✓
- Own step-log projection boundary (no reading LangGraph internals) → Task 1 tables + Task 5 engine. ✓
- New engine, not `AgentRunService`; background task; no checkpointer in v1 → Task 4/5. ✓
- BYOK key resolution in router, clients built in task → Task 6 + Task 5. ✓
- Distinct `/parse-agent-runs` resource; existing `/parse-runs` untouched → Task 6. ✓
- Results-viewer handoff uses `parse_run_id` (existing endpoint) → `parse_run_id` captured in Task 3; no backend work needed beyond exposing it in `state_delta`. ✓
- Polled read API returning run + steps + graph_nodes → Task 6 GET. ✓
- **Not covered (intentionally deferred):** frontend trace UI (follow-on plan), escalation loop, human review/interrupt, orphaned-run reconciler, streamed/SSE transport, data-driven graph builder.

**Placeholder scan:** No TBD/TODO; every code step has complete code. Two verify-before-use notes (the `CamelModel` base and `_resolve_parser_key` helper) are explicit "grep and confirm" instructions with fallbacks, not placeholders.

**Type consistency:** `StepCreate` fields match `append_step` usage (Tasks 2, 5). `make_parse_node`/`health_check_node` output keys match `NODE_SPECS` and the engine's `input_keys` lookup (Tasks 3, 5). `run_parse_agent` kwargs match the router's `add_task` call (Tasks 5, 6). Response field names (`runId`, `graphNodes`, `steps[].node`) match the E2E assertions (Task 6).

## Known follow-ups (out of scope)

- **Frontend trace UI** — the validated graph-strip + timeline + detail-panel + results-viewer-handoff design; consumes `GET /parse-agent-runs/{id}` with ~1s polling. Its own plan.
- **Orphaned-run reconciler** — startup job to fail `running` rows with no active task.
- **Node-level failure granularity** — v1 records run-level failure; per-node failed steps come with the escalation loop.
