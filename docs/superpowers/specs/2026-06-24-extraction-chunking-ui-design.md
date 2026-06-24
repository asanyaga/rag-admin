# Surface Chunking & Citation Granularity in the Extraction UI — Design

**Date:** 2026-06-24
**Status:** Approved (design); pending implementation plan
**Depends on:** backend chunking pipeline (PR #101, merged) — `chunking` / `preprocess` fields on `/extractions/run`.
**Related files:** `frontend/src/components/extraction/ExtractionForm.tsx`,
`frontend/src/components/extraction/ExtractionResultViewer.tsx`,
`frontend/src/hooks/useExtractionResults.ts`, `frontend/src/types/extraction.ts`,
`frontend/src/api/extraction.ts`.

## Problem

The backend extraction pipeline now accepts a `chunking` config (strategy +
params + citation level) and returns richer `extractionMetadata` (chunk count,
token usage, scalar conflicts) plus precise truncation errors. None of this is
reachable from the app: `ExtractionForm` has no controls, and
`runExtractionWithParse` does not forward the fields. Users can only exercise
chunking via direct API calls.

## Goals

- Let users configure **chunking** (strategy + params) and **citation
  granularity** for LLM extractions from the form.
- Surface **result-side metadata** (chunk count, token usage, scalar conflicts)
  and truncation failures in a readable way.
- Preserve current behavior exactly when the new controls are left at defaults.

## Non-goals (this spec)

- Preprocess / `block_filter` controls.
- A schema-driven generic form renderer + backend `config_schema` GET endpoints
  (controls are hand-built, matching the existing form).
- Saved pipeline presets.
- Per-field citation visualization in the result data table.

## Approach

Purely frontend. The `/extractions/run` endpoint already accepts `chunking` and
`preprocess`; only the request types, the orchestration hook, and the form/
result components change. Controls are hand-built (like the existing
`llamaextract` / `llm` sections) rather than schema-driven — simplest, matches
current code, no new endpoints. Trade-off: adding a future chunking strategy
means editing the form. This is acceptable for the current two strategies
(`none`, `token_budget_pages`); a schema-driven renderer remains a future
option if strategies proliferate.

## Input controls — `ExtractionForm`

A new collapsible **"Large document handling"** subsection, rendered **only when
`extractionMethod === 'llm'`**, default **collapsed**, default **`strategy:
none`** (so default behavior is unchanged):

- **Chunking strategy** — `Select`: `None (single-shot)` | `Token-budgeted pages`.
- When `token_budget_pages` is selected, reveal:
  - **Max input tokens** — number `Input`, default `8000`.
  - **Page overlap** — number `Input`, default `0`.
  - **Dedupe key** — text `Input`, optional (placeholder `sku`).
- **Citation detail** — `Select`: `Auto` | `Full` | `Page only` | `Off`,
  default `Auto`. Rendered whenever method is `llm` (applies to single-shot too,
  since it controls `__source` augmentation on the request schema).

Each control carries one line of helper text (e.g. citation: "Auto = page-level
provenance on large documents; Off = no provenance captured").

New local state in the form:

```ts
const [chunkStrategy, setChunkStrategy] = useState<'none' | 'token_budget_pages'>('none')
const [maxInputTokens, setMaxInputTokens] = useState('8000')
const [pageOverlap, setPageOverlap] = useState('0')
const [dedupeKey, setDedupeKey] = useState('')
const [citationLevel, setCitationLevel] = useState<'auto' | 'full' | 'page_only' | 'off'>('auto')
```

`handleRun` builds the `chunking` object for the `llm` branch only, and only
when it differs from defaults, keeping requests minimal:

```ts
let chunking: ChunkingConfig | undefined
if (chunkStrategy !== 'none') {
  const cfg: Record<string, unknown> = {}
  const max = parseInt(maxInputTokens, 10)
  if (!Number.isNaN(max)) cfg.maxInputTokens = max
  const overlap = parseInt(pageOverlap, 10)
  if (!Number.isNaN(overlap) && overlap > 0) cfg.pageOverlap = overlap
  if (dedupeKey.trim()) cfg.dedupeKey = dedupeKey.trim()
  chunking = { strategy: chunkStrategy, config: cfg, citationLevel }
} else if (citationLevel !== 'auto') {
  chunking = { strategy: 'none', citationLevel }
}
// included in the llm extractionConfig as `chunking`
```

Switching the method away from `llm` hides the subsection; `chunking` is never
sent for `llamaextract` (which has its own page handling and where citation
level does not apply).

## Types + hook wiring

`frontend/src/types/extraction.ts` — extend `RunWithParseRequest.extractionConfig`:

```ts
export interface ChunkingConfig {
  strategy: string
  config?: Record<string, unknown>
  citationLevel?: 'auto' | 'full' | 'page_only' | 'off'
}

export interface PreprocessStage {
  stage: string
  config: Record<string, unknown>
}

// inside RunWithParseRequest.extractionConfig:
  chunking?: ChunkingConfig
  preprocess?: PreprocessStage[]   // forwarded for future use; no UI yet
```

`frontend/src/api/extraction.ts` — the `runExtraction` request type gains the
same optional `chunking` and `preprocess` fields.

`frontend/src/hooks/useExtractionResults.ts` — `runExtractionWithParse` forwards
them into the `runExtraction` body (around line 223):

```ts
await extractionApi.runExtraction({
  parseRunId: parseRunId!,
  extractionSchemaId: extractionConfig.extractionSchemaId,
  extractionMethod: extractionConfig.extractionMethod,
  config: extractionConfig.config,
  llmConfig: extractionConfig.llmConfig,
  userPromptTemplate: extractionConfig.userPromptTemplate,
  chunking: extractionConfig.chunking,
  preprocess: extractionConfig.preprocess,
})
```

## Result-side metadata — `ExtractionResultViewer`

Today the component renders `extractionMetadata` as a raw JSON collapsible and
shows `statusMessage` on failure. Add a **summary strip** above the raw block,
shown only when chunking-relevant metadata is present:

- **Chunk count** badge from `extractionMetadata.chunkCount`.
- **Token usage** from `extractionMetadata.usage.total_tokens`.
- **Scalar conflicts** — when `extractionMetadata.scalarConflicts` is a non-empty
  array, an amber callout listing each `path: kept ≠ discarded`. This is the HITL
  signal that two chunks disagreed on a scalar value. Hidden when absent.

Failure handling needs no new work: failed runs already render `statusMessage`,
through which the backend truncation message ("LLM response truncated at
max_tokens … Lower chunking maxInputTokens or raise max_tokens") flows verbatim.
The raw `extractionMetadata` / provider-response collapsibles remain unchanged
for power users.

Render the summary as a small, self-contained presentational subcomponent
(e.g. `ChunkingSummary`) so the viewer stays readable and the piece is testable
in isolation.

## Defaults, validation, edge cases

- Numeric inputs parse to integers; blank/invalid `maxInputTokens` omits the key
  so the backend default applies. `pageOverlap` only sent when `> 0`.
- `dedupeKey` is optional and trimmed; omitted when blank.
- `citationLevel: 'off'` shows a subtle "no provenance captured" hint.
- The subsection state is local to the form; no persistence (per-run only),
  consistent with the backend's per-run config.
- Strategy options are hardcoded (two entries); documented as the trade-off
  against a schema-driven renderer.

## Testing (vitest)

- **`ExtractionForm`:**
  - Selecting `Token-budgeted pages` and setting params yields a `chunking`
    object (with `maxInputTokens` etc.) in the `onRun` request.
  - `strategy: none` + `citationLevel: auto` omits `chunking` entirely.
  - Changing only citation level to `page_only` sends
    `chunking: { strategy: 'none', citationLevel: 'page_only' }`.
  - The "Large document handling" section is absent when method is
    `llamaextract`.
- **`useExtractionResults`:** `runExtractionWithParse` forwards `chunking` to
  `extractionApi.runExtraction`.
- **`ExtractionResultViewer`:** renders the chunk-count/usage summary when
  present; renders the conflicts callout when `scalarConflicts` is non-empty;
  renders neither when `extractionMetadata` lacks them.

## Out of scope (follow-ups)

- Preprocess / `block_filter` controls.
- Schema-driven generic form renderer + backend `config_schema` GET endpoints
  for chunking strategies and preprocess stages.
- Saved pipeline presets / profiles.
- Per-field citation visualization in the result data table.
