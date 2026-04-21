# Canonical Document Model (CDM) — v1 Spec

> **Status**: Spec for v1 implementation.
> **Scope**: CDM types + LlamaParse adapter + lightweight eval harness.
> **Out of scope**: Other parser adapters, downstream workloads (split/extract/classify), citation tracking implementation, streaming, columnar storage.
> **Reference design**: [`docs/planning/cdm_architecture.md`](../planning/cdm_architecture.md)

---

## 1. Goals

Ship the minimum CDM surface that:

1. Represents a parsed document as a parser-agnostic, frozen Pydantic v2 model.
2. Has one working adapter (LlamaParse) that round-trips with no meaningful data loss.
3. Establishes the observability primitives (SourceDocument, ParseRun) that downstream workloads and UIs will depend on.
4. Ships with a lightweight eval harness that asserts structural invariants and records run metrics.
5. Leaves clear extension points for the three deferred concerns: additional adapters, downstream workloads, citation tracking implementation.

Non-goals for v1: backwards compatibility, migration from any existing parser integration, workload implementation, production-grade eval framework.

---

## 2. Package Layout

```
backend/app/cdm/
  __init__.py
  models.py              # ParsedDocument, Block, Page, Table, BBox, ...
  source.py              # SourceDocument, ParseRun
  citation.py            # CitationRef (type only; resolution deferred)
  adapters/
    __init__.py
    base.py              # ParserAdapter protocol, SourceMeta
    llamaparse.py        # LlamaParse adapter implementation
  eval/
    __init__.py
    fixtures/            # small sample PDFs + expected snapshots (gitignored bytes, checked-in hashes)
    test_llamaparse.py   # pytest-based structural + snapshot eval
    recorder.py          # writes ParseRun metrics to JSON log for manual diffing
```

**Rationale:** CDM types are shared domain value objects — peers of `app/models/`, not a service. Services that orchestrate parsing (ingestion pipelines) live in `app/services/parsing/` and import `app.cdm`. Keeps the `router → service → repository` layering clean.

---

## 3. Type Hierarchy

### 3.1 Three-level identity

```
SourceDocument (1) ──< ParseRun (N) ──> ParsedDocument (1 per successful run)
    id, sha256,              representation_kind,
    storage_uri, filename    config, parser, metrics
```

- **`SourceDocument`** — content-addressable representation of the input bytes. Identified by sha256. Carries `storage_uri` (S3 key / local path) so providers that require the original bytes can fetch them.
- **`ParseRun`** — execution record. One per parser invocation. Carries config, cost, latency, tokens, warnings, failed pages, parser-native job refs.
- **`ParsedDocument`** — content artifact. The pages/blocks/tables. References `source_document_id` and `parse_run_id`.

**A single `SourceDocument` can have multiple `ParsedDocument` representations** — e.g. a `vector_light` representation for embedding and an `extract_rich` representation for extraction. Callers pick representation by `(source_document_id, representation_kind)`; orchestration either finds an existing run or triggers a new one.

### 3.2 SourceDocument

```python
class SourceDocument(BaseModel):
    id:           str              # UUIDv4, application-minted
    sha256:       str              # content hash — natural key
    filename:     Optional[str] = None
    mime_type:    Optional[str] = None
    byte_size:    Optional[int] = None
    storage_uri:  Optional[str] = None   # fetch location for byte-in providers
    created_at:   datetime
```

### 3.3 ParseRun

```python
class ParseRunStatus(str, Enum):
    PENDING   = "pending"
    RUNNING   = "running"
    SUCCEEDED = "succeeded"
    FAILED    = "failed"
    PARTIAL   = "partial"          # some pages parsed, some failed

class ParseRun(BaseModel):
    id:                   str              # UUIDv4
    source_document_id:   str
    parser:               ParserKind
    parser_version:       Optional[str] = None
    representation_kind:  str              # open string: "vector_light" | "extract_rich" | ...
    config:               Dict[str, Any] = {}
    status:               ParseRunStatus
    started_at:           datetime
    finished_at:          Optional[datetime] = None
    duration_ms:          Optional[int] = None
    cost:                 Dict[str, Any] = {}       # parser-shaped, e.g. {"credits": 1.2}
    input_tokens:         Optional[int] = None
    output_tokens:        Optional[int] = None
    warnings:             List[str] = []
    failed_pages:         List[int] = []
    provider_refs:        Dict[str, Any] = {}       # e.g. {"llamaparse_job_id": "..."}
    error:                Optional[str] = None
```

**`provider_refs`** holds parser-native handles (LlamaParse `job_id`, Landing AI `job_id`) so downstream extractors can re-reference the provider's own artifact without re-uploading bytes. Opaque to CDM.

### 3.4 ParsedDocument and children

Shape follows `docs/planning/cdm_architecture.md` §2 with these adjustments:

- `Provenance` is removed from `ParsedDocument`. Metrics and run metadata live on `ParseRun`.
- `ParsedDocument` gains `source_document_id: str` and `parse_run_id: str`.
- `derived_from` / `derivation` (for future `split()` children) move to `ParsedDocument` directly — they describe lineage between ParsedDocuments, not runs.

Otherwise: `Page`, `Block`, `Span`, `Table`, `Cell`, `BBox`, `BlockRole`, `ParserKind`, `Label`, `Quality`, `Style` as specified.

**Frozen**: all core types are `model_config(frozen=True)`. Mutations via `model_copy(update=...)`.

### 3.5 CitationRef (type only — resolution deferred)

```python
class CitationRef(BaseModel):
    source_document_id: str
    parse_run_id:       str         # required: block IDs are only unique within a run
    block_id:           str
    page_index:         int
    char_start:         Optional[int] = None
    char_end:           Optional[int] = None
    cell_id:            Optional[str] = None   # "r{row}c{col}" for tables
    bbox:               Optional[BBox] = None  # denormalized for UI overlay without a lookup
```

Ships as a type in v1 so downstream workloads can depend on it. The mechanism that *produces* `CitationRef`s from extract/classify outputs is deferred to the workload specs.

---

## 4. LlamaParse Adapter

### 4.1 Protocol

```python
class SourceMeta(BaseModel):
    source_document_id: str
    parse_run_id:       str
    filename:           Optional[str] = None
    sha256:             Optional[str] = None

class ParserAdapter(Protocol):
    parser: ClassVar[ParserKind]

    def adapt(self, raw: Any, source_meta: SourceMeta) -> ParsedDocument: ...
```

Adapters are stateless. `raw` is the parser's native output object; `source_meta` carries identity so IDs on the output reference the right `SourceDocument` / `ParseRun`.

### 4.2 Mapping rules (LlamaParse → CDM)

Follows `docs/planning/cdm_architecture.md` §5 "LlamaParse" notes. Key points:

- Call `.model_dump()` on `ParsingGetResponse` first.
- Flatten nested `items` tree → flat `blocks` list; preserve `parent_id` / `children_ids`.
- `type → BlockRole` via fixed lookup (heading/text/list/image/table/header/footer/code/link).
- `label → native_label`; `type → native_type`.
- `md → Block.markdown`, `value → Block.text`.
- Convert PDF points `(x, y, w, h)` to normalized `(x0, y0, x1, y1)` using page width/height; preserve originals on `BBox.source_space` / `source_coords`.
- Page indexes: subtract 1 (LlamaParse is 1-indexed; CDM canonical is 0-indexed). Preserve original as `Page.parser_extras["source_page_number"]`.
- Multi-bbox items: union for `Block.bbox`; originals in `parser_extras["bboxes"]`.
- `start_index` / `end_index` → `parser_extras["char_range"]`.
- Per-item `confidence` → `Block.quality.confidence`; per-page `confidence` → `Page.quality.confidence`.
- `original_orientation_angle` → `Page.rotation`.
- `model_invocations`, `pdf-inputTokens`, `pdf-outputTokens`, `pdf-llmTime` → roll up into the `ParseRun` (`input_tokens`, `output_tokens`, `duration_ms`). Per-page invocation detail → `parse_run.config["invocations"]` or a structured field if it becomes useful. v1: just sum tokens.
- `job_id` → `parse_run.provider_refs["llamaparse_job_id"]`.
- Build `full_markdown` by joining per-page markdowns with `\n\n<!-- PAGE BREAK -->\n\n`; build `full_text` by joining page text.
- Block IDs: mint deterministically as `f"{source_document_id}:{page_index}:{reading_order}"` so a reparse with the same input produces stable IDs (useful for eval snapshots).

### 4.3 Orchestration (thin)

A thin orchestrator function lives in `app/services/parsing/llamaparse_runner.py` (outside the CDM package) that:

1. Takes a `SourceDocument` and a config dict.
2. Creates a `ParseRun` (`status=PENDING`).
3. Calls LlamaParse client; transitions to `RUNNING` / `SUCCEEDED` / `FAILED` / `PARTIAL`.
4. Populates `ParseRun` metrics from the response.
5. Calls `LlamaParseAdapter().adapt(...)` to build the `ParsedDocument`.
6. Returns `(ParseRun, ParsedDocument)`.

**Persistence is out of scope for this PR.** Return the objects in-memory; a future PR wires them to repositories. This keeps the CDM PR focused on the model + adapter contract.

---

## 5. Eval Harness

### 5.1 Structural invariants

For every fixture + adapter output, assert:

- `page_count == len(pages)`
- Every `block.page_index` in `[0, page_count)`
- Every `bbox` has `0 <= x0 <= x1 <= 1` and `0 <= y0 <= y1 <= 1`
- Every block has a non-empty `role` and `native_type`
- Every `Page.block_ids` references blocks that exist in `doc.blocks`
- `parent_id` references (if set) point to blocks that exist
- `full_markdown` / `full_text` non-empty when pages contain content
- `parse_run.source_document_id == parsed_doc.source_document_id`
- `parsed_doc.parse_run_id == parse_run.id`
- Round-trip: `ParsedDocument.model_validate_json(doc.model_dump_json())` equals `doc`

### 5.2 Snapshot eval

For each fixture: snapshot `ParsedDocument.model_dump_json()` to `fixtures/<name>.expected.json` on first run; diff on subsequent runs. Updating snapshots is an intentional commit, not silent.

### 5.3 Metrics recorder

On every eval run, append a line to `cdm/eval/metrics.jsonl`:

```json
{"ts": "...", "fixture": "...", "parser": "llamaparse", "config_hash": "...", "duration_ms": 3210, "input_tokens": 1200, "output_tokens": 450, "cost": {...}}
```

Not a framework — just a log you can grep. Per-config evals and config matrices are deferred.

### 5.4 Fixtures

2–3 small PDFs:

- `one_page_text.pdf` — single page, plain prose (smoke test).
- `table_and_headings.pdf` — one table + two heading levels (exercises table model and hierarchy).
- `multi_column.pdf` — two-column layout (exercises reading order).

Bytes checked into `fixtures/` (keep under 500 KB total; larger fixtures stored by reference with sha256 if they grow).

---

## 6. Notes for Downstream Work (Non-binding Reminders)

These are not v1 deliverables; they're here so the extract / classify / split specs don't re-derive them from scratch.

### 6.1 Extract adapter note — citation mapping burden

Different extract providers take different inputs:

- **Markdown-in extractors** (Landing AI extract, most small local models): fed `block.markdown` / `full_markdown`. Citations back to block IDs are natural — you know which block you fed in.
- **Bytes-in extractors** (LlamaParse extract, vision models fed raw bytes): the extractor returns citations as page + bbox (or char offsets into its own rendered view). Mapping those back to CDM block IDs is a **post-processing step that lives in the extract adapter**, not in CDM.
- **Provider-native extract endpoints** (LlamaParse, Landing AI) can be re-invoked using `ParseRun.provider_refs[...]` without re-uploading bytes.

CDM guarantees: stable block IDs within a ParseRun, normalized bboxes, `full_markdown` cached on root. Mapping logic is the extractor's problem.

### 6.2 Workload contracts

`split()`, `extract()`, `classify()` signatures and invariants are captured in `docs/planning/cdm_architecture.md` §7. The CDM types in v1 are chosen to satisfy those signatures without modification — confirm against that doc when writing the workload specs.

### 6.3 Observability boundaries

- **ParseRun** owns parser cost / latency / tokens.
- **LangGraph checkpointer** owns agent cost / latency / node I/O.
- **Join via IDs**, not shared storage. `CitationRef.parse_run_id` + `block_id` is the bridge between an agent output and a source region.

---

## 7. Acceptance Criteria

1. `app/cdm/models.py`, `app/cdm/source.py`, `app/cdm/citation.py` defined with types per §3. All frozen Pydantic v2.
2. `app/cdm/adapters/base.py` defines `ParserAdapter` protocol and `SourceMeta`.
3. `app/cdm/adapters/llamaparse.py` implements the adapter per §4.2.
4. `app/services/parsing/llamaparse_runner.py` orchestrates one end-to-end parse returning `(ParseRun, ParsedDocument)`.
5. `app/cdm/eval/test_llamaparse.py` passes against 2–3 fixtures; structural invariants from §5.1 all assert.
6. Snapshot files committed under `app/cdm/eval/fixtures/`.
7. Existing backend tests continue to pass (`uv run python -m pytest -o "addopts="`).
8. No persistence layer changes in this PR — repositories / Alembic migrations come in a follow-up.

---

## 8. Relationship to Existing Models (Persistence Follow-up)

v1 introduces CDM as an in-memory Pydantic layer and does **not** touch persistence. The follow-up persistence PR must reconcile CDM types with the existing ORM:

| CDM type | Existing ORM | Reconciliation |
|---|---|---|
| `SourceDocument` | `app/models/document.py::Document` | Same concept. Extend `Document` with `sha256`, `storage_uri`, `mime_type`, `byte_size` columns. `SourceDocument` becomes the Pydantic DTO; `Document` stays the ORM model. **Do not create a `source_documents` table.** |
| `ParseRun` + `ParsedDocument` | `app/models/parse_result.py::ParseResult` | **Split required.** `ParseResult` today fuses execution metadata (`parser_type`, `parser_config`, `status`, `started_at`, `diagnostics`) with content (`raw_text`, `markdown`, `pages`, `document_structure`). Persistence PR splits into a `parse_runs` table (execution) and stores `ParsedDocument` as JSONB on a sibling table or column keyed by `parse_run_id`. |
| `ParseRun.representation_kind` | `ParseResult.fidelity` | Same concept (text / markdown / layout_json). Rename and keep open (not an enum). |
| `ParserAdapter` / `ParsedDocument` | `app/ports/document_parsing.py::DocumentParser` + `ParseOutput` | Superseded. Old port + dataclass retired once upload pipeline is re-wired onto CDM. |
| `ParsedDocument.full_text` | `Document.extracted_text` | Redundant after CDM is persisted. Drop `extracted_text` in the migration. |

**No backwards compatibility is promised.** The persistence PR writes a migration that splits `parse_results`, drops `Document.extracted_text`, adds the new `Document` columns, and rewires the upload and parsing pipelines onto CDM. Existing adapter code at `app/adapters/parsing/llamaparse.py` is retired at that point.

---

## 9. Source-of-Truth Storage (Forward-Looking Note)

**Policy: rag-admin always stores a content-addressed snapshot of every ingested document.** External sources (future connectors: Google Drive, Notion, Confluence, etc.) add a reference pointer but do not replace the snapshot.

Rationale: live source links rot. Deleted files, permission changes, and content edits silently invalidate saved citations — an agent's answer from last month can become un-verifiable if the underlying doc drifts. Production RAG systems default to copy-on-ingest for this reason.

Implementation guidance for future connector work (not v1):

- Keep `SourceDocument.storage_uri` as rag-admin's own snapshot location.
- Extend `SourceDocument` with optional `external_uri`, `external_revision`, `external_synced_at` when connectors ship.
- Each sync that produces changed bytes creates a **new** `SourceDocument` (new `sha256`, new id). Prior `SourceDocument`s are retained so historical citations resolve against the snapshot they were made against.
- UI can render "source: Notion page X, rev 7 (synced 2026-03-15)" with a live-view link, but citation bbox/offset rendering always targets the stored snapshot.

This is compatible with the v1 CDM types — the follow-up fields are purely additive on `SourceDocument`.

---

## 10. Open Questions Inherited from Design Doc

All 10 items in `docs/planning/cdm_architecture.md` §9 remain deferred. Additionally:

- **Persistence schema** — Alembic migration extending `documents`, splitting `parse_results` into `parse_runs` + ParsedDocument storage (JSONB vs. decomposed tables), dropping `Document.extracted_text`, and retiring `app/adapters/parsing/` in favor of the CDM stack. See §8 for the reconciliation plan — follow-up PR.
- **UI integration** — Playground documents view and Agents flow view surfacing ParseRun metrics — follow-up spec.
- **Config-matrix eval** — per-parse-config eval framework (promoted from §5 when needed) — deferred.

---

## 11. Next Steps (for follow-up sessions)

v1 delivered in PR #25: CDM types, LlamaParse adapter, runner, eval harness. **This spec is done** — do NOT expand it further. The work below is scoped to new specs in `docs/specs/`, each with its own plan under `docs/planning/`.

### 11.1 Merge gate (small, same PR or immediate follow-up)

1. **Unblock libmagic** — `app/services/__init__.py` eagerly imports `document_service` → `magic`. Either install libmagic in the backend env (`pip install python-magic-bin` on Windows) or lazify the imports so the full pytest suite can run. Task 15 regression is blocked until this lands.
2. **Failed ParseRun plumbing** — `run_llamaparse` currently constructs a `ParseRun(status=FAILED)` in its except block but discards it. Decide:
   - Option A: raise a custom `LlamaParseRunError(RuntimeError)` carrying `.run` so persistence can record it.
   - Option B: return `(ParseRun, Optional[ParsedDocument])` and never raise.
   - Option C: delete the dead local and commit to raise-and-log only.
   - Recommendation: Option A — keeps the call-site clean but lets the persistence layer (§11.2) record failures without a second API.

### 11.2 Persistence spec (largest, load-bearing)

**New spec:** `docs/specs/cdm_persistence.md`

Reconcile the in-memory CDM types with the existing ORM and write the migration. Key design questions:

- **`Document` ↔ `SourceDocument` unification.** Keep `documents` table, widen it to cover `SourceDocument` fields (add `sha256`, `storage_uri`, `byte_size` if missing), drop `extracted_text` (now derivable from `ParsedDocument.full_text`). Decide whether `Document.id` remains the single identity or is replaced by `SourceDocument.id`.
- **Split `parse_results` into `parse_runs` + `parsed_documents`.** `parse_runs` stores execution metrics; `parsed_documents` stores CDM content. Foreign key: `parsed_documents.parse_run_id → parse_runs.id`.
- **ParsedDocument storage: JSONB blob vs. normalized tables.** Trade-off: blob is simple and round-trips cleanly; normalized tables (`pages`, `blocks`, `cells`) enable SQL queries on structure but bloat schema and require bidirectional mapping. **Recommendation: start with JSONB, add selective extraction (e.g. `blocks` table with `role`, `page_index`, `text_fts`) only when a query need shows up.**
- **Migration of existing rows.** Retire `app/adapters/parsing/llamaparse.py` and `app/ports/document_parsing.py`. Existing `parse_results` rows either (a) migrate by replaying parser against stored source bytes, (b) wrap as a single legacy `ParseRun(parser=ParserKind.LEGACY, ...)` without re-parsing, or (c) drop. Decide based on how much production data exists.
- **Repository layer:** `SourceDocumentRepository`, `ParseRunRepository`, `ParsedDocumentRepository` under `app/repositories/`.

### 11.3 Ingestion integration

**New spec:** `docs/specs/cdm_ingestion.md`

Wire the runner into the upload flow:

- `document_service.py` upload path calls `run_llamaparse()` instead of the legacy `DocumentParser` port.
- Retire `app/adapters/parsing/llamaparse.py` and `app/ports/document_parsing.py` after persistence lands.
- Background worker (if one exists) writes `ParseRun` + `ParsedDocument` via the repositories from §11.2.
- Idempotency: re-upload of same `sha256` reuses the existing `SourceDocument`; re-parse creates a new `ParseRun`.

### 11.4 UI viewer

**New spec:** `docs/specs/cdm_viewer.md`

Playground surface for `ParsedDocument`. Spec should cover:

- Page list sidebar with confidence indicators
- Block tree / reading-order view
- Markdown and text tabs
- PDF + normalized-bbox overlay (citation rendering uses the same bbox pipeline)
- ParseRun history panel with re-run-with-different-config button
- Cost/latency readout per run

This is where provenance earns its keep visually — a user should be able to click a block and see where it came from in the PDF.

### 11.5 First downstream workload (extract) + real fixtures

**New spec:** `docs/specs/cdm_extract_adapter.md`

Port one existing extract path to consume `ParsedDocument` and emit `CitationRef`s. Prove the CDM hypothesis end-to-end: parser-agnostic extract, citations that resolve back to bboxes.

In parallel: replace synthetic eval fixtures with 3-5 recorded real LlamaParse responses from representative PDFs (short memo, multi-column paper, table-heavy financial doc, nested-list contract). Regenerate snapshots. Keep synthetic fixtures as edge-case probes (empty document, single-page, deep nesting).

### Suggested sequencing

1. 11.1 (merge gate, hours)
2. 11.2 persistence (spec + plan + PR, likely 2-3 days)
3. 11.3 ingestion (builds on 11.2, ~1 day)
4. 11.4 viewer (parallel with 11.5, ~2 days)
5. 11.5 extract + real fixtures (~2 days)

Each follow-up should follow the same flow: spec in `docs/specs/`, plan in `docs/planning/YYYY-MM-DD-<name>.md`, GitHub issue, subagent-driven execution.
