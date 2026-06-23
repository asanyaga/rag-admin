# Extraction Parse Configuration Design

**Date:** 2026-06-23
**Status:** Approved
**Scope:** Allow users to configure parse parameters directly from the extraction screen, triggering a fresh parse when needed instead of always using the latest existing parse run.

---

## Problem

Running extraction always uses the latest viable parse run for the selected document. To compare extraction quality across different parse configurations (e.g. simple vs. extract_rich), the user must navigate to the documents page, run each parse variant, then return to the extraction page. There is no way to drive parsing from the extraction screen.

---

## Goals

1. Always show a full parse configuration section in `ExtractionForm`, pre-populated from the latest parse run for the selected document
2. When the user runs extraction with a parse config that matches an existing parse run, reuse it — no redundant parsing
3. When no matching parse run exists, trigger a fresh parse first, then extract from the result
4. Show explicit phase progress during a two-step run: "Parsing…" → "Extracting…"
5. No backend changes

---

## Architecture

Frontend-only. `useExtractionResults` owns the full orchestration and phase state. `ExtractionPage` passes existing parse runs into the hook so no extra API calls are needed for the match check.

```
ExtractionPage
├── useParseRuns (existing) — supplies existing parse runs + latest config for pre-population
├── useExtractionResults (extended) — orchestration + phase state
│
└── ExtractionForm (extended)
    ├── [NEW] Parse Configuration section (always visible)
    │   ├── ParseMethodSelector (reused from components/documents/)
    │   └── Parser-specific config form (LlamaParseConfig, LandingAIConfig, or nothing)
    │   Pre-populated from: latestParseRun.parser + latestParseRun.config
    │
    ├── Schema selector (unchanged)
    ├── Extraction method + LLM config (unchanged)
    └── Run Extraction button → now emits RunWithParseRequest
```

---

## Data Flow

```
User clicks "Run Extraction"
  → ExtractionForm emits RunWithParseRequest { parseConfig, extractionConfig }
    → useExtractionResults.runExtractionWithParse(documentId, existingParseRuns, request)

      Step 1 — Match check
        Find run in existingParseRuns where:
          run.parser === parseConfig.parser
          AND run.representationKind === parseConfig.representationKind
          AND stableStringify(run.config) === stableStringify({ parser: parseConfig.parser, ...parseConfig.config })
          AND run.status is "succeeded" | "partial"
        stableStringify: JSON.stringify with keys sorted alphabetically (recursive)
        Note: stored run.config includes a "parser" key added by the backend but excludes "representationKind"
        If found → skip to Step 3 with matched run.id

      Step 2 — Parse (only if no match)
        phase = "parsing"
        POST /documents/{documentId}/parse-runs  { parser_type, config: { ...parseConfig.config, representation_kind } }
        Response is { status: "accepted" } — no run ID returned
        Poll listParseRuns(documentId) every 3s to find the new run:
          match on: run.parser === parseConfig.parser
                    AND run.representationKind === parseConfig.representationKind
                    AND stableStringify(run.config) === stableStringify({ parser: parseConfig.parser, ...parseConfig.config })
          take the newest matching run (list is ordered newest-first)
        Once ID found, switch to getParseRun(runId) for status polling
        Terminal: succeeded | partial → proceed; failed → phase = "failed", phaseError = run.error, return early

      Step 3 — Extract
        phase = "extracting"
        POST /extractions/run  { parse_run_id, ...extractionConfig }
        Existing polling takes over
        On completion → phase = "done"
        On failure → phase = "failed" (existing ExtractionResult.status_message carries the error)
```

---

## Frontend Changes

### `ExtractionForm.tsx`

**File:** `frontend/src/components/extraction/ExtractionForm.tsx`

New state:
```ts
selectedParser: string                        // "simple" | "llamaparse" | "landingai" | "docling"
parserConfig: Record<string, unknown>         // parser-specific config fields
```

Pre-population: `ExtractionPage` derives `defaultParser` and `defaultParserConfig` from `latestParseRun?.parser` and `latestParseRun?.config`. When no parse run exists for the selected document, defaults to `"simple"` with empty config. Props reset when `selectedDocument` changes.

New "Parse Configuration" section rendered above the schema selector:

```tsx
<div className="space-y-3">
  <Label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
    Parse Configuration
  </Label>
  <ParseMethodSelector
    value={selectedParser}
    onChange={(parser) => { setSelectedParser(parser); setParserConfig({}); }}
  />
  {selectedParser === 'llamaparse' && (
    <LlamaParseConfig value={parserConfig} onChange={setParserConfig} />
  )}
  {selectedParser === 'landingai' && (
    <LandingAIConfig value={parserConfig} onChange={setParserConfig} />
  )}
</div>
```

`representationKind` is fixed to `"extract_rich"` and not exposed in the UI — same default as the documents parse form.

`onRun` callback type changes from `RunExtractionRequest` to `RunWithParseRequest`:

```ts
interface RunWithParseRequest {
  parseConfig: {
    parser: string
    // Parser-specific fields (tier, expand, model, etc.) — does NOT include representationKind
    config: Record<string, unknown>
    // Passed inside the config dict to POST /parse-runs; stored separately by backend as ParseRun.representationKind
    representationKind: string
  }
  extractionConfig: {
    extractionSchemaId: string
    extractionMethod: string
    config?: Record<string, unknown>
    llmConfig?: PromptConfig
    userPromptTemplate?: string
  }
}
```

### `useExtractionResults.ts`

**File:** `frontend/src/hooks/useExtractionResults.ts`

New types:
```ts
type ExtractionPhase = 'idle' | 'parsing' | 'extracting' | 'done' | 'failed'
```

New state:
```ts
extractionPhase: ExtractionPhase   // replaces ad-hoc isRunning boolean
phaseError: string | null          // set only on parse-step failures
```

New function (replaces `runExtraction`):
```ts
async function runExtractionWithParse(
  documentId: string,
  existingParseRuns: ParseRunResponse[],
  request: RunWithParseRequest
): Promise<void>
```

Internal helpers:
- `findOrWaitForParseRun(documentId, parseConfig)`: polls `listParseRuns(documentId)` every 3s to find a run matching parser + representationKind + config (see match logic above). Returns the run ID once any non-failed match is found.
- `pollParseRunById(parseRunId)`: calls `getParseRun(parseRunId)` every 3s until status is `succeeded | partial | failed`.
- 10-minute total timeout (600s) across both helpers combined.

The existing extraction result polling is unchanged — it activates once the extraction result ID is known.

### `ExtractionPage.tsx`

**File:** `frontend/src/pages/ExtractionPage.tsx`

- Derives `defaultParser` and `defaultParserConfig` from `latestParseRun` (already available via `useParseRuns`) and passes as props to `ExtractionForm`
- Passes `existingParseRuns` from `useParseRuns` into `runExtractionWithParse`
- Passes `extractionPhase` and `phaseError` to `ExtractionHistory` for phase display

### `ExtractionHistory.tsx`

**File:** `frontend/src/components/extraction/ExtractionHistory.tsx`

New prop:
```ts
inProgressPhase?: {
  phase: 'parsing' | 'extracting'
  parserLabel: string     // e.g. "Simple" | "LlamaParse"
  schemaLabel: string     // extraction schema name
}
```

When `inProgressPhase` is set, a synthetic in-progress row is prepended to the result list:

- Phase `parsing`: shows spinner + "Parsing document…" + parser label
- Phase `extracting`: shows spinner + "Extracting…" + schema label + extraction method

Once a real `ExtractionResult` row appears in the API response, the synthetic row is replaced by the real polling result. On parse failure, the synthetic row shows a failed state with `phaseError` and a "Retry" button that re-invokes `runExtractionWithParse`.

The Run Extraction button is disabled while `extractionPhase !== 'idle'`.

---

## Error Handling

| Failure point | Behaviour |
|---|---|
| `POST /parse-runs` non-2xx | `phase = 'failed'`, `phaseError = 'Failed to start parse'`, extraction not triggered |
| Parse run reaches `failed` status | `phase = 'failed'`, `phaseError = parseRun.error ?? 'Parse failed'`, extraction not triggered |
| Parse poll timeout (10 min) | `phase = 'failed'`, `phaseError = 'Parse timed out'`, extraction not triggered |
| Extraction failure | Handled by existing `ExtractionResult.status = 'failed'` + `status_message` flow; `phase` set to `'failed'` |
| `existingParseRuns` empty or loading | Treat as no match; proceed to parse step — backend deduplicates by config hash anyway |

**No special retry state for the two-step case:** if parse succeeds but extraction fails, the user re-clicks Run. The match check finds the now-existing parse run and skips straight to the extract step.

---

## Files Changed

**Modified:**
- `frontend/src/components/extraction/ExtractionForm.tsx` — add parse config section, update `onRun` type
- `frontend/src/hooks/useExtractionResults.ts` — add `runExtractionWithParse`, `extractionPhase`, `phaseError`, `pollParseRun`; uses `getParseRun` from `api/parseRuns.ts` and `createParseRun` from `api/parseRuns.ts` for orchestration
- `frontend/src/pages/ExtractionPage.tsx` — derive default parse props, wire phase into history
- `frontend/src/components/extraction/ExtractionHistory.tsx` — accept `inProgressPhase` prop, render synthetic row

**No new files. No backend changes.**

---

## What Is Not Changing

- All backend endpoints, services, and models
- The `RunExtractionRequest` backend schema
- Existing extraction result polling behaviour
- `ParseMethodSelector`, `LlamaParseConfig`, `LandingAIConfig` components — reused as-is
- `useParseRuns` hook — read-only consumer, not involved in orchestration
- The `representationKind` field — fixed to `"extract_rich"`, not configurable in this iteration
