# Parse Functionality Review — Backend (Iteration 1)

**Date:** 2026-07-11
**Scope:** Backend parse path — upload routers, `DocumentService` / `process_cdm_parsing`,
`ParsingService`, all five runners, custom-pipeline config/tools, CDM models, repositories,
storage adapter, and the parsing test suite.
**Context:** The project is being evolved from a personal RAG learning project into a
self-service tool for consulting clients, with a possible standalone commercial product later.

---

## TL;DR

The core architecture is genuinely good and worth keeping. The three things standing between
this and "safe to put in front of a consulting client" are:

1. A **cross-tenant data-exposure chain** around shared `SourceDocument`s.
2. A **path-traversal hole** in file storage.
3. **Synchronous parsing work running on the event loop**, which lets one user's OCR job
   freeze the whole API.

Everything else is iterative polish. Findings are organized as four shippable iterations,
ordered easy/low-risk → security/scalability. Each item is tagged with its dimension
(code quality, systems design, security, scalability) inline.

---

## What's already strong (keep it)

- **The CDM + provenance model is the crown jewel.** `ParseRun` (execution/provenance)
  separated from `ParsedDocument` (content), frozen Pydantic models in
  `backend/app/cdm/models.py`, and `config_hash`-based idempotent reuse in
  `backend/app/services/parsing/parsing_service.py:152`. This is the right shape for a
  commercial "compare parser tooling" product — most vendors don't get this right.
- **Ports & adapters is real, not decorative.** `StorageService` port, per-parser runners
  behind a registry, CDM adapters isolating vendor SDK shapes. Swapping local disk for S3
  later will be cheap because of this.
- **Failed runs are persisted with full context** (error, duration, config) rather than
  swallowed — great for an eval product.
- **Test coverage is honest**: per-runner tests, service tests, router tests, ORM round-trips.

> **Ordering note:** iterations below go easy → hard, but the security items in Iteration 3
> should ship **before** any client touches this, even though they're not first in effort order.

---

## Iteration 1 — Low-risk wins (days, no behavior change)

*Dimension: code quality.*

### 1.1 Deduplicate the failed-`ParseRun` boilerplate
All five runners repeat the same ~15 lines (timestamps, duration, build failed run, wrap in
error) — e.g. `custom_pipeline_runner.py:34-49` vs `llamaparse_runner.py:44-59`. Extract a
small helper (`RunClock`, or a context manager that yields `started_at` / `finalize()` and
builds the failed run on exception). This also fixes the drift where each runner formats
errors slightly differently.

### 1.2 Replace `Dict[ParserKind, Callable]` with a `Protocol`
`parsing_service.py:33` types runners as bare `Callable`; the runner signature is a de-facto
interface (`source, file_path, representation_kind, config, client, parse_run_id`). A
`ParserRunner(Protocol)` makes it type-checked and self-documenting.

### 1.3 Deduplicate the parse-dispatch plumbing in the router
Four endpoints in `backend/app/routers/documents.py` (upload, bulk, from-source,
create_parse_run) each rebuild `representation_kind` / `parse_cfg` /
`background_tasks.add_task(process_cdm_parsing, ...)` by hand. Extract one
`dispatch_parse(...)` helper — this is also where the later swap from BackgroundTasks to a
real queue happens in exactly one place (see 4.1).

### 1.4 Validate `parser_type` at the API boundary
`_ParseRunCreateRequest` (`documents.py:46`) and the upload forms accept any string; an
unknown parser only fails deep inside the background task and surfaces as "Internal error
during parsing." Type it as `ParserKind` (Pydantic will 422 it) and validate parser-specific
config with a small Pydantic model per parser. The custom pipeline already does this properly
in `cdm/adapters/custom_pipeline/config.py:104`; LlamaParse's `tier` / `expand` / `version`
get no such treatment.

### 1.5 Move `process_cdm_parsing` out of `document_service.py`
It's a 140-line background task with its own imports and client construction living in a
service module (`document_service.py:488`). It belongs in `services/parsing/tasks.py` next to
the thing it orchestrates.

### 1.6 Small hygiene items
- Close the `NamedTemporaryFile` handle in `docling_runner.py:48` (fd leak per batch).
- Move the inline `compute_checksum` import in `parsing_service.py:109` to the top.
- `datetime.utcnow` in ORM defaults is deprecated in Python 3.12 — use
  `datetime.now(timezone.utc)`.

---

## Iteration 2 — Correctness & robustness (a week-ish)

*Dimension: systems design — make the async path honest.*

### 2.1 Stop blocking the event loop (biggest single reliability fix)
`run_custom_pipeline` calls `inst.tool.run(...)` synchronously
(`custom_pipeline_runner.py:62-78`), and the Tesseract tool does
`pytesseract.image_to_data` inline. A 50-page OCR run freezes **every** request the server is
handling — login included — for minutes. Same for `_split_pdf` in the docling runner
(`docling_runner.py:102`). Wrap the CPU-bound sections in `asyncio.to_thread(...)` exactly as
the docling `_convert` already does. Cheap, mechanical, huge payoff.

### 2.2 Don't hold a DB connection across a multi-minute parse
`process_cdm_parsing` opens a session, queries the source doc (which begins a transaction),
then `await`s the external parse — the connection sits "idle in transaction" for the whole
run. The engine uses default pool sizing (`database.py:13`), so ~15 concurrent parses exhaust
the pool and the API starts timing out on unrelated requests. Restructure to: read what you
need → close the session → run the parse → open a fresh session to persist.

### 2.3 Make run + document persistence one transaction
`ParseRunRepository.create` commits, then `ParsedDocumentRepository.create` commits
(`parsing_service.py:181-190`). A crash between them yields a `succeeded` run whose
parsed-document endpoint 404s forever. Broader pattern fix: repositories should `flush`,
services should own commit (unit of work). This also makes future composition possible.

### 2.4 Recover documents stuck in `processing`
FastAPI `BackgroundTasks` are in-process and non-persistent: a restart mid-parse strands the
document at `processing` with no path out. Minimal iterative fix now: a startup sweep (or the
re-parse endpoint) that marks stale `processing` documents failed. The real fix is the
Iteration 4 queue (4.1).

### 2.5 Cache the docling converter
`_convert` builds a fresh `DocumentConverter()` per batch (`docling_runner.py:83`) — that
re-initializes models every 20 pages. Build once at module level (it's already serialized by
the semaphore).

---

## Iteration 3 — Security hardening (do before any client sees this)

*Dimension: security / multi-tenancy.*

Effort-wise this fits third, but **items 3.1–3.3 are the actual gate for the
consulting-client goal.** The current model is effectively "all authenticated users share one
tenant" — fine for a learning project, disqualifying for a multi-client tool.

### 3.1 Close the cross-tenant chain around `SourceDocument`
Three links, each individually broken:

- `GET /source-documents` (`routers/source_documents.py:14`) lists **every user's** uploads —
  ids, filenames, hashes — with no ownership filter.
- `POST /documents/from-source` (`routers/documents.py:308`) links any `source_document_id`
  into the caller's project with **no ownership check**, after which
  `GET /documents/{id}/file` downloads the other user's file.
- `_user_owns_source` (`routers/parse_runs.py:24`) grants access to a `ParseRun` if the caller
  owns *any* document over the same content — so two users who uploaded the same file can
  read **and delete** each other's runs, configs, and raw payloads
  (`parse_runs.py:143` is a cross-user destructive action).

**Fix direction:** introduce an explicit owner/tenant on `SourceDocument` (or an ownership
join table), scope every source-document and parse-run query by it, and authorize parse-run
access via the run's own `project_id` (the column already exists on
`models/parse_run.py:25` — the authz just doesn't use it). Decide deliberately whether
content dedup is per-tenant or global; global dedup across clients is itself a subtle
info-leak — scope it per tenant for a client-facing product.

### 3.2 Fix path traversal in storage
`ensure_source_document` writes to `uploads/{sha256}/{filename}` with the raw user-supplied
filename (`parsing_service.py:111`), and `LocalStorageService.save` joins
`base_path / relative_path` with no containment check (`adapters/storage/local.py:39`). A
filename like `..\..\..\evil` writes outside the storage root.

**Two-layer fix:** sanitize to `Path(filename).name` at the call site, **and** enforce
`full_path.resolve().is_relative_to(self.base_path)` inside the adapter so no future caller
can regress it. Also stop mutating the shared row in `parsing_service.py:122` — user B
re-uploading shared content currently rewrites user A's `storage_uri`.

### 3.3 Production config guards
`backend/app/config.py` ships `JWT_SECRET_KEY="change-this-..."`, a placeholder
`ENCRYPTION_KEY`, and `DEBUG=True` (which also turns on SQL echo) as *defaults*. Add a
startup check that refuses to boot outside dev if any secret is a placeholder.

### 3.4 Smaller hardening
- Don't surface raw exception text (`f"{type(exc).__name__}: {exc}"`) in user-visible
  `status_message` / `error` — it leaks server paths. Log the detail, store a sanitized message.
- Add per-user rate limiting on parse triggers — local parsers (docling/tesseract) burn
  server CPU, and nothing today stops a user launching unbounded concurrent
  custom-pipeline runs.
- Longer-term flag: parsing untrusted PDFs with fitz/pypdf/camelot in-process is a real
  attack surface — the Iteration 4 worker split is also the sandboxing boundary.

---

## Iteration 4 — Scalability & systems design (the productization step)

*Dimension: scalability.*

### 4.1 Move parsing to a persistent job queue with worker processes
This is the structural change everything above prepares for: `BackgroundTasks` → a
Postgres-backed queue (arq, procrastinate, or a SKIP-LOCKED table — Postgres is already in
the stack, don't add Redis/Celery yet) with separate worker processes. It buys:
retries, restart-survival, per-tenant concurrency limits, horizontal scale-out of CPU-heavy
parsing independent of the API, a process boundary for sandboxing untrusted documents, and it
makes the docling semaphore an actual global constraint instead of per-process. Because of
1.3, the swap touches one dispatch helper.

### 4.2 Get big blobs out of hot rows
`parse_runs.raw_payload` stores the full vendor payload — for docling, the *entire serialized
document per batch* — in a `JSON` column, and `list_for_source_document` loads full entities,
so listing a document's runs pulls every payload into memory even though the response schema
drops them.

- **Short term:** mark `raw_payload` (and `parsed_documents.content`) as `deferred()` in the ORM.
- **Medium term:** write raw payloads to object storage via the existing `StorageService`
  port and keep only a URI in the row — this is also what makes an S3 migration trivial.

### 4.3 Kill the data duplication
Full text currently lives in up to five places per document: `documents.extracted_text`
(the shim at `document_service.py:597`), `parsed_documents.full_text`, `full_markdown`, again
inside `parsed_documents.content`, and again inside `raw_payload`. Retire the shim (the
migration spec already plans this), and make `content` blocks-only with
`full_text` / `full_markdown` as the single denormalized columns.

### 4.4 Streaming and limits
Upload reads the whole file into memory before validating size (`routers/documents.py:144`) —
a 20-file bulk request can spike ~500MB. Enforce size while streaming to a temp file, and add
pagination to run/source listings.

---

## Suggested sequence

1. **This week:** 1.1–1.6 as a cleanup PR series.
2. **Next:** 2.1 + 2.2 — the fixes that stop the app falling over under one real workload.
3. **Before any client onboarding:** Iteration 3 tenancy work as its own tracked project.
4. **When there's a second concurrent user in practice:** Iteration 4.

Each item is scoped to be a single GitHub issue + PR per the project workflow.

## Structural note

These are tracked as **iterations** (shippable units) rather than by dimension
(code quality / security / etc.), because the dimensions cut across them; each item carries
its dimension tag inline so both views are available.
