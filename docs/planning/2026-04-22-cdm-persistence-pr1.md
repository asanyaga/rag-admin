# CDM Persistence PR 1 — Schema + Models + Repositories

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the durable persistence layer for CDM — three new tables (`source_documents`, `parse_runs`, `parsed_documents`), their ORM models, and async repositories — with no production caller. This is PR 1 of three (see [docs/specs/cdm_persistence.md](../specs/cdm_persistence.md) §7).

**Architecture:** Alembic migration creates the three tables plus a nullable `documents.source_document_id` FK. SQLAlchemy 2.0 async ORM models mirror the schema. Repositories expose async CRUD + a same-project reuse lookup. Services / runner wiring is **out of scope** — it lives in PR 2.

**Tech Stack:** Python 3.12, SQLAlchemy 2.0 (async), Alembic, Postgres 16 (JSONB + GIN), pytest-asyncio, `pytest -o "addopts="` per repo convention.

**Spec:** [docs/specs/cdm_persistence.md](../specs/cdm_persistence.md)

---

## File Structure

**Create:**
- `backend/alembic/versions/<revision>_add_cdm_persistence_tables.py` — migration
- `backend/app/models/source_document.py` — `SourceDocumentORM`
- `backend/app/models/parse_run.py` — `ParseRunORM` + column-typed enums as strings
- `backend/app/models/parsed_document.py` — `ParsedDocumentORM`
- `backend/app/repositories/source_document_repository.py`
- `backend/app/repositories/parse_run_repository.py`
- `backend/app/repositories/parsed_document_repository.py`
- `backend/tests/repositories/test_source_document_repository.py`
- `backend/tests/repositories/test_parse_run_repository.py`
- `backend/tests/repositories/test_parsed_document_repository.py`
- `backend/tests/repositories/conftest_cdm.py` — shared fixtures for these three test files

**Modify:**
- `backend/app/models/document.py` — add `source_document_id` column + relationship
- `backend/app/models/__init__.py` — export new models

**Why three separate repo modules:** one repository per aggregate root. `SourceDocumentRepository` operates on bytes identity; `ParseRunRepository` handles execution rows (the hot path for reuse lookups); `ParsedDocumentRepository` handles the content blob. Each is small, focused, and independently testable — matches the existing repository pattern in `backend/app/repositories/`.

---

## Preflight

Confirm the environment before the first task.

- [ ] **Preflight 1: Create and check out a feature branch**

```bash
git -C /c/Repos/rag-admin checkout -b feat/cdm-persistence-schema main
git -C /c/Repos/rag-admin status
```

Expected: `On branch feat/cdm-persistence-schema`, working tree clean.

- [ ] **Preflight 2: Confirm current alembic head revision**

```bash
uv run --directory /c/Repos/rag-admin/backend alembic heads
```

Expected: exactly one head printed. Record the revision ID — it becomes `down_revision` in Task 1.

- [ ] **Preflight 3: Confirm baseline test suite passes**

```bash
uv run --directory /c/Repos/rag-admin/backend python -m pytest -o "addopts=" -q
```

Expected: suite passes. If not, stop and investigate — PR 1 must not land on a red baseline.

- [ ] **Preflight 4: Copy real LlamaParse fixtures into the backend test tree**

Real LlamaParse outputs from provider research live in a sibling repo at `C:\Repos\doc_processing_research\demos\llamaparse_outputs`. Copy a curated subset into the backend test tree so Task 10 (and PR 2's service tests later) can assert against real provider payloads rather than hand-rolled synthetic shapes.

```bash
mkdir -p /c/Repos/rag-admin/backend/tests/fixtures/llamaparse/annual_pp1-5
mkdir -p /c/Repos/rag-admin/backend/tests/fixtures/llamaparse/receipt
cp /c/Repos/doc_processing_research/demos/llamaparse_outputs/annual_pp1-5_items.json \
   /c/Repos/rag-admin/backend/tests/fixtures/llamaparse/annual_pp1-5/items.json
cp /c/Repos/doc_processing_research/demos/llamaparse_outputs/annual_pp1-5_markdown.md \
   /c/Repos/rag-admin/backend/tests/fixtures/llamaparse/annual_pp1-5/markdown.md
cp /c/Repos/doc_processing_research/demos/llamaparse_outputs/receipt_items.json \
   /c/Repos/rag-admin/backend/tests/fixtures/llamaparse/receipt/items.json
cp /c/Repos/doc_processing_research/demos/llamaparse_outputs/receipt_markdown.md \
   /c/Repos/rag-admin/backend/tests/fixtures/llamaparse/receipt/markdown.md
cp /c/Repos/doc_processing_research/demos/llamaparse_outputs/batch_summary.json \
   /c/Repos/rag-admin/backend/tests/fixtures/llamaparse/batch_summary.json
ls -la /c/Repos/rag-admin/backend/tests/fixtures/llamaparse/annual_pp1-5/
```

Expected: the two files (`items.json`, `markdown.md`) are listed with non-zero size (~65KB / ~5KB).

Commit the fixtures so later tasks have a stable base:

```bash
git -C /c/Repos/rag-admin add backend/tests/fixtures/llamaparse/
git -C /c/Repos/rag-admin commit -m "test(cdm): add real LlamaParse output fixtures for round-trip + mock use"
```

---

## Task 1: Alembic migration — create CDM tables + `documents` FK column

**Files:**
- Create: `backend/alembic/versions/<revision>_add_cdm_persistence_tables.py`

Use `uv run --directory /c/Repos/rag-admin/backend alembic revision -m "add cdm persistence tables"` to mint the revision file with the correct `down_revision`, then replace its body with the content below.

- [ ] **Step 1: Generate the revision skeleton**

```bash
uv run --directory /c/Repos/rag-admin/backend alembic revision -m "add cdm persistence tables"
```

Note the generated filename — it contains the new revision ID.

- [ ] **Step 2: Write the migration body**

Replace the generated file's contents with:

```python
"""add cdm persistence tables

Revision ID: <generated>
Revises: <previous head from Preflight 2>
Create Date: 2026-04-22

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "<generated>"
down_revision: Union[str, None] = "<previous head>"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "source_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("sha256", sa.CHAR(64), nullable=False, unique=True),
        sa.Column("filename", sa.Text(), nullable=True),
        sa.Column("mime_type", sa.Text(), nullable=True),
        sa.Column("byte_size", sa.BigInteger(), nullable=True),
        sa.Column("storage_uri", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_source_documents_sha256", "source_documents", ["sha256"], unique=True)

    op.create_table(
        "parse_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source_document_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("source_documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parser", sa.Text(), nullable=False),
        sa.Column("parser_version", sa.Text(), nullable=True),
        sa.Column("representation_kind", sa.Text(), nullable=False),
        sa.Column("config", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("config_hash", sa.CHAR(64), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("cost", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("warnings", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("failed_pages", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("provider_refs", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index(
        "ux_parse_runs_content_config",
        "parse_runs",
        ["source_document_id", "representation_kind", "config_hash"],
        unique=True,
    )
    op.create_index("ix_parse_runs_status", "parse_runs", ["status"])
    op.create_index("ix_parse_runs_source_document_id", "parse_runs", ["source_document_id"])

    op.create_table(
        "parsed_documents",
        sa.Column("parse_run_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("parse_runs.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("source_document_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("source_documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("full_text", sa.Text(), nullable=True),
        sa.Column("full_markdown", sa.Text(), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column("block_count", sa.Integer(), nullable=False),
        sa.Column("content", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index(
        "ix_parsed_documents_source_document_id",
        "parsed_documents",
        ["source_document_id"],
    )

    op.add_column(
        "documents",
        sa.Column("source_document_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_documents_source_document_id",
        "documents",
        "source_documents",
        ["source_document_id"],
        ["id"],
    )
    op.create_index("ix_documents_source_document_id", "documents", ["source_document_id"])


def downgrade() -> None:
    op.drop_index("ix_documents_source_document_id", table_name="documents")
    op.drop_constraint("fk_documents_source_document_id", "documents", type_="foreignkey")
    op.drop_column("documents", "source_document_id")

    op.drop_index("ix_parsed_documents_source_document_id", table_name="parsed_documents")
    op.drop_table("parsed_documents")

    op.drop_index("ix_parse_runs_source_document_id", table_name="parse_runs")
    op.drop_index("ix_parse_runs_status", table_name="parse_runs")
    op.drop_index("ux_parse_runs_content_config", table_name="parse_runs")
    op.drop_table("parse_runs")

    op.drop_index("ix_source_documents_sha256", table_name="source_documents")
    op.drop_table("source_documents")
```

Replace `<generated>` and `<previous head>` with the IDs from Preflight 2 / Step 1.

- [ ] **Step 3: Apply the migration**

```bash
uv run --directory /c/Repos/rag-admin/backend alembic upgrade head
```

Expected: no errors. Command prints `Running upgrade <prev> -> <new>`.

- [ ] **Step 4: Verify `downgrade` is reversible**

```bash
uv run --directory /c/Repos/rag-admin/backend alembic downgrade -1
uv run --directory /c/Repos/rag-admin/backend alembic upgrade head
```

Expected: both commands succeed. Tables exist after final `upgrade`.

- [ ] **Step 5: Commit**

```bash
git -C /c/Repos/rag-admin add backend/alembic/versions/*_add_cdm_persistence_tables.py
git -C /c/Repos/rag-admin commit -m "feat(cdm): alembic migration for source_documents, parse_runs, parsed_documents"
```

---

## Task 2: `SourceDocumentORM` model

**Files:**
- Create: `backend/app/models/source_document.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/repositories/conftest_cdm.py` (bootstrapped here, reused in later tasks)

- [ ] **Step 1: Write the failing test (minimal round-trip)**

Create `backend/tests/models/test_source_document_orm.py`:

```python
"""Round-trip sanity test for SourceDocumentORM."""
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.source_document import SourceDocumentORM


@pytest.mark.asyncio
async def test_source_document_round_trip(test_db: AsyncSession):
    row = SourceDocumentORM(
        id=uuid4(),
        sha256="a" * 64,
        filename="test.pdf",
        mime_type="application/pdf",
        byte_size=1234,
        storage_uri="local://test.pdf",
    )
    test_db.add(row)
    await test_db.commit()

    result = await test_db.execute(
        select(SourceDocumentORM).where(SourceDocumentORM.sha256 == "a" * 64)
    )
    fetched = result.scalar_one()
    assert fetched.filename == "test.pdf"
    assert fetched.byte_size == 1234
    assert fetched.storage_uri == "local://test.pdf"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run --directory /c/Repos/rag-admin/backend python -m pytest tests/models/test_source_document_orm.py -v -o "addopts="
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.models.source_document'`.

- [ ] **Step 3: Write the model**

Create `backend/app/models/source_document.py`:

```python
"""ORM model for SourceDocument — content-addressed bytes layer."""
from datetime import datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import BigInteger, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SourceDocumentORM(Base):
    __tablename__ = "source_documents"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=sa.text("gen_random_uuid()"),
    )
    sha256: Mapped[str] = mapped_column(sa.CHAR(64), nullable=False, unique=True)
    filename: Mapped[str | None] = mapped_column(Text, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    byte_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    storage_uri: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        server_default=sa.text("NOW()"),
    )
```

- [ ] **Step 4: Register in `app.models`**

Edit `backend/app/models/__init__.py`. Add this line next to other document model imports:

```python
from app.models.source_document import SourceDocumentORM
```

And add `"SourceDocumentORM"` to the `__all__` list.

- [ ] **Step 5: Run test to verify it passes**

```bash
uv run --directory /c/Repos/rag-admin/backend python -m pytest tests/models/test_source_document_orm.py -v -o "addopts="
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git -C /c/Repos/rag-admin add backend/app/models/source_document.py backend/app/models/__init__.py backend/tests/models/test_source_document_orm.py
git -C /c/Repos/rag-admin commit -m "feat(cdm): SourceDocumentORM model + round-trip test"
```

---

## Task 3: `ParseRunORM` model

**Files:**
- Create: `backend/app/models/parse_run.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/models/test_parse_run_orm.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/models/test_parse_run_orm.py`:

```python
"""Round-trip sanity test for ParseRunORM."""
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.parse_run import ParseRunORM
from app.models.source_document import SourceDocumentORM


@pytest.mark.asyncio
async def test_parse_run_round_trip(test_db: AsyncSession):
    src = SourceDocumentORM(
        id=uuid4(), sha256="b" * 64, storage_uri="local://b.pdf",
    )
    test_db.add(src)
    await test_db.commit()

    run = ParseRunORM(
        id=uuid4(),
        source_document_id=src.id,
        parser="llamaparse",
        representation_kind="vector_light",
        config={"tier": "agentic"},
        config_hash="c" * 64,
        status="succeeded",
        started_at=datetime.now(timezone.utc),
    )
    test_db.add(run)
    await test_db.commit()

    fetched = (await test_db.execute(
        select(ParseRunORM).where(ParseRunORM.id == run.id)
    )).scalar_one()
    assert fetched.parser == "llamaparse"
    assert fetched.config == {"tier": "agentic"}
    assert fetched.warnings == []
    assert fetched.provider_refs == {}


@pytest.mark.asyncio
async def test_parse_run_unique_content_config(test_db: AsyncSession):
    """Unique index on (source_document_id, representation_kind, config_hash) enforced."""
    from sqlalchemy.exc import IntegrityError

    src = SourceDocumentORM(id=uuid4(), sha256="d" * 64, storage_uri="local://d.pdf")
    test_db.add(src)
    await test_db.commit()

    def make_run(**kw):
        return ParseRunORM(
            id=uuid4(),
            source_document_id=src.id,
            parser="llamaparse",
            representation_kind="vector_light",
            config={}, config_hash="e" * 64,
            status="succeeded",
            started_at=datetime.now(timezone.utc),
            **kw,
        )

    test_db.add(make_run())
    await test_db.commit()
    test_db.add(make_run())
    with pytest.raises(IntegrityError):
        await test_db.commit()
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run --directory /c/Repos/rag-admin/backend python -m pytest tests/models/test_parse_run_orm.py -v -o "addopts="
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the model**

Create `backend/app/models/parse_run.py`:

```python
"""ORM model for ParseRun — execution + provenance layer."""
from datetime import datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ParseRunORM(Base):
    __tablename__ = "parse_runs"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4,
        server_default=sa.text("gen_random_uuid()"),
    )
    source_document_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("source_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    parser: Mapped[str] = mapped_column(Text, nullable=False)
    parser_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    representation_kind: Mapped[str] = mapped_column(Text, nullable=False)
    config: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb")
    )
    config_hash: Mapped[str] = mapped_column(sa.CHAR(64), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb")
    )
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    warnings: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default=sa.text("'[]'::jsonb")
    )
    failed_pages: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default=sa.text("'[]'::jsonb")
    )
    provider_refs: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=sa.text("'{}'::jsonb")
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=datetime.utcnow, server_default=sa.text("NOW()"),
    )

    __table_args__ = (
        sa.UniqueConstraint(
            "source_document_id", "representation_kind", "config_hash",
            name="ux_parse_runs_content_config",
        ),
        sa.Index("ix_parse_runs_status", "status"),
        sa.Index("ix_parse_runs_source_document_id", "source_document_id"),
    )
```

- [ ] **Step 4: Register in `app.models`**

Edit `backend/app/models/__init__.py`:

```python
from app.models.parse_run import ParseRunORM
```

Add `"ParseRunORM"` to `__all__`.

- [ ] **Step 5: Run tests**

```bash
uv run --directory /c/Repos/rag-admin/backend python -m pytest tests/models/test_parse_run_orm.py -v -o "addopts="
```

Expected: both tests PASS.

- [ ] **Step 6: Commit**

```bash
git -C /c/Repos/rag-admin add backend/app/models/parse_run.py backend/app/models/__init__.py backend/tests/models/test_parse_run_orm.py
git -C /c/Repos/rag-admin commit -m "feat(cdm): ParseRunORM model with unique (source, representation, config_hash) index"
```

---

## Task 4: `ParsedDocumentORM` model

**Files:**
- Create: `backend/app/models/parsed_document.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/models/test_parsed_document_orm.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/models/test_parsed_document_orm.py`:

```python
"""Round-trip sanity test for ParsedDocumentORM."""
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.parse_run import ParseRunORM
from app.models.parsed_document import ParsedDocumentORM
from app.models.source_document import SourceDocumentORM


@pytest.mark.asyncio
async def test_parsed_document_round_trip(test_db: AsyncSession):
    src = SourceDocumentORM(id=uuid4(), sha256="f" * 64, storage_uri="local://f.pdf")
    test_db.add(src)
    await test_db.commit()

    run = ParseRunORM(
        id=uuid4(), source_document_id=src.id,
        parser="llamaparse", representation_kind="vector_light",
        config_hash="0" * 64, status="succeeded",
        started_at=datetime.now(timezone.utc),
    )
    test_db.add(run)
    await test_db.commit()

    content = {"pages": [{"index": 0, "block_ids": []}], "full_text": "hello"}
    pdoc = ParsedDocumentORM(
        parse_run_id=run.id,
        source_document_id=src.id,
        full_text="hello",
        full_markdown="# hello",
        page_count=1,
        block_count=0,
        content=content,
    )
    test_db.add(pdoc)
    await test_db.commit()

    fetched = (await test_db.execute(
        select(ParsedDocumentORM).where(ParsedDocumentORM.parse_run_id == run.id)
    )).scalar_one()
    assert fetched.full_text == "hello"
    assert fetched.page_count == 1
    assert fetched.content == content
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run --directory /c/Repos/rag-admin/backend python -m pytest tests/models/test_parsed_document_orm.py -v -o "addopts="
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the model**

Create `backend/app/models/parsed_document.py`:

```python
"""ORM model for ParsedDocument — content blob layer."""
from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ParsedDocumentORM(Base):
    __tablename__ = "parsed_documents"

    parse_run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("parse_runs.id", ondelete="CASCADE"),
        primary_key=True,
    )
    source_document_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("source_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    full_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    full_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False)
    block_count: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=datetime.utcnow, server_default=sa.text("NOW()"),
    )

    __table_args__ = (
        sa.Index("ix_parsed_documents_source_document_id", "source_document_id"),
    )
```

- [ ] **Step 4: Register**

Edit `backend/app/models/__init__.py`:

```python
from app.models.parsed_document import ParsedDocumentORM
```

Add `"ParsedDocumentORM"` to `__all__`.

- [ ] **Step 5: Run tests**

```bash
uv run --directory /c/Repos/rag-admin/backend python -m pytest tests/models/test_parsed_document_orm.py -v -o "addopts="
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git -C /c/Repos/rag-admin add backend/app/models/parsed_document.py backend/app/models/__init__.py backend/tests/models/test_parsed_document_orm.py
git -C /c/Repos/rag-admin commit -m "feat(cdm): ParsedDocumentORM model with JSONB content"
```

---

## Task 5: Extend `Document` with `source_document_id` FK + relationship

**Files:**
- Modify: `backend/app/models/document.py`
- Test: `backend/tests/models/test_document_source_fk.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/models/test_document_source_fk.py`:

```python
"""Document.source_document_id FK + relationship test."""
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Document, DocumentStatus, Project, User
from app.models.source_document import SourceDocumentORM


@pytest.mark.asyncio
async def test_document_can_reference_source_document(test_db: AsyncSession):
    user = User(id=uuid4(), email="u@e.com", full_name="U", auth_provider="email", password_hash="x")
    project = Project(id=uuid4(), user_id=user.id, name="P")
    src = SourceDocumentORM(id=uuid4(), sha256="1" * 64, storage_uri="local://1.pdf")
    test_db.add_all([user, project, src])
    await test_db.commit()

    doc = Document(
        id=uuid4(), project_id=project.id, created_by=user.id,
        source_type="upload", source_identifier="1" * 64, title="T",
        source_metadata={}, status=DocumentStatus.ready,
        source_document_id=src.id,
    )
    test_db.add(doc)
    await test_db.commit()

    fetched = (await test_db.execute(
        select(Document).where(Document.id == doc.id).options(selectinload(Document.source_document))
    )).scalar_one()
    assert fetched.source_document_id == src.id
    assert fetched.source_document is not None
    assert fetched.source_document.sha256 == "1" * 64


@pytest.mark.asyncio
async def test_document_source_document_id_is_nullable(test_db: AsyncSession):
    """PR 1 leaves FK nullable for migration-ordering reasons."""
    user = User(id=uuid4(), email="u2@e.com", full_name="U", auth_provider="email", password_hash="x")
    project = Project(id=uuid4(), user_id=user.id, name="P2")
    test_db.add_all([user, project])
    await test_db.commit()

    doc = Document(
        id=uuid4(), project_id=project.id, created_by=user.id,
        source_type="upload", source_identifier="null-test", title="T",
        source_metadata={}, status=DocumentStatus.ready,
    )
    test_db.add(doc)
    await test_db.commit()
    assert doc.source_document_id is None
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run --directory /c/Repos/rag-admin/backend python -m pytest tests/models/test_document_source_fk.py -v -o "addopts="
```

Expected: FAIL with `AttributeError: 'Document' has no attribute 'source_document_id'` or similar.

- [ ] **Step 3: Modify `Document`**

Edit `backend/app/models/document.py`. After the `folder_id` column (around line 39), add:

```python
    source_document_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("source_documents.id"),
        nullable=True,
    )
```

In the relationships block near the end of the class (after `user: Mapped["User"] = relationship()`), add:

```python
    source_document: Mapped["SourceDocumentORM | None"] = relationship(lazy="select")
```

Add the import at the top of the file (after existing model imports):

```python
from app.models.source_document import SourceDocumentORM
```

In `__table_args__`, add:

```python
    sa.Index('ix_documents_source_document_id', 'source_document_id'),
```

- [ ] **Step 4: Run tests**

```bash
uv run --directory /c/Repos/rag-admin/backend python -m pytest tests/models/test_document_source_fk.py -v -o "addopts="
```

Expected: both tests PASS.

- [ ] **Step 5: Run full models test directory for regression**

```bash
uv run --directory /c/Repos/rag-admin/backend python -m pytest tests/models/ -v -o "addopts="
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git -C /c/Repos/rag-admin add backend/app/models/document.py backend/tests/models/test_document_source_fk.py
git -C /c/Repos/rag-admin commit -m "feat(cdm): add nullable Document.source_document_id FK + relationship"
```

---

## Task 6: Shared test fixtures for CDM repositories

**Files:**
- Create: `backend/tests/repositories/conftest_cdm.py` — imported by repo tests via standard `conftest.py` discovery (renaming it `conftest.py` would override the directory-level one; instead we use a distinct name and import fixtures explicitly).

**Note:** The test files in Tasks 7–9 define their fixtures inline to stay self-contained, but each fixture body is identical. If you prefer DRY, promote the shared bits to `conftest_cdm.py` and import at the top of each test module. Either is acceptable — the tasks below assume inline fixtures for clarity.

No code step here — this task is a decision marker. Skip to Task 7.

- [ ] **Step 1: Confirm decision**

Keep fixtures inline for PR 1. Re-evaluate after PR 2 is written; if duplication bites, extract to a shared module then.

---

## Task 7: `SourceDocumentRepository`

**Files:**
- Create: `backend/app/repositories/source_document_repository.py`
- Test: `backend/tests/repositories/test_source_document_repository.py`

Repository methods:
- `create(sha256, storage_uri, filename=None, mime_type=None, byte_size=None) -> SourceDocumentORM`
- `get(id) -> SourceDocumentORM | None`
- `get_by_sha256(sha256) -> SourceDocumentORM | None`
- `get_or_create_by_sha256(sha256, storage_uri, **kw) -> tuple[SourceDocumentORM, bool]` — second element is `True` if newly created.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/repositories/test_source_document_repository.py`:

```python
"""Tests for SourceDocumentRepository."""
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.source_document import SourceDocumentORM
from app.repositories.source_document_repository import SourceDocumentRepository


@pytest.fixture
async def repo(test_db: AsyncSession) -> SourceDocumentRepository:
    return SourceDocumentRepository(test_db)


@pytest.mark.asyncio
async def test_create_inserts_and_returns(repo: SourceDocumentRepository):
    sd = await repo.create(sha256="a" * 64, storage_uri="local://a.pdf", filename="a.pdf")
    assert sd.id is not None
    assert sd.sha256 == "a" * 64
    assert sd.filename == "a.pdf"


@pytest.mark.asyncio
async def test_get_by_sha256_returns_row_when_present(repo: SourceDocumentRepository):
    await repo.create(sha256="b" * 64, storage_uri="local://b.pdf")
    found = await repo.get_by_sha256("b" * 64)
    assert found is not None
    assert found.sha256 == "b" * 64


@pytest.mark.asyncio
async def test_get_by_sha256_returns_none_when_absent(repo: SourceDocumentRepository):
    assert await repo.get_by_sha256("z" * 64) is None


@pytest.mark.asyncio
async def test_get_by_id(repo: SourceDocumentRepository):
    sd = await repo.create(sha256="c" * 64, storage_uri="local://c.pdf")
    fetched = await repo.get(sd.id)
    assert fetched is not None and fetched.id == sd.id


@pytest.mark.asyncio
async def test_get_or_create_creates_when_absent(repo: SourceDocumentRepository):
    sd, created = await repo.get_or_create_by_sha256(
        sha256="d" * 64, storage_uri="local://d.pdf", filename="d.pdf",
    )
    assert created is True
    assert sd.filename == "d.pdf"


@pytest.mark.asyncio
async def test_get_or_create_reuses_when_present(repo: SourceDocumentRepository):
    first = await repo.create(sha256="e" * 64, storage_uri="local://e.pdf", filename="first.pdf")
    second, created = await repo.get_or_create_by_sha256(
        sha256="e" * 64, storage_uri="ignored", filename="ignored",
    )
    assert created is False
    assert second.id == first.id
    # Existing fields are NOT overwritten on reuse.
    assert second.filename == "first.pdf"
```

- [ ] **Step 2: Run tests to verify failure**

```bash
uv run --directory /c/Repos/rag-admin/backend python -m pytest tests/repositories/test_source_document_repository.py -v -o "addopts="
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.repositories.source_document_repository'`.

- [ ] **Step 3: Implement the repository**

Create `backend/app/repositories/source_document_repository.py`:

```python
"""Repository for SourceDocumentORM — content-addressed bytes layer."""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.source_document import SourceDocumentORM


class SourceDocumentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        *,
        sha256: str,
        storage_uri: str,
        filename: str | None = None,
        mime_type: str | None = None,
        byte_size: int | None = None,
    ) -> SourceDocumentORM:
        row = SourceDocumentORM(
            sha256=sha256,
            storage_uri=storage_uri,
            filename=filename,
            mime_type=mime_type,
            byte_size=byte_size,
        )
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def get(self, source_document_id: UUID) -> SourceDocumentORM | None:
        result = await self.session.execute(
            select(SourceDocumentORM).where(SourceDocumentORM.id == source_document_id)
        )
        return result.scalar_one_or_none()

    async def get_by_sha256(self, sha256: str) -> SourceDocumentORM | None:
        result = await self.session.execute(
            select(SourceDocumentORM).where(SourceDocumentORM.sha256 == sha256)
        )
        return result.scalar_one_or_none()

    async def get_or_create_by_sha256(
        self,
        *,
        sha256: str,
        storage_uri: str,
        filename: str | None = None,
        mime_type: str | None = None,
        byte_size: int | None = None,
    ) -> tuple[SourceDocumentORM, bool]:
        existing = await self.get_by_sha256(sha256)
        if existing is not None:
            return existing, False
        try:
            created = await self.create(
                sha256=sha256, storage_uri=storage_uri,
                filename=filename, mime_type=mime_type, byte_size=byte_size,
            )
            return created, True
        except IntegrityError:
            # Lost the race. Roll back and re-read.
            await self.session.rollback()
            existing = await self.get_by_sha256(sha256)
            assert existing is not None, "IntegrityError but sha256 not found"
            return existing, False
```

- [ ] **Step 4: Run tests**

```bash
uv run --directory /c/Repos/rag-admin/backend python -m pytest tests/repositories/test_source_document_repository.py -v -o "addopts="
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git -C /c/Repos/rag-admin add backend/app/repositories/source_document_repository.py backend/tests/repositories/test_source_document_repository.py
git -C /c/Repos/rag-admin commit -m "feat(cdm): SourceDocumentRepository with sha256 get_or_create"
```

---

## Task 8: `ParseRunRepository`

**Files:**
- Create: `backend/app/repositories/parse_run_repository.py`
- Test: `backend/tests/repositories/test_parse_run_repository.py`

Repository methods:
- `create(dto: ParseRunCreate) -> ParseRunORM` — DTO is defined below; keeps `ParsingService` (PR 2) from passing ORM instances around.
- `get(id) -> ParseRunORM | None`
- `get_latest_for_content(source_document_id, representation_kind, config_hash) -> ParseRunORM | None` — point lookup on the unique index. Returns the single run if it exists.
- `update_status(id, status, **metrics) -> ParseRunORM` — mutates a row that is already persisted (used for PENDING → RUNNING → SUCCEEDED transitions in PR 2).

The DTO lives alongside the repository (colocated with its consumer). `ParsingService` in PR 2 will construct it from the Pydantic `ParseRun` after hashing the config.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/repositories/test_parse_run_repository.py`:

```python
"""Tests for ParseRunRepository."""
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.source_document import SourceDocumentORM
from app.repositories.parse_run_repository import (
    ParseRunCreate,
    ParseRunRepository,
)


@pytest.fixture
async def source_doc(test_db: AsyncSession) -> SourceDocumentORM:
    sd = SourceDocumentORM(id=uuid4(), sha256="a" * 64, storage_uri="local://a.pdf")
    test_db.add(sd)
    await test_db.commit()
    await test_db.refresh(sd)
    return sd


@pytest.fixture
async def repo(test_db: AsyncSession) -> ParseRunRepository:
    return ParseRunRepository(test_db)


def make_dto(source_doc, **override) -> ParseRunCreate:
    base = dict(
        source_document_id=source_doc.id,
        parser="llamaparse",
        parser_version=None,
        representation_kind="vector_light",
        config={"tier": "agentic"},
        config_hash="h" * 64,
        status="pending",
        started_at=datetime.now(timezone.utc),
    )
    base.update(override)
    return ParseRunCreate(**base)


@pytest.mark.asyncio
async def test_create_persists_row(repo, source_doc):
    run = await repo.create(make_dto(source_doc))
    assert run.id is not None
    assert run.parser == "llamaparse"
    assert run.config == {"tier": "agentic"}


@pytest.mark.asyncio
async def test_get_returns_row_by_id(repo, source_doc):
    run = await repo.create(make_dto(source_doc))
    fetched = await repo.get(run.id)
    assert fetched is not None
    assert fetched.id == run.id


@pytest.mark.asyncio
async def test_get_returns_none_when_absent(repo):
    assert await repo.get(uuid4()) is None


@pytest.mark.asyncio
async def test_get_latest_for_content_finds_exact_match(repo, source_doc):
    run = await repo.create(make_dto(source_doc, config_hash="x" * 64))
    found = await repo.get_latest_for_content(
        source_document_id=source_doc.id,
        representation_kind="vector_light",
        config_hash="x" * 64,
    )
    assert found is not None and found.id == run.id


@pytest.mark.asyncio
async def test_get_latest_for_content_returns_none_on_config_mismatch(repo, source_doc):
    await repo.create(make_dto(source_doc, config_hash="y" * 64))
    found = await repo.get_latest_for_content(
        source_document_id=source_doc.id,
        representation_kind="vector_light",
        config_hash="different" + "y" * 55,
    )
    assert found is None


@pytest.mark.asyncio
async def test_update_status_transitions_pending_to_succeeded(repo, source_doc):
    run = await repo.create(make_dto(source_doc, status="pending"))
    updated = await repo.update_status(
        run.id,
        status="succeeded",
        finished_at=datetime.now(timezone.utc),
        duration_ms=1234,
        input_tokens=100,
        output_tokens=50,
    )
    assert updated.status == "succeeded"
    assert updated.duration_ms == 1234
    assert updated.input_tokens == 100
    assert updated.output_tokens == 50
    assert updated.finished_at is not None
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run --directory /c/Repos/rag-admin/backend python -m pytest tests/repositories/test_parse_run_repository.py -v -o "addopts="
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement the repository**

Create `backend/app/repositories/parse_run_repository.py`:

```python
"""Repository for ParseRunORM — execution rows."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.parse_run import ParseRunORM


@dataclass
class ParseRunCreate:
    source_document_id: UUID
    parser: str
    representation_kind: str
    config: dict[str, Any]
    config_hash: str
    status: str
    started_at: datetime
    parser_version: str | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = None
    cost: dict[str, Any] = field(default_factory=dict)
    input_tokens: int | None = None
    output_tokens: int | None = None
    warnings: list[str] = field(default_factory=list)
    failed_pages: list[int] = field(default_factory=list)
    provider_refs: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class ParseRunRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, dto: ParseRunCreate) -> ParseRunORM:
        row = ParseRunORM(
            source_document_id=dto.source_document_id,
            parser=dto.parser,
            parser_version=dto.parser_version,
            representation_kind=dto.representation_kind,
            config=dto.config,
            config_hash=dto.config_hash,
            status=dto.status,
            started_at=dto.started_at,
            finished_at=dto.finished_at,
            duration_ms=dto.duration_ms,
            cost=dto.cost,
            input_tokens=dto.input_tokens,
            output_tokens=dto.output_tokens,
            warnings=dto.warnings,
            failed_pages=dto.failed_pages,
            provider_refs=dto.provider_refs,
            error=dto.error,
        )
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def get(self, run_id: UUID) -> ParseRunORM | None:
        result = await self.session.execute(
            select(ParseRunORM).where(ParseRunORM.id == run_id)
        )
        return result.scalar_one_or_none()

    async def get_latest_for_content(
        self,
        *,
        source_document_id: UUID,
        representation_kind: str,
        config_hash: str,
    ) -> ParseRunORM | None:
        """Point lookup on the unique index.

        Only ever returns 0 or 1 row; the name 'latest' hedges against a future
        relaxation of the unique constraint (e.g. soft-deletes introducing
        multiple historical rows).
        """
        result = await self.session.execute(
            select(ParseRunORM)
            .where(ParseRunORM.source_document_id == source_document_id)
            .where(ParseRunORM.representation_kind == representation_kind)
            .where(ParseRunORM.config_hash == config_hash)
            .order_by(ParseRunORM.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def update_status(
        self,
        run_id: UUID,
        *,
        status: str,
        finished_at: datetime | None = None,
        duration_ms: int | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        cost: dict[str, Any] | None = None,
        warnings: list[str] | None = None,
        failed_pages: list[int] | None = None,
        provider_refs: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> ParseRunORM:
        run = await self.get(run_id)
        if run is None:
            raise ValueError(f"ParseRun {run_id} not found")
        run.status = status
        if finished_at is not None:
            run.finished_at = finished_at
        if duration_ms is not None:
            run.duration_ms = duration_ms
        if input_tokens is not None:
            run.input_tokens = input_tokens
        if output_tokens is not None:
            run.output_tokens = output_tokens
        if cost is not None:
            run.cost = cost
        if warnings is not None:
            run.warnings = warnings
        if failed_pages is not None:
            run.failed_pages = failed_pages
        if provider_refs is not None:
            run.provider_refs = provider_refs
        if error is not None:
            run.error = error
        await self.session.commit()
        await self.session.refresh(run)
        return run
```

- [ ] **Step 4: Run tests**

```bash
uv run --directory /c/Repos/rag-admin/backend python -m pytest tests/repositories/test_parse_run_repository.py -v -o "addopts="
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git -C /c/Repos/rag-admin add backend/app/repositories/parse_run_repository.py backend/tests/repositories/test_parse_run_repository.py
git -C /c/Repos/rag-admin commit -m "feat(cdm): ParseRunRepository with content-config lookup + status update"
```

---

## Task 9: `ParsedDocumentRepository`

**Files:**
- Create: `backend/app/repositories/parsed_document_repository.py`
- Test: `backend/tests/repositories/test_parsed_document_repository.py`

Repository methods:
- `create(dto: ParsedDocumentCreate) -> ParsedDocumentORM`
- `get_by_run(parse_run_id) -> ParsedDocumentORM | None`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/repositories/test_parsed_document_repository.py`:

```python
"""Tests for ParsedDocumentRepository."""
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.parse_run import ParseRunORM
from app.models.source_document import SourceDocumentORM
from app.repositories.parsed_document_repository import (
    ParsedDocumentCreate,
    ParsedDocumentRepository,
)


@pytest.fixture
async def source_doc(test_db: AsyncSession) -> SourceDocumentORM:
    sd = SourceDocumentORM(id=uuid4(), sha256="a" * 64, storage_uri="local://a.pdf")
    test_db.add(sd)
    await test_db.commit()
    await test_db.refresh(sd)
    return sd


@pytest.fixture
async def parse_run(test_db: AsyncSession, source_doc) -> ParseRunORM:
    run = ParseRunORM(
        id=uuid4(),
        source_document_id=source_doc.id,
        parser="llamaparse",
        representation_kind="vector_light",
        config_hash="h" * 64,
        status="succeeded",
        started_at=datetime.now(timezone.utc),
    )
    test_db.add(run)
    await test_db.commit()
    await test_db.refresh(run)
    return run


@pytest.fixture
async def repo(test_db: AsyncSession) -> ParsedDocumentRepository:
    return ParsedDocumentRepository(test_db)


@pytest.mark.asyncio
async def test_create_persists_row(repo, parse_run, source_doc):
    content = {"pages": [{"index": 0, "block_ids": ["b1"]}], "full_text": "hello"}
    pdoc = await repo.create(ParsedDocumentCreate(
        parse_run_id=parse_run.id,
        source_document_id=source_doc.id,
        full_text="hello",
        full_markdown="# hello",
        page_count=1,
        block_count=1,
        content=content,
    ))
    assert pdoc.parse_run_id == parse_run.id
    assert pdoc.content == content


@pytest.mark.asyncio
async def test_get_by_run_returns_row(repo, parse_run, source_doc):
    await repo.create(ParsedDocumentCreate(
        parse_run_id=parse_run.id,
        source_document_id=source_doc.id,
        full_text="x", full_markdown=None,
        page_count=0, block_count=0, content={},
    ))
    found = await repo.get_by_run(parse_run.id)
    assert found is not None
    assert found.parse_run_id == parse_run.id


@pytest.mark.asyncio
async def test_get_by_run_returns_none_when_absent(repo):
    assert await repo.get_by_run(uuid4()) is None
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run --directory /c/Repos/rag-admin/backend python -m pytest tests/repositories/test_parsed_document_repository.py -v -o "addopts="
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement the repository**

Create `backend/app/repositories/parsed_document_repository.py`:

```python
"""Repository for ParsedDocumentORM — content blob layer."""
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.parsed_document import ParsedDocumentORM


@dataclass
class ParsedDocumentCreate:
    parse_run_id: UUID
    source_document_id: UUID
    full_text: str | None
    full_markdown: str | None
    page_count: int
    block_count: int
    content: dict[str, Any]


class ParsedDocumentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, dto: ParsedDocumentCreate) -> ParsedDocumentORM:
        row = ParsedDocumentORM(
            parse_run_id=dto.parse_run_id,
            source_document_id=dto.source_document_id,
            full_text=dto.full_text,
            full_markdown=dto.full_markdown,
            page_count=dto.page_count,
            block_count=dto.block_count,
            content=dto.content,
        )
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def get_by_run(self, parse_run_id: UUID) -> ParsedDocumentORM | None:
        result = await self.session.execute(
            select(ParsedDocumentORM).where(ParsedDocumentORM.parse_run_id == parse_run_id)
        )
        return result.scalar_one_or_none()
```

- [ ] **Step 4: Run tests**

```bash
uv run --directory /c/Repos/rag-admin/backend python -m pytest tests/repositories/test_parsed_document_repository.py -v -o "addopts="
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git -C /c/Repos/rag-admin add backend/app/repositories/parsed_document_repository.py backend/tests/repositories/test_parsed_document_repository.py
git -C /c/Repos/rag-admin commit -m "feat(cdm): ParsedDocumentRepository for JSONB content layer"
```

---

## Task 10: Round-trip integration — `ParsedDocument` Pydantic ↔ JSONB + real LlamaParse payload

**Files:**
- Test: `backend/tests/repositories/test_parsed_document_round_trip.py`

**Why this task exists:** the spec's acceptance criterion (§9.5) requires `ParsedDocument.model_validate(row.content) == original`. We add two assertions:

1. **CDM round-trip** (spec §9.5): synthetic `ParsedDocument` → JSONB → `ParsedDocument` equals original.
2. **Raw provider round-trip**: load the real LlamaParse JSON committed in Preflight 4 (`backend/tests/fixtures/llamaparse/annual_pp1-5/items.json`), store it as the `content` dict, and assert byte-identical recovery. This stresses JSONB against real-world floats (bbox coordinates like `26.453040448742353`), nested `items` arrays, `null`s, unicode, and deep structure that synthetic fixtures will never reproduce faithfully.

- [ ] **Step 1: Write the integration test**

Create `backend/tests/repositories/test_parsed_document_round_trip.py`:

```python
"""Verify ParsedDocument ↔ JSONB round-trips with zero loss.

Two assertions:
- spec §9.5 — synthetic CDM ParsedDocument survives model_dump → JSONB → model_validate.
- real LlamaParse payload (committed fixture from provider research) survives JSONB
  round-trip byte-identical. Catches float precision, unicode, and nested-dict edge
  cases that a hand-rolled synthetic fixture will not.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.cdm.models import (
    Block, BlockRole, BBox, ParsedDocument, ParserKind, Page,
)
from app.models.parse_run import ParseRunORM
from app.models.source_document import SourceDocumentORM
from app.repositories.parsed_document_repository import (
    ParsedDocumentCreate,
    ParsedDocumentRepository,
)

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "llamaparse"


async def _mk_source_and_run(test_db: AsyncSession) -> tuple[SourceDocumentORM, ParseRunORM]:
    src = SourceDocumentORM(id=uuid4(), sha256=uuid4().hex + uuid4().hex, storage_uri="local://a.pdf")
    # sha256 must be 64 chars — two uuid4 hex concatenated = 64.
    test_db.add(src)
    await test_db.commit()
    run = ParseRunORM(
        id=uuid4(), source_document_id=src.id,
        parser="llamaparse", representation_kind="vector_light",
        config_hash="h" * 64, status="succeeded",
        started_at=datetime.now(timezone.utc),
    )
    test_db.add(run)
    await test_db.commit()
    return src, run


@pytest.mark.asyncio
async def test_cdm_parsed_document_round_trip(test_db: AsyncSession):
    src, run = await _mk_source_and_run(test_db)

    original = ParsedDocument(
        source_document_id=str(src.id),
        parse_run_id=str(run.id),
        parser=ParserKind.LLAMAPARSE,
        pages=[Page(index=0, block_ids=["b1"])],
        blocks=[Block(
            id="b1",
            page_index=0,
            role=BlockRole.TEXT,
            native_type="text",
            text="hello world",
            markdown="hello world",
            bbox=BBox(x0=0.0, y0=0.0, x1=1.0, y1=0.1),
            reading_order=0,
        )],
        full_text="hello world",
        full_markdown="hello world",
    )

    repo = ParsedDocumentRepository(test_db)
    await repo.create(ParsedDocumentCreate(
        parse_run_id=run.id,
        source_document_id=src.id,
        full_text=original.full_text,
        full_markdown=original.full_markdown,
        page_count=len(original.pages),
        block_count=len(original.blocks),
        content=original.model_dump(mode="json"),
    ))

    fetched = await repo.get_by_run(run.id)
    assert fetched is not None
    restored = ParsedDocument.model_validate(fetched.content)
    assert restored == original


@pytest.mark.asyncio
async def test_real_llamaparse_payload_jsonb_byte_identical(test_db: AsyncSession):
    """Real provider payload survives JSONB round-trip with no key re-ordering,
    float drift, or unicode mangling."""
    src, run = await _mk_source_and_run(test_db)

    payload_path = FIXTURES / "annual_pp1-5" / "items.json"
    original_payload = json.loads(payload_path.read_text(encoding="utf-8"))

    # Sanity — the fixture actually has the structure we think it does.
    assert "pages" in original_payload
    assert len(original_payload["pages"]) >= 1
    assert any("bbox" in it for it in original_payload["pages"][0]["items"])

    repo = ParsedDocumentRepository(test_db)
    await repo.create(ParsedDocumentCreate(
        parse_run_id=run.id,
        source_document_id=src.id,
        full_text=None,
        full_markdown=None,
        page_count=len(original_payload["pages"]),
        block_count=sum(len(p.get("items", [])) for p in original_payload["pages"]),
        content=original_payload,
    ))

    fetched = await repo.get_by_run(run.id)
    assert fetched is not None
    # JSONB preserves structure; equality holds across arbitrary nesting, floats, and nulls.
    assert fetched.content == original_payload
```

**Note:** if the CDM `Block` / `Page` / `BBox` field names differ from what's shown above, read `backend/app/cdm/models.py` and update the **CDM** test's constructors to match. The real-payload test is independent of CDM models — it only exercises JSONB.

- [ ] **Step 2: Run it**

```bash
uv run --directory /c/Repos/rag-admin/backend python -m pytest tests/repositories/test_parsed_document_round_trip.py -v -o "addopts="
```

Expected: both tests PASS. If the CDM test fails due to model shape differences, fix the synthetic constructor. If the real-payload test fails, that is a genuine JSONB bug — investigate before moving on.

- [ ] **Step 3: Commit**

```bash
git -C /c/Repos/rag-admin add backend/tests/repositories/test_parsed_document_round_trip.py
git -C /c/Repos/rag-admin commit -m "test(cdm): ParsedDocument ↔ JSONB round-trip + real LlamaParse payload"
```

---

## Task 11: Full regression sweep

- [ ] **Step 1: Run the full backend test suite**

```bash
uv run --directory /c/Repos/rag-admin/backend python -m pytest -o "addopts=" -q
```

Expected: all tests pass (no regressions in unrelated code paths).

- [ ] **Step 2: Run the alembic upgrade/downgrade/upgrade cycle one more time**

```bash
uv run --directory /c/Repos/rag-admin/backend alembic downgrade -1
uv run --directory /c/Repos/rag-admin/backend alembic upgrade head
```

Expected: clean.

- [ ] **Step 3: Push the branch**

```bash
git -C /c/Repos/rag-admin push -u origin feat/cdm-persistence-schema
```

**Stop here.** The next step is opening a PR — that crosses the "PRs need approval" line in CLAUDE.md, so the executor hands off to the user at this point.

---

## Task 12: Open PR (user-gated)

This task is **explicitly user-gated** per CLAUDE.md's autonomy rules. The executor does not run `gh pr create` without confirmation.

- [ ] **Step 1: Confirm with user, then open PR**

Ask the user: *"All tasks complete. Ready to open the PR for this branch against main?"*

On explicit consent, run (substituting the actual issue number once Task 0 / the Pre-Implementation Gate has produced it):

```bash
gh pr create \
  --base main \
  --head feat/cdm-persistence-schema \
  --title "feat(cdm): persistence layer — schema + models + repositories (PR 1/3)" \
  --body "$(cat <<'EOF'
## Summary

PR 1 of 3 for CDM persistence per [docs/specs/cdm_persistence.md](docs/specs/cdm_persistence.md).

Adds durable persistence for CDM types with zero production callers yet:

- New tables: `source_documents`, `parse_runs`, `parsed_documents`.
- `documents.source_document_id` nullable FK.
- Async SQLAlchemy ORM models + repositories.
- Round-trip integration test proving `ParsedDocument → JSONB → ParsedDocument` is lossless.

No upload path changes, no runner wiring, no migration of existing data. Those land in PRs 2 and 3 and a sibling migration spec.

Closes #<issue>

## Test plan

- [x] `alembic upgrade head` / `downgrade -1` / `upgrade head` cycle clean
- [x] Repository unit tests pass for all three repos
- [x] `ParsedDocument ↔ JSONB` round-trip integration test passes
- [x] Full backend suite green (no regressions)
EOF
)"
```

---

## Self-Review

**Spec coverage against [docs/specs/cdm_persistence.md](../specs/cdm_persistence.md):**

- §2.1 `source_documents` table → Task 1 (migration) + Task 2 (ORM)
- §2.1 `parse_runs` table + unique index → Task 1 + Task 3
- §2.1 `parsed_documents` table → Task 1 + Task 4
- §2.2 `documents.source_document_id` (nullable) → Task 1 + Task 5
- §4 `SourceDocumentRepository` → Task 7
- §4 `ParseRunRepository` → Task 8
- §4 `ParsedDocumentRepository` → Task 9
- §9.5 `ParsedDocument.model_validate(row.content) == original` → Task 10
- §9.1 / §9.2 general acceptance (tables, ORM, repos with tests) → Tasks 1–9
- §2.3 reuse policy (same-project lookup joining `documents`) → **deferred to PR 2** (correctly — that's service-layer concern, not PR 1 repositories; `get_latest_for_content` is the primitive, service composes with `documents` filter)
- §3 `LlamaParseRunError` / failed-run plumbing → **PR 2**
- §5 `ParsingService` → **PR 2**
- §6 upload path integration → **PR 3**
- §7 PR slicing → confirmed: this plan is PR 1 only
- §8 migration notes → sibling spec, not in plan

No spec gaps for PR 1.

**Placeholder scan:** No "TBD", "TODO", "implement later". Task 6 is a decision marker with a single step — acceptable. Task 10 notes that CDM model field names may differ from the sketched fixture; the executor is instructed to resolve that by reading `app/cdm/models.py` rather than guessing.

**Type consistency:** `SourceDocumentORM`, `ParseRunORM`, `ParsedDocumentORM` are the three ORM names used consistently. DTOs `ParseRunCreate` and `ParsedDocumentCreate` match their repository consumers. Column names (`source_document_id`, `config_hash`, `representation_kind`, `parse_run_id`, `content`) are used identically across migration, ORM, tests, and repositories.
