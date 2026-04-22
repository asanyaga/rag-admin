# CDM Persistence — v1 Spec

> **Status**: Spec for implementation.
> **Scope**: Persist CDM (`SourceDocument`, `ParseRun`, `ParsedDocument`) to Postgres. Wire the existing `llamaparse_runner` through a new `ParsingService` into the upload path. Separate `documents` (project-scoped admin + ACL edge) from `source_documents` (content-addressed bytes).
> **Out of scope**: Data migration of pre-existing rows and retirement of the legacy adapter — covered in a sibling spec `cdm_persistence_migration.md`. UI viewer — covered by §11.4.
> **Reference**: [`docs/specs/cdm_v1.md`](cdm_v1.md) §8, §11.1, §11.2, §11.3.

---

## 1. Goals

1. Durably persist every `ParseRun` — succeeded, partial, **and failed** — with full provenance. Traceability is first-class.
2. Separate the bytes layer (`source_documents`) from the admin/ACL layer (`documents`) so that content addressing, cross-project parse reuse (deferred by policy), and future connector work (§9) all have a clean home.
3. Persist `ParsedDocument` with zero structural loss — every block, bbox, span, table cell, and parser_extra survives round-trip.
4. Wire `llamaparse_runner` into the upload flow via a new `ParsingService`, replacing the legacy `DocumentParser` port path behind a feature flag. Rollback remains available until the migration PR retires the legacy adapter.
5. Resolve the dead `ParseRun(FAILED)` in the runner's except block (`cdm_v1.md` §11.1) with a typed exception that carries the run to the service layer for persistence.

Non-goals: normalized block/cell tables, config presets, UI, migration of existing rows, multi-tenant ACL enforcement.

---

## 2. Data Model

### 2.1 New tables

```sql
-- Bytes layer. Content-addressed, no project scope, no ACL.
CREATE TABLE source_documents (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sha256        CHAR(64) NOT NULL UNIQUE,
    filename      TEXT,
    mime_type     TEXT,
    byte_size     BIGINT,
    storage_uri   TEXT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Execution layer. One row per parser invocation.
CREATE TABLE parse_runs (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_document_id   UUID NOT NULL REFERENCES source_documents(id) ON DELETE CASCADE,
    parser               TEXT NOT NULL,             -- ParserKind enum value
    parser_version       TEXT,
    representation_kind  TEXT NOT NULL,             -- open string: "vector_light" | "extract_rich" | ...
    config               JSONB NOT NULL DEFAULT '{}'::jsonb,
    config_hash          CHAR(64) NOT NULL,         -- sha256 of canonical JSON (sorted keys)
    status               TEXT NOT NULL,             -- ParseRunStatus enum value
    started_at           TIMESTAMPTZ NOT NULL,
    finished_at          TIMESTAMPTZ,
    duration_ms          INT,
    cost                 JSONB NOT NULL DEFAULT '{}'::jsonb,
    input_tokens         INT,
    output_tokens        INT,
    warnings             JSONB NOT NULL DEFAULT '[]'::jsonb,
    failed_pages         JSONB NOT NULL DEFAULT '[]'::jsonb,
    provider_refs        JSONB NOT NULL DEFAULT '{}'::jsonb,
    error                TEXT,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX ux_parse_runs_content_config
    ON parse_runs (source_document_id, representation_kind, config_hash);
CREATE INDEX ix_parse_runs_status ON parse_runs (status);
CREATE INDEX ix_parse_runs_source_document_id ON parse_runs (source_document_id);

-- Content layer. One row per successful (or partial) run. No row on failure.
CREATE TABLE parsed_documents (
    parse_run_id         UUID PRIMARY KEY REFERENCES parse_runs(id) ON DELETE CASCADE,
    source_document_id   UUID NOT NULL REFERENCES source_documents(id) ON DELETE CASCADE,
    full_text            TEXT,
    full_markdown        TEXT,
    page_count           INT NOT NULL,
    block_count          INT NOT NULL,
    content              JSONB NOT NULL,            -- ParsedDocument.model_dump()
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_parsed_documents_source_document_id ON parsed_documents (source_document_id);
-- GIN index on content deferred until first structural-query workload ships.
```

**Storage-of-truth rule:** `parsed_documents.content` is authoritative. `full_text`, `full_markdown`, `page_count`, `block_count` are sidecar projections for hot-path reads (embedding, list views). If a sidecar ever disagrees with `content`, `content` wins and the sidecar is rebuilt.

**No normalized `blocks` / `cells` tables.** Every near-term workload (embedding, extract, classify, split, viewer, citation resolution) consumes whole documents or does point lookups by `block_id` within one run. None of them are SQL-join-shaped. When a real structural-search workload ships, it projects the shape it needs out of `content`.

### 2.2 Extensions to `documents`

```sql
ALTER TABLE documents
    ADD COLUMN source_document_id UUID REFERENCES source_documents(id);

CREATE INDEX ix_documents_source_document_id ON documents (source_document_id);
```

- Nullable during PRs 1–3 for migration-ordering reasons only. New inserts on the CDM path always populate it.
- The migration spec backfills pre-existing rows and flips to `NOT NULL`.
- `documents.extracted_text` is **not** dropped in this spec. It is superseded by `parsed_documents.full_text` but stays in place until the migration spec retires it — keeps PR 3 cutover reversible.

**Layering boundary:** `documents` remains the ACL edge (project-scoped, role-gated when auth ships). `source_documents` is global bytes with no project scope. Joins:

```
documents.source_document_id → source_documents.id
parse_runs.source_document_id → source_documents.id
parsed_documents.parse_run_id → parse_runs.id
```

A `Document` has zero-or-many `ParseRun`s via its `source_document_id`. ParseRuns are never referenced directly by `documents` — the content layer is addressed by bytes, not by project pointer.

### 2.3 Reuse policy

Within the **same project**, on upload of a `Document`:

1. Compute `sha256` of bytes.
2. If a `source_documents` row with that `sha256` exists, reuse it; else insert.
3. If a `parse_runs` row exists with matching `(source_document_id, representation_kind, config_hash)`, return it. Do not re-parse.
4. Else create a new `ParseRun(PENDING)` and invoke the runner.

**Cross-project reuse is disabled by policy in v1** even though the schema supports it. Rationale: a project-Y user inferring project-X's existence via pre-populated ParsedDocuments is a side-channel once authorization lands. The `ParsingService` checks reuse only against ParseRuns whose `source_document_id` is referenced by a `documents` row in the **same project**. When authorization ships, cross-project reuse becomes an opt-in policy decision.

`config_hash` = `sha256(json.dumps(config, sort_keys=True, separators=(",", ":")))`. No default-filling, no normalization beyond key ordering. `{"tier": "agentic"}` and `{"tier": "agentic", "version": "latest"}` hash differently and are treated as distinct runs — correct, because LlamaParse interprets them differently.

---

## 3. Failed-Run Plumbing

Resolves `cdm_v1.md` §11.1 Option A.

### 3.1 Exception

```python
# app/services/parsing/errors.py
class LlamaParseRunError(RuntimeError):
    def __init__(self, message: str, *, run: ParseRun):
        super().__init__(message)
        self.run = run
```

### 3.2 Runner change

`app/services/parsing/llamaparse_runner.py` no longer discards the failed `ParseRun`. The `except` block constructs it (as today) and raises `LlamaParseRunError(message, run=failed_run)`. No other signature change; happy path still returns `(ParseRun, ParsedDocument)`.

### 3.3 Service handling

`ParsingService` catches `LlamaParseRunError`, persists `err.run` via `ParseRunRepository`, then raises a domain error `ParseFailedError` for the router. The repository is never error-aware: it writes whatever row it is handed.

Partial runs (`status=PARTIAL`) are returned normally with a valid `ParsedDocument`; the service persists both.

---

## 4. Repository Layer

Three new modules under `app/repositories/`, following the existing async SQLAlchemy pattern (see [backend/app/repositories/document_repository.py](backend/app/repositories/document_repository.py)):

- `source_document_repository.py`
  - `get_by_sha256(sha256) -> SourceDocument | None`
  - `get(id) -> SourceDocument | None`
  - `create(dto: SourceDocumentCreate) -> SourceDocument`
  - `get_or_create_by_sha256(dto) -> tuple[SourceDocument, bool]` — handles the race via unique-constraint retry.

- `parse_run_repository.py`
  - `get(id)`, `get_latest_for(source_document_id, representation_kind, config_hash, project_id)` (the last joins `documents` to enforce same-project scope).
  - `create(dto)`, `update_status(id, status, **metrics)`.

- `parsed_document_repository.py`
  - `get_by_run(parse_run_id)`, `create(dto)`.

Each repository operates on Pydantic DTOs at the boundary and SQLAlchemy ORM internally. The CDM Pydantic types (`SourceDocument`, `ParseRun`, `ParsedDocument`) are the DTOs — no intermediate layer.

---

## 5. Service Layer

New module `app/services/parsing/parsing_service.py`:

```python
class ParsingService:
    def __init__(
        self,
        source_doc_repo: SourceDocumentRepository,
        parse_run_repo: ParseRunRepository,
        parsed_doc_repo: ParsedDocumentRepository,
        document_repo: DocumentRepository,
        storage: StorageService,
        llamaparse_client: AsyncLlamaCloud,
    ): ...

    async def ensure_source_document(
        self, *, bytes_: bytes, filename: str, mime_type: str
    ) -> SourceDocument: ...

    async def parse_and_persist(
        self,
        *,
        source: SourceDocument,
        file_path: str,
        representation_kind: str,
        config: dict[str, Any],
        project_id: UUID,
    ) -> tuple[ParseRun, ParsedDocument | None]:
        """Run parse with same-project reuse. Persists success, partial, and failure runs.
        Returns (run, parsed_doc-or-None). parsed_doc is None iff run.status == FAILED.
        Raises ParseFailedError on terminal failure after the failed ParseRun has been persisted.
        """
```

Reuse check, runner invocation, failure capture, and transactional persistence all live here. The router calls a single method and gets a persisted, queryable result.

---

## 6. Upload Path Integration (PR 3)

`app/services/document_service.py::initiate_upload`:

1. Validate file (existing logic).
2. Compute `sha256` (`compute_checksum` already exists at [backend/app/utils/file_validation.py](backend/app/utils/file_validation.py)).
3. Store bytes via `StorageService` (existing).
4. `ParsingService.ensure_source_document(...)` — idempotent on sha256.
5. Create `Document` row with `source_document_id` populated.
6. Trigger parse: `ParsingService.parse_and_persist(...)` — background task or inline based on existing dispatch pattern.

**Feature flag.** `settings.USE_CDM_PARSER: bool = True` (default True in dev). When False, upload falls back to the legacy `DocumentParser` port path unchanged. Flag and legacy path are deleted in the migration spec once the new path is validated in dev for a few days. Rollback lever stays live until then.

**`extracted_text` shim during cutover.** Downstream readers (chunking, indexing) currently read `documents.extracted_text`. For the duration of PR 3's cutover window, the CDM path also writes `documents.extracted_text = parsed_doc.full_text` after a successful parse. This is a transitional shim: the migration spec re-points downstream readers at `parsed_documents.full_text` and drops the column.

---

## 7. PR Slicing

Intentional byte-sized PRs for review capacity. Each is independently reviewable; none wires the previous PR's code into a hot path until the next one merges.

### PR 1 — Schema + models + repositories (no callers)

- Alembic migration creating `source_documents`, `parse_runs`, `parsed_documents`.
- Adds nullable `documents.source_document_id` FK.
- SQLAlchemy ORM models for the three new tables.
- Repository modules with round-trip tests against a real (test) database.
- **Deliverable:** persistence layer exists; no production caller yet. Reviewer focus: schema correctness, indexes, FK cascade, repo contracts.

### PR 2 — `ParsingService` + runner wiring + failed-run plumbing

- `LlamaParseRunError` defined; runner raises it on failure.
- `ParsingService.parse_and_persist` implemented against PR 1 repositories.
- Reuse policy implemented and unit-tested (same project / different project / different config).
- Integration test: mocked LlamaParse client, real repos. Happy path, partial path, failure path — each asserts rows in the expected tables.
- **Not called from `document_service` yet.** Reviewer focus: error plumbing, reuse logic, service-layer contract.

### PR 3 — Upload path cutover

- `document_service.initiate_upload` rewired onto `ParsingService` behind `USE_CDM_PARSER`.
- End-to-end test: HTTP upload → rows in `source_documents`, `documents`, `parse_runs`, `parsed_documents`.
- Legacy adapter path remains callable with flag off.
- **Deliverable:** new uploads are fully CDM-persisted. Reviewer focus: hot-path behavior, idempotency on sha256 re-upload, flag semantics.

### Sibling workstream — `cdm_persistence_migration.md`

- Drop legacy `parse_results` rows (dev-only; no customer impact).
- Backfill `source_documents` for pre-existing `documents` rows via stored-bytes sha256.
- Flip `documents.source_document_id` to `NOT NULL`.
- Drop `documents.extracted_text`, drop `parse_results` table.
- Delete `app/adapters/parsing/llamaparse.py`, `app/ports/document_parsing.py`, `USE_CDM_PARSER` flag.

---

## 8. Notes for the Migration Spec

Collected during this design so the migration spec doesn't re-derive them.

- **Legacy rows are not losslessly recoverable.** The legacy adapter at [backend/app/adapters/parsing/llamaparse.py:128](backend/app/adapters/parsing/llamaparse.py:128) destructures the LlamaParse response into `raw_text` / `markdown` / `pages` / `document_structure.items` and discards the raw `.model_dump()`. Re-adapting through the new `LlamaParseAdapter` requires re-parsing from source bytes.
- **Three recovery strategies** for legacy `parse_results` rows, in decreasing fidelity:
  1. Re-parse from source bytes (full CDM fidelity, costs credits, requires bytes present).
  2. Legacy-to-CDM shim that synthesizes a partial `ParsedDocument` from `document_structure.items` — approximate bboxes, approximate roles, newly minted block IDs.
  3. Minimal wrap: `ParseRun(parser=LEGACY)` + `ParsedDocument` with only `full_text`/`full_markdown`.
- **v1 migration recommendation: drop.** Dev-only data, no customer impact, small volume. The shim is throw-away code with no long-term home. Document strategies 1 and 2 in the migration spec for the hypothetical case where production data exists before cutover.
- **Downstream cascade.** Dropping legacy `parse_results` implies dropping `chunks`, `index_documents`, and any data referencing them. The migration spec must enumerate affected tables and sequence the truncations.
- **`documents.extracted_text`** stays populated during PR 3 (legacy fallback depends on it). Migration drops it after cutover is validated.
- **sha256 backfill** for pre-existing `documents`: read bytes from `storage_uri` (or reconstruct from current storage location), run `compute_checksum`, insert `source_documents` row, set `documents.source_document_id`. A pre-existing `documents` row whose bytes cannot be located is deleted — dev-only policy.

---

## 9. Acceptance Criteria

1. Three new tables per §2.1 exist; ORM models and repositories at §4 implemented with passing tests.
2. `documents.source_document_id` FK added (nullable in PR 1, enforced NOT NULL in migration spec).
3. `LlamaParseRunError` raised by runner on failure; `ParsingService` persists the failed `ParseRun`, re-raises `ParseFailedError` for routers.
4. `ParsingService.parse_and_persist` enforces same-project reuse keyed on `(source_document_id, representation_kind, config_hash)`; unique index prevents races.
5. `parsed_documents.content` round-trips `ParsedDocument.model_validate(row.content) == original`. No block, bbox, or span data lost.
6. Upload path (`document_service.initiate_upload`) under `USE_CDM_PARSER=True` writes rows to all four tables end-to-end; E2E test asserts this.
7. Feature flag off restores the legacy adapter path unchanged.
8. Existing backend tests continue to pass (`uv run python -m pytest -o "addopts="`).

---

## 10. Open Questions

- **Partial-run semantics.** `ParseRun(status=PARTIAL)` is persisted with a `ParsedDocument` whose `failed_pages` list is non-empty. Do embedding / extract workloads consume PARTIAL runs, or wait for SUCCEEDED only? Decide in the workload spec; schema is neutral.
- **ParseRun re-invocation without bytes.** When `provider_refs.llamaparse_job_id` is present, the parsing service could in principle re-hydrate without re-uploading. Out of scope here; revisit when extract adapter ships (§11.5).
- **`parsed_documents.content` size.** Multi-hundred-page PDFs may produce 5–15 MB JSONB. Postgres TOASTs beyond 2 KB, so read amplification is bounded, but a hard cap (e.g., reject docs whose adapted content exceeds N MB) may be prudent. Defer until a real oversized fixture surfaces.
- **Storage URI scheme.** Current storage returns filesystem paths; connector work will introduce `s3://` / `gdrive://` URIs. `SourceDocument.storage_uri` is an opaque string today; a scheme registry may be worth introducing when the second backend ships.
