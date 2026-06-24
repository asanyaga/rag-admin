# Extraction Result Debug Panel — Design

**Date:** 2026-06-24
**Status:** Draft
**Related files:** `frontend/src/components/extraction/ExtractionResultViewer.tsx`,
`frontend/src/components/extraction/ExtractionResultViewer.test.tsx`,
`frontend/src/types/extraction.ts`.

## Problem

The current "Extraction Metadata" and "Provider Response" collapsibles in
`ExtractionResultViewer` dump raw `JSON.stringify` into a `<pre>` block. This
makes it impractical to inspect a run:

- **Config is not surfaced** — model, provider, chunking settings, structured
  output mode, and citation level are buried in a flat JSON blob.
- **Prompt messages are unreadable** — the embedded schema (~3 kB) and
  document text are crammed into a single `user.content` string with no
  visual separation.
- **LLM response is a raw string** — `providerResponseRaw` contains JSON but
  is displayed as an opaque pre-formatted dump.
- **Chunked runs lose everything** — the merge step discards `model`,
  `provider`, `latency_ms`, and `prompt_messages` from per-chunk outputs,
  leaving only `{usage, chunkCount, scalarConflicts}` (separate backend fix
  tracked below).

## Goals

- Replace the two raw-JSON collapsibles with three structured, scannable panels:
  **Run Config**, **Prompt**, and **LLM Response**.
- Render all JSON values (schemas, extracted objects, response payloads) with
  proper indentation and syntax colouring so they are legible without copy-paste.
- No new backend endpoints; frontend-only change.
- Panels are collapsed by default; opening them is a deliberate debug action.

## Non-goals (this spec)

- Per-chunk prompt / response drill-down for chunked runs (requires backend
  changes to preserve per-chunk context; tracked as a follow-on).
- A full interactive JSON tree (expand/collapse nodes, copy paths). A
  scrollable, syntax-coloured `pre` block is sufficient.
- Exporting or diffing across runs.

---

## Data sources

All data is already on `ExtractionResult` (no new API fields needed):

| UI section | Source field(s) |
|---|---|
| Run Config — method / mode / flags | `result.config` (stored on the result) |
| Run Config — model / provider / latency | `result.extractionMetadata.model`, `.provider`, `.latency_ms` |
| Run Config — usage | `result.extractionMetadata.usage` |
| Run Config — chunking | `result.extractionMetadata.chunkCount` + `result.config.chunking` |
| Prompt — system | `result.extractionMetadata.prompt_messages[0].content` |
| Prompt — user (schema + document) | `result.extractionMetadata.prompt_messages[1].content` |
| LLM Response | `result.providerResponseRaw` |

For **chunked runs** `prompt_messages`, `model`, `provider`, and `latency_ms`
are absent from `extractionMetadata` (they are stripped by `merge_outputs`).
Each absent field is replaced with a muted placeholder: *"Not available for
chunked runs"*. A follow-on backend task should propagate first-chunk model/
provider and aggregate latency into the merged metadata.

---

## UI design

### Layout

Replace the current two collapsibles (`Extraction Metadata`, `Provider
Response`) with three collapsible panels, stacked below the result card, each
following the existing `Collapsible` + `Button` trigger pattern:

```
[ Run Config ▾ ]
[ Prompt ▾ ]
[ LLM Response ▾ ]
```

All collapsed by default. Only the panels for which data exists are rendered
(e.g. `LLM Response` is hidden when `providerResponseRaw` is null — chunked
runs).

---

### Panel 1 — Run Config

A two-column key-value grid (label left, value right), divided by a `Separator`
into three logical groups:

**Model**
- Model: `claude-opus-4-7`
- Provider: `anthropic`
- Latency: `17,794 ms`

**Tokens** (from `extractionMetadata.usage`)
- Prompt tokens: `3,712`
- Completion tokens: `1,830`
- Total tokens: `5,542`

**Settings** (from `result.config`)
- Extraction method: `llm`
- Structured output mode: `json_schema`
- Inject block IDs: `No`
- Chunking strategy: `token_budget_pages` | `none` | `—` (if absent)
- Max input tokens: `4,000` (shown only when strategy ≠ none)
- Citation level: `auto`
- Chunk count: `3` (shown only when `chunkCount` is present)

Numbers formatted with `toLocaleString()`. Missing fields show `—`.

Implementation: no new component; inline JSX inside
`ExtractionResultViewer`. Values read directly from `result.extractionMetadata`
and `result.config`.

---

### Panel 2 — Prompt

Two tabs using shadcn `Tabs` / `TabsList` / `TabsContent`:

**System tab**
- Renders `prompt_messages[0].content` as plain text in a scrollable `pre`
  block (max-height `12rem`, overflow-y auto).

**User tab**
- The user message content is a long string containing the schema JSON and
  document text. Parse it into three labelled sub-sections:

  1. **Instruction** — text before `<schema>` tag (one or two lines).
  2. **Schema** — content of `<schema>…</schema>` tag, rendered via
     `<FormattedJson>` (see below).
  3. **Document** — content of `<document>…</document>` tag, rendered as
     plain text in a scrollable `pre` block.

  Parse with simple string indexOf / slice on the known tag boundaries
  (`<schema>`, `</schema>`, `<document>`, `</document>`). If the tags are
  absent (non-standard prompt), fall back to rendering the full content as
  plain pre-formatted text.

When `prompt_messages` is absent (chunked run), render a single muted line:
*"Prompt not available — this run used chunking. Individual chunk prompts are
not yet preserved."*

---

### Panel 3 — LLM Response

Renders `result.providerResponseRaw` via `<FormattedJson>` (see below) in a
scrollable container (max-height `24rem`).

When `providerResponseRaw` is null (chunked run) or contains a `raw_content`
string key (truncation error), show the raw string in a plain `pre` block with
a muted label *"Raw (non-JSON) response"* instead.

---

## `FormattedJson` component

A new small utility component:

```
frontend/src/components/shared/FormattedJson.tsx
```

Props: `{ value: unknown; maxHeight?: string }`.

Renders `JSON.stringify(value, null, 2)` inside a scrollable `<pre>` block
with:

- Tailwind classes for monospace, small font, muted background, rounded border,
  horizontal and vertical overflow scroll.
- Syntax colouring via inline `<span>` wrapping, using a simple regex pass over
  the stringified output:
  - JSON string values → `text-green-700 dark:text-green-400`
  - JSON keys (`"key":`) → `text-blue-700 dark:text-blue-400`
  - Numbers and booleans → `text-amber-600 dark:text-amber-400`
  - Punctuation (`{}[],:`) → default `text-foreground`
- No external dependency (no `react-json-view` or Prism); the regex approach
  is sufficient for well-formed JSON and keeps the bundle unchanged.

`FormattedJson` is also used in place of the existing raw `pre` blocks in the
current `Extraction Metadata` / `Provider Response` panels that are being
replaced.

---

## Component changes

| File | Change |
|---|---|
| `frontend/src/components/extraction/ExtractionResultViewer.tsx` | Replace two raw collapsibles with three structured panels; add Tabs import; add inline Run Config grid; call `FormattedJson` and prompt parser. |
| `frontend/src/components/shared/FormattedJson.tsx` | New component (see above). |
| `frontend/src/components/shared/FormattedJson.test.tsx` | Unit tests: renders JSON string, numbers, booleans; respects maxHeight prop; handles null/undefined gracefully. |
| `frontend/src/components/extraction/ExtractionResultViewer.test.tsx` | Add: Run Config panel shows model/provider/tokens; Prompt panel shows system/user tabs; LLM Response panel renders JSON; chunked-run placeholders render correctly. |

No changes to `ExtractionResult` type, API layer, or backend.

---

## Chunked-run limitations (follow-on backend task)

`merge_outputs` in `backend/app/adapters/extraction/chunking/merge.py`
currently builds the merged metadata as `{usage, chunkCount, scalarConflicts}`
only. The following should be added to the merged metadata so that Run Config
has complete data even for chunked runs:

- `model` and `provider` — taken from `outputs[0].extraction_metadata`
  (identical across all chunks).
- `latency_ms` — sum of per-chunk latencies.

`prompt_messages` intentionally remains absent from merged metadata (N
identical schemas would be noise); the placeholder message in the Prompt panel
is the correct UX for this case.

---

## Acceptance criteria

- [ ] Run Config panel shows model, provider, latency, token counts, and
  extraction settings (method, output mode, chunking) for a completed LLM run.
- [ ] Prompt panel System tab shows the system prompt text.
- [ ] Prompt panel User tab separates instruction, schema (formatted JSON), and
  document sections.
- [ ] LLM Response panel renders `providerResponseRaw` as formatted,
  syntax-coloured JSON.
- [ ] All JSON values use `FormattedJson`; no raw `JSON.stringify` in `pre`
  blocks visible to the user.
- [ ] For chunked runs: Run Config shows `chunkCount`; Prompt and LLM Response
  show the "not available" placeholder.
- [ ] For failed runs with truncation: LLM Response shows the raw string
  content with a "Raw (non-JSON) response" label.
- [ ] All new behaviour covered by unit tests.
- [ ] No regressions in existing `ExtractionResultViewer` tests.
