# CDM Index — Unit 3: Request Shape Tightening + Bridge Removal

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Spec:** [`docs/superpowers/specs/2026-04-29-cdm-index-parser-config-selector.md`](../specs/2026-04-29-cdm-index-parser-config-selector.md) §3, §4, §5 (last paragraph), §"Migration"
**Depends on:** Unit 2 (source-resolution seam — PR #49) merged into `main`. Unit 1 (parsed-doc reads + ORM tighten — PR #47) and slice-2 (markdown chunking — PR #45) are also precursors.
**Issue:** [#50](https://github.com/asanyaga/rag-admin/issues/50)

**Goal:** Make `parsed_document_id` the canonical wire shape across the index API. Drop the `raw_text` source-representation, the per-row `(document_id, parse_run_id)` binding shape, and the temporary `documentId` bridge on chunk preview. Cascade-delete legacy raw_text indexes to align the database with the new schema.

**Architecture:** Breaking, primarily in the request/response wire format and the `IndexConfig` schema. Backend collapses the `raw_text` branch in `IndexProcessingService.process_index()` and the `IndexConfig` Literal; `IndexCreate` and `AddDocumentsRequest` collapse to flat `parsed_document_ids: list[UUID]` lists; `ChunkPreviewRequest` requires `parsedDocumentId`. `IndexService.create_index()` and `add_parsed_documents()` validate each parsed-doc against the declared family and segment. The wizard UI is **not** yet rebuilt (that's Unit 4) — instead it gains a thin client-side adapter that resolves the user's existing document selection to parsed-doc IDs at submit time, so the wizard keeps working until the parsed-doc picker lands. The data migration cascade-deletes legacy raw_text indexes (rows with `parse_run_id IS NULL`); pre-prod nature of the project makes this acceptable per the spec.

**Tech Stack:** Python 3.12 · FastAPI async · SQLAlchemy 2.0 async · Alembic · Pydantic v2 · pytest · React 18 · TypeScript · Vitest

---

## Scope and breaking changes

| Area | Before | After Unit 3 |
|---|---|---|
| `IndexConfig.source_representation` | `Literal["raw_text", "full_text", "full_markdown", "block"]`, default `"raw_text"` | `Literal["full_text", "full_markdown", "block"]`, default `"full_text"` |
| `IndexConfig.parser` / `parse_config_hash` | optional, no validator | optional fields but **required at validation time** via `require_family_for_indexing` model_validator |
| `IndexCreate` body | `documentIds: list[UUID]` | `parsedDocumentIds: list[UUID]` |
| `AddDocumentsRequest` | `{documentIds, parseRunIds}` | renamed `AddParsedDocumentsRequest` with `parsedDocumentIds: list[UUID]` |
| Route | `POST /projects/{p}/indexes/{id}/documents` | `POST /projects/{p}/indexes/{id}/parsed-documents` |
| Validation in `create_index` / `add_parsed_documents` | unchecked document IDs | each parsed-doc validated: exists, in project, parse_run.parser+config_hash matches `IndexConfig.(parser, parse_config_hash)`, segment populated, status succeeded |
| `ChunkPreviewRequest` | `documentId?` + `parsedDocumentId?` (exactly one) | `parsedDocumentId` (required) — no bridge |
| `ChunkingService.preview_chunks(...)` | called from raw_text branch of preview endpoint | callers gone; legacy method may stay (used internally by router projection helper) |
| `ParsedDocumentRepository.get_latest_for_document` | bridge helper | **deleted** |
| `IndexProcessingService.process_index()` | `if raw_text: ... elif CDM: ... else: ...` | only CDM branch + `else: NotImplementedError` |
| Database | mixed legacy raw_text + CDM rows | legacy raw_text indexes cascade-deleted |
| Wizard | submits `documentIds` | submits `parsedDocumentIds`, computed from selected documents at submit time (Unit 4 replaces this with a real picker) |
| Source-rep toggle | three options including `Raw text` | two options: `Full text`, `Full Markdown` (`block` deferred to a future unit's UI) |

### Out of scope (deferred)

- `index_documents.parse_run_id NOT NULL` constraint — Unit 6 cleanup, after Unit 4 (wizard) and Unit 5 (index detail) ship and the new flow is validated.
- Wizard rebuild (parse-config family selector + parsed-doc picker) — Unit 4.
- Index detail "Parsed Documents" tab — Unit 5.
- Block chunking implementation — future unit (the dispatcher still raises `NotImplementedError`).

---

## Pre-implementation gate

- [ ] **Step P1 — Create the GitHub issue and confirm with user.**

```bash
gh issue create \
  --title "feat(index): IndexCreate parsed_document_ids shape + drop raw_text (Unit 3)" \
  --body "$(cat <<'EOF'
## Summary
Third unit of the CDM-index parsed-document refactor. Makes `parsed_document_id`
the canonical wire shape across the index API. Drops `raw_text` from
`IndexConfig.source_representation`, replaces `documentIds` + `parseRunIds`
with flat `parsedDocumentIds`, removes the `documentId` bridge from chunk
preview, and cascade-deletes legacy raw_text indexes.

The wizard UI is not yet rebuilt — it gains a thin client-side adapter that
resolves the user's existing document selection to parsed-doc IDs at submit
time, so it keeps working until the parsed-doc picker lands in Unit 4.

## Acceptance criteria
- [ ] Alembic migration cascade-deletes `index_documents` rows with `parse_run_id IS NULL` and the indexes left empty as a result.
- [ ] `IndexConfig.source_representation` Literal drops `raw_text`; default is now `full_text`. The strategy-vs-representation validator no longer mentions raw_text.
- [ ] `IndexConfig` `require_family_for_indexing` model_validator raises when `parser` or `parse_config_hash` is `None`.
- [ ] `IndexCreate` exposes `parsed_document_ids: list[UUID]` (alias `parsedDocumentIds`); `documentIds` is removed.
- [ ] `AddDocumentsRequest` is renamed `AddParsedDocumentsRequest` with `parsed_document_ids: list[UUID]` (alias `parsedDocumentIds`, min_length=1).
- [ ] `IndexService.create_index()` and `add_parsed_documents()` validate each parsed-doc: exists, in project, family match, segment populated, parse run status succeeded. Each validation failure produces a 404 (missing) or 400 (validation) listing the offending IDs.
- [ ] Route `POST /projects/{p}/indexes/{id}/documents` becomes `/parsed-documents`. The DELETE on a single document still uses `document_id` (legacy until Unit 5).
- [ ] `ChunkPreviewRequest.parsed_document_id` is required; `document_id` is gone. Preview endpoint loses the `documentId` and `raw_text` bridge branches.
- [ ] `ParsedDocumentRepository.get_latest_for_document` is deleted.
- [ ] `IndexProcessingService.process_index()` no longer has a `raw_text` branch.
- [ ] Frontend wizard submits `parsedDocumentIds` derived from the user's document selection; the source-rep toggle drops `Raw text`.
- [ ] All existing tests pass, plus new tests covering the validators, the new shape, and the migration.

## Spec
docs/superpowers/specs/2026-04-29-cdm-index-parser-config-selector.md (§3, §4, §5)

## Plan
docs/superpowers/plans/2026-04-30-cdm-index-parsed-doc-unit-3-shape-tightening.md
EOF
)" \
  --label "enhancement"
```

After the issue is created, confirm the number with the user, then update this file's `**Issue:**` line with `#<n>` before continuing.

---

## File map

### Backend

| Action | Path | What changes |
|---|---|---|
| **Create** | `backend/alembic/versions/<rev>_cascade_delete_legacy_raw_text_indexes.py` | Data migration: delete legacy raw_text indexes |
| Modify | `backend/app/schemas/index.py` | `IndexConfig` (drop `raw_text` from Literal, default `full_text`, add `require_family_for_indexing` validator, update strategy-vs-rep validator); replace `IndexCreate.document_ids` with `parsed_document_ids`; rename `AddDocumentsRequest` to `AddParsedDocumentsRequest` with new shape; `ChunkPreviewRequest` drops `document_id`, makes `parsed_document_id` required |
| Modify | `backend/app/repositories/index_repository.py` | Add `add_parsed_documents(index_id, parsed_document_ids)` method (resolves parsed-docs to IndexDocument rows); leave `add_documents` for now or remove if unused after refactor |
| Modify | `backend/app/repositories/parsed_document_repository.py` | Remove `get_latest_for_document` |
| Modify | `backend/app/services/index_service.py` | `create_index` validates parsed-docs and calls `add_parsed_documents`; `add_documents` renamed to `add_parsed_documents` and switched to new shape; both share a `_validate_parsed_documents` helper |
| Modify | `backend/app/services/index_processing_service.py` | Drop the `raw_text` branch in `process_index()`; simplify the `start_processing` validator that special-cased raw_text |
| Modify | `backend/app/routers/indexes.py` | Route rename `/documents` → `/parsed-documents` for the POST; drop `documentId` bridge + `raw_text` branch in preview endpoint; replace request schemas |
| Modify | `backend/tests/schemas/test_index_config_schema.py` | Add `require_family_for_indexing` tests; remove obsolete raw_text rows; tighten existing tests |
| Modify | `backend/tests/services/test_index_processing_cdm.py` | Drop / update raw_text tests |
| Modify | `backend/tests/routers/test_preview_chunks_router.py` | Remove the bridge + raw_text tests; tighten `parsedDocumentId`-required test |
| **Create** | `backend/tests/repositories/test_index_repository_add_parsed_documents.py` | New `add_parsed_documents` repository test |
| **Create** | `backend/tests/services/test_index_service_create_index_validation.py` | Service-level validation tests (family mismatch, segment missing, foreign project, failed run) |
| **Create** | `backend/tests/migrations/test_cascade_delete_legacy_raw_text.py` | Migration data-flow test |
| Delete | `backend/tests/repositories/test_parsed_document_repository_get_latest.py` | Bridge helper test, no longer needed |

### Frontend

| Action | Path | What changes |
|---|---|---|
| Modify | `frontend/src/types/index.ts` | `IndexCreate`-shaped types: `parsedDocumentIds` instead of `documentIds`; `ChunkPreviewRequest` drops `documentId`, makes `parsedDocumentId` required; `IndexConfig.sourceRepresentation` Literal drops `raw_text` |
| Modify | `frontend/src/api/indexes.ts` | `createIndex` sends `parsedDocumentIds`; `addDocuments` renamed `addParsedDocuments` and POSTs to `/parsed-documents`; `previewChunks` no longer sends `documentId` |
| Modify | `frontend/src/hooks/useIndexes.ts` | Hook signatures + types updated to match the new shape |
| **Create** | `frontend/src/lib/parsed-documents.ts` (or extend an existing util) | `resolveLatestParsedDocsForDocuments(projectId, documentIds, family?)` helper that calls `GET /parsed-documents`, picks latest succeeded per source document, infers parser+parseConfigHash from the chosen rows; throws on multi-family |
| Modify | `frontend/src/components/indexes/IndexCreateDialog.tsx` | Source-rep toggle drops `Raw text`; on submit, runs the resolver, sets `config.parser` + `config.parseConfigHash`, sends `parsedDocumentIds` |
| Modify | `frontend/src/pages/CreateIndexPage.tsx` | Same wizard adapter + same toggle change for parity |
| Modify | `frontend/src/components/indexes/IndexCreateDialog.test.tsx` | Update wizard tests for the new submit flow |
| Modify | `frontend/src/pages/CreateIndexPage.test.tsx` (if exists) | Same |

---

## Implementation tasks (TDD)

### Task 1 — Cascade-delete legacy raw_text data (Alembic migration)

**Files:**
- Create: `backend/alembic/versions/<rev>_cascade_delete_legacy_raw_text_indexes.py`
- Create: `backend/tests/migrations/test_cascade_delete_legacy_raw_text.py`

This is the first thing that must land — before the schema validators tighten, the database needs to lose the rows that would fail validation. The migration is a pure data delete, no schema change.

- [ ] **1.1 Generate the empty migration.**

```bash
uv run --directory /home/asa/rag-admin/backend alembic revision -m "cascade delete legacy raw_text indexes"
```

(Use `revision`, not `--autogenerate` — there's no schema change to detect.)

Find the new file under `backend/alembic/versions/<rev>_cascade_delete_legacy_raw_text_indexes.py`.

- [ ] **1.2 Write the migration body.** Replace the generated stub with:

```python
"""cascade delete legacy raw_text indexes

Revision ID: <rev>
Revises: <down_revision>
Create Date: 2026-04-30 ...

CDM Index Unit 3 cleanup: deletes any `indexes` row that has at least one
`index_documents` row with `parse_run_id IS NULL`. Those rows pre-date the
parsed-document model and would fail post-Unit-3 schema validation.

The cascade is via existing FK ON DELETE CASCADE on `index_documents`,
`chunks`, and `index_events` against `indexes.id`.
"""
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "<rev>"
down_revision: str | None = "<down_revision>"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM indexes
        WHERE id IN (
            SELECT DISTINCT index_id FROM index_documents
            WHERE parse_run_id IS NULL
        )
        """
    )


def downgrade() -> None:
    # Data delete is non-reversible; downgrade is a no-op.
    pass
```

Replace `<rev>` and `<down_revision>` with the actual values Alembic generated. Keep the ones Alembic chose — do not edit revision IDs.

- [ ] **1.3 Write a migration data-flow test.** Create `backend/tests/migrations/test_cascade_delete_legacy_raw_text.py`:

```python
"""Test the Unit 3 cascade-delete-legacy-raw_text migration."""
import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4
from datetime import datetime, timezone

from app.models.document import Document as DocumentORM
from app.models.index import Index, IndexDocument, IndexStatus, IndexDocumentStatus
from app.models.parse_run import ParseRun
from app.models.parsed_document import ParsedDocument
from app.models.project import Project
from app.models.source_document import SourceDocument
from app.models.user import User


@pytest.mark.asyncio
async def test_cascade_delete_keeps_cdm_indexes_drops_raw_text_indexes(test_db: AsyncSession):
    user = User(email="m@example.com", hashed_password="x", full_name="m")
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)

    project = Project(user_id=user.id, name="P")
    test_db.add(project)
    await test_db.commit()
    await test_db.refresh(project)

    sd = SourceDocument(id=uuid4(), sha256="a" * 64, storage_uri="local://a.pdf")
    test_db.add(sd)
    await test_db.commit()

    doc = DocumentORM(
        project_id=project.id,
        source_document_id=sd.id,
        source_type="upload",
        source_identifier="a",
        title="A",
        status="ready",
        created_by=user.id,
    )
    test_db.add(doc)
    await test_db.commit()
    await test_db.refresh(doc)

    pr = ParseRun(
        source_document_id=sd.id,
        parser="llamaparse",
        representation_kind="full_text",
        config={},
        config_hash="h" * 64,
        status="succeeded",
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
    )
    test_db.add(pr)
    await test_db.commit()
    await test_db.refresh(pr)

    pd = ParsedDocument(
        parse_run_id=pr.id,
        source_document_id=sd.id,
        full_text="hello",
        full_markdown=None,
        page_count=1,
        block_count=1,
        content={"blocks": [{"text": "hello"}]},
    )
    test_db.add(pd)
    await test_db.commit()

    legacy_idx = Index(
        project_id=project.id,
        name="legacy-raw-text",
        config={"source_representation": "raw_text"},
        status=IndexStatus.created,
        created_by=user.id,
    )
    cdm_idx = Index(
        project_id=project.id,
        name="cdm-full-text",
        config={"source_representation": "full_text"},
        status=IndexStatus.created,
        created_by=user.id,
    )
    test_db.add_all([legacy_idx, cdm_idx])
    await test_db.commit()
    await test_db.refresh(legacy_idx)
    await test_db.refresh(cdm_idx)

    legacy_doc = IndexDocument(
        index_id=legacy_idx.id,
        document_id=doc.id,
        processing_status=IndexDocumentStatus.completed,
        parse_run_id=None,  # legacy
    )
    cdm_doc = IndexDocument(
        index_id=cdm_idx.id,
        document_id=doc.id,
        processing_status=IndexDocumentStatus.completed,
        parse_run_id=pr.id,
    )
    test_db.add_all([legacy_doc, cdm_doc])
    await test_db.commit()

    # Run the migration's DELETE statement directly.
    await test_db.execute(
        text(
            """
            DELETE FROM indexes
            WHERE id IN (
                SELECT DISTINCT index_id FROM index_documents
                WHERE parse_run_id IS NULL
            )
            """
        )
    )
    await test_db.commit()

    legacy_after = await test_db.execute(
        select(Index).where(Index.id == legacy_idx.id)
    )
    cdm_after = await test_db.execute(
        select(Index).where(Index.id == cdm_idx.id)
    )

    assert legacy_after.scalar_one_or_none() is None, "legacy raw_text index should be deleted"
    assert cdm_after.scalar_one_or_none() is not None, "CDM index should survive"
```

Note: the SQLite test DB does not enforce FK CASCADE by default, so the assertion checks the *primary* delete only. The cascade behaviour is verified manually against the real Postgres dev DB in step 1.5.

- [ ] **1.4 Run tests — verify red, then green after pasting the migration.**

```bash
uv run --directory /home/asa/rag-admin/backend python -m pytest tests/migrations/test_cascade_delete_legacy_raw_text.py -o "addopts=" -v
```

(The migration file's existence isn't required for this test — it only exercises the SQL. So "red" is "test doesn't exist yet"; once the test is written it should pass on its own.)

- [ ] **1.5 Apply the migration to the local dev Postgres and spot-check cascade.**

```bash
docker compose -f /home/asa/rag-admin/docker-compose.local.yml exec backend alembic upgrade head
docker compose -f /home/asa/rag-admin/docker-compose.local.yml exec postgres \
    psql -U postgres -d rag_admin -c \
    "SELECT id, name, config->>'source_representation' AS rep FROM indexes ORDER BY created_at DESC LIMIT 20"
```

Expected: any pre-existing legacy raw_text indexes are gone; CDM indexes (full_text / full_markdown) remain. Cross-check `index_documents` and `chunks` counts dropped accordingly.

- [ ] **1.6 Commit.**

```bash
git -C <worktree-path> add \
  backend/alembic/versions/<rev>_cascade_delete_legacy_raw_text_indexes.py \
  backend/tests/migrations/test_cascade_delete_legacy_raw_text.py
git -C <worktree-path> commit -m "$(cat <<'EOF'
feat(migrations): cascade-delete legacy raw_text indexes

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

(Substitute the actual worktree path created in the implementation session.)

---

### Task 2 — `IndexConfig` schema changes

**Files:**
- Modify: `backend/app/schemas/index.py:17-84` (`IndexConfig` class)
- Modify: `backend/tests/schemas/test_index_config_schema.py`

- [ ] **2.1 Update existing tests + add new tests (red).** In `backend/tests/schemas/test_index_config_schema.py`:

```python
import pytest
from pydantic import ValidationError as PydanticValidationError

from app.schemas.index import IndexConfig


def _valid_config_kwargs(**overrides):
    base = {
        "parser": "llamaparse",
        "parse_config_hash": "h" * 64,
        "source_representation": "full_text",
        "chunking_strategy": "recursive_character",
        "chunk_size": 500,
        "chunk_overlap": 50,
        "chunk_unit": "characters",
        "embedding_provider": "openai",
        "embedding_model": "text-embedding-3-small",
    }
    base.update(overrides)
    return base


def test_index_config_default_source_representation_is_full_text():
    cfg = IndexConfig.model_validate(_valid_config_kwargs())
    assert cfg.source_representation == "full_text"


def test_index_config_rejects_legacy_raw_text():
    with pytest.raises(PydanticValidationError, match="source_representation"):
        IndexConfig.model_validate(_valid_config_kwargs(source_representation="raw_text"))


def test_index_config_requires_parser_and_parse_config_hash():
    with pytest.raises(PydanticValidationError, match="parser and parse_config_hash"):
        IndexConfig.model_validate(_valid_config_kwargs(parser=None))
    with pytest.raises(PydanticValidationError, match="parser and parse_config_hash"):
        IndexConfig.model_validate(_valid_config_kwargs(parse_config_hash=None))


def test_index_config_full_markdown_requires_markdown_strategy():
    with pytest.raises(PydanticValidationError, match="full_markdown"):
        IndexConfig.model_validate(_valid_config_kwargs(
            source_representation="full_markdown",
            chunking_strategy="recursive_character",
        ))


def test_index_config_full_text_accepts_recursive_character():
    cfg = IndexConfig.model_validate(_valid_config_kwargs(
        source_representation="full_text",
        chunking_strategy="recursive_character",
    ))
    assert cfg.chunking_strategy == "recursive_character"


def test_index_config_block_requires_block_strategy():
    cfg = IndexConfig.model_validate(_valid_config_kwargs(
        source_representation="block",
        chunking_strategy="block",
    ))
    assert cfg.chunking_strategy == "block"


def test_index_config_block_rejects_text_strategy():
    with pytest.raises(PydanticValidationError, match="block"):
        IndexConfig.model_validate(_valid_config_kwargs(
            source_representation="block",
            chunking_strategy="recursive_character",
        ))
```

Remove any pre-existing test that asserted `raw_text` is a valid representation. Keep tests that verify chunk_overlap and other existing validators.

- [ ] **2.2 Run tests — verify red.**

```bash
uv run --directory /home/asa/rag-admin/backend python -m pytest tests/schemas/test_index_config_schema.py -o "addopts=" -v
```

Expected: tests fail with messages indicating `raw_text` is still accepted, the family validator doesn't exist, and the default is still `raw_text`.

- [ ] **2.3 Implement (green).** Replace `IndexConfig` in `backend/app/schemas/index.py:17-84` with:

```python
class IndexConfig(BaseModel):
    """Configuration for how documents are chunked and embedded."""

    # Parse-config family — both required at validation time. Optional types
    # let the wizard build IndexConfig progressively before binding the family.
    parser: str | None = Field(default=None)
    parse_config_hash: str | None = Field(default=None, alias="parseConfigHash")
    source_representation: Literal["full_text", "full_markdown", "block"] = Field(
        default="full_text", alias="sourceRepresentation"
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

    # Markdown-based config (markdown_heading)
    split_heading_level: int = Field(default=2, ge=1, le=3, alias="splitHeadingLevel")
    max_section_chars: int = Field(default=4000, ge=500, le=16000, alias="maxSectionChars")

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
    def require_family_for_indexing(self) -> "IndexConfig":
        if self.parser is None or self.parse_config_hash is None:
            raise ValueError(
                "IndexConfig requires parser and parse_config_hash"
            )
        return self

    @model_validator(mode="after")
    def validate_representation_and_strategy(self) -> "IndexConfig":
        rep = self.source_representation
        strategy = self.chunking_strategy

        text_strategies = {"fixed_size", "recursive_character"}
        allowed: dict[str, set[str]] = {
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

- [ ] **2.4 Run tests — verify green.**

```bash
uv run --directory /home/asa/rag-admin/backend python -m pytest tests/schemas/test_index_config_schema.py -o "addopts=" -v
```

Expected: all configured tests pass.

⚠️ Other tests in the suite that constructed `IndexConfig` without `parser` / `parse_config_hash` will now fail. Don't fix them yet — they get fixed in their respective tasks (Task 5 for service tests, Task 7 for preview tests, etc.). Run a scoped pytest only on the schema test file in this step.

- [ ] **2.5 Commit.**

```bash
git -C <worktree-path> add backend/app/schemas/index.py backend/tests/schemas/test_index_config_schema.py
git -C <worktree-path> commit -m "$(cat <<'EOF'
feat(schemas): IndexConfig drops raw_text, requires parser+config_hash

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3 — `IndexCreate` and `AddParsedDocumentsRequest` schemas

**Files:**
- Modify: `backend/app/schemas/index.py:131-148` (`IndexCreate`), `:229-238` (`AddDocumentsRequest`)

- [ ] **3.1 Replace `IndexCreate` with the new shape.** In `backend/app/schemas/index.py`:

```python
class IndexCreate(BaseModel):
    """Schema for creating a new index."""
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=2000)
    parsed_document_ids: list[UUID] = Field(
        default_factory=list,
        alias="parsedDocumentIds",
        description="Parsed-document IDs to include in this index. Each must "
                    "match the family declared in `config.parser` and "
                    "`config.parse_config_hash`.",
    )
    config: IndexConfig = Field(default_factory=IndexConfig)
    auto_process: bool = Field(
        default=False,
        alias="autoProcess",
        description="Start processing immediately after creation",
    )

    model_config = ConfigDict(populate_by_name=True)
```

⚠️ `IndexConfig` no longer has a sensible default after Task 2 (the family fields are required). `Field(default_factory=IndexConfig)` will fail validation. Either drop the default and require `config` to be supplied, or keep the `default_factory=IndexConfig` and accept that any `IndexCreate` constructed without a `config` will fail at `IndexConfig`'s validator. The latter is fine — the only callers always pass a `config`, and the validator is a clearer error message than a missing-field error.

- [ ] **3.2 Replace `AddDocumentsRequest` with `AddParsedDocumentsRequest`.** In `backend/app/schemas/index.py`:

```python
class AddParsedDocumentsRequest(BaseModel):
    """Schema for adding parsed-documents to an existing index."""
    parsed_document_ids: list[UUID] = Field(
        ..., alias="parsedDocumentIds", min_length=1,
        description="Parsed-document IDs to add. Each is validated against the "
                    "index's declared family.",
    )

    model_config = ConfigDict(populate_by_name=True)
```

Remove the old `AddDocumentsRequest` class entirely. If anything in the codebase still imports `AddDocumentsRequest`, those call sites must be updated in this commit (the routers, the service, and any test). A grep before commit:

```bash
grep -rn "AddDocumentsRequest" /home/asa/rag-admin/backend
```

Replace each reference with `AddParsedDocumentsRequest`.

- [ ] **3.3 Run any test that imports `AddDocumentsRequest`.** Just to surface remaining call sites; the actual fixes come in Task 5.

```bash
uv run --directory /home/asa/rag-admin/backend python -m pytest -o "addopts=" --collect-only 2>&1 | grep -E "ImportError|ModuleNotFoundError|AddDocumentsRequest" | head
```

If any test file fails to collect because it imports `AddDocumentsRequest`, note them — they will be fixed in Tasks 5, 7.

- [ ] **3.4 Commit.**

```bash
git -C <worktree-path> add backend/app/schemas/index.py
git -C <worktree-path> commit -m "$(cat <<'EOF'
feat(schemas): IndexCreate.parsed_document_ids; rename AddDocumentsRequest

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

(Other tests in the suite will be broken at this point. They get fixed in subsequent tasks. The build still passes — broken tests don't break runtime.)

---

### Task 4 — `IndexRepository.add_parsed_documents`

**Files:**
- Modify: `backend/app/repositories/index_repository.py:166-187`
- Create: `backend/tests/repositories/test_index_repository_add_parsed_documents.py`

The repo method needs to take `parsed_document_ids` (which under the current 1:1 schema are `parse_run_id` UUIDs), look up the corresponding `parse_run_id`s (trivial — they're the same value), and insert `IndexDocument` rows with `parse_run_id` and `document_id` populated. We need to look up `document_id` from the parsed-doc's `source_document_id` → some Document in the project. (The first matching Document is fine since the Index already lives in the project.)

- [ ] **4.1 Write failing test.** Create `backend/tests/repositories/test_index_repository_add_parsed_documents.py`:

```python
"""Tests for IndexRepository.add_parsed_documents."""
import pytest
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document as DocumentORM
from app.models.index import Index, IndexDocument, IndexStatus, IndexDocumentStatus
from app.models.parse_run import ParseRun
from app.models.parsed_document import ParsedDocument
from app.models.project import Project
from app.models.source_document import SourceDocument
from app.models.user import User
from app.repositories.index_repository import IndexRepository


async def _seed_project(db: AsyncSession):
    user = User(email=f"u{uuid4().hex[:6]}@example.com", hashed_password="x", full_name="u")
    db.add(user)
    await db.commit()
    await db.refresh(user)
    project = Project(user_id=user.id, name=f"P{uuid4().hex[:6]}")
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return user, project


async def _seed_doc_with_parsed(
    db: AsyncSession, *, user: User, project: Project, sha: str
) -> tuple[DocumentORM, ParsedDocument]:
    sd = SourceDocument(id=uuid4(), sha256=sha, storage_uri=f"local://{sha[:6]}.pdf")
    db.add(sd)
    await db.commit()
    doc = DocumentORM(
        project_id=project.id, source_document_id=sd.id,
        source_type="upload", source_identifier=sha, title=sha[:6],
        status="ready", created_by=user.id,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    pr = ParseRun(
        source_document_id=sd.id, parser="llamaparse",
        representation_kind="full_text", config={}, config_hash="h" * 64,
        status="succeeded",
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
    )
    db.add(pr)
    await db.commit()
    await db.refresh(pr)
    pd = ParsedDocument(
        parse_run_id=pr.id, source_document_id=sd.id,
        full_text="hello", full_markdown=None,
        page_count=1, block_count=1, content={"blocks": [{"text": "hi"}]},
    )
    db.add(pd)
    await db.commit()
    return doc, pd


@pytest.mark.asyncio
async def test_add_parsed_documents_creates_index_documents_with_parse_run_id(test_db: AsyncSession):
    user, project = await _seed_project(test_db)
    doc, pd = await _seed_doc_with_parsed(test_db, user=user, project=project, sha="a" * 64)

    idx = Index(
        project_id=project.id, name="idx", config={"source_representation": "full_text"},
        status=IndexStatus.created, created_by=user.id,
    )
    test_db.add(idx)
    await test_db.commit()
    await test_db.refresh(idx)

    repo = IndexRepository(test_db)
    rows = await repo.add_parsed_documents(idx.id, [pd.parse_run_id])
    assert len(rows) == 1
    assert rows[0].parse_run_id == pd.parse_run_id
    assert rows[0].document_id == doc.id
    assert rows[0].processing_status == IndexDocumentStatus.pending


@pytest.mark.asyncio
async def test_add_parsed_documents_handles_multiple(test_db: AsyncSession):
    user, project = await _seed_project(test_db)
    docA, pdA = await _seed_doc_with_parsed(test_db, user=user, project=project, sha="a" * 64)
    docB, pdB = await _seed_doc_with_parsed(test_db, user=user, project=project, sha="b" * 64)

    idx = Index(
        project_id=project.id, name="idx2", config={"source_representation": "full_text"},
        status=IndexStatus.created, created_by=user.id,
    )
    test_db.add(idx)
    await test_db.commit()
    await test_db.refresh(idx)

    repo = IndexRepository(test_db)
    rows = await repo.add_parsed_documents(idx.id, [pdA.parse_run_id, pdB.parse_run_id])
    by_run = {r.parse_run_id: r for r in rows}
    assert by_run[pdA.parse_run_id].document_id == docA.id
    assert by_run[pdB.parse_run_id].document_id == docB.id
```

- [ ] **4.2 Run — verify red.**

```bash
uv run --directory /home/asa/rag-admin/backend python -m pytest tests/repositories/test_index_repository_add_parsed_documents.py -o "addopts=" -v
```

Expected: `AttributeError: 'IndexRepository' object has no attribute 'add_parsed_documents'`.

- [ ] **4.3 Implement.** In `backend/app/repositories/index_repository.py`, replace the existing `add_documents` method (lines 166-187) with:

```python
async def add_parsed_documents(
    self,
    index_id: UUID,
    parsed_document_ids: list[UUID],
) -> list[IndexDocument]:
    """Add parsed-documents to an index.

    Each `parsed_document_id` is the parse_run_id of a ParsedDocument
    (under the current 1:1 schema). The corresponding `document_id` is
    looked up via the parsed-doc → source_document → document chain.
    """
    if not parsed_document_ids:
        return []

    # Resolve (parse_run_id, source_document_id) pairs. Under the current
    # 1:1 schema, parse_run_id is the parsed-document handle.
    pr_rows = await self.session.execute(
        select(ParseRun.id, ParseRun.source_document_id)
        .where(ParseRun.id.in_(parsed_document_ids))
    )
    sd_by_pr = {pr_id: sd_id for pr_id, sd_id in pr_rows.all()}

    # Resolve source_document_id -> document_id (any Document in the index's
    # project that points at this source_document). The Index's project_id
    # scopes us, but we only need a representative Document here.
    src_ids = list(sd_by_pr.values())
    doc_rows = await self.session.execute(
        select(DocumentORM.id, DocumentORM.source_document_id)
        .where(DocumentORM.source_document_id.in_(src_ids))
    )
    # Pick any Document for each source_document; service-level
    # validation ensures the parsed-doc is in the right project.
    doc_by_sd: dict[UUID, UUID] = {}
    for doc_id, sd_id in doc_rows.all():
        doc_by_sd.setdefault(sd_id, doc_id)

    rows: list[IndexDocument] = []
    for parsed_doc_id in parsed_document_ids:
        sd_id = sd_by_pr.get(parsed_doc_id)
        if sd_id is None:
            raise ValueError(f"Parsed document {parsed_doc_id} not found")
        doc_id = doc_by_sd.get(sd_id)
        if doc_id is None:
            raise ValueError(
                f"No Document references source_document {sd_id} "
                f"for parsed_document {parsed_doc_id}"
            )
        row = IndexDocument(
            index_id=index_id,
            document_id=doc_id,
            parse_run_id=parsed_doc_id,
            processing_status=IndexDocumentStatus.pending,
        )
        self.session.add(row)
        rows.append(row)

    await self.session.commit()
    for row in rows:
        await self.session.refresh(row)
    return rows
```

Add the imports at the top of the file:

```python
from app.models.document import Document as DocumentORM
from app.models.parse_run import ParseRun
```

(Confirm if they're already imported; the file already imports `IndexDocument` and `IndexDocumentStatus`.)

- [ ] **4.4 Run tests — verify green.**

```bash
uv run --directory /home/asa/rag-admin/backend python -m pytest tests/repositories/test_index_repository_add_parsed_documents.py -o "addopts=" -v
```

- [ ] **4.5 Commit.**

```bash
git -C <worktree-path> add \
  backend/app/repositories/index_repository.py \
  backend/tests/repositories/test_index_repository_add_parsed_documents.py
git -C <worktree-path> commit -m "$(cat <<'EOF'
feat(repos): add_parsed_documents resolves parsed-doc IDs to IndexDocument rows

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 5 — `IndexService` validation + new shape

**Files:**
- Modify: `backend/app/services/index_service.py:73-110` (`create_index`), `:205-229` (`add_documents` → `add_parsed_documents`)
- Modify: `backend/app/routers/indexes.py:132-...` (the `create_index` route uses the new shape) and `:420-448` (the `add_documents` route — rename + new path)
- Create: `backend/tests/services/test_index_service_create_index_validation.py`
- Modify: `backend/tests/routers/...` (any test that posts the old shape; update with parsed_document_ids)

This task wires the new shape end-to-end: schema → service validation → repository → route. It necessarily touches multiple tests at once because the wire shape change is observable from every layer.

- [ ] **5.1 Write the new validation tests (red).** Create `backend/tests/services/test_index_service_create_index_validation.py`:

```python
"""Tests for IndexService validation against the parsed-document family."""
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document as DocumentORM
from app.models.parse_run import ParseRun
from app.models.parsed_document import ParsedDocument
from app.models.project import Project
from app.models.source_document import SourceDocument
from app.models.user import User
from app.repositories.index_repository import IndexRepository
from app.repositories.parsed_document_repository import ParsedDocumentRepository
from app.repositories.project_repository import ProjectRepository
from app.schemas.index import IndexConfig, IndexCreate
from app.services.exceptions import NotFoundError, ValidationError
from app.services.index_service import IndexService


def _config(parser="llamaparse", parse_config_hash=None, source_rep="full_text", strategy="recursive_character"):
    return IndexConfig.model_validate({
        "parser": parser,
        "parse_config_hash": parse_config_hash or "h" * 64,
        "source_representation": source_rep,
        "chunking_strategy": strategy,
        "chunk_size": 500,
        "chunk_overlap": 50,
        "chunk_unit": "characters",
        "embedding_provider": "openai",
        "embedding_model": "text-embedding-3-small",
    })


async def _seed_user_project(db: AsyncSession):
    user = User(email=f"u{uuid4().hex[:6]}@example.com", hashed_password="x", full_name="u")
    db.add(user)
    await db.commit()
    await db.refresh(user)
    project = Project(user_id=user.id, name=f"P{uuid4().hex[:6]}")
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return user, project


async def _seed_parsed(
    db: AsyncSession, *,
    user: User, project: Project, sha: str,
    parser: str = "llamaparse", config_hash: str = "h" * 64,
    full_markdown: str | None = None, status: str = "succeeded",
) -> ParsedDocument:
    sd = SourceDocument(id=uuid4(), sha256=sha, storage_uri=f"local://{sha[:6]}.pdf")
    db.add(sd)
    await db.commit()
    doc = DocumentORM(
        project_id=project.id, source_document_id=sd.id,
        source_type="upload", source_identifier=sha, title=sha[:6],
        status="ready", created_by=user.id,
    )
    db.add(doc)
    await db.commit()
    pr = ParseRun(
        source_document_id=sd.id, parser=parser,
        representation_kind="full_markdown" if full_markdown else "full_text",
        config={}, config_hash=config_hash,
        status=status,
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc) if status == "succeeded" else None,
    )
    db.add(pr)
    await db.commit()
    await db.refresh(pr)
    pd = ParsedDocument(
        parse_run_id=pr.id, source_document_id=sd.id,
        full_text="hello", full_markdown=full_markdown,
        page_count=1, block_count=1, content={"blocks": [{"text": "hi"}]},
    )
    db.add(pd)
    await db.commit()
    await db.refresh(pd)
    return pd


def _service(db: AsyncSession) -> IndexService:
    return IndexService(
        index_repo=IndexRepository(db),
        project_repo=ProjectRepository(db),
        parsed_doc_repo=ParsedDocumentRepository(db),
    )


@pytest.mark.asyncio
async def test_create_index_persists_parse_run_id_per_row(test_db):
    user, project = await _seed_user_project(test_db)
    pd = await _seed_parsed(test_db, user=user, project=project, sha="a" * 64)
    svc = _service(test_db)

    response = await svc.create_index(
        project_id=project.id, user_id=user.id,
        data=IndexCreate(name="i", config=_config(), parsed_document_ids=[pd.parse_run_id]),
    )
    assert response.document_count >= 1


@pytest.mark.asyncio
async def test_create_index_rejects_unknown_parsed_doc(test_db):
    user, project = await _seed_user_project(test_db)
    svc = _service(test_db)

    with pytest.raises(NotFoundError, match="parsed_document"):
        await svc.create_index(
            project_id=project.id, user_id=user.id,
            data=IndexCreate(name="i", config=_config(), parsed_document_ids=[uuid4()]),
        )


@pytest.mark.asyncio
async def test_create_index_rejects_parsed_doc_outside_project(test_db):
    user_a, project_a = await _seed_user_project(test_db)
    user_b, project_b = await _seed_user_project(test_db)
    pd_b = await _seed_parsed(test_db, user=user_b, project=project_b, sha="b" * 64)
    svc = _service(test_db)

    with pytest.raises(NotFoundError, match="parsed_document"):
        await svc.create_index(
            project_id=project_a.id, user_id=user_a.id,
            data=IndexCreate(name="i", config=_config(), parsed_document_ids=[pd_b.parse_run_id]),
        )


@pytest.mark.asyncio
async def test_create_index_rejects_family_mismatch(test_db):
    user, project = await _seed_user_project(test_db)
    pd = await _seed_parsed(
        test_db, user=user, project=project, sha="c" * 64,
        parser="landingai", config_hash="h" * 64,
    )
    svc = _service(test_db)

    cfg = _config(parser="llamaparse", parse_config_hash="h" * 64)
    with pytest.raises(ValidationError, match="family"):
        await svc.create_index(
            project_id=project.id, user_id=user.id,
            data=IndexCreate(name="i", config=cfg, parsed_document_ids=[pd.parse_run_id]),
        )


@pytest.mark.asyncio
async def test_create_index_rejects_missing_segment(test_db):
    user, project = await _seed_user_project(test_db)
    # Parsed-doc with full_markdown=None
    pd = await _seed_parsed(test_db, user=user, project=project, sha="d" * 64, full_markdown=None)
    svc = _service(test_db)

    cfg = _config(source_rep="full_markdown", strategy="markdown_heading")
    with pytest.raises(ValidationError, match="full_markdown"):
        await svc.create_index(
            project_id=project.id, user_id=user.id,
            data=IndexCreate(name="i", config=cfg, parsed_document_ids=[pd.parse_run_id]),
        )


@pytest.mark.asyncio
async def test_create_index_rejects_failed_parse_run(test_db):
    user, project = await _seed_user_project(test_db)
    pd = await _seed_parsed(test_db, user=user, project=project, sha="e" * 64, status="failed")
    svc = _service(test_db)

    with pytest.raises(ValidationError, match="parse run"):
        await svc.create_index(
            project_id=project.id, user_id=user.id,
            data=IndexCreate(name="i", config=_config(), parsed_document_ids=[pd.parse_run_id]),
        )
```

The test fixture seeds: a User, a Project, and then a SourceDocument + Document + ParseRun + ParsedDocument chain. The seeded `parse_run_id` is the parsed-document handle.

⚠️ The constructor signature `IndexService(index_repo=..., project_repo=..., parsed_doc_repo=...)` is what we'll write in step 5.3. If the existing constructor has different args, update both the test and the service signature. The current `IndexService.__init__` likely takes only `index_repo` — we need to extend it to inject the parsed-doc repo for validation.

- [ ] **5.2 Run — verify red.** (Many will fail on `IndexService` not accepting the new args; that's expected.)

```bash
uv run --directory /home/asa/rag-admin/backend python -m pytest tests/services/test_index_service_create_index_validation.py -o "addopts=" -v
```

- [ ] **5.3 Implement validation in `IndexService`.** In `backend/app/services/index_service.py`, replace `create_index` and `add_documents`:

```python
async def create_index(
    self,
    project_id: UUID,
    user_id: UUID,
    data: IndexCreate,
) -> IndexResponse:
    """Create a new index. Validates parsed-doc family + segment per spec §4."""
    config = data.config

    if data.parsed_document_ids:
        await self._validate_parsed_documents(
            project_id=project_id,
            config=config,
            parsed_document_ids=data.parsed_document_ids,
        )

    try:
        index = await self.index_repo.create(
            project_id=project_id,
            user_id=user_id,
            name=data.name,
            description=data.description,
            config=config,
        )
        if data.parsed_document_ids:
            await self.index_repo.add_parsed_documents(
                index.id, data.parsed_document_ids,
            )
        return self._to_response(index)
    except IntegrityError as e:
        if "uq_indexes_project_name" in str(e).lower():
            raise ConflictError(
                f"Index with name '{data.name}' already exists in this project"
            )
        raise


async def add_parsed_documents(
    self,
    index_id: UUID,
    project_id: UUID,
    request: AddParsedDocumentsRequest,
) -> IndexResponse:
    """Add parsed-documents to an index."""
    index = await self.index_repo.get_by_id(index_id, project_id)
    if not index:
        raise NotFoundError(f"Index {index_id} not found")

    if index.status == IndexStatus.processing:
        raise ValidationError("Cannot add parsed-documents while index is processing")

    config = IndexConfig.model_validate(index.config)
    await self._validate_parsed_documents(
        project_id=project_id,
        config=config,
        parsed_document_ids=request.parsed_document_ids,
    )
    await self.index_repo.add_parsed_documents(
        index_id=index_id,
        parsed_document_ids=request.parsed_document_ids,
    )
    return await self.get_index(index_id, project_id)


async def _validate_parsed_documents(
    self,
    *,
    project_id: UUID,
    config: IndexConfig,
    parsed_document_ids: list[UUID],
) -> None:
    """Validate every parsed_doc against the index's declared family + segment.

    Raises NotFoundError when a parsed-doc is missing or in another project,
    listing the offending IDs. Raises ValidationError for family mismatch,
    segment-missing, or failed parse runs.
    """
    if not parsed_document_ids:
        return

    rows = await self.parsed_doc_repo.get_for_validation(
        parsed_document_ids=parsed_document_ids,
        project_id=project_id,
    )
    by_id = {row.parse_run_id: row for row in rows}

    missing = [pid for pid in parsed_document_ids if pid not in by_id]
    if missing:
        raise NotFoundError(
            f"parsed_document(s) not found in project: "
            f"{', '.join(str(m) for m in missing)}"
        )

    family_mismatch: list[UUID] = []
    failed_runs: list[UUID] = []
    segment_missing: list[UUID] = []
    for pid, row in by_id.items():
        if row.parser != config.parser or row.config_hash != config.parse_config_hash:
            family_mismatch.append(pid)
            continue
        if row.run_status != "succeeded":
            failed_runs.append(pid)
            continue
        if config.source_representation == "full_markdown" and row.full_markdown is None:
            segment_missing.append(pid)
        elif config.source_representation == "block" and row.block_count == 0:
            segment_missing.append(pid)
        # full_text is always populated by invariant

    if family_mismatch:
        raise ValidationError(
            f"parsed_document(s) do not match declared family "
            f"({config.parser}, {config.parse_config_hash}): "
            f"{', '.join(str(m) for m in family_mismatch)}"
        )
    if failed_runs:
        raise ValidationError(
            f"parsed_document(s) come from a non-succeeded parse run: "
            f"{', '.join(str(m) for m in failed_runs)}"
        )
    if segment_missing:
        raise ValidationError(
            f"parsed_document(s) lack {config.source_representation} segment: "
            f"{', '.join(str(m) for m in segment_missing)}"
        )
```

Update the constructor:

```python
def __init__(
    self,
    index_repo: IndexRepository,
    project_repo: ProjectRepository,
    parsed_doc_repo: ParsedDocumentRepository,
):
    self.index_repo = index_repo
    self.project_repo = project_repo
    self.parsed_doc_repo = parsed_doc_repo
```

Update the imports at the top of `index_service.py`:

```python
from app.repositories.parsed_document_repository import ParsedDocumentRepository
from app.schemas.index import (
    AddParsedDocumentsRequest,
    IndexConfig,
    IndexCreate,
    IndexResponse,
    IndexUpdate,
    IndexListResponse,
    IndexProcessingStatusResponse,
    IndexDocumentStatusResponse,
)
```

Replace the existing import of `AddDocumentsRequest` with `AddParsedDocumentsRequest`.

- [ ] **5.4 Add `ParsedDocumentRepository.get_for_validation`.** A small helper that returns parsed-docs scoped to a project with the fields the validator needs. In `backend/app/repositories/parsed_document_repository.py`:

```python
@dataclass(frozen=True)
class ParsedDocValidationRow:
    parse_run_id: UUID
    parser: str
    config_hash: str
    run_status: str
    full_markdown: str | None
    block_count: int


async def get_for_validation(
    self,
    *,
    parsed_document_ids: list[UUID],
    project_id: UUID,
) -> list[ParsedDocValidationRow]:
    """Return validation-row data for parsed-docs scoped to a project.

    Joins parsed_doc → parse_run → source_document → document on project_id
    so a parsed-doc in another project's source-document is silently filtered.
    """
    if not parsed_document_ids:
        return []
    stmt = (
        select(
            ParsedDocument.parse_run_id,
            ParseRun.parser,
            ParseRun.config_hash,
            ParseRun.status,
            ParsedDocument.full_markdown,
            ParsedDocument.block_count,
        )
        .join(ParseRun, ParseRun.id == ParsedDocument.parse_run_id)
        .join(DocumentORM, DocumentORM.source_document_id == ParseRun.source_document_id)
        .where(
            ParsedDocument.parse_run_id.in_(parsed_document_ids),
            DocumentORM.project_id == project_id,
        )
    )
    result = await self.session.execute(stmt)
    return [
        ParsedDocValidationRow(
            parse_run_id=row.parse_run_id,
            parser=row.parser,
            config_hash=row.config_hash,
            run_status=row.status,
            full_markdown=row.full_markdown,
            block_count=row.block_count,
        )
        for row in result.all()
    ]
```

If `DocumentORM` and `ParseRun` aren't already imported, they were added in Unit 1; keep them.

- [ ] **5.5 Update the routers.** In `backend/app/routers/indexes.py`:

Update the `add_documents` route at line 420 — rename to `add_parsed_documents`:

```python
@router.post(
    "/{index_id}/parsed-documents",
    response_model=IndexResponse,
    summary="Add parsed-documents",
    description="Add parsed-documents to an existing index.",
)
async def add_parsed_documents(
    project_id: UUID,
    index_id: UUID,
    data: AddParsedDocumentsRequest,
    current_user: User = Depends(get_current_active_user),
    service: IndexService = Depends(get_index_service),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    await verify_project_access(project_id, current_user, project_repo)
    try:
        return await service.add_parsed_documents(index_id, project_id, data)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
```

Update the imports at the top: `AddDocumentsRequest` → `AddParsedDocumentsRequest`. The DELETE route at `:451-453` (`/documents/{document_id}`) keeps its `document_id` semantics for now — Unit 5 (index detail) addresses that.

Also update the dependency factory `get_index_service` (~line 59) to inject `ProjectRepository` and `ParsedDocumentRepository`:

```python
def get_index_service(db: AsyncSession = Depends(get_db)) -> IndexService:
    return IndexService(
        index_repo=IndexRepository(db),
        project_repo=ProjectRepository(db),
        parsed_doc_repo=ParsedDocumentRepository(db),
    )
```

- [ ] **5.6 Run validation tests — verify green.**

```bash
uv run --directory /home/asa/rag-admin/backend python -m pytest tests/services/test_index_service_create_index_validation.py -o "addopts=" -v
```

Expect 6 passing.

- [ ] **5.7 Fix any other tests that broke.** Run the full backend suite and update tests that constructed `IndexCreate(document_ids=...)` or `AddDocumentsRequest(...)` to use the new shapes:

```bash
uv run --directory /home/asa/rag-admin/backend python -m pytest -o "addopts=" 2>&1 | tail -50
```

Common fix patterns:
- `IndexCreate(document_ids=[...])` → `IndexCreate(parsed_document_ids=[...])` plus a `config=_config(parser=..., parse_config_hash=...)` if the test didn't supply one.
- `AddDocumentsRequest(document_ids=...)` → `AddParsedDocumentsRequest(parsed_document_ids=...)`.
- POSTs to `/indexes/{id}/documents` → `/indexes/{id}/parsed-documents`.
- Test seeds that lacked a parse_run / parsed_doc need to add one (the new shape can't accept arbitrary documents).

If a test is fundamentally raw_text-only and can't be straightforwardly migrated, delete it — its scenario is gone post-Unit-3. Note any deletion in the commit message.

- [ ] **5.8 Commit.**

```bash
git -C <worktree-path> add \
  backend/app/services/index_service.py \
  backend/app/repositories/parsed_document_repository.py \
  backend/app/routers/indexes.py \
  backend/tests/services/test_index_service_create_index_validation.py \
  backend/tests/  # any other test files updated
git -C <worktree-path> commit -m "$(cat <<'EOF'
feat(index): IndexService validates parsed_doc family/segment; route → /parsed-documents

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 6 — Drop `raw_text` from `IndexProcessingService`

**Files:**
- Modify: `backend/app/services/index_processing_service.py:104-112` (the start_processing config check), `:179-211` (the dispatch block)
- Modify: `backend/tests/services/test_index_processing_cdm.py`

- [ ] **6.1 Identify and remove the raw_text test cases.** Search:

```bash
grep -n "raw_text\|extracted_text" /home/asa/rag-admin/backend/tests/services/test_index_processing_cdm.py
```

For each match: if the test is *about* raw_text, delete it. If it's a CDM test that incidentally references raw_text in setup, update.

- [ ] **6.2 Remove the raw_text branch in `process_index()`.** In `backend/app/services/index_processing_service.py`, replace the dispatch (~lines 179-211):

Before:
```python
if config.source_representation == "raw_text":
    if not document.extracted_text:
        raise ValueError("Document has no extracted text")
    source_type = "raw_text"
    doc_parse_run_id = None
    chunks = self.chunking_service.chunk_text(
        text=document.extracted_text,
        config=config,
        source_document_id=str(doc_id),
        source_filename=document.source_metadata.get("filename"),
        page_boundaries=document.processing_metadata.get("page_boundaries")
            if document.processing_metadata else None,
    )
elif config.source_representation in ("full_text", "full_markdown", "block"):
    # ... CDM seam ...
else:
    raise NotImplementedError(...)
```

After:
```python
if config.source_representation in ("full_text", "full_markdown", "block"):
    source = await self.source_resolver.resolve(
        parsed_document_id=index_doc.parse_run_id,
        source_representation=config.source_representation,
    )
    chunks = self.chunking_dispatcher.dispatch(
        source=source,
        config=config,
        source_document_id=str(doc_id),
        source_filename=document.source_metadata.get("filename"),
    )
    source_type = config.source_representation
    doc_parse_run_id = index_doc.parse_run_id
else:
    raise NotImplementedError(
        f"source_representation '{config.source_representation}' not yet supported"
    )
```

(Effectively: the leading `if raw_text` branch and the `elif` keyword are both gone; the CDM branch becomes the leading `if`.)

- [ ] **6.3 Simplify `start_processing` raw_text guard.** In the same file around line 104-112:

Before:
```python
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

After:
```python
# Every CDM source_representation requires a parse run on each pending row.
for index_doc in index.index_documents:
    if index_doc.processing_status == IndexDocumentStatus.pending:
        if not index_doc.parse_run_id:
            raise ValidationError(
                f"IndexDocument {index_doc.document_id} has no parse_run_id; "
                "every parsed-doc indexed must reference a parse run"
            )
```

Also remove the unused `self.chunking_service` instance attribute from `__init__` — after this task, only the raw_text path used it directly. (`ChunkingDispatcher` instantiates its own internal singleton.)

```python
# In __init__, delete this line:
self.chunking_service = get_chunking_service()
```

And remove the now-unused import:

```python
# Delete:
from app.services.chunking_service import get_chunking_service
```

- [ ] **6.4 Run CDM tests.**

```bash
uv run --directory /home/asa/rag-admin/backend python -m pytest tests/services/test_index_processing_cdm.py -o "addopts=" -v
```

Expect: tests pass after raw_text-specific cases are deleted; CDM tests are unchanged.

- [ ] **6.5 Commit.**

```bash
git -C <worktree-path> add \
  backend/app/services/index_processing_service.py \
  backend/tests/services/test_index_processing_cdm.py
git -C <worktree-path> commit -m "$(cat <<'EOF'
refactor(index): drop raw_text branch from process_index

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 7 — Tighten `ChunkPreviewRequest`; remove preview bridge; delete `get_latest_for_document`

**Files:**
- Modify: `backend/app/schemas/index.py:245-266` (`ChunkPreviewRequest`)
- Modify: `backend/app/routers/indexes.py:592-...` (the `preview_chunks` handler)
- Modify: `backend/app/repositories/parsed_document_repository.py` (remove the bridge method)
- Modify: `backend/tests/routers/test_preview_chunks_router.py` (remove bridge tests)
- Delete: `backend/tests/repositories/test_parsed_document_repository_get_latest.py`

- [ ] **7.1 Update `ChunkPreviewRequest` (red — schema test will fail).**

Replace the schema:

```python
class ChunkPreviewRequest(BaseModel):
    """Schema for previewing chunks before processing.

    `parsed_document_id` is the unit of preview — the same parsed-doc the
    save path will read.
    """
    parsed_document_id: UUID = Field(..., alias="parsedDocumentId")
    config: IndexConfig
    max_chunks: int = Field(default=5, ge=1, le=20, alias="maxChunks")

    model_config = ConfigDict(populate_by_name=True)
```

Drop the `document_id` field and the `exactly_one_handle` validator entirely.

- [ ] **7.2 Remove the bridge from the preview endpoint.** In `backend/app/routers/indexes.py`, replace the `preview_chunks` handler with a single-path implementation:

```python
@router.post(
    "/preview-chunks",
    response_model=ChunkPreviewResponse,
    summary="Preview chunks",
    description="Preview how a parsed-document would be chunked without processing.",
)
async def preview_chunks(
    project_id: UUID,
    data: ChunkPreviewRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    project_repo: ProjectRepository = Depends(get_project_repo),
):
    await verify_project_access(project_id, current_user, project_repo)

    parsed_doc_repo = ParsedDocumentRepository(db)
    parsed_doc = await parsed_doc_repo.get_by_run(data.parsed_document_id)
    if parsed_doc is None:
        raise HTTPException(404, f"Parsed document {data.parsed_document_id} not found")

    # Project scoping: a Document in this project must reference the same
    # SourceDocument the parsed-doc points at.
    scope_stmt = (
        select(Document.id)
        .where(
            Document.source_document_id == parsed_doc.source_document_id,
            Document.project_id == project_id,
        )
        .limit(1)
    )
    scope_result = await db.execute(scope_stmt)
    if scope_result.scalar_one_or_none() is None:
        raise HTTPException(
            404, f"Parsed document {data.parsed_document_id} not in project"
        )

    return await _preview_via_seam(
        db=db,
        parsed_document_id=data.parsed_document_id,
        config=data.config,
        source_document_id=None,
        source_filename=None,
        max_chunks=data.max_chunks,
    )
```

Drop the `documentId` and `raw_text` branches entirely. The `_preview_via_seam` and `_project_to_preview_response` helpers from Unit 2 stay; just the handler shrinks.

Update the imports — remove `DocumentRepository` from the dependency injection if it's no longer needed (it isn't, after this change).

- [ ] **7.3 Delete `ParsedDocumentRepository.get_latest_for_document`.** In `backend/app/repositories/parsed_document_repository.py`, find and delete the method (added in Unit 2, commit `282232a`).

- [ ] **7.4 Delete the bridge test file.**

```bash
rm /home/asa/rag-admin/backend/tests/repositories/test_parsed_document_repository_get_latest.py
```

(Use the worktree path in the actual implementation.)

- [ ] **7.5 Update the preview router tests.** In `backend/tests/routers/test_preview_chunks_router.py`, delete:
- `test_preview_chunks_validates_exactly_one_handle` (renamed below)
- `test_preview_chunks_bridge_document_id_full_markdown`
- `test_preview_chunks_bridge_document_id_no_parse_run_returns_400`
- `test_preview_chunks_legacy_raw_text_path_unchanged`

Keep:
- `test_preview_chunks_with_parsed_document_id_full_markdown`
- `test_preview_chunks_parsed_document_outside_project_returns_404`
- `test_preview_chunks_seam_overlap_matches_config`

Add:
```python
@pytest.mark.asyncio
async def test_preview_chunks_requires_parsed_document_id(client, test_db):
    """Posting a body with no parsed_document_id returns 422."""
    token = await _signup(client, "preview_no_handle@example.com")
    user = await _user_by_email(test_db, "preview_no_handle@example.com")
    project = await _make_project(test_db, user)
    body = {
        "config": {
            "parser": "llamaparse",
            "parseConfigHash": "h" * 64,
            "sourceRepresentation": "full_text",
            "chunkingStrategy": "recursive_character",
            "chunkSize": 500,
            "chunkOverlap": 50,
            "chunkUnit": "characters",
            "embeddingProvider": "openai",
            "embeddingModel": "text-embedding-3-small",
        },
    }
    resp = await client.post(
        f"/api/v1/projects/{project.id}/indexes/preview-chunks",
        json=body,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422
```

- [ ] **7.6 Run the suite.**

```bash
uv run --directory /home/asa/rag-admin/backend python -m pytest -o "addopts="
```

Expect green.

- [ ] **7.7 Commit.**

```bash
git -C <worktree-path> add \
  backend/app/schemas/index.py \
  backend/app/routers/indexes.py \
  backend/app/repositories/parsed_document_repository.py \
  backend/tests/routers/test_preview_chunks_router.py
git -C <worktree-path> rm backend/tests/repositories/test_parsed_document_repository_get_latest.py
git -C <worktree-path> commit -m "$(cat <<'EOF'
feat(routers): chunk preview requires parsedDocumentId; drop bridge

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 8 — Frontend types + API client

**Files:**
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/api/indexes.ts`
- Modify: `frontend/src/hooks/useIndexes.ts`

- [ ] **8.1 Update types.** In `frontend/src/types/index.ts`, find the `IndexConfig` type and drop `'raw_text'` from `sourceRepresentation`:

Before:
```ts
sourceRepresentation: 'raw_text' | 'full_text' | 'full_markdown' | 'block'
```

After:
```ts
sourceRepresentation: 'full_text' | 'full_markdown' | 'block'
```

Update `IndexCreate`:
```ts
export interface IndexCreate {
  name: string
  description?: string | null
  parsedDocumentIds: string[]
  config: IndexConfig
  autoProcess?: boolean
}
```

Update `AddDocumentsRequest` → rename to `AddParsedDocumentsRequest`:
```ts
export interface AddParsedDocumentsRequest {
  parsedDocumentIds: string[]
}
```

Update `ChunkPreviewRequest`:
```ts
export interface ChunkPreviewRequest {
  parsedDocumentId: string
  config: Partial<IndexConfig>
  maxChunks?: number
}
```

(`documentId` is gone.)

- [ ] **8.2 Update `frontend/src/api/indexes.ts`.**

`createIndex` body — change `documentIds` → `parsedDocumentIds`:

```ts
export async function createIndex(
  projectId: string,
  data: IndexCreate,
): Promise<Index> {
  const response = await apiClient.post<Index>(
    `/projects/${projectId}/indexes`,
    {
      name: data.name,
      description: data.description ?? null,
      parsedDocumentIds: data.parsedDocumentIds,
      config: { /* ... existing config payload ... */ },
      autoProcess: data.autoProcess ?? false,
    },
  )
  return response.data
}
```

(Keep the existing config payload mapping. The change is just `documentIds` → `parsedDocumentIds`.)

`addDocuments` → rename to `addParsedDocuments`, change route + body:

```ts
export async function addParsedDocuments(
  projectId: string,
  indexId: string,
  data: AddParsedDocumentsRequest,
): Promise<Index> {
  const response = await apiClient.post<Index>(
    `/projects/${projectId}/indexes/${indexId}/parsed-documents`,
    { parsedDocumentIds: data.parsedDocumentIds },
  )
  return response.data
}
```

`previewChunks` body — drop the `documentId` branch (Task 6 made `parsedDocumentId` required at the schema level; Unit 2 already had the conditional sender). The Unit 2 implementation looks like:

```ts
if (data.parsedDocumentId) body.parsedDocumentId = data.parsedDocumentId
else if (data.documentId) body.documentId = data.documentId
```

Replace with:

```ts
body.parsedDocumentId = data.parsedDocumentId
```

(Type-level: `data.parsedDocumentId` is now required; TypeScript enforces this at the call site.)

- [ ] **8.3 Update `useIndexes.ts` hook signatures.** Find `previewChunks`, `addDocuments`, `createIndex` consumers — anything that takes `ChunkPreviewRequest`, `AddDocumentsRequest`, or `IndexCreate`. Rename `addDocuments` → `addParsedDocuments`. The hook just passes through to the API client; the types flow through.

```bash
grep -n "addDocuments\|AddDocumentsRequest\|documentIds" /home/asa/rag-admin/frontend/src/hooks/useIndexes.ts
```

For each match: rename / replace.

- [ ] **8.4 Run frontend lint + typecheck.**

```bash
npm --prefix /home/asa/rag-admin/frontend run lint
npm --prefix /home/asa/rag-admin/frontend run build
```

Expect: TypeScript errors at every call site that hasn't been updated yet (the wizard). Those are fixed in Task 9.

⚠️ Don't commit yet — a half-updated codebase has a non-building TypeScript build. Wait for Task 9 to land too, then commit Tasks 8+9 together (or commit Task 8 with the wizard intentionally broken and explicitly note it's fixed in the next commit).

---

### Task 9 — Frontend wizard adapter

**Files:**
- Create: `frontend/src/lib/parsed-documents.ts`
- Modify: `frontend/src/components/indexes/IndexCreateDialog.tsx`
- Modify: `frontend/src/pages/CreateIndexPage.tsx`
- Modify: `frontend/src/components/indexes/IndexCreateDialog.test.tsx` (and any matching `CreateIndexPage` test)

The wizard still has its old document selector — Unit 4 replaces it with a parsed-doc picker. To keep the wizard working with the new backend, on submit we resolve each selected document to its latest succeeded parsed-doc and infer the family from those rows.

- [ ] **9.1 Create the resolver helper.** `frontend/src/lib/parsed-documents.ts`:

```ts
import { apiClient } from '@/api/client'

export interface ParsedDocumentListItem {
  id: string
  parseRunId: string
  parser: string
  parseConfigHash: string
  sourceDocumentId: string
  sourceFilename: string | null
  hasFullMarkdown: boolean
  blockCount: number
  parsedAt: string
}

export async function listParsedDocuments(
  projectId: string,
  params: {
    parser?: string
    parseConfigHash?: string
    representation?: 'full_text' | 'full_markdown' | 'block'
    latestPerSource?: boolean
  } = {},
): Promise<ParsedDocumentListItem[]> {
  const response = await apiClient.get<ParsedDocumentListItem[]>(
    `/projects/${projectId}/parsed-documents`,
    { params },
  )
  return response.data
}

export interface ResolvedFamily {
  parser: string
  parseConfigHash: string
  parsedDocumentIds: string[]
}

/**
 * Resolves a wizard-selected document set to:
 *   1. The latest succeeded parsed-doc per document.
 *   2. The (parser, parseConfigHash) family inferred from those parsed-docs.
 *
 * Throws if the resolved parsed-docs span multiple families, or if a selected
 * document has no succeeded parsed-doc.
 *
 * BRIDGE: Unit 4 replaces this with an explicit parsed-doc picker in the wizard.
 */
export async function resolveLatestParsedDocsForDocuments(
  projectId: string,
  documentIds: string[],
  representation: 'full_text' | 'full_markdown' | 'block',
): Promise<ResolvedFamily> {
  if (documentIds.length === 0) {
    throw new Error('No documents selected')
  }
  const all = await listParsedDocuments(projectId, {
    representation,
    latestPerSource: true,
  })
  const docSet = new Set(documentIds)
  // Group by source_document_id since a Document maps to a SourceDocument
  // and parsed-docs are keyed by source_document_id. The wizard's
  // `documentIds` are Document IDs; we need to translate.
  // Simpler: assume one Document per SourceDocument in this project (standard);
  // and pick the parsed-doc whose source_document_id matches a selected doc's
  // source_document_id. We don't have that mapping client-side, so we instead
  // ask the user to pick parsed-docs directly — but to keep slice-2 working,
  // we treat the document selection as a hint and pick all latest parsed-docs.
  //
  // Pragmatic choice: pick all latest parsed-docs and trust the backend to
  // reject any that aren't in the user's selection's source. Better: extend
  // the listing endpoint with a documentIds filter — but that's a Unit 4 job.
  //
  // For Unit 3's bridge: we use ALL latest parsed-docs in the project for
  // the chosen representation. Unit 4's picker makes this precise.
  const families = new Set<string>()
  const ids: string[] = []
  for (const pd of all) {
    families.add(`${pd.parser}|${pd.parseConfigHash}`)
    ids.push(pd.parseRunId)
  }
  if (families.size > 1) {
    throw new Error(
      'Multiple parse-config families detected in this project. ' +
      'The Unit 4 picker will let you choose one explicitly. ' +
      'For now, parse all documents with a single configuration.',
    )
  }
  if (families.size === 0) {
    throw new Error(
      'No succeeded parsed-documents found in this project for ' +
      `representation=${representation}. Parse documents first.`,
    )
  }
  const [family] = [...families]
  const [parser, parseConfigHash] = family.split('|')
  return { parser, parseConfigHash, parsedDocumentIds: ids }
}
```

This is a wide-net bridge — it submits all latest parsed-docs in the project rather than only those tied to the user's selection. The simpler precise approach (filter by selected documents' source_document_ids) requires a backend filter that Unit 1 didn't ship; adding it is more scope than warranted for a bridge that Unit 4 deletes. The trade-off is documented in the helper's comment block.

Tests for this helper are out of scope — the dialog tests (step 9.4) cover its observable behaviour.

- [ ] **9.2 Update `IndexCreateDialog.tsx` submit handler.** Find the existing submit handler (looks like `const handleSubmit = async () => { ... }` around line 100-130). Modify to call the resolver before submitting:

```tsx
const handleSubmit = async () => {
  setIsSubmitting(true)
  try {
    const family = await resolveLatestParsedDocsForDocuments(
      projectId,
      selectedDocumentIds,
      config.sourceRepresentation as 'full_text' | 'full_markdown' | 'block',
    )

    await onCreateIndex({
      name,
      description,
      parsedDocumentIds: family.parsedDocumentIds,
      config: {
        ...config,
        parser: family.parser,
        parseConfigHash: family.parseConfigHash,
      },
      autoProcess,
    })
    onClose()
  } catch (e) {
    toast.error(extractErrorMessage(e))
  } finally {
    setIsSubmitting(false)
  }
}
```

(Adapt names to what's already in scope — `onCreateIndex`, `extractErrorMessage`, etc. The existing handler already does most of this; the change is the resolver call and the `parsedDocumentIds` field.)

- [ ] **9.3 Update `CreateIndexPage.tsx` similarly.** Same resolver call pattern in its submit handler.

- [ ] **9.4 Update existing wizard tests.** The tests in `IndexCreateDialog.test.tsx` (and any matching `CreateIndexPage` test) need to:
- Mock `listParsedDocuments` (the helper or the API client) so the resolver returns a deterministic family.
- Update the assertion on the call to `previewChunks` / `createIndex` to check `parsedDocumentIds` rather than `documentIds`.
- Drop any test asserting `Raw text` is selectable.

Replace the previously-added "enabled when full_markdown selected" tests with the equivalent post-Unit-3 versions.

- [ ] **9.5 Run frontend lint, build, and tests.**

```bash
npm --prefix /home/asa/rag-admin/frontend run lint
npm --prefix /home/asa/rag-admin/frontend run build
npx --prefix /home/asa/rag-admin/frontend vitest run frontend/src/components/indexes/IndexCreateDialog.test.tsx
```

Expect green.

- [ ] **9.6 Commit Tasks 8+9 together.**

```bash
git -C <worktree-path> add \
  frontend/src/types/index.ts \
  frontend/src/api/indexes.ts \
  frontend/src/hooks/useIndexes.ts \
  frontend/src/lib/parsed-documents.ts \
  frontend/src/components/indexes/IndexCreateDialog.tsx \
  frontend/src/pages/CreateIndexPage.tsx \
  frontend/src/components/indexes/IndexCreateDialog.test.tsx
git -C <worktree-path> commit -m "$(cat <<'EOF'
feat(frontend): wizard submits parsedDocumentIds via resolver bridge

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 10 — Drop `raw_text` from the source-rep toggle

**Files:**
- Modify: `frontend/src/components/indexes/IndexCreateDialog.tsx`
- Modify: `frontend/src/pages/CreateIndexPage.tsx`

The toggle currently has three options: Raw text / Full text / Full Markdown. Drop the `Raw text` option.

- [ ] **10.1 Find and remove the `raw_text` ToggleGroupItem.** In `IndexCreateDialog.tsx`:

Search for:

```bash
grep -n "raw_text\|'Raw text'\|sourceRepresentation === 'raw_text'" /home/asa/rag-admin/frontend/src/components/indexes/IndexCreateDialog.tsx /home/asa/rag-admin/frontend/src/pages/CreateIndexPage.tsx
```

For each match:
- The `ToggleGroupItem` with `value="raw_text"` — delete the element.
- The default value of the toggle / `IndexConfig` initial state — change from `'raw_text'` to `'full_text'`.
- Any `if (sourceRepresentation === 'raw_text')` branches — delete or simplify.

Specifically in `IndexCreateDialog.tsx`:
- Line 46 (`sourceRepresentation: 'raw_text'`) → change to `'full_text'`.
- Line 168 (`else if (value === 'raw_text' || value === 'full_text')`) → drop the `value === 'raw_text'` term.
- Line 235 (`value={config.sourceRepresentation ?? 'raw_text'}`) → change default to `'full_text'`.
- Line 242 (`<ToggleGroupItem value="raw_text" aria-label="Raw text">...`) → delete the element.

Same shape in `CreateIndexPage.tsx` line 422 area.

- [ ] **10.2 Run lint + build + tests.**

```bash
npm --prefix /home/asa/rag-admin/frontend run lint
npm --prefix /home/asa/rag-admin/frontend run build
npx --prefix /home/asa/rag-admin/frontend vitest run
```

Expect green.

- [ ] **10.3 Commit.**

```bash
git -C <worktree-path> add \
  frontend/src/components/indexes/IndexCreateDialog.tsx \
  frontend/src/pages/CreateIndexPage.tsx \
  frontend/src/components/indexes/IndexCreateDialog.test.tsx
git -C <worktree-path> commit -m "$(cat <<'EOF'
fix(frontend): drop raw_text from source-representation toggle

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 11 — Verification

- [ ] **11.1 Full backend suite.**

```bash
uv run --directory /home/asa/rag-admin/backend python -m pytest -o "addopts=" -q 2>&1 | tail -5
```

Expect all tests passing. New test count should be roughly: existing (~592) − deleted (4 bridge tests + raw_text tests in test_index_processing_cdm.py) + added (~13 new, across schemas, repos, services, migrations).

- [ ] **11.2 Frontend lint + build + vitest.**

```bash
npm --prefix /home/asa/rag-admin/frontend run lint
npm --prefix /home/asa/rag-admin/frontend run build
npx --prefix /home/asa/rag-admin/frontend vitest run
```

- [ ] **11.3 Apply the migration to dev DB and spot-check.**

```bash
docker compose -f /home/asa/rag-admin/docker-compose.local.yml exec backend alembic upgrade head
```

Confirm any pre-existing legacy raw_text indexes are deleted. Confirm no errors.

- [ ] **11.4 Manual smoke against local stack.**

```bash
docker compose -f /home/asa/rag-admin/docker-compose.local.yml up -d --build
```

For an existing project with succeeded parsed-docs:
1. Open Create Index. The source-rep toggle should show only `Full text` and `Full Markdown` (no `Raw text`).
2. Pick a few documents, choose `full_markdown`, fill in chunking params, submit. The wizard should resolve the parsed-doc IDs internally and create the index.
3. Verify in the DB: `index_documents.parse_run_id` is populated for every row of the new index.
4. Process the index. Chunks should be byte-identical to a pre-Unit-3 run of the same family (regression check).
5. Try Add Documents on an existing index — POST to `/parsed-documents` (the new path).
6. Try the chunk preview button — works for full_text and full_markdown.

- [ ] **11.5 Confirm no regressions in raw_text-adjacent flows.** Anything previously protected by `if config.source_representation == "raw_text"` should now either be CDM-only or have no special case. Verify:
- Document upload → process flow still works (it doesn't depend on indexes).
- Existing CDM indexes still display correctly (no display logic broken by Literal change).

---

## Manual verification checklist (to attach to the PR)

- [ ] Migration runs cleanly and removes legacy raw_text indexes.
- [ ] No remaining `raw_text` references in the IndexConfig validators or processing service dispatch.
- [ ] `IndexCreate` accepts `parsedDocumentIds`; rejects `documentIds`.
- [ ] `AddParsedDocumentsRequest` route is `POST /indexes/{id}/parsed-documents`; old `/documents` returns 404.
- [ ] `ChunkPreviewRequest` requires `parsedDocumentId`; sending only `documentId` returns 422.
- [ ] `ParsedDocumentRepository.get_latest_for_document` is gone (`grep` confirms).
- [ ] Wizard creates an index end-to-end and the result has parsed_run_id populated on every row.
- [ ] Source-rep toggle in the wizard has only Full text and Full Markdown.
- [ ] Existing CDM indexes process unchanged.
- [ ] Chunk preview works for full_text and full_markdown indexes.

---

## Out of scope (next units)

- **Unit 4:** Wizard rebuild — parse-config family selector + parsed-doc picker. Removes the `resolveLatestParsedDocsForDocuments` adapter and replaces the wide-net bridge with explicit picker selection.
- **Unit 5:** Index detail "Documents" tab → "Parsed Documents" with the new column shape (Source filename / Parse run / Parsed at / Status / Chunks).
- **Unit 6 (cleanup):** `ALTER COLUMN index_documents.parse_run_id SET NOT NULL`. Delete denormalized `index_documents.document_id` if confirmed unused. Implement block chunking and remove `ChunkingDispatcher`'s `NotImplementedError`.
