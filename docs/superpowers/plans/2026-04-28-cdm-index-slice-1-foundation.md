# CDM Index Slice 1 — Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the CDM parse pipeline into the index pipeline — index documents can now be sourced from `ParsedDocument.full_text` instead of raw extracted text, with version tracking and per-document parse run binding.

**Architecture:** Add `version`, `parser`, `parse_config_hash`, `config_dirty` to `Index`; add `parse_run_id` to `IndexDocument`; add `index_version`, `parse_run_id`, `source_type` to `Chunk`; add a new `IndexEvent` model. The processing service dispatches on `source_representation` — routing `full_text` to the existing chunker but loading text from `ParsedDocument` instead of `document.extracted_text`. On each successful reprocess the version is incremented and an `IndexEvent` row is written.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 async, Alembic, PostgreSQL (SQLite for tests), React 18, TypeScript, shadcn/ui

---

## File Map

**Create:**
- `backend/alembic/versions/a2b3c4d5e6f7_cdm_index_slice1_foundation.py` — migration
- `backend/app/models/index_event.py` — new `IndexEvent` ORM model
- `backend/tests/models/test_index_event_orm.py` — ORM smoke test
- `backend/tests/services/test_index_processing_cdm.py` — processing service CDM tests
- `backend/tests/schemas/test_index_config_schema.py` — schema validation tests

**Modify:**
- `backend/app/models/index.py` — add version, parser, parse_config_hash, config_dirty, index_events relationship
- `backend/app/models/index_document.py` — add parse_run_id, parse_run relationship
- `backend/app/models/chunk.py` — add index_version, parse_run_id, source_type
- `backend/app/models/__init__.py` — export IndexEvent
- `backend/app/schemas/index.py` — update IndexConfig, AddDocumentsRequest, IndexResponse
- `backend/app/repositories/index_repository.py` — add increment_version, write_index_event, update add_documents
- `backend/app/services/index_processing_service.py` — CDM dispatch, version increment on complete
- `backend/app/services/index_service.py` — pass parse_run_ids through add_documents
- `backend/app/routers/indexes.py` — pass parse_run_ids from request to service
- `frontend/src/types/index.ts` — update IndexConfig, Index, AddDocumentsRequest
- `frontend/src/api/indexes.ts` — update createIndex, addDocuments
- `frontend/src/pages/IndexDetailPage.tsx` — version badge + parse run column on document list

---

## Task 1: Alembic migration

**Files:**
- Create: `backend/alembic/versions/a2b3c4d5e6f7_cdm_index_slice1_foundation.py`

- [ ] **Step 1: Create the migration file**

```python
# backend/alembic/versions/a2b3c4d5e6f7_cdm_index_slice1_foundation.py
"""cdm_index_slice1_foundation

Revision ID: a2b3c4d5e6f7
Revises: f9b0c1d2e3a4
Create Date: 2026-04-28 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'a2b3c4d5e6f7'
down_revision: Union[str, None] = 'f9b0c1d2e3a4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # indexes — versioning and CDM binding
    op.add_column('indexes', sa.Column('version', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('indexes', sa.Column('parser', sa.String(), nullable=True))
    op.add_column('indexes', sa.Column('parse_config_hash', sa.String(), nullable=True))
    op.add_column('indexes', sa.Column('config_dirty', sa.Boolean(), nullable=False, server_default='false'))

    # index_documents — per-document parse run binding
    op.add_column('index_documents', sa.Column(
        'parse_run_id',
        sa.UUID(),
        sa.ForeignKey('parse_runs.id', ondelete='SET NULL'),
        nullable=True
    ))
    op.create_index('ix_index_documents_parse_run_id', 'index_documents', ['parse_run_id'])

    # chunks — provenance fields
    op.add_column('chunks', sa.Column('index_version', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('chunks', sa.Column('parse_run_id', sa.UUID(), nullable=True))
    op.add_column('chunks', sa.Column('source_type', sa.String(), nullable=False, server_default='raw_text'))
    op.create_index('ix_chunks_source_type', 'chunks', ['source_type'])

    # index_events — write-once audit trail
    op.create_table(
        'index_events',
        sa.Column('id', sa.UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('index_id', sa.UUID(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('config_snapshot', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('document_bindings', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('triggered_by', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['index_id'], ['indexes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['triggered_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_index_events_index_id', 'index_events', ['index_id'])
    op.create_index('ix_index_events_index_version', 'index_events', ['index_id', 'version'])


def downgrade() -> None:
    op.drop_table('index_events')
    op.drop_index('ix_chunks_source_type', 'chunks')
    op.drop_column('chunks', 'source_type')
    op.drop_column('chunks', 'parse_run_id')
    op.drop_column('chunks', 'index_version')
    op.drop_index('ix_index_documents_parse_run_id', 'index_documents')
    op.drop_column('index_documents', 'parse_run_id')
    op.drop_column('indexes', 'config_dirty')
    op.drop_column('indexes', 'parse_config_hash')
    op.drop_column('indexes', 'parser')
    op.drop_column('indexes', 'version')
```

- [ ] **Step 2: Verify migration runs**

```bash
uv run --directory backend alembic upgrade head
```

Expected: applies without error.

- [ ] **Step 3: Verify downgrade**

```bash
uv run --directory backend alembic downgrade -1
uv run --directory backend alembic upgrade head
```

Expected: both run without error.

- [ ] **Step 4: Commit**

```bash
git add backend/alembic/versions/a2b3c4d5e6f7_cdm_index_slice1_foundation.py
git commit -m "feat(db): add CDM index foundation migration — version, parse_run_id, index_events"
```

---

## Task 2: `IndexEvent` ORM model

**Files:**
- Create: `backend/app/models/index_event.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/models/test_index_event_orm.py`:

```python
import pytest
from uuid import uuid4
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.index_event import IndexEvent


@pytest.mark.asyncio
async def test_index_event_can_be_created(test_db: AsyncSession):
    # Requires a user and index to exist — use raw inserts to avoid FK issues in test
    user_id = uuid4()
    index_id = uuid4()

    event = IndexEvent(
        index_id=index_id,
        version=1,
        config_snapshot={"chunking_strategy": "recursive_character"},
        document_bindings={str(uuid4()): str(uuid4())},
        triggered_by=user_id,
    )
    test_db.add(event)
    await test_db.commit()
    await test_db.refresh(event)

    assert event.id is not None
    assert event.version == 1
    assert event.config_snapshot["chunking_strategy"] == "recursive_character"
    assert event.created_at is not None
```

- [ ] **Step 2: Run test — expect FAIL (model not defined)**

```bash
uv run --directory backend python -m pytest tests/models/test_index_event_orm.py -o "addopts=" -v
```

Expected: `ImportError: cannot import name 'IndexEvent'`

- [ ] **Step 3: Create `IndexEvent` model**

```python
# backend/app/models/index_event.py
from datetime import datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class IndexEvent(Base):
    __tablename__ = "index_events"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=sa.text('gen_random_uuid()')
    )
    index_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("indexes.id", ondelete="CASCADE"),
        nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    config_snapshot: Mapped[dict] = mapped_column(
        sa.JSON, nullable=False, default=dict, server_default='{}'
    )
    document_bindings: Mapped[dict] = mapped_column(
        sa.JSON, nullable=False, default=dict, server_default='{}'
    )
    triggered_by: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        server_default=sa.text('NOW()')
    )

    index: Mapped["Index"] = relationship(back_populates="index_events")

    __table_args__ = (
        sa.Index('ix_index_events_index_id', 'index_id'),
        sa.Index('ix_index_events_index_version', 'index_id', 'version'),
    )
```

- [ ] **Step 4: Export from `__init__.py`**

In `backend/app/models/__init__.py`, add after the `ParsedDocument` import line:

```python
from app.models.index_event import IndexEvent
```

And add `"IndexEvent"` to the `__all__` list.

- [ ] **Step 5: Run test — expect PASS**

```bash
uv run --directory backend python -m pytest tests/models/test_index_event_orm.py -o "addopts=" -v
```

Expected: PASS (SQLite creates the table from ORM metadata).

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/index_event.py backend/app/models/__init__.py backend/tests/models/test_index_event_orm.py
git commit -m "feat(models): add IndexEvent write-once audit model"
```

---

## Task 3: Update ORM models — Index, IndexDocument, Chunk

**Files:**
- Modify: `backend/app/models/index.py`
- Modify: `backend/app/models/index_document.py`
- Modify: `backend/app/models/chunk.py`

- [ ] **Step 1: Write failing test**

Add to `backend/tests/models/test_index_event_orm.py`:

```python
from app.models import Index, IndexDocument, Chunk


def test_index_model_has_new_fields():
    index = Index()
    assert hasattr(index, 'version')
    assert hasattr(index, 'parser')
    assert hasattr(index, 'parse_config_hash')
    assert hasattr(index, 'config_dirty')


def test_index_document_model_has_parse_run_id():
    doc = IndexDocument()
    assert hasattr(doc, 'parse_run_id')


def test_chunk_model_has_provenance_fields():
    chunk = Chunk()
    assert hasattr(chunk, 'index_version')
    assert hasattr(chunk, 'parse_run_id')
    assert hasattr(chunk, 'source_type')
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
uv run --directory backend python -m pytest tests/models/test_index_event_orm.py::test_index_model_has_new_fields -o "addopts=" -v
```

Expected: `AssertionError` — `version` attribute not found.

- [ ] **Step 3: Update `Index` model**

In `backend/app/models/index.py`, add these columns after `error_message`:

```python
# CDM pipeline binding and versioning
version: Mapped[int] = mapped_column(
    sa.Integer,
    nullable=False,
    default=1,
    server_default='1'
)
parser: Mapped[str | None] = mapped_column(
    sa.String(100),
    nullable=True
)
parse_config_hash: Mapped[str | None] = mapped_column(
    sa.String(64),
    nullable=True
)
config_dirty: Mapped[bool] = mapped_column(
    sa.Boolean,
    nullable=False,
    default=False,
    server_default='false'
)
```

Add the `index_events` relationship after the existing `chunks` relationship:

```python
index_events: Mapped[list["IndexEvent"]] = relationship(
    back_populates="index",
    cascade="all, delete-orphan",
    order_by="IndexEvent.version"
)
```

- [ ] **Step 4: Update `IndexDocument` model**

In `backend/app/models/index_document.py`, add after `chunks_created`:

```python
# CDM parse run binding for this document
parse_run_id: Mapped[UUID | None] = mapped_column(
    PGUUID(as_uuid=True),
    ForeignKey("parse_runs.id", ondelete="SET NULL"),
    nullable=True
)
```

Add relationship after existing relationships:

```python
parse_run: Mapped["ParseRun | None"] = relationship()
```

Add the index to `__table_args__`:

```python
sa.Index('ix_index_documents_parse_run_id', 'parse_run_id'),
```

- [ ] **Step 5: Update `Chunk` model**

In `backend/app/models/chunk.py`, add after `chunk_metadata`:

```python
# CDM provenance — which version and parse run created this chunk
index_version: Mapped[int] = mapped_column(
    Integer,
    nullable=False,
    default=1,
    server_default='1'
)
parse_run_id: Mapped[UUID | None] = mapped_column(
    PGUUID(as_uuid=True),
    nullable=True
)
source_type: Mapped[str] = mapped_column(
    sa.String(30),
    nullable=False,
    default='raw_text',
    server_default='raw_text'
)
```

Add index to `__table_args__`:

```python
sa.Index('ix_chunks_source_type', 'source_type'),
```

- [ ] **Step 6: Run all three attribute tests — expect PASS**

```bash
uv run --directory backend python -m pytest tests/models/test_index_event_orm.py -o "addopts=" -v
```

Expected: all PASS.

- [ ] **Step 7: Run existing model tests to confirm no regressions**

```bash
uv run --directory backend python -m pytest tests/models/ -o "addopts=" -v
```

Expected: all PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/app/models/index.py backend/app/models/index_document.py backend/app/models/chunk.py backend/tests/models/test_index_event_orm.py
git commit -m "feat(models): add version/parser/parse_run_id fields to Index, IndexDocument, Chunk"
```

---

## Task 4: Update `IndexConfig` schema

**Files:**
- Modify: `backend/app/schemas/index.py`
- Create: `backend/tests/schemas/test_index_config_schema.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/schemas/__init__.py` (empty) and `backend/tests/schemas/test_index_config_schema.py`:

```python
import pytest
from pydantic import ValidationError as PydanticValidationError

from app.schemas.index import IndexConfig


def test_default_config_is_raw_text():
    config = IndexConfig()
    assert config.source_representation == "raw_text"
    assert config.parser is None
    assert config.parse_config_hash is None


def test_full_text_requires_parser():
    with pytest.raises(PydanticValidationError) as exc_info:
        IndexConfig(source_representation="full_text")
    assert "parser" in str(exc_info.value).lower()


def test_full_text_with_parser_is_valid():
    config = IndexConfig(
        source_representation="full_text",
        parser="llamaparse",
        parse_config_hash="abc123",
    )
    assert config.source_representation == "full_text"
    assert config.parser == "llamaparse"


def test_markdown_heading_requires_full_markdown():
    with pytest.raises(PydanticValidationError):
        IndexConfig(
            source_representation="raw_text",
            chunking_strategy="markdown_heading",
        )


def test_block_strategy_requires_block_representation():
    with pytest.raises(PydanticValidationError):
        IndexConfig(
            source_representation="full_text",
            chunking_strategy="block",
            parser="llamaparse",
        )


def test_raw_text_with_fixed_size_is_valid():
    config = IndexConfig(
        source_representation="raw_text",
        chunking_strategy="fixed_size",
        chunk_size=256,
    )
    assert config.chunking_strategy == "fixed_size"


def test_parsing_strategy_field_no_longer_exists():
    # Removed in this slice — any config containing it should either ignore or fail
    config = IndexConfig()
    assert not hasattr(config, 'parsing_strategy')
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
uv run --directory backend python -m pytest tests/schemas/test_index_config_schema.py -o "addopts=" -v
```

Expected: mix of failures — `source_representation` attribute missing, `parsing_strategy` still present.

- [ ] **Step 3: Update `IndexConfig` in `backend/app/schemas/index.py`**

Replace the existing `IndexConfig` class with:

```python
class IndexConfig(BaseModel):
    """Configuration for how documents are chunked and embedded."""

    # Parse source binding
    parser: str | None = Field(default=None, alias="parser")
    parse_config_hash: str | None = Field(default=None, alias="parseConfigHash")
    source_representation: Literal["raw_text", "full_text", "full_markdown", "block"] = Field(
        default="raw_text", alias="sourceRepresentation"
    )

    # Chunking strategy
    chunking_strategy: Literal[
        "fixed_size",
        "recursive_character",
        "markdown_heading",
        "block",
        "classified_block",
    ] = Field(
        default="recursive_character",
        alias="chunkingStrategy",
        description="How documents are split into chunks",
    )

    # Text-based config (fixed_size, recursive_character)
    chunk_size: int = Field(default=512, ge=100, le=8000, alias="chunkSize")
    chunk_overlap: int = Field(default=50, ge=0, alias="chunkOverlap")
    chunk_unit: Literal["tokens", "characters"] = Field(default="characters", alias="chunkUnit")

    # Embedding config (unchanged)
    embedding_provider: str = Field(default="openai", alias="embeddingProvider")
    embedding_model: str = Field(default="text-embedding-3-small", alias="embeddingModel")
    embedding_dimensions: int | None = Field(default=None, alias="embeddingDimensions")

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("chunk_overlap")
    @classmethod
    def validate_overlap(cls, v: int, info) -> int:
        chunk_size = info.data.get("chunk_size", 512)
        max_overlap = chunk_size // 2
        if v > max_overlap:
            raise ValueError(f"chunk_overlap must be at most {max_overlap}")
        return v

    @model_validator(mode="after")
    def validate_representation_and_strategy(self) -> "IndexConfig":
        rep = self.source_representation
        strategy = self.chunking_strategy

        # CDM representations require parser to be set
        if rep != "raw_text" and not self.parser:
            raise ValueError(
                f"source_representation='{rep}' requires 'parser' to be set"
            )

        # Validate strategy is compatible with representation
        text_strategies = {"fixed_size", "recursive_character"}
        allowed: dict[str, set[str]] = {
            "raw_text": text_strategies,
            "full_text": text_strategies,
            "full_markdown": {"markdown_heading"},
            "block": {"block", "classified_block"},
        }
        if strategy not in allowed.get(rep, set()):
            raise ValueError(
                f"chunking_strategy='{strategy}' is not compatible with "
                f"source_representation='{rep}'. "
                f"Allowed: {sorted(allowed[rep])}"
            )
        return self
```

Note: `@model_validator` requires adding `model_validator` to the pydantic imports at the top of the file:

```python
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
uv run --directory backend python -m pytest tests/schemas/test_index_config_schema.py -o "addopts=" -v
```

Expected: all PASS.

- [ ] **Step 5: Run existing tests to check nothing broke**

```bash
uv run --directory backend python -m pytest tests/ -o "addopts=" -v --ignore=tests/cdm/eval
```

Expected: PASS. If any test creates an `IndexConfig` with `parsing_strategy`, update it to omit that field.

- [ ] **Step 6: Update `IndexResponse` to include `version` and `config_dirty`**

In `backend/app/schemas/index.py`, update `IndexResponse`:

```python
class IndexResponse(BaseModel):
    id: UUID
    project_id: UUID = Field(..., alias="projectId")
    name: str
    description: str | None
    config: IndexConfig
    stats: IndexStats | None
    status: str
    error_message: str | None = Field(None, alias="errorMessage")
    created_by: UUID = Field(..., alias="createdBy")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")
    version: int = Field(default=1)
    config_dirty: bool = Field(default=False, alias="configDirty")
    document_count: int = Field(0, alias="documentCount")
    chunk_count: int = Field(0, alias="chunkCount")
    document_ids: list[UUID] = Field(default_factory=list, alias="documentIds")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
```

- [ ] **Step 7: Update `AddDocumentsRequest`**

```python
class AddDocumentsRequest(BaseModel):
    document_ids: list[UUID] = Field(..., alias="documentIds", min_length=1)
    parse_run_ids: dict[UUID, UUID] | None = Field(
        default=None,
        alias="parseRunIds",
        description="Map of document_id → parse_run_id. Required per document when source_representation != raw_text.",
    )

    model_config = ConfigDict(populate_by_name=True)
```

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas/index.py backend/tests/schemas/ 
git commit -m "feat(schemas): update IndexConfig with source_representation, remove parsing_strategy; add version/configDirty to IndexResponse"
```

---

## Task 5: Repository — `increment_version` and `write_index_event`

**Files:**
- Modify: `backend/app/repositories/index_repository.py`

- [ ] **Step 1: Write failing tests**

Add to a new file `backend/tests/repositories/test_index_event_repository.py`:

```python
import pytest
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Index, IndexStatus
from app.models.index_event import IndexEvent
from app.repositories.index_repository import IndexRepository


async def _make_index(db: AsyncSession, project_id, user_id) -> Index:
    index = Index(
        project_id=project_id,
        created_by=user_id,
        name="test-index",
        config={"chunking_strategy": "recursive_character", "source_representation": "raw_text"},
        status=IndexStatus.ready,
    )
    db.add(index)
    await db.commit()
    await db.refresh(index)
    return index


@pytest.mark.asyncio
async def test_increment_version(test_db: AsyncSession):
    project_id = uuid4()
    user_id = uuid4()
    index = await _make_index(test_db, project_id, user_id)
    assert index.version == 1

    repo = IndexRepository(test_db)
    await repo.increment_version(index.id)

    await test_db.refresh(index)
    assert index.version == 2


@pytest.mark.asyncio
async def test_write_index_event(test_db: AsyncSession):
    project_id = uuid4()
    user_id = uuid4()
    index = await _make_index(test_db, project_id, user_id)

    repo = IndexRepository(test_db)
    doc_id = str(uuid4())
    run_id = str(uuid4())

    event = await repo.write_index_event(
        index_id=index.id,
        version=1,
        config_snapshot={"chunking_strategy": "recursive_character"},
        document_bindings={doc_id: run_id},
        triggered_by=user_id,
    )

    assert event.version == 1
    assert event.document_bindings[doc_id] == run_id
    assert event.triggered_by == user_id


@pytest.mark.asyncio
async def test_write_index_event_preserves_null_bindings(test_db: AsyncSession):
    project_id = uuid4()
    user_id = uuid4()
    index = await _make_index(test_db, project_id, user_id)

    repo = IndexRepository(test_db)
    doc_id = str(uuid4())

    event = await repo.write_index_event(
        index_id=index.id,
        version=1,
        config_snapshot={},
        document_bindings={doc_id: None},
        triggered_by=user_id,
    )

    assert event.document_bindings[doc_id] is None
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
uv run --directory backend python -m pytest tests/repositories/test_index_event_repository.py -o "addopts=" -v
```

Expected: `AttributeError: 'IndexRepository' object has no attribute 'increment_version'`

- [ ] **Step 3: Add methods to `IndexRepository`**

Add at the end of `IndexRepository` in `backend/app/repositories/index_repository.py`:

```python
async def increment_version(self, index_id: UUID) -> None:
    """Increment the version counter on an index. Call after successful reprocess."""
    result = await self.session.execute(
        select(Index).where(Index.id == index_id)
    )
    index = result.scalar_one_or_none()
    if index:
        index.version += 1
        await self.session.commit()

async def write_index_event(
    self,
    index_id: UUID,
    version: int,
    config_snapshot: dict,
    document_bindings: dict,
    triggered_by: UUID,
) -> "IndexEvent":
    """Write a write-once audit event for a reprocess."""
    from app.models.index_event import IndexEvent
    event = IndexEvent(
        index_id=index_id,
        version=version,
        config_snapshot=config_snapshot,
        document_bindings=document_bindings,
        triggered_by=triggered_by,
    )
    self.session.add(event)
    await self.session.commit()
    await self.session.refresh(event)
    return event
```

Also update `add_documents` to accept parse run bindings:

```python
async def add_documents(
    self,
    index_id: UUID,
    document_ids: list[UUID],
    parse_run_ids: dict[UUID, UUID] | None = None,
) -> list["IndexDocument"]:
    """Add documents to an index, optionally binding each to a parse run."""
    index_docs = []
    for doc_id in document_ids:
        index_doc = IndexDocument(
            index_id=index_id,
            document_id=doc_id,
            processing_status=IndexDocumentStatus.pending,
            parse_run_id=(parse_run_ids or {}).get(doc_id),
        )
        self.session.add(index_doc)
        index_docs.append(index_doc)

    await self.session.commit()
    for doc in index_docs:
        await self.session.refresh(doc)
    return index_docs
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
uv run --directory backend python -m pytest tests/repositories/test_index_event_repository.py -o "addopts=" -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/repositories/index_repository.py backend/tests/repositories/test_index_event_repository.py
git commit -m "feat(repo): add increment_version, write_index_event; update add_documents with parse_run_ids"
```

---

## Task 6: Processing service — CDM dispatch and version increment

**Files:**
- Modify: `backend/app/services/index_processing_service.py`
- Create: `backend/tests/services/test_index_processing_cdm.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/services/test_index_processing_cdm.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.models import IndexStatus, IndexDocumentStatus
from app.schemas.index import IndexConfig
from app.services.index_processing_service import IndexProcessingService
from app.services.exceptions import ValidationError


def _make_mock_index(source_representation="raw_text"):
    config = IndexConfig(
        source_representation=source_representation,
        chunking_strategy="recursive_character",
        parser="llamaparse" if source_representation != "raw_text" else None,
        parse_config_hash="abc123" if source_representation != "raw_text" else None,
    )
    index = MagicMock()
    index.id = uuid4()
    index.config = config.model_dump()
    index.status = IndexStatus.created
    return index


def _make_mock_index_doc(parse_run_id=None):
    doc = MagicMock()
    doc.document_id = uuid4()
    doc.parse_run_id = parse_run_id
    doc.processing_status = IndexDocumentStatus.pending
    doc.document = MagicMock()
    doc.document.id = doc.document_id
    doc.document.title = "Test Doc"
    doc.document.extracted_text = "raw extracted text"
    doc.document.source_metadata = {"filename": "test.pdf"}
    doc.document.processing_metadata = {}
    return doc


@pytest.mark.asyncio
async def test_start_processing_raises_when_cdm_doc_has_no_parse_run():
    index = _make_mock_index(source_representation="full_text")
    index_doc = _make_mock_index_doc(parse_run_id=None)  # no parse run set
    index.index_documents = [index_doc]

    index_repo = AsyncMock()
    index_repo.get_by_id_with_documents = AsyncMock(return_value=index)

    provider_key_repo = AsyncMock()
    provider_key_repo.get_for_provider = AsyncMock(return_value=MagicMock())

    service = IndexProcessingService(
        session=AsyncMock(),
        index_repo=index_repo,
        chunk_repo=AsyncMock(),
        provider_key_repo=provider_key_repo,
    )

    with pytest.raises(ValidationError, match="no parse run set"):
        await service.start_processing(index.id, uuid4(), uuid4())


@pytest.mark.asyncio
async def test_process_index_uses_full_text_from_parsed_document():
    index = _make_mock_index(source_representation="full_text")
    parse_run_id = uuid4()
    index_doc = _make_mock_index_doc(parse_run_id=parse_run_id)
    index.index_documents = [index_doc]
    index.version = 1

    parsed_doc = MagicMock()
    parsed_doc.full_text = "clean parsed text from CDM"

    index_repo = AsyncMock()
    index_repo.get_by_id_with_documents = AsyncMock(return_value=index)
    index_repo.get_pending_documents = AsyncMock(return_value=[index_doc])
    index_repo.update_document_status = AsyncMock()
    index_repo.update_status = AsyncMock()
    index_repo.update_stats = AsyncMock()
    index_repo.increment_version = AsyncMock()
    index_repo.write_index_event = AsyncMock()

    parsed_doc_repo = AsyncMock()
    parsed_doc_repo.get_by_run = AsyncMock(return_value=parsed_doc)

    chunk_repo = AsyncMock()
    chunk_repo.create_batch = AsyncMock()
    chunk_repo.get_stats = AsyncMock(return_value={
        "total_chunks": 2, "total_documents": 1,
        "avg_chunk_size_chars": 100.0, "avg_chunk_size_tokens": 20.0,
        "min_chunk_size_chars": 80, "max_chunk_size_chars": 120,
        "total_tokens": 40,
    })

    mock_embedding_provider = AsyncMock()
    mock_embedding_provider.embed_texts = AsyncMock(return_value=[[0.1, 0.2], [0.3, 0.4]])
    mock_embedding_provider.get_dimensions = MagicMock(return_value=2)

    # ParsedDocumentRepository is at app/repositories/parsed_document_repository.py
    # It has get_by_run(parse_run_id) → ParsedDocument | None
    with patch("app.services.index_processing_service.EmbeddingProviderRegistry") as mock_registry, \
         patch("app.services.index_processing_service.ParsedDocumentRepository", return_value=parsed_doc_repo):
        mock_registry.get_provider.return_value = mock_embedding_provider

        service = IndexProcessingService(
            session=AsyncMock(),
            index_repo=index_repo,
            chunk_repo=chunk_repo,
            provider_key_repo=AsyncMock(),
        )

        await service.process_index(index.id, uuid4(), uuid4())

    # Verify ParsedDocumentRepository was queried with the parse_run_id
    parsed_doc_repo.get_by_run.assert_called_once_with(parse_run_id)

    # Verify chunks were created with correct source_type and parse_run_id
    call_args = chunk_repo.create_batch.call_args[0][0]
    assert call_args[0]["source_type"] == "full_text"
    assert call_args[0]["parse_run_id"] == str(parse_run_id)
    assert call_args[0]["index_version"] == 2  # version + 1

    # Verify version was incremented and event written
    index_repo.increment_version.assert_called_once_with(index.id)
    index_repo.write_index_event.assert_called_once()


@pytest.mark.asyncio
async def test_process_index_raises_not_implemented_for_unsupported_representation():
    index = _make_mock_index(source_representation="raw_text")
    # Force an unsupported source_representation via raw config dict
    index.config = {
        "source_representation": "block",
        "chunking_strategy": "block",
        "parser": "llamaparse",
        "parse_config_hash": "abc123",
        "embedding_provider": "openai",
        "embedding_model": "text-embedding-3-small",
    }
    parse_run_id = uuid4()
    index_doc = _make_mock_index_doc(parse_run_id=parse_run_id)
    index.index_documents = [index_doc]
    index.version = 1

    index_repo = AsyncMock()
    index_repo.get_by_id_with_documents = AsyncMock(return_value=index)
    index_repo.get_pending_documents = AsyncMock(return_value=[index_doc])
    index_repo.update_document_status = AsyncMock()
    index_repo.update_status = AsyncMock()
    index_repo.update_stats = AsyncMock()
    index_repo.increment_version = AsyncMock()
    index_repo.write_index_event = AsyncMock()

    chunk_repo = AsyncMock()
    chunk_repo.get_stats = AsyncMock(return_value={
        "total_chunks": 0, "total_documents": 1,
        "avg_chunk_size_chars": 0.0, "avg_chunk_size_tokens": 0.0,
        "min_chunk_size_chars": 0, "max_chunk_size_chars": 0,
        "total_tokens": 0,
    })

    mock_embedding_provider = AsyncMock()
    mock_embedding_provider.embed_texts = AsyncMock(return_value=[])
    mock_embedding_provider.get_dimensions = MagicMock(return_value=1536)

    with patch("app.services.index_processing_service.EmbeddingProviderRegistry") as mock_registry:
        mock_registry.get_provider.return_value = mock_embedding_provider

        service = IndexProcessingService(
            session=AsyncMock(),
            index_repo=index_repo,
            chunk_repo=chunk_repo,
            provider_key_repo=AsyncMock(),
        )

        await service.process_index(index.id, uuid4(), uuid4())

    # Document should be marked failed with NotImplementedError message
    failed_call = [
        c for c in index_repo.update_document_status.call_args_list
        if c.args[2] == IndexDocumentStatus.failed
    ]
    assert len(failed_call) == 1
    assert "not yet supported" in failed_call[0].kwargs.get("error_message", "") or \
           "not yet supported" in str(failed_call[0].args)


@pytest.mark.asyncio
async def test_process_index_raw_text_still_works():
    """Regression: raw_text mode unchanged from before this slice."""
    index = _make_mock_index(source_representation="raw_text")
    index_doc = _make_mock_index_doc(parse_run_id=None)
    index.index_documents = [index_doc]
    index.version = 1

    index_repo = AsyncMock()
    index_repo.get_by_id_with_documents = AsyncMock(return_value=index)
    index_repo.get_pending_documents = AsyncMock(return_value=[index_doc])
    index_repo.update_document_status = AsyncMock()
    index_repo.update_status = AsyncMock()
    index_repo.update_stats = AsyncMock()
    index_repo.increment_version = AsyncMock()
    index_repo.write_index_event = AsyncMock()

    chunk_repo = AsyncMock()
    chunk_repo.create_batch = AsyncMock()
    chunk_repo.get_stats = AsyncMock(return_value={
        "total_chunks": 1, "total_documents": 1,
        "avg_chunk_size_chars": 100.0, "avg_chunk_size_tokens": 20.0,
        "min_chunk_size_chars": 100, "max_chunk_size_chars": 100,
        "total_tokens": 20,
    })

    mock_embedding_provider = AsyncMock()
    mock_embedding_provider.embed_texts = AsyncMock(return_value=[[0.1, 0.2]])
    mock_embedding_provider.get_dimensions = MagicMock(return_value=2)

    with patch("app.services.index_processing_service.EmbeddingProviderRegistry") as mock_registry:
        mock_registry.get_provider.return_value = mock_embedding_provider

        service = IndexProcessingService(
            session=AsyncMock(),
            index_repo=index_repo,
            chunk_repo=chunk_repo,
            provider_key_repo=AsyncMock(),
        )
        await service.process_index(index.id, uuid4(), uuid4())

    call_args = chunk_repo.create_batch.call_args[0][0]
    assert call_args[0]["source_type"] == "raw_text"
    assert call_args[0]["parse_run_id"] is None
    index_repo.increment_version.assert_called_once()
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
uv run --directory backend python -m pytest tests/services/test_index_processing_cdm.py -o "addopts=" -v
```

Expected: `AssertionError` / `AttributeError` — service doesn't have CDM dispatch yet.

- [ ] **Step 3: Update `IndexProcessingService`**

In `backend/app/services/index_processing_service.py`:

Add `ParsedDocumentRepository` import near the top:

```python
from app.repositories.parsed_document_repository import ParsedDocumentRepository
```

In `start_processing()`, add after the existing "validate has documents" block:

```python
# Validate CDM mode: all pending documents must have parse_run_id set
if config.source_representation != "raw_text":
    for index_doc in index.index_documents:
        if index_doc.processing_status == IndexDocumentStatus.pending:
            if not index_doc.parse_run_id:
                raise ValidationError(
                    f"Document {index_doc.document_id} has no parse run set. "
                    "All documents require a parse run when source_representation "
                    "is not 'raw_text'."
                )
```

In `process_index()`, in the per-document loop, replace the existing text-fetching block:

```python
# Get document text based on source_representation
if config.source_representation == "raw_text":
    text = document.extracted_text
    if not text:
        raise ValueError("Document has no extracted text")
    source_type = "raw_text"
    doc_parse_run_id = None
elif config.source_representation == "full_text":
    parsed_doc_repo = ParsedDocumentRepository(self.session)
    parsed_doc = await parsed_doc_repo.get_by_run(index_doc.parse_run_id)
    if not parsed_doc or not parsed_doc.full_text:
        raise ValueError(
            f"Parse run {index_doc.parse_run_id} did not produce full_text. "
            "Re-parse with a configuration that outputs full text."
        )
    text = parsed_doc.full_text
    source_type = "full_text"
    doc_parse_run_id = index_doc.parse_run_id
else:
    raise NotImplementedError(
        f"source_representation '{config.source_representation}' not yet supported"
    )
```

Update the chunk data assembly to include provenance fields:

```python
chunk_data.append({
    "index_id": index_id,
    "document_id": doc_id,
    "content": chunk.content,
    "embedding": embedding,
    "chunk_index": chunk.chunk_index,
    "token_count": chunk.token_count,
    "char_count": chunk.char_count,
    "chunk_metadata": chunk.metadata,
    "index_version": index.version + 1,
    "parse_run_id": str(doc_parse_run_id) if doc_parse_run_id else None,
    "source_type": source_type,
})
```

After `await self.index_repo.update_stats(...)` and before determining final status, add:

```python
# Increment version and write audit event
await self.index_repo.increment_version(index_id)
await self.index_repo.write_index_event(
    index_id=index_id,
    version=index.version + 1,
    config_snapshot=config.model_dump(mode="json"),
    document_bindings={
        str(doc.document_id): str(doc.parse_run_id) if doc.parse_run_id else None
        for doc in index.index_documents
    },
    triggered_by=user_id,
)
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
uv run --directory backend python -m pytest tests/services/test_index_processing_cdm.py -o "addopts=" -v
```

Expected: all PASS.

- [ ] **Step 5: Run full test suite to check regressions**

```bash
uv run --directory backend python -m pytest tests/ -o "addopts=" -v --ignore=tests/cdm/eval
```

Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/index_processing_service.py backend/tests/services/test_index_processing_cdm.py
git commit -m "feat(service): add CDM dispatch in index processing — full_text sourcing + version increment on reprocess"
```

---

## Task 7: Service and router — thread `parse_run_ids` through add_documents

**Files:**
- Modify: `backend/app/services/index_service.py`
- Modify: `backend/app/routers/indexes.py`

- [ ] **Step 1: Write failing test**

Add to `backend/tests/services/test_index_processing_cdm.py`:

```python
from app.services.index_service import IndexService
from app.schemas.index import AddDocumentsRequest


@pytest.mark.asyncio
async def test_add_documents_passes_parse_run_ids_to_repo():
    doc_id = uuid4()
    run_id = uuid4()

    index_repo = AsyncMock()
    index_repo.get_by_id = AsyncMock(return_value=MagicMock(
        id=uuid4(),
        project_id=uuid4(),
        status=IndexStatus.created,
        index_documents=[],
    ))
    index_repo.add_documents = AsyncMock(return_value=[])
    index_repo.get_document_ids = AsyncMock(return_value=[doc_id])
    index_repo.count_documents = AsyncMock(return_value=1)
    index_repo.count_chunks = AsyncMock(return_value=0)

    service = IndexService(index_repo=index_repo, chunk_repo=AsyncMock())
    request = AddDocumentsRequest(
        document_ids=[doc_id],
        parse_run_ids={doc_id: run_id},
    )

    await service.add_documents(uuid4(), uuid4(), request)

    index_repo.add_documents.assert_called_once()
    call_kwargs = index_repo.add_documents.call_args
    assert call_kwargs.kwargs.get("parse_run_ids") == {doc_id: run_id} or \
           (len(call_kwargs.args) > 2 and call_kwargs.args[2] == {doc_id: run_id})
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
uv run --directory backend python -m pytest tests/services/test_index_processing_cdm.py::test_add_documents_passes_parse_run_ids_to_repo -o "addopts=" -v
```

Expected: FAIL — `add_documents` in `IndexService` ignores `parse_run_ids`.

- [ ] **Step 3: Update `IndexService.add_documents`**

In `backend/app/services/index_service.py`, find `add_documents` and update its signature and repo call:

```python
async def add_documents(
    self,
    index_id: UUID,
    project_id: UUID,
    request: "AddDocumentsRequest",
) -> IndexResponse:
    """Add documents to an index."""
    from app.schemas.index import AddDocumentsRequest
    index = await self.index_repo.get_by_id(index_id, project_id)
    if not index:
        raise NotFoundError(f"Index {index_id} not found")

    await self.index_repo.add_documents(
        index_id=index_id,
        document_ids=request.document_ids,
        parse_run_ids=request.parse_run_ids,
    )
    return await self.get_index(index_id, project_id)
```

- [ ] **Step 4: Update the router to pass the full request object**

In `backend/app/routers/indexes.py`, update `add_documents` handler:

```python
@router.post("/{index_id}/documents", response_model=IndexResponse)
async def add_documents(
    project_id: UUID,
    index_id: UUID,
    data: AddDocumentsRequest,
    current_user: User = Depends(get_current_active_user),
    service: IndexService = Depends(get_index_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    await verify_project_access(project_id, current_user, project_repo)
    try:
        return await service.add_documents(index_id, project_id, data)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
```

- [ ] **Step 5: Run test — expect PASS**

```bash
uv run --directory backend python -m pytest tests/services/test_index_processing_cdm.py -o "addopts=" -v
```

Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/index_service.py backend/app/routers/indexes.py
git commit -m "feat(service/router): thread parse_run_ids through add_documents"
```

---

## Task 8: `IndexService._to_response` — surface version and config_dirty

**Files:**
- Modify: `backend/app/services/index_service.py`

- [ ] **Step 1: Write failing test**

Add to `backend/tests/services/test_index_processing_cdm.py`:

```python
from app.services.index_service import IndexService


def test_index_response_includes_version_and_config_dirty():
    index = MagicMock()
    index.id = uuid4()
    index.project_id = uuid4()
    index.name = "my-index"
    index.description = None
    index.config = {
        "chunking_strategy": "recursive_character",
        "source_representation": "raw_text",
        "chunk_size": 512,
        "chunk_overlap": 50,
        "chunk_unit": "characters",
        "embedding_provider": "openai",
        "embedding_model": "text-embedding-3-small",
        "embedding_dimensions": None,
    }
    index.stats = None
    index.status = IndexStatus.created
    index.error_message = None
    index.created_by = uuid4()
    index.created_at = MagicMock()
    index.updated_at = MagicMock()
    index.version = 3
    index.config_dirty = True

    service = IndexService(index_repo=MagicMock(), chunk_repo=MagicMock())
    response = service._to_response(index)

    assert response.version == 3
    assert response.config_dirty is True
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
uv run --directory backend python -m pytest tests/services/test_index_processing_cdm.py::test_index_response_includes_version_and_config_dirty -o "addopts=" -v
```

Expected: FAIL — response doesn't include version/config_dirty yet.

- [ ] **Step 3: Update `_to_response` in `IndexService`**

In `backend/app/services/index_service.py`, update `_to_response`:

```python
def _to_response(self, index, include_counts: bool = True) -> IndexResponse:
    config = IndexConfig.model_validate(index.config)
    stats = IndexStats.model_validate(index.stats) if index.stats else None

    response_data = {
        "id": index.id,
        "project_id": index.project_id,
        "name": index.name,
        "description": index.description,
        "config": config,
        "stats": stats,
        "status": index.status.value,
        "error_message": index.error_message,
        "created_by": index.created_by,
        "created_at": index.created_at,
        "updated_at": index.updated_at,
        "version": getattr(index, "version", 1),
        "config_dirty": getattr(index, "config_dirty", False),
        "document_count": 0,
        "chunk_count": 0,
    }
    return IndexResponse.model_validate(response_data)
```

- [ ] **Step 4: Run test — expect PASS**

```bash
uv run --directory backend python -m pytest tests/services/test_index_processing_cdm.py -o "addopts=" -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/index_service.py
git commit -m "feat(service): surface version and config_dirty in IndexResponse"
```

---

## Task 9: Frontend types and API client

**Files:**
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/api/indexes.ts`

- [ ] **Step 1: Update `IndexConfig` type in `frontend/src/types/index.ts`**

Replace the existing `IndexConfig` interface:

```typescript
export type SourceRepresentation = 'raw_text' | 'full_text' | 'full_markdown' | 'block'

export type ChunkingStrategy =
  | 'fixed_size'
  | 'recursive_character'
  | 'markdown_heading'
  | 'block'
  | 'classified_block'

export interface IndexConfig {
  // CDM binding
  sourceRepresentation: SourceRepresentation
  parser: string | null
  parseConfigHash: string | null
  // Chunking
  chunkingStrategy: ChunkingStrategy
  chunkSize: number
  chunkOverlap: number
  chunkUnit: 'tokens' | 'characters'
  // Embedding
  embeddingProvider: string
  embeddingModel: string
  embeddingDimensions: number | null
}
```

- [ ] **Step 2: Update `Index` type**

In the `Index` interface, add:

```typescript
version: number
configDirty: boolean
```

Remove `parsingStrategy` if present.

- [ ] **Step 3: Update `AddDocumentsRequest` type**

```typescript
export interface AddDocumentsRequest {
  documentIds: string[]
  parseRunIds?: Record<string, string>  // document_id → parse_run_id
}
```

- [ ] **Step 4: Update `frontend/src/api/indexes.ts` — `createIndex`**

Update the config object sent in `createIndex`:

```typescript
config: {
  source_representation: data.config.sourceRepresentation ?? 'raw_text',
  parser: data.config.parser ?? null,
  parse_config_hash: data.config.parseConfigHash ?? null,
  chunking_strategy: data.config.chunkingStrategy,
  chunk_size: data.config.chunkSize,
  chunk_overlap: data.config.chunkOverlap,
  chunk_unit: data.config.chunkUnit,
  embedding_provider: data.config.embeddingProvider,
  embedding_model: data.config.embeddingModel,
  embedding_dimensions: data.config.embeddingDimensions,
},
```

- [ ] **Step 5: Update `addDocuments` in `frontend/src/api/indexes.ts`**

```typescript
export async function addDocuments(
  projectId: string,
  indexId: string,
  data: AddDocumentsRequest
): Promise<Index> {
  const response = await apiClient.post<Index>(
    `/projects/${projectId}/indexes/${indexId}/documents`,
    {
      documentIds: data.documentIds,
      parseRunIds: data.parseRunIds ?? null,
    }
  )
  return response.data
}
```

- [ ] **Step 6: Fix type errors in pages that reference `parsingStrategy`**

Run TypeScript check:

```bash
npm --prefix frontend run build 2>&1 | grep -E "error TS|parsingStrategy"
```

For any file referencing `parsingStrategy`, remove or replace with `sourceRepresentation`. The most likely files are `CreateIndexPage.tsx` and `ChunkPreviewPanel.tsx`. Replace `parsingStrategy: 'static'` with `sourceRepresentation: 'raw_text'` in `DEFAULT_CONFIG`.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/api/indexes.ts
git commit -m "feat(frontend): update IndexConfig types — add sourceRepresentation, version, configDirty; remove parsingStrategy"
```

---

## Task 10: Frontend UI — version badge and parse run column

**Files:**
- Modify: `frontend/src/pages/IndexDetailPage.tsx`

- [ ] **Step 1: Add version badge to the index detail header**

In `frontend/src/pages/IndexDetailPage.tsx`, find line 309–319 (the non-editing branch of the name header):

```tsx
// BEFORE (line 309–319):
<div className="flex items-center gap-2 group">
  <h1 className="text-xl font-semibold">{index.name}</h1>
  {canEdit && (
    <button
      onClick={() => setEditingName(true)}
      className="p-1 rounded-md text-muted-foreground/40 hover:text-muted-foreground opacity-0 group-hover:opacity-100 transition-all"
    >
      <Pencil className="h-3.5 w-3.5" />
    </button>
  )}
</div>
```

Replace with:

```tsx
// AFTER:
<div className="flex items-center gap-2 group">
  <h1 className="text-xl font-semibold">{index.name}</h1>
  <span className="text-xs text-muted-foreground font-mono bg-muted px-1.5 py-0.5 rounded">
    v{index.version ?? 1}
  </span>
  {canEdit && (
    <button
      onClick={() => setEditingName(true)}
      className="p-1 rounded-md text-muted-foreground/40 hover:text-muted-foreground opacity-0 group-hover:opacity-100 transition-all"
    >
      <Pencil className="h-3.5 w-3.5" />
    </button>
  )}
</div>
```

- [ ] **Step 2: Add parse run column to the document list table**

The document list table is the chunks table at line ~555. This table shows chunks, not index documents. The index document list lives higher up in the page (the document accordion). For Slice 1, add a "Parse run" column skeleton to the `index.documentIds` list only — the full implementation is Slice 5.

In the section that renders `indexDocuments` (search for `indexDocuments.map`), find the row that shows each document and add a muted "—" cell after the existing cells:

```tsx
<TableCell className="text-muted-foreground text-sm">—</TableCell>
```

And add the corresponding header `<TableHead>Parse run</TableHead>` in the `<TableHeader>` row above.

Note: The full parse run display (parser name, config, date, "Needs parsing" state) is Slice 5. The "—" placeholder ensures the column exists in the correct position.

- [ ] **Step 3: Run the dev server and verify visually**

```bash
npm --prefix frontend run dev
```

Navigate to an index detail page. Verify:
- Version badge shows "v1" next to the index name
- Document list has a "Parse run" column (showing "—" for now)

- [ ] **Step 4: Run lint**

```bash
npm --prefix frontend run lint
```

Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/IndexDetailPage.tsx
git commit -m "feat(ui): add version badge and parse run column skeleton to IndexDetailPage"
```

---

## Task 11: Run full test suite and fix any regressions

- [ ] **Step 1: Run all backend tests**

```bash
uv run --directory backend python -m pytest tests/ -o "addopts=" -v --ignore=tests/cdm/eval
```

Expected: all PASS. If any existing test creates `IndexConfig` with `parsing_strategy`, remove that field from the test — `IndexConfig` no longer has it.

- [ ] **Step 2: Run frontend build**

```bash
npm --prefix frontend run build
```

Expected: builds without TypeScript errors. The pre-existing chunk size warning is not a failure.

- [ ] **Step 3: Final commit**

```bash
git add frontend/src/types/index.ts frontend/src/api/indexes.ts frontend/src/pages/IndexDetailPage.tsx frontend/src/pages/CreateIndexPage.tsx
git commit -m "chore: fix any type regressions from CDM index slice 1"
```

---

## E2E Validation Checklist

After all tasks complete, verify end-to-end:

1. Run `alembic upgrade head` — migration applies cleanly
2. Create a document, trigger a LlamaParse run, confirm `ParsedDocument.full_text` is populated via the API (`GET /parse-runs/{id}/parsed-document`)
3. Create an index via the API with:
   ```json
   {
     "name": "cdm-test",
     "documentIds": ["<doc_id>"],
     "config": {
       "source_representation": "full_text",
       "parser": "llamaparse",
       "parse_config_hash": "<hash_from_parse_run>",
       "chunking_strategy": "recursive_character"
     }
   }
   ```
   with `parseRunIds: { "<doc_id>": "<parse_run_id>" }` in the add-documents call
4. Trigger processing (`POST /indexes/{id}/process`)
5. Fetch chunks (`GET /indexes/{id}/chunks`) — verify `source_type = "full_text"` in chunk metadata
6. Fetch the index (`GET /indexes/{id}`) — verify `version = 1`, `configDirty = false`
7. Trigger reprocess — verify `version = 2` and two rows in `index_events`
8. Open the index detail page in the browser — verify "v2" badge is visible
