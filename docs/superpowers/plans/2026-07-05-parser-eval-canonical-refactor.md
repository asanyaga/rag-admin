# Parser Eval Canonical Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reshape the parser-eval backend to the canonical eval entity model — Eval Case = (source document, dimension, ground truth), a Dataset M:N container, Metric-as-map on Result, and Variant = (adapter, config).

**Architecture:** Backend-only refactor (no parser-eval frontend exists yet). Nothing is deployed, so the single Alembic migration `8da704a351d2` is **rewritten in place** rather than superseded. Data flow unchanged: router → service → engine → repository → models.

**Tech Stack:** Python 3.12, FastAPI (async), SQLAlchemy 2.0, Alembic, pytest (SQLite in-memory via `test_db`).

## Global Constraints

- Backend tests run on **SQLite in-memory** (fixture `test_db`, `seed_project_user_source`); Postgres not required to run them. Enum columns use `create_type=False` (Postgres DDL, degrades to VARCHAR on SQLite).
- Run tests with: `cd backend && uv run python -m pytest -o "addopts=" <path> -v`.
- All DB operations async, fully type-hinted.
- Services raise `app.services.exceptions` errors; routers catch and map to HTTP.
- Feature branch already created: `feat/parser-eval-canonical-refactor`. Do not touch `main`.
- Commit after every green task. Commit message trailer: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- Reference model: `docs/architecture/eval-entity-model.md` (r3). Reference spec: `docs/superpowers/specs/2026-07-05-parser-eval-canonical-refactor-design.md`.

---

### Task 1: Models — enums, `ParserEvalCase`, Dataset, Run, Result

**Files:**
- Modify (full rewrite): `backend/app/models/parser_eval.py`
- Modify: `backend/app/models/__init__.py` (parser_eval export block)
- Test: `backend/tests/models/test_parser_eval_models.py` (rewrite)

**Interfaces:**
- Produces: enums `ParserEvalDimension{text}`, `ParserEvalSourceMethod{human,generated,bootstrapped}`, `ParserEvalReviewStatus{draft,verified}`, `ParserEvalRunStatus{pending,running,completed,failed}`; models `ParserEvalCase`, `ParserEvalDataset`, `ParserEvalDatasetCase`, `ParserEvalRun`, `ParserEvalResult`.
- `ParserEvalCase` columns: `id, project_id, source_document_id, dimension, expected(JSON), source_method, review_status, created_by, created_at`; unique `(source_document_id, dimension)`.
- `ParserEvalResult` columns: `id, run_id, eval_case_id, adapter, config(JSON), variant_key, metrics(JSON), primary_metric, details(JSON), cost(JSON), latency_ms, created_at`; unique `(run_id, eval_case_id, variant_key)`.
- `ParserEvalRun` columns: `id, project_id, name, variants(JSON), eval_case_ids(JSON), dataset_id(nullable FK), status, error_message, created_by, created_at, updated_at`.

- [ ] **Step 1: Write the failing model test**

Rewrite `backend/tests/models/test_parser_eval_models.py`:

```python
import pytest
from uuid import uuid4
from app.models.parser_eval import (
    ParserEvalCase, ParserEvalDataset, ParserEvalDatasetCase,
    ParserEvalRun, ParserEvalResult,
    ParserEvalDimension, ParserEvalSourceMethod, ParserEvalReviewStatus,
    ParserEvalRunStatus,
)


@pytest.mark.asyncio
async def test_case_defaults_and_persist(test_db, seed_project_user_source):
    project_id, user_id, source_id = seed_project_user_source
    case = ParserEvalCase(
        project_id=project_id, source_document_id=source_id,
        dimension=ParserEvalDimension.text, expected={"pages": ["hi"]},
        created_by=user_id)
    test_db.add(case)
    await test_db.commit()
    await test_db.refresh(case)
    assert case.source_method == ParserEvalSourceMethod.human
    assert case.review_status == ParserEvalReviewStatus.draft


@pytest.mark.asyncio
async def test_dataset_membership(test_db, seed_project_user_source):
    project_id, user_id, source_id = seed_project_user_source
    case = ParserEvalCase(project_id=project_id, source_document_id=source_id,
                          dimension=ParserEvalDimension.text, expected={"pages": ["x"]},
                          created_by=user_id)
    ds = ParserEvalDataset(project_id=project_id, name="smoke", created_by=user_id)
    test_db.add_all([case, ds])
    await test_db.commit()
    test_db.add(ParserEvalDatasetCase(dataset_id=ds.id, eval_case_id=case.id))
    await test_db.commit()
    await test_db.refresh(ds)
    assert [c.id for c in ds.cases] == [case.id]


@pytest.mark.asyncio
async def test_run_and_result_shapes(test_db, seed_project_user_source):
    project_id, user_id, source_id = seed_project_user_source
    run = ParserEvalRun(project_id=project_id, name="r",
                        variants=[{"adapter": "docling", "config": {}}],
                        eval_case_ids=[], created_by=user_id)
    case = ParserEvalCase(project_id=project_id, source_document_id=source_id,
                          dimension=ParserEvalDimension.text, expected={"pages": ["x"]},
                          created_by=user_id)
    test_db.add_all([run, case])
    await test_db.commit()
    result = ParserEvalResult(
        run_id=run.id, eval_case_id=case.id, adapter="docling", config={},
        variant_key="docling@abc123", metrics={"similarity": 0.9}, primary_metric="similarity",
        details={"per_page": []}, cost={"usd": 0.0}, latency_ms=120)
    test_db.add(result)
    await test_db.commit()
    await test_db.refresh(result)
    assert result.metrics["similarity"] == 0.9
    assert run.status == ParserEvalRunStatus.pending
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/models/test_parser_eval_models.py -v`
Expected: FAIL (ImportError: `ParserEvalDataset` / `ParserEvalSourceMethod` not found).

- [ ] **Step 3: Rewrite the models file**

Replace `backend/app/models/parser_eval.py` entirely:

```python
"""Models for parser evaluation — canonical eval entity model.

Eval Case = (source document, dimension, ground-truth `expected`). Dataset is an M:N
container over cases. A Run executes variants=(adapter, config) over a snapshot of cases;
each Result is one (run, case, variant) cell holding a metrics map.
"""
from datetime import datetime
from uuid import UUID, uuid4
import enum

import sqlalchemy as sa
from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ParserEvalDimension(str, enum.Enum):
    text = "text"          # seam #1: table/reading_order/roles added later


class ParserEvalSourceMethod(str, enum.Enum):
    human = "human"
    generated = "generated"
    bootstrapped = "bootstrapped"


class ParserEvalReviewStatus(str, enum.Enum):
    draft = "draft"
    verified = "verified"


class ParserEvalRunStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class ParserEvalCase(Base):
    """Input + ground truth: one asserted dimension of one source document."""
    __tablename__ = "parser_eval_cases"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4,
                                     server_default=sa.text('gen_random_uuid()'))
    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    source_document_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("source_documents.id", ondelete="RESTRICT"), nullable=False)
    dimension: Mapped[ParserEvalDimension] = mapped_column(
        Enum(ParserEvalDimension, name='parser_eval_dimension', create_type=False), nullable=False)
    expected: Mapped[dict] = mapped_column(JSON, nullable=False)
    source_method: Mapped[ParserEvalSourceMethod] = mapped_column(
        Enum(ParserEvalSourceMethod, name='parser_eval_source_method', create_type=False),
        nullable=False, default=ParserEvalSourceMethod.human, server_default='human')
    review_status: Mapped[ParserEvalReviewStatus] = mapped_column(
        Enum(ParserEvalReviewStatus, name='parser_eval_review_status', create_type=False),
        nullable=False, default=ParserEvalReviewStatus.draft, server_default='draft')
    created_by: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                 default=datetime.utcnow, server_default=sa.text('NOW()'))

    __table_args__ = (
        sa.UniqueConstraint('source_document_id', 'dimension', name='uq_parser_eval_cases_source_dim'),
        sa.Index('ix_parser_eval_cases_project_id', 'project_id'),
    )


class ParserEvalDataset(Base):
    """A curated container over eval cases (M:N)."""
    __tablename__ = "parser_eval_datasets"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4,
                                     server_default=sa.text('gen_random_uuid()'))
    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                 default=datetime.utcnow, server_default=sa.text('NOW()'))

    cases: Mapped[list["ParserEvalCase"]] = relationship(
        secondary="parser_eval_dataset_cases", lazy="selectin")

    __table_args__ = (
        sa.Index('ix_parser_eval_datasets_project_id', 'project_id'),
    )


class ParserEvalDatasetCase(Base):
    """M:N membership of an eval case in a dataset."""
    __tablename__ = "parser_eval_dataset_cases"

    dataset_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("parser_eval_datasets.id", ondelete="CASCADE"),
        primary_key=True)
    eval_case_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("parser_eval_cases.id", ondelete="CASCADE"),
        primary_key=True)


class ParserEvalRun(Base):
    """One execution of variants=(adapter, config) over a snapshot of cases."""
    __tablename__ = "parser_eval_runs"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4,
                                     server_default=sa.text('gen_random_uuid()'))
    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    variants: Mapped[list] = mapped_column(JSON, nullable=False, default=list, server_default='[]')
    eval_case_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list, server_default='[]')
    dataset_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("parser_eval_datasets.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[ParserEvalRunStatus] = mapped_column(
        Enum(ParserEvalRunStatus, name='parser_eval_run_status', create_type=False),
        nullable=False, default=ParserEvalRunStatus.pending, server_default='pending')
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                 default=datetime.utcnow, server_default=sa.text('NOW()'))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                 default=datetime.utcnow, onupdate=datetime.utcnow,
                                                 server_default=sa.text('NOW()'))

    results: Mapped[list["ParserEvalResult"]] = relationship(
        back_populates="run", cascade="all, delete-orphan")

    __table_args__ = (
        sa.Index('ix_parser_eval_runs_project_id', 'project_id'),
    )


class ParserEvalResult(Base):
    """One score cell: (run, eval_case, variant) -> metrics map + attribution + cost/latency."""
    __tablename__ = "parser_eval_results"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4,
                                     server_default=sa.text('gen_random_uuid()'))
    run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("parser_eval_runs.id", ondelete="CASCADE"), nullable=False)
    eval_case_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("parser_eval_cases.id", ondelete="CASCADE"), nullable=False)
    adapter: Mapped[str] = mapped_column(String(64), nullable=False)
    config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, server_default='{}')
    variant_key: Mapped[str] = mapped_column(String(128), nullable=False)
    metrics: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, server_default='{}')
    primary_metric: Mapped[str | None] = mapped_column(String(64), nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    cost: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                 default=datetime.utcnow, server_default=sa.text('NOW()'))

    run: Mapped["ParserEvalRun"] = relationship(back_populates="results")

    __table_args__ = (
        sa.UniqueConstraint('run_id', 'eval_case_id', 'variant_key',
                            name='uq_parser_eval_results_run_case_variant'),
        sa.Index('ix_parser_eval_results_run_id', 'run_id'),
    )
```

- [ ] **Step 4: Update the models package exports**

In `backend/app/models/__init__.py`, update the parser_eval import/`__all__` block: remove `ParserEvalTarget`; add `ParserEvalDataset`, `ParserEvalDatasetCase`, `ParserEvalSourceMethod`, `ParserEvalReviewStatus`. Keep `ParserEvalCase`, `ParserEvalRun`, `ParserEvalResult`, `ParserEvalDimension`, `ParserEvalRunStatus`.

- [ ] **Step 5: Run to verify it passes**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/models/test_parser_eval_models.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/parser_eval.py backend/app/models/__init__.py backend/tests/models/test_parser_eval_models.py
git commit -m "refactor(parser-eval): canonical models — Case=(doc,dimension,expected), Dataset, metrics Result"
```

---

### Task 2: Rewrite the Alembic migration in place

**Files:**
- Modify (full rewrite of body): `backend/alembic/versions/8da704a351d2_add_parser_eval_tables.py`

**Interfaces:**
- Consumes: nothing (bottom of the parser-eval stack). `down_revision` stays `30add7b93531`.
- Produces: the five tables + four enums matching Task 1 exactly. Verified by the executor on Postgres (SQLite tests build schema from models, not this file).

- [ ] **Step 1: Replace `upgrade()` / `downgrade()`**

Keep the revision identifiers (lines 15–18) unchanged. Replace the two functions:

```python
def upgrade() -> None:
    dimension = postgresql.ENUM('text', name='parser_eval_dimension', create_type=False)
    dimension.create(op.get_bind(), checkfirst=True)
    source_method = postgresql.ENUM('human', 'generated', 'bootstrapped',
                                    name='parser_eval_source_method', create_type=False)
    source_method.create(op.get_bind(), checkfirst=True)
    review_status = postgresql.ENUM('draft', 'verified',
                                    name='parser_eval_review_status', create_type=False)
    review_status.create(op.get_bind(), checkfirst=True)
    run_status = postgresql.ENUM('pending', 'running', 'completed', 'failed',
                                 name='parser_eval_run_status', create_type=False)
    run_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        'parser_eval_cases',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('source_document_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('dimension', postgresql.ENUM('text', name='parser_eval_dimension', create_type=False), nullable=False),
        sa.Column('expected', sa.JSON(), nullable=False),
        sa.Column('source_method', postgresql.ENUM('human', 'generated', 'bootstrapped', name='parser_eval_source_method', create_type=False), server_default='human', nullable=False),
        sa.Column('review_status', postgresql.ENUM('draft', 'verified', name='parser_eval_review_status', create_type=False), server_default='draft', nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['source_document_id'], ['source_documents.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.UniqueConstraint('source_document_id', 'dimension', name='uq_parser_eval_cases_source_dim'),
    )
    op.create_index('ix_parser_eval_cases_project_id', 'parser_eval_cases', ['project_id'])

    op.create_table(
        'parser_eval_datasets',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
    )
    op.create_index('ix_parser_eval_datasets_project_id', 'parser_eval_datasets', ['project_id'])

    op.create_table(
        'parser_eval_dataset_cases',
        sa.Column('dataset_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('eval_case_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint('dataset_id', 'eval_case_id'),
        sa.ForeignKeyConstraint(['dataset_id'], ['parser_eval_datasets.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['eval_case_id'], ['parser_eval_cases.id'], ondelete='CASCADE'),
    )

    op.create_table(
        'parser_eval_runs',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('variants', sa.JSON(), server_default='[]', nullable=False),
        sa.Column('eval_case_ids', sa.JSON(), server_default='[]', nullable=False),
        sa.Column('dataset_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('status', postgresql.ENUM('pending', 'running', 'completed', 'failed', name='parser_eval_run_status', create_type=False), server_default='pending', nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['dataset_id'], ['parser_eval_datasets.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
    )
    op.create_index('ix_parser_eval_runs_project_id', 'parser_eval_runs', ['project_id'])

    op.create_table(
        'parser_eval_results',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('run_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('eval_case_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('adapter', sa.String(64), nullable=False),
        sa.Column('config', sa.JSON(), server_default='{}', nullable=False),
        sa.Column('variant_key', sa.String(128), nullable=False),
        sa.Column('metrics', sa.JSON(), server_default='{}', nullable=False),
        sa.Column('primary_metric', sa.String(64), nullable=True),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('cost', sa.JSON(), nullable=True),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['run_id'], ['parser_eval_runs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['eval_case_id'], ['parser_eval_cases.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('run_id', 'eval_case_id', 'variant_key', name='uq_parser_eval_results_run_case_variant'),
    )
    op.create_index('ix_parser_eval_results_run_id', 'parser_eval_results', ['run_id'])


def downgrade() -> None:
    op.drop_table('parser_eval_results')
    op.drop_table('parser_eval_runs')
    op.drop_table('parser_eval_dataset_cases')
    op.drop_table('parser_eval_datasets')
    op.drop_table('parser_eval_cases')
    op.execute('DROP TYPE IF EXISTS parser_eval_run_status')
    op.execute('DROP TYPE IF EXISTS parser_eval_review_status')
    op.execute('DROP TYPE IF EXISTS parser_eval_source_method')
    op.execute('DROP TYPE IF EXISTS parser_eval_dimension')
```

- [ ] **Step 2: Verify migration syntax imports**

Run: `cd backend && uv run python -c "import importlib.util, pathlib; p=pathlib.Path('alembic/versions/8da704a351d2_add_parser_eval_tables.py'); s=importlib.util.spec_from_file_location('m', p); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); print('ok', m.revision, m.down_revision)"`
Expected: `ok 8da704a351d2 30add7b93531`

- [ ] **Step 3: Commit**

```bash
git add backend/alembic/versions/8da704a351d2_add_parser_eval_tables.py
git commit -m "refactor(parser-eval): rewrite migration in place for canonical schema"
```

> **Executor note:** Postgres round-trip (`alembic upgrade head && alembic downgrade -1 && alembic upgrade head`) is a manual verification step — record its outcome; it cannot be run under SQLite tests.

---

### Task 3: `variant_key` helper

**Files:**
- Create: `backend/app/services/parser_eval/variants.py`
- Test: `backend/tests/services/parser_eval/test_variants.py`

**Interfaces:**
- Produces: `variant_key(adapter: str, config: dict | None) -> str` — deterministic, config-key-order independent.

- [ ] **Step 1: Write the failing test**

```python
from app.services.parser_eval.variants import variant_key


def test_variant_key_is_order_independent():
    assert variant_key("docling", {"a": 1, "b": 2}) == variant_key("docling", {"b": 2, "a": 1})


def test_variant_key_distinguishes_config_and_adapter():
    assert variant_key("custom_pipeline", {"tool": "pdfplumber"}) != variant_key("custom_pipeline", {"tool": "fitz"})
    assert variant_key("docling", {}) != variant_key("simple", {})


def test_variant_key_none_config_equals_empty():
    assert variant_key("docling", None) == variant_key("docling", {})
    assert variant_key("docling", {}).startswith("docling@")
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/parser_eval/test_variants.py -v`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Implement**

```python
"""Deterministic identity for a Variant = (adapter, config)."""
from __future__ import annotations

import hashlib
import json


def variant_key(adapter: str, config: dict | None) -> str:
    normalized = json.dumps(config or {}, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]
    return f"{adapter}@{digest}"
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/parser_eval/test_variants.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/parser_eval/variants.py backend/tests/services/parser_eval/test_variants.py
git commit -m "feat(parser-eval): deterministic variant_key for (adapter, config)"
```

---

### Task 4: Scorer registry (`ScorerSpec`) + text scorer returns `(metrics, details)`

**Files:**
- Modify: `backend/app/services/parser_eval/scorers/__init__.py`
- Modify: `backend/app/services/parser_eval/scorers/text.py`
- Test: `backend/tests/services/parser_eval/test_text_scorer.py` (update), `backend/tests/services/parser_eval/test_registry.py` (update)

**Interfaces:**
- Consumes: `ParsedDocument` from `app.cdm.models`.
- Produces: `ScorerSpec{fn, emits, primary}`; `get_scorer(dimension) -> ScorerSpec`; `score_text(cdm, expected) -> tuple[dict[str, float], dict]` returning `(metrics, details)` with metrics keys `similarity, omission, hallucination`.

- [ ] **Step 1: Update the scorer test to the new return shape**

Rewrite `backend/tests/services/parser_eval/test_text_scorer.py`:

```python
from app.cdm.models import ParsedDocument, Page
from app.services.parser_eval.scorers.text import score_text


def _doc(text: str) -> ParsedDocument:
    return ParsedDocument(id="d", source_document_id="s", parse_run_id="r", page_count=1,
                          pages=[Page(index=0, start_char=0, end_char=len(text))],
                          blocks=[], full_text=text)


def test_score_text_perfect_match():
    metrics, details = score_text(_doc("hello world"), {"pages": ["hello world"]})
    assert metrics["similarity"] == 1.0
    assert metrics["omission"] == 0.0
    assert metrics["hallucination"] == 0.0
    assert "per_page" in details


def test_score_text_reports_omission():
    metrics, _ = score_text(_doc("hello"), {"pages": ["hello world"]})
    assert metrics["omission"] > 0.0
```

And in `backend/tests/services/parser_eval/test_registry.py`:

```python
from app.services.parser_eval.scorers import get_scorer


def test_text_scorer_spec_signature():
    spec = get_scorer("text")
    assert spec.primary == "similarity"
    assert set(spec.emits) == {"similarity", "omission", "hallucination"}
    assert callable(spec.fn)
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/parser_eval/test_text_scorer.py tests/services/parser_eval/test_registry.py -v`
Expected: FAIL (`score_text` returns a float, `get_scorer` returns a function not a spec).

- [ ] **Step 3: Update `text.py` return shape**

In `backend/app/services/parser_eval/scorers/text.py`, change the final `score_text` to return `(metrics, details)` (keep all page-alignment math identical; only the return packaging changes):

```python
def score_text(cdm: ParsedDocument, expected: dict[str, Any]) -> tuple[dict[str, float], dict]:
    reference_pages: list[str] = expected["pages"]
    parsed_pages = _parsed_page_texts(cdm)

    per_page: list[dict[str, Any]] = []
    n = max(len(reference_pages), len(parsed_pages))
    for i in range(n):
        ref = reference_pages[i] if i < len(reference_pages) else ""
        par = parsed_pages[i] if i < len(parsed_pages) else ""
        per_page.append({"page": i, **_score_page(ref, par)})

    def _weight(i: int) -> int:
        ref_len = len(reference_pages[i]) if i < len(reference_pages) else 0
        par_len = len(parsed_pages[i]) if i < len(parsed_pages) else 0
        return max(ref_len, par_len, 1)

    total_w = sum(_weight(i) for i in range(n)) or 1
    metrics = {
        "similarity": sum(p["similarity"] * _weight(p["page"]) for p in per_page) / total_w,
        "omission": sum(p["omission"] * _weight(p["page"]) for p in per_page) / total_w,
        "hallucination": sum(p["hallucination"] * _weight(p["page"]) for p in per_page) / total_w,
    }
    details = {
        "per_page": per_page,
        "page_count_expected": len(reference_pages),
        "page_count_parsed": len(parsed_pages),
    }
    return metrics, details
```

- [ ] **Step 4: Update the registry to `ScorerSpec`**

Replace `backend/app/services/parser_eval/scorers/__init__.py`:

```python
"""Registry of dimension scorers. Add a dimension = add one ScorerSpec entry here (seam #1)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.cdm.models import ParsedDocument
from app.services.parser_eval.scorers.text import score_text

ScorerFn = Callable[[ParsedDocument, dict[str, Any]], "tuple[dict[str, float], dict]"]


@dataclass(frozen=True)
class ScorerSpec:
    fn: ScorerFn
    emits: tuple[str, ...]
    primary: str


SCORERS: dict[str, ScorerSpec] = {
    "text": ScorerSpec(fn=score_text, emits=("similarity", "omission", "hallucination"),
                       primary="similarity"),
}


def get_scorer(dimension: str) -> ScorerSpec:
    return SCORERS[dimension]
```

- [ ] **Step 5: Run to verify it passes**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/parser_eval/test_text_scorer.py tests/services/parser_eval/test_registry.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/parser_eval/scorers/ backend/tests/services/parser_eval/test_text_scorer.py backend/tests/services/parser_eval/test_registry.py
git commit -m "refactor(parser-eval): scorer emits metrics map; registry uses ScorerSpec"
```

---

### Task 5: Repository rewrite

**Files:**
- Modify (full rewrite): `backend/app/repositories/parser_eval_repository.py`
- Test: `backend/tests/repositories/test_parser_eval_repository.py` (rewrite)

**Interfaces:**
- Consumes: Task 1 models.
- Produces methods:
  - `create_case(project_id, source_document_id, dimension, expected, user_id, source_method=human, review_status=draft) -> ParserEvalCase`
  - `get_case(case_id) -> ParserEvalCase | None`; `list_cases(project_id) -> list[ParserEvalCase]`; `get_cases_by_ids(ids) -> list[ParserEvalCase]`
  - `create_dataset(project_id, name, description, user_id) -> ParserEvalDataset`; `list_datasets(project_id)`; `get_dataset(dataset_id)`; `add_case_to_dataset(dataset_id, eval_case_id)`; `remove_case_from_dataset(dataset_id, eval_case_id)`; `list_dataset_case_ids(dataset_id) -> list[UUID]`
  - `create_run(project_id, name, variants, eval_case_ids, user_id, dataset_id=None) -> ParserEvalRun`; `get_run`; `list_runs`; `set_run_status`
  - `upsert_result(run_id, eval_case_id, adapter, config, variant_key, metrics, primary_metric, details, cost, latency_ms)`; `get_results(run_id)`

- [ ] **Step 1: Write the failing repository tests**

Rewrite `backend/tests/repositories/test_parser_eval_repository.py`:

```python
import pytest
from app.models.parser_eval import ParserEvalDimension, ParserEvalRunStatus
from app.repositories.parser_eval_repository import ParserEvalRepository


@pytest.mark.asyncio
async def test_create_case_and_fetch(test_db, seed_project_user_source):
    project_id, user_id, source_id = seed_project_user_source
    repo = ParserEvalRepository(test_db)
    case = await repo.create_case(project_id, source_id, ParserEvalDimension.text,
                                  {"pages": ["hello"]}, user_id)
    fetched = await repo.get_case(case.id)
    assert fetched.expected == {"pages": ["hello"]}
    assert [c.id for c in await repo.list_cases(project_id)] == [case.id]


@pytest.mark.asyncio
async def test_dataset_membership_roundtrip(test_db, seed_project_user_source):
    project_id, user_id, source_id = seed_project_user_source
    repo = ParserEvalRepository(test_db)
    case = await repo.create_case(project_id, source_id, ParserEvalDimension.text,
                                  {"pages": ["x"]}, user_id)
    ds = await repo.create_dataset(project_id, "smoke", None, user_id)
    await repo.add_case_to_dataset(ds.id, case.id)
    assert await repo.list_dataset_case_ids(ds.id) == [case.id]
    await repo.remove_case_from_dataset(ds.id, case.id)
    assert await repo.list_dataset_case_ids(ds.id) == []


@pytest.mark.asyncio
async def test_result_upsert_keyed_by_variant(test_db, seed_project_user_source):
    project_id, user_id, source_id = seed_project_user_source
    repo = ParserEvalRepository(test_db)
    case = await repo.create_case(project_id, source_id, ParserEvalDimension.text,
                                  {"pages": ["x"]}, user_id)
    run = await repo.create_run(project_id, "r", [{"adapter": "docling", "config": {}}],
                                [str(case.id)], user_id)
    await repo.upsert_result(run.id, case.id, "docling", {}, "docling@aaa",
                             {"similarity": 0.9}, "similarity", {}, {}, 100)
    await repo.upsert_result(run.id, case.id, "docling", {}, "docling@aaa",
                             {"similarity": 0.95}, "similarity", {}, {}, 110)  # same variant_key
    results = await repo.get_results(run.id)
    assert len(results) == 1
    assert results[0].metrics["similarity"] == 0.95
    await repo.set_run_status(run.id, ParserEvalRunStatus.completed)
    assert (await repo.get_run(run.id)).status == ParserEvalRunStatus.completed
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/repositories/test_parser_eval_repository.py -v`
Expected: FAIL (method signatures changed).

- [ ] **Step 3: Rewrite the repository**

Replace `backend/app/repositories/parser_eval_repository.py`:

```python
"""Repository for parser evaluation data access (canonical model)."""
from uuid import UUID

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.parser_eval import (
    ParserEvalCase, ParserEvalDataset, ParserEvalDatasetCase,
    ParserEvalRun, ParserEvalResult, ParserEvalDimension,
    ParserEvalSourceMethod, ParserEvalReviewStatus, ParserEvalRunStatus,
)


class ParserEvalRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # --- cases ---
    async def create_case(self, project_id: UUID, source_document_id: UUID,
                          dimension: ParserEvalDimension, expected: dict, user_id: UUID,
                          source_method: ParserEvalSourceMethod = ParserEvalSourceMethod.human,
                          review_status: ParserEvalReviewStatus = ParserEvalReviewStatus.draft
                          ) -> ParserEvalCase:
        case = ParserEvalCase(project_id=project_id, source_document_id=source_document_id,
                              dimension=dimension, expected=expected, created_by=user_id,
                              source_method=source_method, review_status=review_status)
        self.session.add(case)
        await self.session.commit()
        await self.session.refresh(case)
        return case

    async def get_case(self, case_id: UUID) -> ParserEvalCase | None:
        res = await self.session.execute(
            select(ParserEvalCase).where(ParserEvalCase.id == case_id))
        return res.scalar_one_or_none()

    async def list_cases(self, project_id: UUID) -> list[ParserEvalCase]:
        res = await self.session.execute(
            select(ParserEvalCase).where(ParserEvalCase.project_id == project_id)
            .order_by(ParserEvalCase.created_at.desc()))
        return list(res.scalars().all())

    async def get_cases_by_ids(self, ids: list[UUID]) -> list[ParserEvalCase]:
        if not ids:
            return []
        res = await self.session.execute(
            select(ParserEvalCase).where(ParserEvalCase.id.in_(ids)))
        return list(res.scalars().all())

    # --- datasets ---
    async def create_dataset(self, project_id: UUID, name: str, description: str | None,
                             user_id: UUID) -> ParserEvalDataset:
        ds = ParserEvalDataset(project_id=project_id, name=name, description=description,
                               created_by=user_id)
        self.session.add(ds)
        await self.session.commit()
        await self.session.refresh(ds)
        return ds

    async def get_dataset(self, dataset_id: UUID) -> ParserEvalDataset | None:
        res = await self.session.execute(
            select(ParserEvalDataset).where(ParserEvalDataset.id == dataset_id))
        return res.scalar_one_or_none()

    async def list_datasets(self, project_id: UUID) -> list[ParserEvalDataset]:
        res = await self.session.execute(
            select(ParserEvalDataset).where(ParserEvalDataset.project_id == project_id)
            .order_by(ParserEvalDataset.created_at.desc()))
        return list(res.scalars().all())

    async def add_case_to_dataset(self, dataset_id: UUID, eval_case_id: UUID) -> None:
        exists = await self.session.execute(
            select(ParserEvalDatasetCase).where(
                ParserEvalDatasetCase.dataset_id == dataset_id,
                ParserEvalDatasetCase.eval_case_id == eval_case_id))
        if exists.scalar_one_or_none() is None:
            self.session.add(ParserEvalDatasetCase(dataset_id=dataset_id, eval_case_id=eval_case_id))
            await self.session.commit()

    async def remove_case_from_dataset(self, dataset_id: UUID, eval_case_id: UUID) -> None:
        await self.session.execute(
            delete(ParserEvalDatasetCase).where(
                ParserEvalDatasetCase.dataset_id == dataset_id,
                ParserEvalDatasetCase.eval_case_id == eval_case_id))
        await self.session.commit()

    async def list_dataset_case_ids(self, dataset_id: UUID) -> list[UUID]:
        res = await self.session.execute(
            select(ParserEvalDatasetCase.eval_case_id)
            .where(ParserEvalDatasetCase.dataset_id == dataset_id))
        return list(res.scalars().all())

    # --- runs / results ---
    async def create_run(self, project_id: UUID, name: str, variants: list[dict],
                         eval_case_ids: list[str], user_id: UUID,
                         dataset_id: UUID | None = None) -> ParserEvalRun:
        run = ParserEvalRun(project_id=project_id, name=name, variants=variants,
                            eval_case_ids=eval_case_ids, dataset_id=dataset_id, created_by=user_id)
        self.session.add(run)
        await self.session.commit()
        await self.session.refresh(run)
        return run

    async def get_run(self, run_id: UUID) -> ParserEvalRun | None:
        res = await self.session.execute(
            select(ParserEvalRun).where(ParserEvalRun.id == run_id))
        return res.scalar_one_or_none()

    async def list_runs(self, project_id: UUID) -> list[ParserEvalRun]:
        res = await self.session.execute(
            select(ParserEvalRun).where(ParserEvalRun.project_id == project_id)
            .order_by(ParserEvalRun.created_at.desc()))
        return list(res.scalars().all())

    async def set_run_status(self, run_id: UUID, status: ParserEvalRunStatus,
                             error_message: str | None = None) -> None:
        run = await self.get_run(run_id)
        if run is None:
            return
        run.status = status
        if error_message is not None:
            run.error_message = error_message
        await self.session.commit()

    async def upsert_result(self, run_id: UUID, eval_case_id: UUID, adapter: str, config: dict,
                            variant_key: str, metrics: dict, primary_metric: str | None,
                            details: dict | None, cost: dict, latency_ms: int | None) -> None:
        res = await self.session.execute(
            select(ParserEvalResult).where(
                ParserEvalResult.run_id == run_id,
                ParserEvalResult.eval_case_id == eval_case_id,
                ParserEvalResult.variant_key == variant_key))
        existing = res.scalar_one_or_none()
        if existing is None:
            self.session.add(ParserEvalResult(
                run_id=run_id, eval_case_id=eval_case_id, adapter=adapter, config=config,
                variant_key=variant_key, metrics=metrics, primary_metric=primary_metric,
                details=details, cost=cost, latency_ms=latency_ms))
        else:
            existing.adapter, existing.config = adapter, config
            existing.metrics, existing.primary_metric = metrics, primary_metric
            existing.details, existing.cost, existing.latency_ms = details, cost, latency_ms
        await self.session.commit()

    async def get_results(self, run_id: UUID) -> list[ParserEvalResult]:
        res = await self.session.execute(
            select(ParserEvalResult).where(ParserEvalResult.run_id == run_id)
            .order_by(ParserEvalResult.eval_case_id, ParserEvalResult.variant_key))
        return list(res.scalars().all())
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/repositories/test_parser_eval_repository.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/repositories/parser_eval_repository.py backend/tests/repositories/test_parser_eval_repository.py
git commit -m "refactor(parser-eval): repository for canonical cases/datasets/runs/results"
```

---

### Task 6: Engine rewrite (variant loop + metrics)

**Files:**
- Modify: `backend/app/services/parser_eval/engine.py`
- Test: `backend/tests/services/parser_eval/test_engine.py` (rewrite)

**Interfaces:**
- Consumes: `capture(...)` (unchanged signature — keyword `parser`), `get_scorer` (ScorerSpec), `variant_key`, repository `upsert_result` (Task 5), `ParserEvalRunStatus`.
- Produces: `run_evaluation(repo, parsing_service, storage, *, run_id, cases, variants, project_id, _case_source)` where `variants: list[dict]` each `{adapter, config}`. Each `case` has `.dimension` and `.expected` directly (no `.targets`).

- [ ] **Step 1: Rewrite the engine test**

Replace `backend/tests/services/parser_eval/test_engine.py`:

```python
import pytest
from types import SimpleNamespace
from app.services.parser_eval import engine as engine_mod
from app.services.parser_eval.engine import run_evaluation
from app.models.parser_eval import ParserEvalDimension


class _Repo:
    def __init__(self):
        self.status = None
        self.results = []
    async def set_run_status(self, run_id, status, error_message=None):
        self.status = status
    async def upsert_result(self, run_id, eval_case_id, adapter, config, variant_key,
                            metrics, primary_metric, details, cost, latency_ms):
        self.results.append((adapter, variant_key, metrics, details))


def _case():
    return SimpleNamespace(id="c1", source_document_id="s1",
                           dimension=ParserEvalDimension.text, expected={"pages": ["hi"]})


@pytest.mark.asyncio
async def test_two_configs_of_one_adapter_yield_two_results(monkeypatch):
    from app.cdm.models import ParsedDocument, Page

    async def fake_capture(*a, **k):
        doc = ParsedDocument(id="d", source_document_id="s", parse_run_id="r", page_count=1,
                             pages=[Page(index=0, start_char=0, end_char=2)], blocks=[], full_text="hi")
        return doc, {"usd": 0.0}, 5
    monkeypatch.setattr(engine_mod, "capture", fake_capture)

    repo = _Repo()
    variants = [{"adapter": "custom_pipeline", "config": {"tool": "pdfplumber"}},
                {"adapter": "custom_pipeline", "config": {"tool": "fitz"}}]
    await run_evaluation(repo, object(), object(), run_id="run", cases=[_case()],
                         variants=variants, project_id="p",
                         _case_source=lambda c: ("s1", "uri", "f.pdf", "application/pdf"))
    assert len(repo.results) == 2
    assert repo.results[0][1] != repo.results[1][1]  # distinct variant_key


@pytest.mark.asyncio
async def test_capture_failure_writes_zero_primary(monkeypatch):
    async def fake_capture(*a, **k):
        return None, {}, None
    monkeypatch.setattr(engine_mod, "capture", fake_capture)

    repo = _Repo()
    await run_evaluation(repo, object(), object(), run_id="run", cases=[_case()],
                         variants=[{"adapter": "docling", "config": {}}], project_id="p",
                         _case_source=lambda c: ("s1", "uri", "f.pdf", "application/pdf"))
    assert repo.results[0][2] == {"similarity": 0.0}
    assert repo.results[0][3] == {"capture_failed": True}
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/parser_eval/test_engine.py -v`
Expected: FAIL (`run_evaluation` still expects `parsers` / `case.targets`).

- [ ] **Step 3: Rewrite the engine**

Replace `backend/app/services/parser_eval/engine.py`:

```python
"""Orchestrate one parser-eval run: capture per variant, score the case's dimension, persist."""
from __future__ import annotations

import logging
from typing import Any, Callable

from app.models.parser_eval import ParserEvalRunStatus
from app.services.parser_eval.capture import capture
from app.services.parser_eval.scorers import get_scorer
from app.services.parser_eval.variants import variant_key

logger = logging.getLogger(__name__)


def _default_case_source(case: Any) -> tuple[str, str, str, str]:
    raise NotImplementedError


async def run_evaluation(
    repo: Any,
    parsing_service: Any,
    storage: Any,
    *,
    run_id: Any,
    cases: list[Any],
    variants: list[dict],
    project_id: Any,
    _case_source: Callable[[Any], tuple[str, str, str, str]] = _default_case_source,
) -> None:
    await repo.set_run_status(run_id, ParserEvalRunStatus.running)
    try:
        for case in cases:
            source_document_id, storage_uri, filename, mime_type = _case_source(case)
            spec = get_scorer(case.dimension.value)
            for variant in variants:
                adapter = variant["adapter"]
                config = variant.get("config") or {}
                cdm, cost, latency = await capture(
                    parsing_service, storage,
                    source_document_id=source_document_id, storage_uri=storage_uri,
                    filename=filename, mime_type=mime_type, parser=adapter,
                    project_id=project_id, config=config)
                if cdm is None:
                    metrics, details = {spec.primary: 0.0}, {"capture_failed": True}
                else:
                    metrics, details = spec.fn(cdm, case.expected)
                await repo.upsert_result(
                    run_id, case.id, adapter, config, variant_key(adapter, config),
                    metrics, spec.primary, details, cost, latency)
        await repo.set_run_status(run_id, ParserEvalRunStatus.completed)
    except Exception as err:                            # noqa: BLE001 — record and surface
        logger.exception("parser-eval run %s failed", run_id)
        await repo.set_run_status(run_id, ParserEvalRunStatus.failed, error_message=str(err))
        raise
```

- [ ] **Step 4: Extend `capture` to accept per-variant `config`**

In `backend/app/services/parser_eval/capture.py`, add a `config: dict | None = None` keyword and merge it into the parse config so variant config reaches the adapter:

```python
async def capture(
    parsing_service: Any,
    storage: Any,
    *,
    source_document_id: str,
    storage_uri: str,
    filename: str,
    mime_type: str,
    parser: str,
    project_id: Any,
    config: dict | None = None,
) -> tuple[ParsedDocument | None, dict, int | None]:
    data = await storage.get(storage_uri)
    source = await parsing_service.ensure_source_document(
        bytes_=data, filename=filename, mime_type=mime_type)

    suffix = os.path.splitext(filename)[1] or ".bin"
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(data)
            tmp_path = tmp.name
        run, doc = await parsing_service.parse_and_persist(
            source=source, file_path=tmp_path,
            representation_kind=DEFAULT_REPRESENTATION_KIND,
            config={"parser": parser, **(config or {})}, project_id=project_id, force=False)
        return doc, dict(run.cost or {}), run.duration_ms
    except ParseFailedError as err:
        logger.warning("parser-eval capture failed parser=%s: %s", parser, err)
        return None, {}, None
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
```

- [ ] **Step 5: Run to verify it passes**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/parser_eval/test_engine.py tests/services/parser_eval/test_capture.py -v`
Expected: PASS. (If `test_capture.py` asserts the old config shape, update its expected `config` to `{"parser": ...}` merged form.)

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/parser_eval/engine.py backend/app/services/parser_eval/capture.py backend/tests/services/parser_eval/test_engine.py backend/tests/services/parser_eval/test_capture.py
git commit -m "refactor(parser-eval): engine loops variants=(adapter,config), writes metrics map"
```

---

### Task 7: Schemas (DTOs)

**Files:**
- Modify (full rewrite): `backend/app/schemas/parser_eval.py`
- Test: `backend/tests/schemas/test_parser_eval_schema.py` (rewrite)

**Interfaces:**
- Produces: `CaseCreate{source_document_id, dimension, expected, source_method?, review_status?}`, `CaseResponse`, `DatasetCreate{name, description?}`, `DatasetResponse`, `VariantInput{adapter, config}`, `RunCreate{name?, variants, eval_case_ids?, dataset_id?}`, `RunResponse`, `ResultResponse{eval_case_id, adapter, config, variant_key, metrics, primary_metric, details, cost, latency_ms}`.
- `RunCreate.variants` validates each `adapter` against `ParserKind` (reuse the existing 422 pattern).

- [ ] **Step 1: Rewrite the schema test**

Replace `backend/tests/schemas/test_parser_eval_schema.py`:

```python
import pytest
from pydantic import ValidationError
from app.schemas.parser_eval import CaseCreate, RunCreate, VariantInput


def test_case_create_requires_dimension_and_expected():
    c = CaseCreate(source_document_id="00000000-0000-0000-0000-000000000001",
                   dimension="text", expected={"pages": ["hi"]})
    assert c.dimension == "text"


def test_run_create_rejects_unknown_adapter():
    with pytest.raises(ValidationError):
        RunCreate(variants=[VariantInput(adapter="not_a_parser", config={})],
                  eval_case_ids=["00000000-0000-0000-0000-000000000001"])


def test_run_create_accepts_known_adapter():
    r = RunCreate(variants=[VariantInput(adapter="docling", config={"x": 1})],
                  eval_case_ids=["00000000-0000-0000-0000-000000000001"])
    assert r.variants[0].adapter == "docling"
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/schemas/test_parser_eval_schema.py -v`
Expected: FAIL (`VariantInput` not defined; `CaseCreate` still has `targets`).

- [ ] **Step 3: Rewrite the schemas**

Replace `backend/app/schemas/parser_eval.py`:

```python
"""Pydantic schemas for the parser-eval API (canonical model)."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from app.cdm.models import ParserKind


class CaseCreate(BaseModel):
    source_document_id: UUID
    dimension: str
    expected: dict
    source_method: str | None = None
    review_status: str | None = None

    @model_validator(mode="after")
    def _validate_expected(self):
        if self.dimension == "text":
            pages = self.expected.get("pages")
            if not isinstance(pages, list) or not all(isinstance(p, str) for p in pages):
                raise ValueError("text case requires expected.pages: list[str]")
        return self


class CaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    source_document_id: UUID
    dimension: str
    source_method: str
    review_status: str
    created_at: datetime


class DatasetCreate(BaseModel):
    name: str
    description: str | None = None


class DatasetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    description: str | None
    created_at: datetime


class VariantInput(BaseModel):
    adapter: str
    config: dict = {}

    @field_validator("adapter")
    @classmethod
    def _validate_adapter(cls, value: str) -> str:
        valid = {p.value for p in ParserKind}
        if value not in valid:
            raise ValueError(f"Invalid adapter '{value}'. Valid: {sorted(valid)}")
        return value


class RunCreate(BaseModel):
    name: str | None = None
    variants: list[VariantInput]
    eval_case_ids: list[UUID] = []
    dataset_id: UUID | None = None


class RunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    status: str
    variants: list[dict]
    dataset_id: UUID | None = None
    error_message: str | None = None
    created_at: datetime


class ResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    eval_case_id: UUID
    adapter: str
    config: dict
    variant_key: str
    metrics: dict
    primary_metric: str | None
    details: dict | None
    cost: dict | None
    latency_ms: int | None
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/schemas/test_parser_eval_schema.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/parser_eval.py backend/tests/schemas/test_parser_eval_schema.py
git commit -m "refactor(parser-eval): DTOs for cases/datasets/variant runs/metric results"
```

---

### Task 8: Service + Router (cases, datasets, runs, results)

**Files:**
- Modify (full rewrite): `backend/app/services/parser_eval/service.py`
- Modify: `backend/app/routers/parser_eval.py`
- Test: `backend/tests/services/parser_eval/test_service.py` (rewrite)

**Interfaces:**
- Consumes: repository (Task 5), engine `run_evaluation` (Task 6, keyword `variants`), schemas (Task 7).
- Produces service methods: `create_case`, `list_cases`, `create_dataset`, `list_datasets`, `add_case_to_dataset`, `remove_case_from_dataset`, `list_dataset_cases`, `create_run` (resolves `dataset_id`→snapshot when `eval_case_ids` empty), `execute_run`, `list_runs`, `get_run`, `get_results`.

- [ ] **Step 1: Rewrite the service test**

Replace `backend/tests/services/parser_eval/test_service.py`:

```python
import pytest
from app.cdm.models import ParsedDocument, Page
from app.repositories.parser_eval_repository import ParserEvalRepository
from app.repositories.source_document_repository import SourceDocumentRepository
from app.schemas.parser_eval import CaseCreate, DatasetCreate, RunCreate, VariantInput
from app.services.parser_eval import engine as engine_mod
from app.services.parser_eval.service import ParserEvalService


def _service(db):
    return ParserEvalService(ParserEvalRepository(db), SourceDocumentRepository(db),
                             parsing_service=object(), storage=object())


@pytest.mark.asyncio
async def test_case_then_run_produces_metric_result(test_db, seed_project_user_source, monkeypatch):
    project_id, user_id, source_id = seed_project_user_source

    async def fake_capture(*a, **k):
        doc = ParsedDocument(id="d", source_document_id="s", parse_run_id="r", page_count=1,
                             pages=[Page(index=0, start_char=0, end_char=2)], blocks=[], full_text="hi")
        return doc, {"usd": 0.0}, 5
    monkeypatch.setattr(engine_mod, "capture", fake_capture)

    service = _service(test_db)
    case = await service.create_case(project_id, user_id, CaseCreate(
        source_document_id=source_id, dimension="text", expected={"pages": ["hi"]}))
    run = await service.create_run(project_id, user_id, RunCreate(
        name="r1", variants=[VariantInput(adapter="docling", config={})],
        eval_case_ids=[case.id]))
    await service.execute_run(run.id)

    results = await service.get_results(run.id)
    assert len(results) == 1
    assert results[0].metrics["similarity"] == 1.0
    assert results[0].primary_metric == "similarity"


@pytest.mark.asyncio
async def test_run_from_dataset_snapshots_cases(test_db, seed_project_user_source, monkeypatch):
    project_id, user_id, source_id = seed_project_user_source
    monkeypatch.setattr(engine_mod, "capture",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not run")))
    service = _service(test_db)
    case = await service.create_case(project_id, user_id, CaseCreate(
        source_document_id=source_id, dimension="text", expected={"pages": ["hi"]}))
    ds = await service.create_dataset(project_id, user_id, DatasetCreate(name="smoke"))
    await service.add_case_to_dataset(ds.id, case.id)

    run = await service.create_run(project_id, user_id, RunCreate(
        variants=[VariantInput(adapter="docling", config={})], dataset_id=ds.id))
    stored = await service.get_run(run.id)
    # Snapshot resolved from dataset membership at creation time
    assert [str(case.id)] == [str(c) for c in (await service.repo.get_run(run.id)).eval_case_ids]
    assert stored.dataset_id == ds.id
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/parser_eval/test_service.py -v`
Expected: FAIL (service signatures changed; no dataset methods).

- [ ] **Step 3: Rewrite the service**

Replace `backend/app/services/parser_eval/service.py`:

```python
"""Service orchestrating parser-eval CRUD and run execution (canonical model)."""
from __future__ import annotations

from uuid import UUID

from app.models.parser_eval import (
    ParserEvalDimension, ParserEvalSourceMethod, ParserEvalReviewStatus,
)
from app.repositories.parser_eval_repository import ParserEvalRepository
from app.repositories.source_document_repository import SourceDocumentRepository
from app.schemas.parser_eval import (
    CaseCreate, CaseResponse, DatasetCreate, DatasetResponse,
    RunCreate, RunResponse, ResultResponse,
)
from app.services.exceptions import NotFoundError
from app.services.parser_eval.engine import run_evaluation


class ParserEvalService:
    def __init__(self, repo: ParserEvalRepository, source_doc_repo: SourceDocumentRepository,
                 parsing_service, storage):
        self.repo = repo
        self.source_doc_repo = source_doc_repo
        self.parsing_service = parsing_service
        self.storage = storage

    # --- cases ---
    async def create_case(self, project_id: UUID, user_id: UUID, data: CaseCreate) -> CaseResponse:
        source = await self.source_doc_repo.get(data.source_document_id)
        if source is None:
            raise NotFoundError(f"Source document {data.source_document_id} not found")
        case = await self.repo.create_case(
            project_id, data.source_document_id, ParserEvalDimension(data.dimension),
            data.expected, user_id,
            source_method=ParserEvalSourceMethod(data.source_method or "human"),
            review_status=ParserEvalReviewStatus(data.review_status or "draft"))
        return CaseResponse.model_validate(case)

    async def list_cases(self, project_id: UUID) -> list[CaseResponse]:
        return [CaseResponse.model_validate(c) for c in await self.repo.list_cases(project_id)]

    # --- datasets ---
    async def create_dataset(self, project_id: UUID, user_id: UUID,
                             data: DatasetCreate) -> DatasetResponse:
        ds = await self.repo.create_dataset(project_id, data.name, data.description, user_id)
        return DatasetResponse.model_validate(ds)

    async def list_datasets(self, project_id: UUID) -> list[DatasetResponse]:
        return [DatasetResponse.model_validate(d) for d in await self.repo.list_datasets(project_id)]

    async def add_case_to_dataset(self, dataset_id: UUID, eval_case_id: UUID) -> None:
        await self.repo.add_case_to_dataset(dataset_id, eval_case_id)

    async def remove_case_from_dataset(self, dataset_id: UUID, eval_case_id: UUID) -> None:
        await self.repo.remove_case_from_dataset(dataset_id, eval_case_id)

    async def list_dataset_cases(self, dataset_id: UUID) -> list[CaseResponse]:
        ids = await self.repo.list_dataset_case_ids(dataset_id)
        return [CaseResponse.model_validate(c) for c in await self.repo.get_cases_by_ids(ids)]

    # --- runs ---
    async def create_run(self, project_id: UUID, user_id: UUID, data: RunCreate) -> RunResponse:
        name = data.name or "Parser eval run"
        case_ids = [str(cid) for cid in data.eval_case_ids]
        if not case_ids and data.dataset_id is not None:
            case_ids = [str(cid) for cid in await self.repo.list_dataset_case_ids(data.dataset_id)]
        variants = [v.model_dump() for v in data.variants]
        run = await self.repo.create_run(project_id, name, variants, case_ids, user_id,
                                         dataset_id=data.dataset_id)
        return RunResponse.model_validate(run)

    async def execute_run(self, run_id: UUID) -> None:
        run = await self.repo.get_run(run_id)
        if run is None:
            raise NotFoundError(f"Parser eval run {run_id} not found")
        selected = [UUID(cid) for cid in (run.eval_case_ids or [])]
        cases = await self.repo.get_cases_by_ids(selected)

        source_cache: dict[UUID, object] = {}

        async def _resolve(case):
            src = source_cache.get(case.source_document_id)
            if src is None:
                src = await self.source_doc_repo.get(case.source_document_id)
                source_cache[case.source_document_id] = src
            return (str(case.source_document_id), src.storage_uri, src.filename, src.mime_type)

        resolved = {c.id: await _resolve(c) for c in cases}
        await run_evaluation(
            self.repo, self.parsing_service, self.storage,
            run_id=run_id, cases=cases, variants=list(run.variants),
            project_id=run.project_id, _case_source=lambda c: resolved[c.id])

    async def get_run(self, run_id: UUID) -> RunResponse:
        run = await self.repo.get_run(run_id)
        if run is None:
            raise NotFoundError(f"Parser eval run {run_id} not found")
        return RunResponse.model_validate(run)

    async def list_runs(self, project_id: UUID) -> list[RunResponse]:
        return [RunResponse.model_validate(r) for r in await self.repo.list_runs(project_id)]

    async def get_results(self, run_id: UUID) -> list[ResultResponse]:
        run = await self.repo.get_run(run_id)
        if run is None:
            raise NotFoundError(f"Parser eval run {run_id} not found")
        return [ResultResponse.model_validate(r) for r in await self.repo.get_results(run_id)]
```

- [ ] **Step 4: Add dataset routes + update case/run routes**

In `backend/app/routers/parser_eval.py`: update the imports to the new schema names (`DatasetCreate, DatasetResponse`), keep the `create_case`/`list_cases`/`create_run`/`list_runs`/`get_results` routes (their bodies are unchanged — they delegate to the service), and add dataset routes. Insert after the cases routes:

```python
@router.post("/projects/{project_id}/parser-eval/datasets", response_model=DatasetResponse)
async def create_dataset(
    project_id: UUID,
    data: DatasetCreate,
    current_user: User = Depends(get_current_active_user),
    service: ParserEvalService = Depends(get_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    await verify_project_access(project_id, current_user, project_repo)
    return await service.create_dataset(project_id, current_user.id, data)


@router.get("/projects/{project_id}/parser-eval/datasets", response_model=list[DatasetResponse])
async def list_datasets(
    project_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: ParserEvalService = Depends(get_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    await verify_project_access(project_id, current_user, project_repo)
    return await service.list_datasets(project_id)


@router.get("/projects/{project_id}/parser-eval/datasets/{dataset_id}/cases",
            response_model=list[CaseResponse])
async def list_dataset_cases(
    project_id: UUID,
    dataset_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: ParserEvalService = Depends(get_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    await verify_project_access(project_id, current_user, project_repo)
    return await service.list_dataset_cases(dataset_id)


@router.post("/projects/{project_id}/parser-eval/datasets/{dataset_id}/cases/{case_id}",
             status_code=status.HTTP_204_NO_CONTENT)
async def add_dataset_case(
    project_id: UUID,
    dataset_id: UUID,
    case_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: ParserEvalService = Depends(get_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    await verify_project_access(project_id, current_user, project_repo)
    await service.add_case_to_dataset(dataset_id, case_id)


@router.delete("/projects/{project_id}/parser-eval/datasets/{dataset_id}/cases/{case_id}",
               status_code=status.HTTP_204_NO_CONTENT)
async def remove_dataset_case(
    project_id: UUID,
    dataset_id: UUID,
    case_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: ParserEvalService = Depends(get_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    await verify_project_access(project_id, current_user, project_repo)
    await service.remove_case_from_dataset(dataset_id, case_id)
```

Update the import line at the top of the router to:

```python
from app.schemas.parser_eval import (
    CaseCreate, CaseResponse, DatasetCreate, DatasetResponse,
    RunCreate, RunResponse, ResultResponse,
)
```

- [ ] **Step 5: Run to verify service tests pass**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/parser_eval/test_service.py -v`
Expected: PASS (2 tests).

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/parser_eval/service.py backend/app/routers/parser_eval.py backend/tests/services/parser_eval/test_service.py
git commit -m "refactor(parser-eval): service+router for datasets, variant runs, dataset snapshot"
```

---

### Task 9: Router integration tests + full-suite green

**Files:**
- Modify (rewrite): `backend/tests/routers/test_parser_eval_router.py`

**Interfaces:**
- Consumes: the full stack (Tasks 1–8). Uses the app's auth + DB overrides as the existing router test does — mirror its fixtures/overrides exactly.

- [ ] **Step 1: Rewrite the router test to the new endpoints**

Rewrite `backend/tests/routers/test_parser_eval_router.py` to cover: create case (`dimension`+`expected`), create dataset, add member, create run from `dataset_id` (asserts 202), unknown-adapter run → 422, and results shape. Preserve the existing file's auth/dependency-override setup (copy its `app.dependency_overrides` / client fixture block verbatim — it is the established pattern for this router). Example core assertions:

```python
def test_create_run_unknown_adapter_returns_422(client, project_ctx):
    pid, case_id = project_ctx
    resp = client.post(f"/projects/{pid}/parser-eval/runs",
                       json={"variants": [{"adapter": "nope", "config": {}}],
                             "eval_case_ids": [str(case_id)]})
    assert resp.status_code == 422


def test_run_from_dataset_snapshots(client, project_ctx_with_dataset):
    pid, dataset_id = project_ctx_with_dataset
    resp = client.post(f"/projects/{pid}/parser-eval/runs",
                       json={"variants": [{"adapter": "docling", "config": {}}],
                             "dataset_id": str(dataset_id)})
    assert resp.status_code == 202
```

> Adapt fixture names to the existing file's conventions. The point of this task is an HTTP-level pass over the new surface, not new fixture machinery.

- [ ] **Step 2: Run the full parser-eval suite**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests -k parser_eval -v`
Expected: PASS across models, schemas, repository, services (variants/text_scorer/registry/capture/engine/service), and router.

- [ ] **Step 3: Run the whole backend suite for regressions**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests -q`
Expected: PASS (no collateral breakage from the `ParserEvalTarget` removal or `models/__init__` change).

- [ ] **Step 4: Commit**

```bash
git add backend/tests/routers/test_parser_eval_router.py
git commit -m "test(parser-eval): HTTP coverage for datasets, variant runs, metric results"
```

---

## Self-Review

**Spec coverage:**
- Case=(doc,dimension,expected)+provenance → Task 1, 5, 8. ✅
- Dataset M:N container → Task 1, 5, 8. ✅
- Metric map + primary_metric on Result → Task 1, 4, 5, 6. ✅
- Variant=(adapter,config)+variant_key → Task 3, 6, 7. ✅
- Run snapshots dataset members → Task 8 (`create_run`). ✅
- Migration rewritten in place → Task 2. ✅
- Unknown adapter → 422 → Task 7, 9. ✅
- `parser_eval_targets` dropped → Task 1 (models), Task 2 (migration). ✅

**Placeholder scan:** No `TBD`/"add error handling"/bare "write tests" — all steps carry real code. Router Task 8/9 references the existing file's auth-override block rather than reprinting it (it is environment-specific and already established); this is a deliberate "match existing pattern," not a placeholder.

**Type consistency:** `run_evaluation(..., variants=...)` (Task 6) matches service call (Task 8). `upsert_result(run_id, eval_case_id, adapter, config, variant_key, metrics, primary_metric, details, cost, latency_ms)` identical in Task 5 (def), Task 6 (call). `score_text -> (metrics, details)` consistent across Task 4 (def), Task 6 (call). `variant_key(adapter, config)` consistent Task 3/6. `ScorerSpec{fn,emits,primary}` consistent Task 4/6.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-05-parser-eval-canonical-refactor.md`.

Per the project pre-implementation gate: **a GitHub issue must exist and be confirmed before implementation begins.** Once that gate is cleared, two execution options:

1. **Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks.
2. **Inline Execution** — execute tasks in this session with checkpoints.
