# ParseRun Viewer — Design

**Date:** 2026-04-25
**Status:** Draft (pending review)
**Related specs:** [cdm_v1.md](./cdm_v1.md), [cdm_persistence.md](./cdm_persistence.md), [cdm_viewer_frontend.md](./cdm_viewer_frontend.md)

## 1. Motivation

Users need full visibility into how their documents are transformed by the parsing pipeline. Today the document sheet exposes the adapted `ParsedDocument` (CDM) but hides the parser's raw response and the `ParseRun` execution context (parser, config, timing, cost, errors). When a parse "looks wrong," there is no way to compare CDM vs. source-of-truth without re-running against the parser SDK.

The ParseRun Viewer is a per-document debugging surface that answers the question:

> "I put this document through `<parser>` with `<config>`, it returned `<raw payload>`, and we interpreted it as `<ParsedDocument>`."

Comparison across runs/parsers and bulk-run aggregates are explicitly **out of scope** for v1; those land in the evaluation flow later.

## 2. Scope

### In scope (v1)

- Persist the verbatim parser SDK response on every `ParseRun`.
- Per-document run timeline in the existing document sheet (list of runs, status, parser, age, "open viewer" link).
- Dedicated viewer route `/documents/:documentId/runs/:runId` with:
  - Sticky header: parser, version, status, timing, cost, tokens, warnings, error, config (read-only JSON).
  - Two-pane body: raw JSON (collapsible, syntax-highlighted, copy/download) on the left; adapted CDM viewer (reuse `ParsedDocumentViewer`) on the right.
- Re-parse action wired to the existing `ReparseDialog` (parser picker + parser-specific config form).
- API endpoint to fetch a run's raw payload separately from the standard ParseRun read (payloads are large; keep them off list responses).

### Out of scope (deferred)

- Raw JSON full-text search / filter
- Page-by-page raw↔CDM scroll sync
- Source PDF/image preview panel on the viewer
- Diff/comparison between two runs
- Global cross-document run feed
- Bulk-upload run grouping
- Parse-as-component in the agent flow builder

## 3. Backend changes

### 3.1 Persistence

Add a `raw_payload` column to `parse_runs`:

- Type: `JSONB`, nullable (legacy rows have `NULL`; failures may also have `NULL`).
- Single round-trip with the existing run row; no separate table for v1. Revisit if row sizes become operationally painful.
- Alembic migration in `backend/alembic/versions/`.

### 3.2 CDM model

Add `raw_payload: Optional[Dict[str, Any]] = None` to `app/cdm/source.py::ParseRun`. This is consistent with the existing parser-specific fields (`parser`, `config`, `provider_refs`) — `ParseRun` already records execution provenance, not parser-agnostic content. `ParsedDocument` remains the parser-agnostic surface.

### 3.3 Repository / service wiring

- `app/repositories/parse_run_repository.py::ParseRunCreate` — accept `raw_payload`.
- `app/services/parsing/llamaparse_runner.py` — thread `raw_payload=raw` through to persistence (it already calls `result.model_dump()` and passes `raw` to the adapter; the dict simply gets persisted alongside).
- `app/services/parsing/parsing_service.py` — no logic change; the create call grows one field.

### 3.4 API surface

- `GET /api/v1/parse-runs/{id}/raw-payload` — returns `{ "raw_payload": <json> | null }`. Auth check identical to existing `parse_runs` router. Kept as a separate endpoint so list responses stay small.
- Existing `GET /api/v1/parse-runs/{id}` and the per-document list endpoint remain unchanged in shape (no `raw_payload` on those).

### 3.5 Tests

- `tests/repositories/test_parse_run_repository.py` — persist/retrieve roundtrip with a non-trivial dict.
- `tests/services/parsing/test_parsing_service.py` — assert `raw_payload` is populated on success and `None` on adapter-only paths if any.
- New router test for the raw-payload endpoint: 200 with payload, 404 for unknown run, 401/403 for unauthorized.

## 4. Frontend changes

### 4.1 Run timeline in the document sheet

In the existing document sheet, add a "Parse Runs" section above or below the current CDM viewer:

- Vertical list of runs for the document, newest first.
- Each row: status chip · parser (e.g. `llamaparse@v1`) · `representation_kind` · started-at (relative) · duration · cost (if present).
- Row actions: "Open viewer" (deep-links to the dedicated route), "Re-parse" (only on the most recent row, opens existing `ReparseDialog`).
- Failure rows show error excerpt inline.

### 4.2 Dedicated viewer route

Route: `/documents/:documentId/runs/:runId`. Page component: `ParseRunDetailPage`.

Layout (desktop, ≥1024px):

```
┌────────────────────────────────────────────────────────────┐
│  ← Back to foo.pdf                          [Re-parse ▾]   │
│  Run abc123 · llamaparse@v1 · ✓ Succeeded · 4.2s · $0.012  │
│  Config: {…}  (collapsed by default, expand to show JSON)  │
├─────────────────────────────┬──────────────────────────────┤
│                             │                              │
│   RAW PAYLOAD               │   ADAPTED CDM                │
│   (collapsible JSON tree)   │   (ParsedDocumentViewer)     │
│   [Copy] [Download]         │                              │
│                             │                              │
│                             │                              │
└─────────────────────────────┴──────────────────────────────┘
```

Below the lg breakpoint, panes stack vertically with the raw payload first.

### 4.3 Components

- `ParseRunDetailPage` — page shell, route param parsing, layout, error/loading states.
- `RunHeader` — metadata strip + collapsible config view.
- `RawPayloadViewer` — collapsible JSON tree with copy/download. Use a small dependency (e.g. `react-json-view-lite`) or hand-roll using existing UI primitives — decide in implementation plan based on bundle cost.
- `ParsedDocumentViewer` — reuse the component from the existing CDM viewer work.
- `RunTimeline` (lives in the document sheet) — list rows + actions.

### 4.4 API hooks

- `useParseRunDetail(runId)` — fetches the existing `GET /api/v1/parse-runs/{id}` for metadata.
- `useParseRunRawPayload(runId)` — fetches `GET /api/v1/parse-runs/{id}/raw-payload` lazily (only when the dedicated viewer is mounted).
- `useDocumentParseRuns(documentId)` — drives the timeline; reuse existing list endpoint if it covers this, otherwise extend.

### 4.5 Re-parse

The "Re-parse" button on the viewer header opens the existing `ReparseDialog` with the current run's parser pre-selected. On success, navigate to the new run's viewer route.

## 5. Phasing

Two phases, each one PR + issue:

**Phase 1 — Raw payload persistence**
Backend-only. Migration, model, repo, runner, endpoint, tests. Ships with no UI change. Unblocks the viewer.

**Phase 2 — ParseRun Viewer UI**
Frontend. Run timeline in sheet + dedicated viewer route + raw payload pane + re-parse rewire.

## 6. Open questions / decisions to revisit

- JSON tree library choice (bundle size vs. UX). Decide in Phase 2 plan.
- Whether to show partial raw payload for `partial`/`failed` runs (likely yes if persisted, gated `null`-safe).
- When a global run feed or comparison view lands, the dedicated route may grow a sibling `/parse-runs/:runId` flat alias. Defer.

## 7. Acceptance criteria

**Phase 1**
- New `parse_runs.raw_payload` column exists; migration runs cleanly on a DB previously at head.
- LlamaParse runs persist the verbatim SDK dict; failures persist `NULL` (or partial dict if available — runner choice).
- `GET /api/v1/parse-runs/{id}/raw-payload` returns the dict with auth equivalent to the rest of the parse-runs router.
- Repository, service, and router tests pass.

**Phase 2**
- From the document sheet, the user can see all runs for a document and open any run's dedicated viewer.
- The viewer shows raw JSON (verbatim) and adapted CDM side-by-side, with run metadata and config visible above.
- Re-parse from the viewer launches the existing dialog and, on success, navigates to the new run.
- No regressions in the existing CDM viewer or document upload flow.
