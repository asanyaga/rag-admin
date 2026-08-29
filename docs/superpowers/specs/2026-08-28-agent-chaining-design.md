# Definition 2 — Chaining & Edge Validation in the Composer

- **Date:** 2026-08-28
- **Status:** Design — pending review
- **Author:** Brainstormed with Claude
- **Builds on:** [2026-08-27-parse-tool-composer-design.md](2026-08-27-parse-tool-composer-design.md) (the three-way tool contract + generic run form this extends). Slices A + B merged (#189, #191).

## Objective

Make multi-tool agents (**Definition 2**) first-class: a user can chain configured
tools in the composer (`extract → review → export` today), the composer **validates**
the chain and shows what each node still needs, and the chain **runs through the
generic run form** — not just a bespoke per-domain entrypoint. Prove it end-to-end on
the tools that already exist; add no new tools.

## Product decisions (brainstormed)

1. **Input model — `source`-tagged inputs.** `FieldSpec` gains
   `source: 'form' | 'upstream' | 'either'`. One input list per tool stays the single
   source of truth; edge-validation and the run form both derive from it.
2. **Scope — validate + run the existing chain.** Retrofit `llamaextract` /
   `human-review` / `export` contracts so `extract → review → export` is authorable,
   validated, and runnable via the generic path. No new tools.
3. **Validation UX — warn + gate Run.** Free-draw edges, free save (drafts); show each
   node's unmet inputs; disable Run until the graph is valid; the backend also rejects an
   invalid run with a 400.
4. **Small, valuable iterations.** Backend slice first (contract + validation + generic
   extract run), then the frontend slice (run form + composer validation UX).

## Current state (what exists)

- The engine already executes multi-node graphs (`build_agent_graph` handles edges,
  conditional edges; `AgentRunService` runs them; the composer already draws edges).
- The generic run form (Slice A) already derives `⋃ runtime_inputs − ⋃ outputs`.
- **Gap:** the non-parse tools declare `runtime_inputs=[]` and consume their real inputs
  implicitly from state (`review`/`export` read `extracted_data`, declared only in a
  comment). So `upstream.outputs ⊇ downstream.runtime_inputs` has nothing to check, and a
  chain can only run through the bespoke `/agent/extract` entrypoint (extract declares no
  inputs, so the generic form would ask for nothing and the run would fail).

## Design

### §1 — Contract: `source`-tagged inputs

`FieldSpec` gains `source: str` (`"form"` default, back-compat with Slice A):

- **`form`** — collected by the run form (or by an upstream output if one covers it).
- **`upstream`** — satisfiable *only* by an upstream node's output; never prompted. The
  input that makes an edge meaningful and that validation checks.
- **`either`** — a document/parsed-doc that the form collects *unless* an upstream node
  already produced it. **Conflict rule:** an upstream output always wins; the form only
  ever shows an `either` field when no upstream covers it, so there is never a runtime
  conflict.

Retrofitted contracts:

| Tool | runtime_inputs (source, widget) | outputs |
|------|--------------------------------|---------|
| `parse.*` | `source_document_id` (form, source_document_picker) | `parse_run_id`, `parsed_document_id`, `page_count`, `text_len`, `failed_page_count`, `block_count` |
| `llamaextract` | `document_id` (form, document_picker), `extraction_schema_id` (form, extraction_schema_picker) | `extracted_data` |
| `human-review` | `extracted_data` (upstream) | `review_action`, `reviewed_data` |
| `export` | `extracted_data` (upstream) | `exported`, `rows_exported` |

`export` reads `reviewed_data or extracted_data`; its **hard** requirement is
`extracted_data` (present in both `extract → export` and `extract → review → export`),
`reviewed_data` is an optional refinement the node prefers when present — keeping the
validation rule a simple set check.

### §2 — Validation: reachable-predecessor rule

For each node `N`, `satisfiedUpstream(N)` = union of `outputs` of every node that can run
**strictly before** `N` (reachable predecessors along the directed edges — a real
topological check, closing the "produced by *any* node" simplification Slice A deferred).

- An `upstream` input whose key ∉ `satisfiedUpstream(N)` → **unmet** (the only blocking
  condition).
- An `either` input always has the form fallback; a `form` input is always satisfiable.
- **The graph is runnable ⇔ no node has an unmet `upstream` input.**

The same algorithm runs in two places — the **frontend** (live composer feedback) and the
**backend** (`start_run` guard). Two implementations (TS + Python), each unit-tested; plus
one test that drives the *real* reject path (an invalid graph actually 400s through
`start_run`) and mutation-checks the guard, so the two sides can't silently agree on the
wrong thing.

### §3 — Running the chain generically

**`extract_node` retrofit** (mirrors `parse_node` / `parsing_bridge`): a new
`services/agent/extraction_bridge.py` resolves `document_id → file_path`
(`DocumentRepository.get_by_id_unscoped`, `source_metadata["file_path"]`) and
`extraction_schema_id → schema_definition` (`ExtractionSchemaRepository.get_by_id`).
`extract_node` opens its own session (it currently opens none), reads `document_id` /
`extraction_schema_id` from state and resolves them internally, **with a fallback** to
pre-seeded `state["file_path"]` / `state["schema_definition"]` so the bespoke
`/agent/extract` entrypoint keeps working (same pattern `parse_node` uses). Outputs stay
`extracted_data`.

**Run-form derivation honors `source`:** form fields = `runtime_inputs` with
`source ∈ {form, either}` minus reachable-upstream-covered. For `extract → review →
export`, the form asks for a **document** and a **schema**; review's and export's
`extracted_data` are upstream-only and never prompted.

**Backend run guard:** `validate_graph(definition, tools) → list[Unmet]` (Python,
reachable-predecessor). `AgentRunService.start_run` calls it **before** creating or
executing the run and raises `ValueError` → **400** with a clear message
("node `export` needs `extracted_data` from an upstream node"), not a cryptic 500.

### §4 — Composer UX

A TS `validateGraph(nodes, edges, tools)` (mirror of §2) drives live feedback:

- Nodes with an unmet `upstream` input show a **warning badge** naming what is missing,
  human-labeled ("needs Extracted data").
- The **Run action is disabled** while any node is unmet, with a banner listing reasons.
- **Save stays allowed** (drafts). Edges stay free-draw. When every node is satisfied, the
  graph reads as runnable.

## Build order

### Slice 1 — backend: contract + validation + generic extract run
- `FieldSpec.source`; retrofit the four tool contracts (§1).
- `extraction_bridge` + `extract_node` retrofit (resolve document/schema, own session,
  state fallback).
- `validate_graph` (reachable-predecessor) + `start_run` guard (400 before execution).
- Tests: contract; `validate_graph` valid/invalid incl. wrong ordering; `start_run` rejects
  an invalid graph via the real path (mutation-checked); `extract_node` resolves ids (faked
  bridge); a full `extract → review → export` graph run through faked boundaries proving the
  generic path.
- **Ships:** the chain runs via generic `POST /agent/projects/{id}/runs`; invalid graphs 400.

### Slice 2 — frontend: run form + composer validation
- TS `validateGraph` (same cases as backend); run-form honors `source` and renders the
  document/schema pickers; composer per-node unmet-input badges + Run gate.
- Tests: `validateGraph` mirror cases; run-form derivation for the chain; Run disabled when
  invalid, enabled when satisfied.
- **Ships:** author → validate → run the chain end-to-end in the UI.

### Later specs (out of scope here)
- Branching / conditional-edge authoring (review approve/reject paths).
- New consumer tools (index / classify) so parse-rooted chains gain a downstream.
- Retiring the bespoke `/agent/parse` + `/agent/extract` entrypoints once the generic path
  fully covers them.

## Acceptance criteria (this spec: Slices 1 + 2)

1. `FieldSpec` exposes `source` (`form`/`upstream`/`either`); `GET /agent/tools` reflects
   it; the four tools declare their real inputs per §1.
2. `validate_graph` (backend) and `validateGraph` (frontend) both return a node's unmet
   `upstream` inputs using the reachable-predecessor rule; a producer placed *after* its
   consumer does not count as satisfying it.
3. `AgentRunService.start_run` rejects a definition with any unmet `upstream` input with a
   400 and a message naming the node and missing key, before executing.
4. `extract_node` resolves `document_id` → `file_path` and `extraction_schema_id` →
   `schema_definition` internally; the bespoke `/agent/extract` entrypoint still works via
   the state fallback.
5. `extract → review → export` runs end-to-end through the generic
   `POST /agent/projects/{id}/runs`, with the run form asking only for a document + schema.
6. The composer shows unmet-input warnings per node and disables Run until the graph is
   valid; Save is unaffected.
7. Backend + frontend suites and `npm run build` green; no regression to Slices A/B or the
   extract path.

## Risks / open questions

- **`extract_node` now opens a DB session** (it didn't before) to resolve ids — matches
  `parse_node`/`export_node`; keep resolution in the bridge so the node stays thin.
- **Two validation implementations (TS + Python)** can drift; mitigated by mirrored test
  cases and the real-path reject test. A future option is a single shared spec/fixture set.
- **`export`'s OR-dependency** (`reviewed_data or extracted_data`) is modeled as a hard
  `extracted_data` requirement + optional `reviewed_data`; if a future chain wants
  review's output to be mandatory, that becomes a per-tool concern, not a contract change.
- **Inline execution cost / BYOK** limitations from Slice A still apply (runs execute inline;
  a missing key surfaces as a failed run) — unchanged here.
