# Parser Evaluation — Backend (Plan 1 of 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the backend for the parser-evaluation feature's first slice — a project-scoped API that stores benchmark cases with per-dimension ground truth, runs a set of parsers over each case, scores the `text` dimension, and persists comparable per-parser results.

**Architecture:** Mirrors the existing `extraction_eval` feature: `models → repository → service (+ engine + scorers) → router`, all async. The scoring engine reuses `ParsingService.parse_and_persist` to produce a `ParsedDocument` per parser (getting cost/latency from the returned `ParseRun` for free). Scorers are pure functions behind a registry keyed by dimension; only `text` is implemented in this slice.

**Tech Stack:** Python 3.12, FastAPI (async), SQLAlchemy 2.0 (`Mapped`/`mapped_column`), Alembic, Pydantic v2, Postgres (ParadeDB), pytest. Text similarity uses stdlib `difflib` (no new dependency).

## Global Constraints

- Data flow is strictly `router → service → repository → database`; services raise exceptions, routers translate to HTTP. (Copied from CLAUDE.md.)
- All DB operations are async with type hints.
- Result rows are unique on `(run_id, case_id, parser, dimension)` — this is the mental-model result key.
- The user never authors a `ParsedDocument`. Ground truth is a per-dimension JSON payload; `text` = `{ "pages": [str] }`.
- A scorer runs for a case only if a target for that dimension exists (asserted-or-not; no false-zeros).
- New models MUST be exported from `app/models/__init__.py` (so Alembic autogenerate and relationships resolve).
- Enum columns follow the existing pattern: `Enum(<PyEnum>, name='<snake>', create_type=False)` with the type created explicitly in the migration.
- Reuse `app.services.exceptions.NotFoundError` for missing entities; the router maps it to 404.
- Tests run with: `cd backend && uv run python -m pytest -o "addopts=" <path> -v`.

**Reference files to imitate (read before starting):**
- Models: `app/models/extraction_eval.py`
- Repository: `app/repositories/extraction_eval_repository.py`
- Service: `app/services/extraction_eval/service.py`
- Router + DI: `app/routers/extraction_eval.py`
- Parsing entry point: `app/services/parsing/parsing_service.py` (`ensure_source_document`, `parse_and_persist`)
- Parsing DI: `app/dependencies/documents.py` (`get_parsing_service`)
- CDM types: `app/cdm/models.py` (`ParsedDocument`, `Page`, `ParserKind`)

---

## Known deviation from the product vision (build as specified; do NOT "fix" here)

`ParserEvalCase` is a deliberate pragmatic stand-in: it re-wraps `project_id + source_document_id`
(plus `name`/`doc_type`/`source_filename`) in a parallel table. The product vision treats `Document`
and `ParsedDocument` as first-class primitives ("Document" = the source_document that belongs to this
project), and eval/ground-truth should ultimately bind to those rather than a parallel case entity;
raw-text `text` ground truth is a convenience, not canonical; `source_filename` is redundant
denormalization of `SourceDocument.filename`. **Build the model exactly as specified for the first
slice** — collapsing `ParserEvalCase` onto `Document`/`ParsedDocument` is a separate future refactor
(see the design spec's "Vision alignment & known deviations"), gated on the Index→`ParsedDocument`
refactor. Do not attempt it in this plan.

---

## File Structure

- Create `app/models/parser_eval.py` — `ParserEvalCase`, `ParserEvalTarget`, `ParserEvalRun`, `ParserEvalResult`, `ParserEvalDimension`, `ParserEvalRunStatus`.
- Modify `app/models/__init__.py` — export the new models.
- Create `alembic/versions/<rev>_add_parser_eval_tables.py` — enum types + 4 tables.
- Create `app/services/parser_eval/__init__.py`
- Create `app/services/parser_eval/scorers/__init__.py` — registry.
- Create `app/services/parser_eval/scorers/text.py` — text-faithfulness scorer.
- Create `app/services/parser_eval/capture.py` — wraps `ParsingService`.
- Create `app/services/parser_eval/engine.py` — orchestrates a run.
- Create `app/services/parser_eval/service.py` — CRUD + `execute_run`.
- Create `app/repositories/parser_eval_repository.py`
- Create `app/schemas/parser_eval.py`
- Create `app/routers/parser_eval.py`
- Modify `app/main.py` — include the router.
- Create tests under `tests/services/parser_eval/`, `tests/repositories/`, `tests/routers/`.

---

## Task 1: Text-faithfulness scorer (pure function)

Start here — it's the novel logic, has zero infra dependencies, and is fully unit-testable.

**Files:**
- Create: `app/services/parser_eval/__init__.py` (empty)
- Create: `app/services/parser_eval/scorers/__init__.py` (empty for now)
- Create: `app/services/parser_eval/scorers/text.py`
- Test: `tests/services/parser_eval/__init__.py` (empty), `tests/services/parser_eval/test_text_scorer.py`

**Interfaces:**
- Produces: `score_text(cdm: ParsedDocument, expected: dict) -> tuple[float, dict]` where `expected == {"pages": [str, ...]}`. Returns `(similarity_score_0_1, details_dict)`. `details` keys: `per_page: list[{page, similarity, omission, hallucination}]`, `omission`, `hallucination`, `page_count_expected`, `page_count_parsed`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/services/parser_eval/test_text_scorer.py
from app.cdm.models import ParsedDocument, Page
from app.services.parser_eval.scorers.text import score_text


def _doc(full_text: str, pages: list[tuple[int, int]]) -> ParsedDocument:
    """Build a minimal ParsedDocument with page char-offsets into full_text."""
    return ParsedDocument(
        id="d1", source_document_id="s1", parse_run_id="r1",
        page_count=len(pages),
        pages=[Page(index=i, start_char=s, end_char=e) for i, (s, e) in enumerate(pages)],
        blocks=[], full_text=full_text,
    )


def test_perfect_match_scores_one():
    doc = _doc("hello world", [(0, 11)])
    score, details = score_text(doc, {"pages": ["hello world"]})
    assert score == 1.0
    assert details["omission"] == 0.0
    assert details["hallucination"] == 0.0


def test_omission_detected():
    # reference has two words, parse dropped one
    doc = _doc("hello", [(0, 5)])
    score, details = score_text(doc, {"pages": ["hello world"]})
    assert score < 1.0
    assert details["omission"] > 0.0


def test_hallucination_detected():
    doc = _doc("hello world extra", [(0, 17)])
    score, details = score_text(doc, {"pages": ["hello world"]})
    assert details["hallucination"] > 0.0


def test_page_count_mismatch_penalized():
    # reference has 2 pages, parse produced 1 → missing page fully omitted
    doc = _doc("page one text", [(0, 13)])
    score, details = score_text(doc, {"pages": ["page one text", "page two text"]})
    assert details["page_count_expected"] == 2
    assert details["page_count_parsed"] == 1
    assert score < 1.0


def test_normalization_ignores_whitespace_and_case():
    doc = _doc("Hello    WORLD", [(0, 14)])
    score, _ = score_text(doc, {"pages": ["hello world"]})
    assert score == 1.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/parser_eval/test_text_scorer.py -v`
Expected: FAIL — `ModuleNotFoundError: app.services.parser_eval.scorers.text`.

- [ ] **Step 3: Implement the scorer**

```python
# app/services/parser_eval/scorers/text.py
"""Text-faithfulness scorer — compares parsed per-page text to a page-segmented reference.

Content-oriented and parser-agnostic: it flattens each page to text and never inspects
block structure, so parsers that segment blocks differently are scored fairly.
"""
from __future__ import annotations

import difflib
import re
from typing import Any

from app.cdm.models import ParsedDocument

_WS = re.compile(r"\s+")


def _normalize(text: str) -> str:
    return _WS.sub(" ", (text or "").strip().lower())


def _tokens(text: str) -> list[str]:
    return _normalize(text).split()


def _parsed_page_texts(cdm: ParsedDocument) -> list[str]:
    """Per-page text via Page.start_char/end_char slices of full_text.

    Falls back to concatenating each page's block text when offsets are absent.
    """
    full = cdm.full_text or ""
    pages: list[str] = []
    for page in sorted(cdm.pages, key=lambda p: p.index):
        if full and page.start_char is not None and page.end_char is not None:
            pages.append(full[page.start_char:page.end_char])
        else:
            pages.append(
                " ".join(b.text for b in cdm.blocks if b.page_index == page.index)
            )
    return pages


def _score_page(reference: str, parsed: str) -> dict[str, float]:
    ref_norm, par_norm = _normalize(reference), _normalize(parsed)
    similarity = difflib.SequenceMatcher(None, ref_norm, par_norm).ratio()

    ref_toks, par_toks = set(_tokens(reference)), set(_tokens(parsed))
    omission = 0.0 if not ref_toks else len(ref_toks - par_toks) / len(ref_toks)
    hallucination = 0.0 if not par_toks else len(par_toks - ref_toks) / len(par_toks)
    return {"similarity": similarity, "omission": omission, "hallucination": hallucination}


def score_text(cdm: ParsedDocument, expected: dict[str, Any]) -> tuple[float, dict[str, Any]]:
    reference_pages: list[str] = expected["pages"]
    parsed_pages = _parsed_page_texts(cdm)

    per_page: list[dict[str, Any]] = []
    n = max(len(reference_pages), len(parsed_pages))
    for i in range(n):
        ref = reference_pages[i] if i < len(reference_pages) else ""
        par = parsed_pages[i] if i < len(parsed_pages) else ""
        page_scores = _score_page(ref, par)
        per_page.append({"page": i, **page_scores})

    # Length-weighted aggregate by reference character count (empty ref pages weight 0,
    # but an unmatched *parsed* page still contributes hallucination via a min weight of 1).
    def _weight(i: int) -> int:
        return max(len(reference_pages[i]) if i < len(reference_pages) else 0, 1)

    total_w = sum(_weight(i) for i in range(n)) or 1
    similarity = sum(p["similarity"] * _weight(p["page"]) for p in per_page) / total_w
    omission = sum(p["omission"] * _weight(p["page"]) for p in per_page) / total_w
    hallucination = sum(p["hallucination"] * _weight(p["page"]) for p in per_page) / total_w

    details = {
        "per_page": per_page,
        "omission": omission,
        "hallucination": hallucination,
        "page_count_expected": len(reference_pages),
        "page_count_parsed": len(parsed_pages),
    }
    return similarity, details
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/parser_eval/test_text_scorer.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/parser_eval backend/tests/services/parser_eval
git commit -m "feat(parser-eval): text-faithfulness scorer"
```

---

## Task 2: Scorer registry

**Files:**
- Modify: `app/services/parser_eval/scorers/__init__.py`
- Test: `tests/services/parser_eval/test_registry.py`

**Interfaces:**
- Consumes: `score_text` from Task 1.
- Produces: `SCORERS: dict[str, Scorer]` and `get_scorer(dimension: str) -> Scorer`. `Scorer` is `Callable[[ParsedDocument, dict], tuple[float, dict]]`. Unknown dimension raises `KeyError`.

- [ ] **Step 1: Write the failing test**

```python
# tests/services/parser_eval/test_registry.py
import pytest
from app.services.parser_eval.scorers import get_scorer
from app.services.parser_eval.scorers.text import score_text


def test_text_scorer_registered():
    assert get_scorer("text") is score_text


def test_unknown_dimension_raises():
    with pytest.raises(KeyError):
        get_scorer("does_not_exist")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/parser_eval/test_registry.py -v`
Expected: FAIL — `ImportError: cannot import name 'get_scorer'`.

- [ ] **Step 3: Implement the registry**

```python
# app/services/parser_eval/scorers/__init__.py
"""Registry of dimension scorers. Add a dimension = add one entry here (seam #1)."""
from __future__ import annotations

from typing import Any, Callable

from app.cdm.models import ParsedDocument
from app.services.parser_eval.scorers.text import score_text

Scorer = Callable[[ParsedDocument, dict[str, Any]], tuple[float, dict[str, Any]]]

SCORERS: dict[str, Scorer] = {
    "text": score_text,
}


def get_scorer(dimension: str) -> Scorer:
    return SCORERS[dimension]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/parser_eval/test_registry.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/parser_eval/scorers/__init__.py backend/tests/services/parser_eval/test_registry.py
git commit -m "feat(parser-eval): scorer registry"
```

---

## Task 3: Data model + migration

**Files:**
- Create: `app/models/parser_eval.py`
- Modify: `app/models/__init__.py` (add exports)
- Create: `alembic/versions/<rev>_add_parser_eval_tables.py`
- Test: `tests/models/test_parser_eval_models.py`

**Interfaces:**
- Produces (imported by later tasks):
  - `ParserEvalDimension(str, enum.Enum)` with member `text = "text"`.
  - `ParserEvalRunStatus(str, enum.Enum)`: `pending, running, completed, failed`.
  - `ParserEvalCase(id, project_id, name, doc_type, source_document_id, source_filename, created_by, created_at)` with `targets` relationship.
  - `ParserEvalTarget(id, case_id, dimension, expected: dict)`.
  - `ParserEvalRun(id, project_id, name, parsers: list[str], case_ids: list[str], status, error_message, created_by, created_at, updated_at)` with `results` relationship.
  - `ParserEvalResult(id, run_id, case_id, parser, dimension, score, details: dict, cost: dict, latency_ms, created_at)`; unique `(run_id, case_id, parser, dimension)`.

- [ ] **Step 1: Write the failing test**

```python
# tests/models/test_parser_eval_models.py
from app.models.parser_eval import (
    ParserEvalCase, ParserEvalTarget, ParserEvalRun, ParserEvalResult,
    ParserEvalDimension, ParserEvalRunStatus,
)


def test_dimension_and_status_enums():
    assert ParserEvalDimension.text.value == "text"
    assert ParserEvalRunStatus.pending.value == "pending"


def test_tablenames():
    assert ParserEvalCase.__tablename__ == "parser_eval_cases"
    assert ParserEvalTarget.__tablename__ == "parser_eval_targets"
    assert ParserEvalRun.__tablename__ == "parser_eval_runs"
    assert ParserEvalResult.__tablename__ == "parser_eval_results"


def test_result_unique_constraint_present():
    names = {c.name for c in ParserEvalResult.__table__.constraints}
    assert "uq_parser_eval_results_run_case_parser_dim" in names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/models/test_parser_eval_models.py -v`
Expected: FAIL — `ModuleNotFoundError: app.models.parser_eval`.

- [ ] **Step 3: Implement the models**

```python
# app/models/parser_eval.py
"""Models for parser evaluation — scoring parser CDM output against per-dimension ground truth."""
from datetime import datetime
from uuid import UUID, uuid4
import enum

import sqlalchemy as sa
from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ParserEvalDimension(str, enum.Enum):
    text = "text"          # first slice; table/reading_order/roles added later (seam #1)


class ParserEvalRunStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class ParserEvalCase(Base):
    """A benchmark document plus its per-dimension ground-truth targets."""
    __tablename__ = "parser_eval_cases"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4,
                                     server_default=sa.text('gen_random_uuid()'))
    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    doc_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_document_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("source_documents.id", ondelete="RESTRICT"), nullable=False)
    source_filename: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_by: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                 default=datetime.utcnow, server_default=sa.text('NOW()'))

    targets: Mapped[list["ParserEvalTarget"]] = relationship(
        back_populates="case", cascade="all, delete-orphan")

    __table_args__ = (
        sa.Index('ix_parser_eval_cases_project_id', 'project_id'),
    )


class ParserEvalTarget(Base):
    """One asserted dimension + its ground-truth payload for a case."""
    __tablename__ = "parser_eval_targets"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4,
                                     server_default=sa.text('gen_random_uuid()'))
    case_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("parser_eval_cases.id", ondelete="CASCADE"), nullable=False)
    dimension: Mapped[ParserEvalDimension] = mapped_column(
        Enum(ParserEvalDimension, name='parser_eval_dimension', create_type=False), nullable=False)
    expected: Mapped[dict] = mapped_column(JSON, nullable=False)

    case: Mapped["ParserEvalCase"] = relationship(back_populates="targets")

    __table_args__ = (
        sa.UniqueConstraint('case_id', 'dimension', name='uq_parser_eval_targets_case_dim'),
        sa.Index('ix_parser_eval_targets_case_id', 'case_id'),
    )


class ParserEvalRun(Base):
    """One execution over selected cases × parsers."""
    __tablename__ = "parser_eval_runs"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4,
                                     server_default=sa.text('gen_random_uuid()'))
    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    parsers: Mapped[list] = mapped_column(JSON, nullable=False, default=list, server_default='[]')
    case_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list, server_default='[]')  # UUID strings
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
    """One score cell: (run, case, parser, dimension) -> score + details + cost/latency."""
    __tablename__ = "parser_eval_results"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4,
                                     server_default=sa.text('gen_random_uuid()'))
    run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("parser_eval_runs.id", ondelete="CASCADE"), nullable=False)
    case_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("parser_eval_cases.id", ondelete="CASCADE"), nullable=False)
    parser: Mapped[str] = mapped_column(String(64), nullable=False)
    dimension: Mapped[ParserEvalDimension] = mapped_column(
        Enum(ParserEvalDimension, name='parser_eval_dimension', create_type=False), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    cost: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                 default=datetime.utcnow, server_default=sa.text('NOW()'))

    run: Mapped["ParserEvalRun"] = relationship(back_populates="results")

    __table_args__ = (
        sa.UniqueConstraint('run_id', 'case_id', 'parser', 'dimension',
                            name='uq_parser_eval_results_run_case_parser_dim'),
        sa.Index('ix_parser_eval_results_run_id', 'run_id'),
    )
```

- [ ] **Step 4: Export the models**

Add to `app/models/__init__.py` (follow the existing import + `__all__` style already used for `extraction_eval`):

```python
from app.models.parser_eval import (
    ParserEvalCase, ParserEvalTarget, ParserEvalRun, ParserEvalResult,
    ParserEvalDimension, ParserEvalRunStatus,
)
```
Add those six names to `__all__` if the file defines one.

- [ ] **Step 5: Run model test to verify it passes**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/models/test_parser_eval_models.py -v`
Expected: PASS.

- [ ] **Step 6: Generate the migration**

Run: `cd backend && alembic revision --autogenerate -m "add parser eval tables"`
Then open the generated file and verify/adjust:
- The two enum types (`parser_eval_dimension`, `parser_eval_run_status`) are created before the tables that use them. If autogenerate omitted them (common with `create_type=False`), add explicit creation at the top of `upgrade()` and drop at the bottom of `downgrade()`:

```python
from alembic import op
import sqlalchemy as sa

def upgrade():
    dim = sa.Enum('text', name='parser_eval_dimension')
    status = sa.Enum('pending', 'running', 'completed', 'failed', name='parser_eval_run_status')
    dim.create(op.get_bind(), checkfirst=True)
    status.create(op.get_bind(), checkfirst=True)
    # ... op.create_table(...) for the 4 tables (autogenerated) ...

def downgrade():
    # ... op.drop_table(...) in reverse FK order (results, targets, runs, cases) ...
    sa.Enum(name='parser_eval_run_status').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='parser_eval_dimension').drop(op.get_bind(), checkfirst=True)
```

- [ ] **Step 7: Apply and verify the migration**

Run: `cd backend && alembic upgrade head`
Expected: no error; tables created. Sanity check round-trip:
Run: `cd backend && alembic downgrade -1 && alembic upgrade head`
Expected: both succeed (down/up are symmetric).

- [ ] **Step 8: Commit**

```bash
git add backend/app/models/parser_eval.py backend/app/models/__init__.py backend/alembic/versions backend/tests/models/test_parser_eval_models.py
git commit -m "feat(parser-eval): data model + migration"
```

---

## Task 4: Repository

**Files:**
- Create: `app/repositories/parser_eval_repository.py`
- Test: `tests/repositories/test_parser_eval_repository.py`

**Interfaces:**
- Consumes: models from Task 3.
- Produces `ParserEvalRepository(session)` with:
  - `create_case(project_id, name, doc_type, source_document_id, source_filename, user_id) -> ParserEvalCase`
  - `add_target(case_id, dimension, expected) -> ParserEvalTarget`
  - `get_case(case_id) -> ParserEvalCase | None` (targets eager-loaded)
  - `list_cases(project_id) -> list[ParserEvalCase]`
  - `create_run(project_id, name, parsers, case_ids, user_id) -> ParserEvalRun`
  - `get_run(run_id) -> ParserEvalRun | None`
  - `list_runs(project_id) -> list[ParserEvalRun]`
  - `set_run_status(run_id, status, error_message=None) -> None`
  - `upsert_result(run_id, case_id, parser, dimension, score, details, cost, latency_ms) -> None`
  - `get_results(run_id) -> list[ParserEvalResult]`

- [ ] **Step 1: Write the failing test** (uses the async DB session fixture used by other repo tests — imitate `tests/repositories/test_classification_run_repository.py` for fixture names)

```python
# tests/repositories/test_parser_eval_repository.py
import pytest
from app.models.parser_eval import ParserEvalDimension, ParserEvalRunStatus
from app.repositories.parser_eval_repository import ParserEvalRepository


@pytest.mark.asyncio
async def test_create_case_with_target_and_fetch(db_session, seed_project_user_source):
    project_id, user_id, source_id = seed_project_user_source
    repo = ParserEvalRepository(db_session)

    case = await repo.create_case(project_id, "acme_invoice", "invoice", source_id, "acme.pdf", user_id)
    await repo.add_target(case.id, ParserEvalDimension.text, {"pages": ["hello"]})

    fetched = await repo.get_case(case.id)
    assert fetched.name == "acme_invoice"
    assert len(fetched.targets) == 1
    assert fetched.targets[0].expected == {"pages": ["hello"]}


@pytest.mark.asyncio
async def test_run_and_result_upsert(db_session, seed_project_user_source):
    project_id, user_id, _ = seed_project_user_source
    repo = ParserEvalRepository(db_session)
    run = await repo.create_run(project_id, "run-1", ["docling", "simple"], [], user_id)

    case = await repo.create_case(project_id, "c", None, _seed_source_of(seed_project_user_source), None, user_id)
    await repo.upsert_result(run.id, case.id, "docling", ParserEvalDimension.text, 0.9, {}, {}, 120)
    await repo.upsert_result(run.id, case.id, "docling", ParserEvalDimension.text, 0.95, {}, {}, 130)  # same key

    results = await repo.get_results(run.id)
    assert len(results) == 1              # upsert replaced, not duplicated
    assert results[0].score == 0.95

    await repo.set_run_status(run.id, ParserEvalRunStatus.completed)
    assert (await repo.get_run(run.id)).status == ParserEvalRunStatus.completed
```

> Note for implementer: `seed_project_user_source` is a fixture you add to `tests/conftest.py` (or the nearest package conftest) that inserts a `Project`, `User`, and `SourceDocument` and returns their ids. Follow the existing seeding helpers in `tests/conftest.py`. `_seed_source_of` is illustrative — reuse the same `source_id` from the fixture; simplify the second test to reuse `source_id` if a helper isn't warranted.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/repositories/test_parser_eval_repository.py -v`
Expected: FAIL — `ModuleNotFoundError: app.repositories.parser_eval_repository`.

- [ ] **Step 3: Implement the repository** (mirror `extraction_eval_repository.py`)

```python
# app/repositories/parser_eval_repository.py
"""Repository for parser evaluation data access."""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.parser_eval import (
    ParserEvalCase, ParserEvalTarget, ParserEvalRun, ParserEvalResult,
    ParserEvalDimension, ParserEvalRunStatus,
)


class ParserEvalRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # --- cases / targets ---
    async def create_case(self, project_id: UUID, name: str, doc_type: str | None,
                          source_document_id: UUID, source_filename: str | None,
                          user_id: UUID) -> ParserEvalCase:
        case = ParserEvalCase(project_id=project_id, name=name, doc_type=doc_type,
                              source_document_id=source_document_id,
                              source_filename=source_filename, created_by=user_id)
        self.session.add(case)
        await self.session.commit()
        await self.session.refresh(case)
        return case

    async def add_target(self, case_id: UUID, dimension: ParserEvalDimension,
                         expected: dict) -> ParserEvalTarget:
        target = ParserEvalTarget(case_id=case_id, dimension=dimension, expected=expected)
        self.session.add(target)
        await self.session.commit()
        await self.session.refresh(target)
        return target

    async def get_case(self, case_id: UUID) -> ParserEvalCase | None:
        res = await self.session.execute(
            select(ParserEvalCase).options(selectinload(ParserEvalCase.targets))
            .where(ParserEvalCase.id == case_id))
        return res.scalar_one_or_none()

    async def list_cases(self, project_id: UUID) -> list[ParserEvalCase]:
        res = await self.session.execute(
            select(ParserEvalCase).options(selectinload(ParserEvalCase.targets))
            .where(ParserEvalCase.project_id == project_id)
            .order_by(ParserEvalCase.created_at.desc()))
        return list(res.scalars().all())

    # --- runs / results ---
    async def create_run(self, project_id: UUID, name: str, parsers: list[str],
                         case_ids: list[str], user_id: UUID) -> ParserEvalRun:
        run = ParserEvalRun(project_id=project_id, name=name, parsers=parsers,
                            case_ids=case_ids, created_by=user_id)
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

    async def upsert_result(self, run_id: UUID, case_id: UUID, parser: str,
                            dimension: ParserEvalDimension, score: float, details: dict,
                            cost: dict, latency_ms: int | None) -> None:
        res = await self.session.execute(
            select(ParserEvalResult).where(
                ParserEvalResult.run_id == run_id, ParserEvalResult.case_id == case_id,
                ParserEvalResult.parser == parser, ParserEvalResult.dimension == dimension))
        existing = res.scalar_one_or_none()
        if existing is None:
            self.session.add(ParserEvalResult(
                run_id=run_id, case_id=case_id, parser=parser, dimension=dimension,
                score=score, details=details, cost=cost, latency_ms=latency_ms))
        else:
            existing.score, existing.details = score, details
            existing.cost, existing.latency_ms = cost, latency_ms
        await self.session.commit()

    async def get_results(self, run_id: UUID) -> list[ParserEvalResult]:
        res = await self.session.execute(
            select(ParserEvalResult).where(ParserEvalResult.run_id == run_id)
            .order_by(ParserEvalResult.case_id, ParserEvalResult.parser))
        return list(res.scalars().all())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/repositories/test_parser_eval_repository.py -v`
Expected: PASS (adjust the `seed_project_user_source` fixture until green).

- [ ] **Step 5: Commit**

```bash
git add backend/app/repositories/parser_eval_repository.py backend/tests/repositories/test_parser_eval_repository.py backend/tests/conftest.py
git commit -m "feat(parser-eval): repository"
```

---

## Task 5: Capture (wraps ParsingService)

**Files:**
- Create: `app/services/parser_eval/capture.py`
- Test: `tests/services/parser_eval/test_capture.py`

**Interfaces:**
- Consumes: `ParsingService` (`ensure_source_document`, `parse_and_persist`), `app.ports.storage.StorageService`, `ParserKind`.
- Produces: `async capture(parsing_service, storage, *, source_document_id, storage_uri, filename, mime_type, parser, project_id) -> tuple[ParsedDocument | None, dict, int | None]` returning `(cdm, cost_dict, latency_ms)`. On parse failure returns `(None, {}, None)`.

Design note: `parse_and_persist` needs a local `file_path`. We fetch bytes via `storage.get(storage_uri)`, write them to a temp file, and pass that path. We call `ensure_source_document` to obtain the CDM `SourceDocument` the parser expects.

- [ ] **Step 1: Write the failing test** (unit test with fakes — no real parsers)

```python
# tests/services/parser_eval/test_capture.py
import pytest
from types import SimpleNamespace
from app.cdm.models import ParsedDocument
from app.services.parser_eval.capture import capture


class _FakeStorage:
    async def get(self, path): return b"%PDF-1.4 fake"
    async def save(self, content, rel): return rel


class _FakeParsing:
    async def ensure_source_document(self, *, bytes_, filename, mime_type):
        return SimpleNamespace(id="src-1", sha256="abc", filename=filename,
                               mime_type=mime_type, byte_size=len(bytes_), storage_uri="u")
    async def parse_and_persist(self, *, source, file_path, representation_kind, config, project_id, force=False):
        run = SimpleNamespace(cost={"usd": 0.0}, duration_ms=42,
                              input_tokens=None, output_tokens=None)
        doc = ParsedDocument(id="d", source_document_id="src-1", parse_run_id="r",
                             page_count=1, pages=[], blocks=[], full_text="hi")
        return run, doc


@pytest.mark.asyncio
async def test_capture_returns_cdm_and_metrics():
    cdm, cost, latency = await capture(
        _FakeParsing(), _FakeStorage(),
        source_document_id="src-1", storage_uri="u", filename="a.pdf",
        mime_type="application/pdf", parser="docling", project_id="p1")
    assert cdm.full_text == "hi"
    assert latency == 42
    assert cost == {"usd": 0.0}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/parser_eval/test_capture.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement capture**

```python
# app/services/parser_eval/capture.py
"""Capture a ParsedDocument for one parser by reusing ParsingService.

Cost/latency come from the returned ParseRun — no bespoke timing.
"""
from __future__ import annotations

import logging
import os
import tempfile
from typing import Any

from app.cdm.models import ParsedDocument
from app.services.parsing.errors import ParseFailedError

logger = logging.getLogger(__name__)

DEFAULT_REPRESENTATION_KIND = "extract_rich"


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
            config={"parser": parser}, project_id=project_id, force=False)
        return doc, dict(run.cost or {}), run.duration_ms
    except ParseFailedError as err:
        logger.warning("parser-eval capture failed parser=%s: %s", parser, err)
        return None, {}, None
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/parser_eval/test_capture.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/parser_eval/capture.py backend/tests/services/parser_eval/test_capture.py
git commit -m "feat(parser-eval): capture via ParsingService"
```

---

## Task 6: Engine (orchestrate a run)

**Files:**
- Create: `app/services/parser_eval/engine.py`
- Test: `tests/services/parser_eval/test_engine.py`

**Interfaces:**
- Consumes: `capture` (Task 5), `get_scorer` (Task 2), `ParserEvalRepository` (Task 4).
- Produces: `async run_evaluation(repo, parsing_service, storage, *, run_id, cases, parsers, project_id) -> None`. `cases` is a list of `ParserEvalCase` (with `.targets`). For each `(case, parser)` it captures once, then scores each asserted target and upserts a result. A parser that fails capture records a `score=0.0` result with `details={"capture_failed": True}` for each of the case's targets (so failure is visible, not missing). Sets run status running→completed, or failed on unexpected error.

- [ ] **Step 1: Write the failing test** (fakes for capture via monkeypatch and an in-memory repo spy)

```python
# tests/services/parser_eval/test_engine.py
import pytest
from types import SimpleNamespace
from app.cdm.models import ParsedDocument
from app.models.parser_eval import ParserEvalDimension, ParserEvalRunStatus
from app.services.parser_eval import engine as engine_mod


class _RepoSpy:
    def __init__(self): self.results = []; self.status = None
    async def upsert_result(self, run_id, case_id, parser, dimension, score, details, cost, latency_ms):
        self.results.append((parser, dimension, score))
    async def set_run_status(self, run_id, status, error_message=None):
        self.status = status


def _case():
    target = SimpleNamespace(dimension=ParserEvalDimension.text, expected={"pages": ["hi"]})
    return SimpleNamespace(id="c1", targets=[target])


@pytest.mark.asyncio
async def test_run_evaluation_scores_each_parser(monkeypatch):
    async def fake_capture(*args, **kwargs):
        doc = ParsedDocument(id="d", source_document_id="s", parse_run_id="r",
                             page_count=1, pages=[], blocks=[], full_text="hi")
        return doc, {"usd": 0.0}, 10
    monkeypatch.setattr(engine_mod, "capture", fake_capture)

    repo = _RepoSpy()
    await engine_mod.run_evaluation(
        repo, parsing_service=None, storage=None, run_id="run1",
        cases=[_case()], parsers=["docling", "simple"], project_id="p1",
        _case_source=lambda c: ("src", "uri", "a.pdf", "application/pdf"))
    assert repo.status == ParserEvalRunStatus.completed
    assert {r[0] for r in repo.results} == {"docling", "simple"}
    assert all(r[2] == 1.0 for r in repo.results)   # "hi" == "hi"


@pytest.mark.asyncio
async def test_capture_failure_records_zero(monkeypatch):
    async def fake_capture(*args, **kwargs):
        return None, {}, None
    monkeypatch.setattr(engine_mod, "capture", fake_capture)

    repo = _RepoSpy()
    await engine_mod.run_evaluation(
        repo, parsing_service=None, storage=None, run_id="run1",
        cases=[_case()], parsers=["docling"], project_id="p1",
        _case_source=lambda c: ("src", "uri", "a.pdf", "application/pdf"))
    assert repo.results == [("docling", ParserEvalDimension.text, 0.0)]
    assert repo.status == ParserEvalRunStatus.completed
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/parser_eval/test_engine.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement the engine**

```python
# app/services/parser_eval/engine.py
"""Orchestrate one parser-eval run: capture per parser, score each asserted target, persist."""
from __future__ import annotations

import logging
from typing import Any, Callable

from app.models.parser_eval import ParserEvalRunStatus
from app.services.parser_eval.capture import capture
from app.services.parser_eval.scorers import get_scorer

logger = logging.getLogger(__name__)


def _default_case_source(case: Any) -> tuple[str, str, str, str]:
    # Overridden in tests; the service passes a resolver that reads SourceDocument fields.
    raise NotImplementedError


async def run_evaluation(
    repo: Any,
    parsing_service: Any,
    storage: Any,
    *,
    run_id: Any,
    cases: list[Any],
    parsers: list[str],
    project_id: Any,
    _case_source: Callable[[Any], tuple[str, str, str, str]] = _default_case_source,
) -> None:
    await repo.set_run_status(run_id, ParserEvalRunStatus.running)
    try:
        for case in cases:
            source_document_id, storage_uri, filename, mime_type = _case_source(case)
            for parser in parsers:
                cdm, cost, latency = await capture(
                    parsing_service, storage,
                    source_document_id=source_document_id, storage_uri=storage_uri,
                    filename=filename, mime_type=mime_type, parser=parser,
                    project_id=project_id)
                for target in case.targets:            # only asserted dimensions
                    if cdm is None:
                        score, details = 0.0, {"capture_failed": True}
                    else:
                        score, details = get_scorer(target.dimension.value)(cdm, target.expected)
                    await repo.upsert_result(run_id, case.id, parser, target.dimension,
                                             score, details, cost, latency)
        await repo.set_run_status(run_id, ParserEvalRunStatus.completed)
    except Exception as err:                            # noqa: BLE001 — record and surface
        logger.exception("parser-eval run %s failed", run_id)
        await repo.set_run_status(run_id, ParserEvalRunStatus.failed, error_message=str(err))
        raise
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/parser_eval/test_engine.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/parser_eval/engine.py backend/tests/services/parser_eval/test_engine.py
git commit -m "feat(parser-eval): run orchestration engine"
```

---

## Task 7: Schemas

**Files:**
- Create: `app/schemas/parser_eval.py`
- Test: `tests/schemas/test_parser_eval_schema.py`

**Interfaces:**
- Produces Pydantic v2 models: `TargetInput{dimension: str, expected: dict}`, `CaseCreate{name, doc_type: str|None, source_document_id: UUID, targets: list[TargetInput]}`, `CaseResponse`, `RunCreate{name: str|None, case_ids: list[UUID], parsers: list[str]}`, `RunResponse{id, name, status, parsers, created_at}`, `ResultResponse{case_id, parser, dimension, score, details, cost, latency_ms}`. Validate `text` targets have `expected["pages"]: list[str]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/schemas/test_parser_eval_schema.py
import pytest
from uuid import uuid4
from pydantic import ValidationError
from app.schemas.parser_eval import CaseCreate, TargetInput


def test_valid_text_target():
    c = CaseCreate(name="c", doc_type="invoice", source_document_id=uuid4(),
                   targets=[TargetInput(dimension="text", expected={"pages": ["a", "b"]})])
    assert c.targets[0].expected["pages"] == ["a", "b"]


def test_text_target_requires_pages_list():
    with pytest.raises(ValidationError):
        TargetInput(dimension="text", expected={"wrong": 1})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/schemas/test_parser_eval_schema.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement schemas**

```python
# app/schemas/parser_eval.py
"""Pydantic schemas for the parser-eval API."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator


class TargetInput(BaseModel):
    dimension: str
    expected: dict

    @model_validator(mode="after")
    def _validate_expected(self):
        if self.dimension == "text":
            pages = self.expected.get("pages")
            if not isinstance(pages, list) or not all(isinstance(p, str) for p in pages):
                raise ValueError("text target requires expected.pages: list[str]")
        return self


class CaseCreate(BaseModel):
    name: str
    doc_type: str | None = None
    source_document_id: UUID
    targets: list[TargetInput]


class CaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    doc_type: str | None
    source_document_id: UUID
    source_filename: str | None
    created_at: datetime


class RunCreate(BaseModel):
    name: str | None = None
    case_ids: list[UUID]
    parsers: list[str]


class RunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    status: str
    parsers: list[str]
    error_message: str | None = None
    created_at: datetime


class ResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    case_id: UUID
    parser: str
    dimension: str
    score: float
    details: dict | None
    cost: dict | None
    latency_ms: int | None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/schemas/test_parser_eval_schema.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/parser_eval.py backend/tests/schemas/test_parser_eval_schema.py
git commit -m "feat(parser-eval): API schemas"
```

---

## Task 8: Service (CRUD + execute_run)

**Files:**
- Create: `app/services/parser_eval/service.py`
- Test: `tests/services/parser_eval/test_service.py`

**Interfaces:**
- Consumes: `ParserEvalRepository`, `SourceDocumentRepository` (to resolve a case's source `storage_uri`/`filename`/`mime_type`), `ParsingService`, `StorageService`, `run_evaluation`.
- Produces `ParserEvalService(repo, source_doc_repo, parsing_service, storage)` with:
  - `create_case(project_id, user_id, data: CaseCreate) -> CaseResponse` (persists case + targets; copies `source_filename` from the source document)
  - `list_cases(project_id) -> list[CaseResponse]`
  - `create_run(project_id, user_id, data: RunCreate) -> RunResponse`
  - `execute_run(run_id) -> None` (loads run's cases, builds the `_case_source` resolver from `SourceDocument`, calls `run_evaluation`)
  - `get_run / list_runs / get_results` passthroughs, raising `NotFoundError` when missing.

- [ ] **Step 1: Write the failing test** (service-level, DB-backed; monkeypatch `engine.capture` so no real parser runs)

```python
# tests/services/parser_eval/test_service.py
import pytest
from app.cdm.models import ParsedDocument
from app.schemas.parser_eval import CaseCreate, TargetInput, RunCreate
from app.services.parser_eval import engine as engine_mod
from app.services.parser_eval.service import ParserEvalService
# ... construct service from db_session + real repos + fake parsing/storage (see capture test fakes)


@pytest.mark.asyncio
async def test_create_case_then_run_produces_results(db_session, seed_project_user_source, monkeypatch):
    project_id, user_id, source_id = seed_project_user_source

    async def fake_capture(*a, **k):
        doc = ParsedDocument(id="d", source_document_id="s", parse_run_id="r",
                             page_count=1, pages=[], blocks=[], full_text="hi")
        return doc, {"usd": 0.0}, 5
    monkeypatch.setattr(engine_mod, "capture", fake_capture)

    service = _build_service(db_session)   # helper wiring real repos + fakes
    case = await service.create_case(project_id, user_id, CaseCreate(
        name="c", source_document_id=source_id,
        targets=[TargetInput(dimension="text", expected={"pages": ["hi"]})]))
    run = await service.create_run(project_id, user_id, RunCreate(
        name="r1", case_ids=[case.id], parsers=["docling"]))
    await service.execute_run(run.id)

    results = await service.get_results(run.id)
    assert len(results) == 1
    assert results[0].score == 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/parser_eval/test_service.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement the service**

```python
# app/services/parser_eval/service.py
"""Service orchestrating parser-eval CRUD and run execution."""
from __future__ import annotations

from uuid import UUID

from app.models.parser_eval import ParserEvalDimension
from app.repositories.parser_eval_repository import ParserEvalRepository
from app.repositories.source_document_repository import SourceDocumentRepository
from app.schemas.parser_eval import (
    CaseCreate, CaseResponse, RunCreate, RunResponse, ResultResponse,
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

    async def create_case(self, project_id: UUID, user_id: UUID, data: CaseCreate) -> CaseResponse:
        source = await self.source_doc_repo.get(data.source_document_id)
        if source is None:
            raise NotFoundError(f"Source document {data.source_document_id} not found")
        case = await self.repo.create_case(project_id, data.name, data.doc_type,
                                           data.source_document_id, source.filename, user_id)
        for t in data.targets:
            await self.repo.add_target(case.id, ParserEvalDimension(t.dimension), t.expected)
        return CaseResponse.model_validate(case)

    async def list_cases(self, project_id: UUID) -> list[CaseResponse]:
        return [CaseResponse.model_validate(c) for c in await self.repo.list_cases(project_id)]

    async def create_run(self, project_id: UUID, user_id: UUID, data: RunCreate) -> RunResponse:
        name = data.name or "Parser eval run"
        run = await self.repo.create_run(
            project_id, name, data.parsers, [str(cid) for cid in data.case_ids], user_id)
        return RunResponse.model_validate(run)

    async def execute_run(self, run_id: UUID) -> None:
        run = await self.repo.get_run(run_id)
        if run is None:
            raise NotFoundError(f"Parser eval run {run_id} not found")
        # Load only the cases selected for this run (persisted in run.case_ids).
        selected = {str(cid) for cid in (run.case_ids or [])}
        cases = [c for c in await self.repo.list_cases(run.project_id) if str(c.id) in selected]

        # Resolve each case's source document fields for capture, once.
        source_cache: dict[UUID, object] = {}

        async def _resolve(case):
            src = source_cache.get(case.source_document_id)
            if src is None:
                src = await self.source_doc_repo.get(case.source_document_id)
                source_cache[case.source_document_id] = src
            return (str(case.source_document_id), src.storage_uri, src.filename, src.mime_type)

        # run_evaluation expects a sync resolver; pre-resolve into a dict.
        resolved = {c.id: await _resolve(c) for c in cases}
        await run_evaluation(
            self.repo, self.parsing_service, self.storage,
            run_id=run_id, cases=cases, parsers=list(run.parsers),
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

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/parser_eval/test_service.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/parser_eval/service.py backend/tests/services/parser_eval/test_service.py
git commit -m "feat(parser-eval): service (CRUD + execute_run)"
```

---

## Task 9: Router + registration

**Files:**
- Create: `app/routers/parser_eval.py`
- Modify: `app/main.py` (include router)
- Test: `tests/routers/test_parser_eval_router.py`

**Interfaces:**
- Consumes: `ParserEvalService`, schemas, `get_current_active_user`, `get_db`, `get_parsing_service`, `get_storage_service`, `ProjectRepository` for access checks.
- Produces routes (project-scoped, mirroring `extraction_eval.py`):
  - `POST /api/projects/{project_id}/parser-eval/cases` → `CaseResponse`
  - `GET  /api/projects/{project_id}/parser-eval/cases` → `list[CaseResponse]`
  - `POST /api/projects/{project_id}/parser-eval/runs` (BackgroundTasks → `execute_run`) → `RunResponse` (202)
  - `GET  /api/projects/{project_id}/parser-eval/runs` → `list[RunResponse]`
  - `GET  /api/projects/{project_id}/parser-eval/runs/{run_id}/results` → `list[ResultResponse]`

- [ ] **Step 1: Write the failing test** (imitate `tests/routers/test_extraction_router.py` client + auth fixtures)

```python
# tests/routers/test_parser_eval_router.py
import pytest


@pytest.mark.asyncio
async def test_create_case_and_run_flow(async_client, auth_headers, seed_project_source, monkeypatch):
    from app.services.parser_eval import engine as engine_mod
    from app.cdm.models import ParsedDocument

    async def fake_capture(*a, **k):
        return ParsedDocument(id="d", source_document_id="s", parse_run_id="r",
                              page_count=1, pages=[], blocks=[], full_text="hi"), {"usd": 0}, 3
    monkeypatch.setattr(engine_mod, "capture", fake_capture)

    project_id, source_id = seed_project_source
    r = await async_client.post(
        f"/api/projects/{project_id}/parser-eval/cases", headers=auth_headers,
        json={"name": "c", "source_document_id": str(source_id),
              "targets": [{"dimension": "text", "expected": {"pages": ["hi"]}}]})
    assert r.status_code == 200
    case_id = r.json()["id"]

    r = await async_client.post(
        f"/api/projects/{project_id}/parser-eval/runs", headers=auth_headers,
        json={"name": "run", "case_ids": [case_id], "parsers": ["docling"]})
    assert r.status_code in (200, 202)
    run_id = r.json()["id"]

    r = await async_client.get(
        f"/api/projects/{project_id}/parser-eval/runs/{run_id}/results", headers=auth_headers)
    assert r.status_code == 200
```

> Note: with `BackgroundTasks`, the run executes after the response in the test client. If results aren't ready synchronously, either call `service.execute_run` inline in the test or assert on run status instead. Mirror whatever pattern `test_extraction_router.py` uses for background eval runs.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/routers/test_parser_eval_router.py -v`
Expected: FAIL — 404 (route not registered).

- [ ] **Step 3: Implement the router**

```python
# app/routers/parser_eval.py
"""Parser Evaluation API router."""
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_active_user
from app.dependencies.documents import get_parsing_service, get_storage_service
from app.models import User
from app.repositories.parser_eval_repository import ParserEvalRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.source_document_repository import SourceDocumentRepository
from app.schemas.parser_eval import (
    CaseCreate, CaseResponse, RunCreate, RunResponse, ResultResponse,
)
from app.services.exceptions import NotFoundError
from app.services.parser_eval.service import ParserEvalService

router = APIRouter(tags=["parser_eval"])


def _service(db: AsyncSession) -> ParserEvalService:
    return ParserEvalService(
        repo=ParserEvalRepository(db),
        source_doc_repo=SourceDocumentRepository(db),
        parsing_service=get_parsing_service(db),
        storage=get_storage_service(),
    )


def get_service(db: AsyncSession = Depends(get_db)) -> ParserEvalService:
    return _service(db)


async def _verify_project(project_id: UUID, user: User, db: AsyncSession) -> None:
    project = await ProjectRepository(db).get_by_id(project_id, user.id)
    if not project:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Project {project_id} not found")


async def _execute_run_bg(db_maker, run_id: UUID) -> None:
    async with db_maker() as db:               # fresh session for the background task
        await _service(db).execute_run(run_id)


@router.post("/projects/{project_id}/parser-eval/cases", response_model=CaseResponse)
async def create_case(project_id: UUID, body: CaseCreate,
                      user: User = Depends(get_current_active_user),
                      db: AsyncSession = Depends(get_db)):
    await _verify_project(project_id, user, db)
    try:
        return await get_service(db).create_case(project_id, user.id, body)
    except NotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))


@router.get("/projects/{project_id}/parser-eval/cases", response_model=list[CaseResponse])
async def list_cases(project_id: UUID, user: User = Depends(get_current_active_user),
                     db: AsyncSession = Depends(get_db)):
    await _verify_project(project_id, user, db)
    return await get_service(db).list_cases(project_id)


@router.post("/projects/{project_id}/parser-eval/runs", response_model=RunResponse,
             status_code=status.HTTP_202_ACCEPTED)
async def create_run(project_id: UUID, body: RunCreate, background: BackgroundTasks,
                     user: User = Depends(get_current_active_user),
                     db: AsyncSession = Depends(get_db)):
    await _verify_project(project_id, user, db)
    run = await get_service(db).create_run(project_id, user.id, body)
    from app.database import async_session_maker      # background task uses its own session
    background.add_task(_execute_run_bg, async_session_maker, run.id)
    return run


@router.get("/projects/{project_id}/parser-eval/runs", response_model=list[RunResponse])
async def list_runs(project_id: UUID, user: User = Depends(get_current_active_user),
                    db: AsyncSession = Depends(get_db)):
    await _verify_project(project_id, user, db)
    return await get_service(db).list_runs(project_id)


@router.get("/projects/{project_id}/parser-eval/runs/{run_id}/results",
            response_model=list[ResultResponse])
async def get_results(project_id: UUID, run_id: UUID,
                      user: User = Depends(get_current_active_user),
                      db: AsyncSession = Depends(get_db)):
    await _verify_project(project_id, user, db)
    try:
        return await get_service(db).get_results(run_id)
    except NotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))
```

> Confirm the exact background-session helper name (`async_session_maker`) and the router prefix used by peers in `app/main.py` (extraction_eval is included with a prefix like `/api`). Match that prefix so paths become `/api/projects/{id}/parser-eval/...`.

- [ ] **Step 4: Register the router in `app/main.py`**

Mirror the existing `extraction_eval` include line, e.g.:
```python
from app.routers import parser_eval
app.include_router(parser_eval.router, prefix="/api")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/routers/test_parser_eval_router.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/parser_eval.py backend/app/main.py backend/tests/routers/test_parser_eval_router.py
git commit -m "feat(parser-eval): API router + registration"
```

---

## Task 10: Full-suite regression check

- [ ] **Step 1: Run the whole backend suite**

Run: `cd backend && uv run python -m pytest -o "addopts="`
Expected: no new failures introduced by this feature. Fix any import/registration fallout (e.g. `app/models/__init__.py` export, migration head).

- [ ] **Step 2: Commit any fixes**

```bash
git add -A && git commit -m "test(parser-eval): green full backend suite"
```

---

## Self-Review (completed against the spec)

- **Spec coverage:** data model (Task 3) ✔; per-dimension asserted truth + result key `(run,case,parser,dimension)` (Tasks 3–4, unique constraint) ✔; capture reuses `ParsingService`, cost/latency from `ParseRun` (Task 5) ✔; text scorer page-segmented with omission/hallucination (Task 1) ✔; scorer registry seam (Task 2) ✔; project-scoped API mirroring `extraction_eval` (Task 9) ✔.
- **Deferred to Plan 2 (frontend):** case/truth authoring UI, run trigger, comparison table (`ComparisonTable`/`ScorePill`). Backend endpoints here are the contract that plan consumes.
- **Run→case selection:** persisted via a `case_ids` JSON column on `ParserEvalRun` (Task 3), filtered in `execute_run` (Task 8) — no "run all project cases" trap.
- **Confirm-at-implementation (environment specifics, not logic gaps):** the background DB session-maker symbol (`async_session_maker`) and the router prefix peers use in `app/main.py`; the `seed_project_user_source` test fixture wiring. Each is a name to match against the existing codebase, shown with its expected shape.
- **Not in this slice (seams):** table/reading-order/roles scorers, profiles/weighting/selection, caching/capture-score split, baselines/regression, LLM-judge. All additive via the registry (Task 2) and dimension-typed `expected` payloads.
