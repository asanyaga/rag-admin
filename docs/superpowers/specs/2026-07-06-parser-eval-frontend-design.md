# Parser Eval — Frontend (Design)

**Date:** 2026-07-06
**Status:** Draft for review
**Author:** brainstorming session (asanyaga)
**Depends on:** parser-eval backend (canonical model, merged PR #144) · `docs/architecture/eval-entity-model.md`

## Problem

The parser-eval backend is shipped (cases, datasets, variant=(adapter,config) runs, metric results)
but has **no UI**. Users can't author ground truth, launch a comparison, or read results. This spec
covers a **thin, end-to-end frontend vertical** that proves the full stack in the app:

> Author a `text` ground-truth case → pick cases + adapters → run → read a per-parser comparison table
> (similarity, omission, hallucination, cost, latency).

## Scope

**In scope** — mirrors the peer `ExtractionEvaluationPage`:
- Route `/evaluation/parser` → tabbed page (**Cases**, **Runs**), + `/evaluation/parser/runs/:runId`.
- Cases tab: list + author `text` ground truth (per-page textareas).
- Runs tab: list + create (ad-hoc case selection + adapter multi-select), status.
- Run-detail page: comparison table grouped by case, one row per adapter.
- One small backend addition (get-one-run route, §2).

**Non-goals (deferred seams, documented not built):**
- Datasets UI (backend M:N container exists; runs use ad-hoc `eval_case_ids` for now).
- Per-variant `(adapter, config)` editor — runs send `config: {}` (adapter default config).
- Truth bootstrap-from-parser, verification (draft→verified) workflow.
- Additional dimensions (table/reading_order/roles) — UI keys off `dimension` but only `text` ships.
- Delete/edit of cases and runs.

## 2. Backend prerequisites

Two small backend changes are required before the frontend can follow app conventions:

**(a) camelCase response conformance.** The whole app emits **camelCase JSON** via per-field Pydantic
`alias="camelCase"` + `ConfigDict(populate_by_name=True)` (FastAPI serializes `by_alias`; see
`app/schemas/extraction_eval.py`). The parser-eval DTOs currently emit **snake_case** — an
inconsistency. Since no client consumes them yet, conform them now: add camelCase aliases +
`populate_by_name=True` to every parser-eval schema (`CaseCreate`, `CaseResponse`, `DatasetCreate`,
`DatasetResponse`, `VariantInput`, `RunCreate`, `RunResponse`, `ResultResponse`). Inputs still accept
snake_case (populate_by_name), so create-request bodies in existing tests keep working; only
**response-key reads** in the existing router test change (`review_status`→`reviewStatus`,
`primary_metric`→`primaryMetric`, `variant_key`→`variantKey`; `metrics`/`config` are dicts, unchanged).

**(b) get-one-run route.** The run-detail page needs run metadata + status polling, but the router
exposes only `list_runs`/`get_results`. Add
**`GET /projects/{project_id}/parser-eval/runs/{run_id}` → `RunResponse`** (service `get_run` already
exists; mirror `get_results` + `verify_project_access`) with one router test (200 owner, 404 unknown).

## 3. Architecture

Follows the established layering: `api/*.ts` → `types/*.ts` → `hooks/use*.ts` → `pages/` + feature
`components/`.

**Routes** (`frontend/src/App.tsx`, in the `evaluation/*` block):
- `evaluation/parser` → `ParserEvaluationPage` (breadcrumb "Parser Evaluation").
- `evaluation/parser/runs/:runId` → `ParserEvalRunDetailPage` (breadcrumb "Run Detail").

**Nav** (`frontend/src/components/layout/AppSidebar.tsx`): add a **Parsing** entry to the Evaluation
group, alongside Retrieval and Extraction, linking to `/evaluation/parser`.

## 4. Types (`frontend/src/types/parserEval.ts`)

Mirror the backend DTOs exactly:

```ts
export interface ParserEvalCase {
  id: string
  sourceDocumentId: string      // source_document_id
  dimension: string             // "text"
  sourceMethod: string          // "human"
  reviewStatus: string          // "draft"
  createdAt: string
}
export interface ParserEvalRun {
  id: string
  name: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  variants: { adapter: string; config: Record<string, unknown> }[]
  datasetId: string | null
  errorMessage: string | null
  createdAt: string
}
export interface ParserEvalResult {
  evalCaseId: string            // eval_case_id
  adapter: string
  config: Record<string, unknown>
  variantKey: string            // variant_key
  metrics: Record<string, number>   // { similarity, omission, hallucination }
  primaryMetric: string | null
  details: Record<string, unknown> | null
  cost: Record<string, number> | null
  latencyMs: number | null
}
export interface CreateCaseRequest {
  sourceDocumentId: string
  dimension: string
  expected: { pages: string[] }
}
export interface CreateRunRequest {
  name?: string
  variants: { adapter: string; config: Record<string, unknown> }[]
  evalCaseIds: string[]
}
```

> **Casing:** backend uses `snake_case`. Follow whatever the existing api modules do (extractionEval
> maps to camelCase in types). Confirm the request/response key convention against `extractionEval.ts`
> during implementation and stay consistent (map at the api boundary if that's the existing pattern).

## 5. API (`frontend/src/api/parserEval.ts`)

Axios `apiClient` (base already includes `/api/v1`), functions per endpoint:
- `listCases(projectId)` → `GET /projects/{pid}/parser-eval/cases`
- `createCase(projectId, data)` → `POST /projects/{pid}/parser-eval/cases`
- `listRuns(projectId)` → `GET /projects/{pid}/parser-eval/runs`
- `createRun(projectId, data)` → `POST /projects/{pid}/parser-eval/runs` (202)
- `getRun(projectId, runId)` → `GET /projects/{pid}/parser-eval/runs/{runId}` (§2)
- `getRunResults(projectId, runId)` → `GET /projects/{pid}/parser-eval/runs/{runId}/results`

## 6. Hooks (`frontend/src/hooks/useParserEval.ts`)

**Hand-rolled `useState`/`useEffect`/`useCallback` + `setInterval` polling, mirroring `useExtractionEval`**
(the codebase does not use react-query here):
- `useParserEvalCases(projectId)`, `useCreateParserEvalCase(projectId)`
- `useParserEvalRuns(projectId)`, `useCreateParserEvalRun(projectId)`
- `useParserEvalRun(projectId, runId)` — `refetchInterval` while status is `pending|running`, off once
  `completed|failed`.
- `useParserEvalRunResults(projectId, runId)` — enabled once run is `completed`.
- Reuse `useSourceDocuments(projectId)` (`frontend/src/hooks/useSourceDocuments.ts`) to resolve
  `sourceDocumentId → filename` for display.

## 7. Components & pages (`frontend/src/components/parser-eval/`)

### `ParserEvaluationPage` (`pages/ParserEvaluationPage.tsx`)
Tabbed shell (copy the tab-button pattern from `ExtractionEvaluationPage`): **Cases** / **Runs**.
Guards on `currentProject` like the peer.

### Cases tab — `ParserEvalCasesTab.tsx`
- Table of cases: **source-document filename** (resolved via `useSourceDocuments`) · dimension ·
  review-status badge · created-at.
- Empty state: "No cases yet — author one." **New Case** button → `CaseEditorDialog`.

### `CaseEditorDialog.tsx`
- **Source document**: combobox from the project's source documents (`useSourceDocuments`).
- **Dimension**: fixed `text` shown as "Text faithfulness" (only option; disabled select).
- **Ground truth**: dynamic list of per-page `<Textarea>`s labelled "Page 1…N", **Add page** /
  **Remove page**, minimum 1. Submit builds `{ pages: [...] }` → `createCase`.
- Validation: ≥1 page, non-empty. On backend `unique(source_document_id, dimension)` conflict, show
  inline "A text case already exists for this document."

### Runs tab — `ParserEvalRunsTab.tsx`
- Table of runs: name · `EvalStatusBadge` (reuse `components/evaluation/EvalStatusBadge.tsx`) ·
  adapters · created-at. Row click → `/evaluation/parser/runs/:runId`.
- Empty state: "No runs yet." **New Run** → `NewRunDialog`.

### `NewRunDialog.tsx`
- Optional **name**.
- **Cases**: multi-select checkbox list of the project's cases (filename · dimension).
- **Adapters**: multi-select from the shared parser registry (`PARSER_REGISTRY` in
  `components/documents/ParseMethodSelector.tsx` — reuse its keys+labels; do **not** re-list). Each
  selected adapter → `{ adapter, config: {} }`.
- Validation: ≥1 case and ≥1 adapter. Submit → `createRun` → navigate to the run-detail route.

### `ParserEvalRunDetailPage` (`pages/ParserEvalRunDetailPage.tsx`)
- Header: run name, `EvalStatusBadge`, adapters, created-at. Uses `useParserEvalRun` (polls) +
  `useParserEvalRunResults`.
- `pending|running`: show a running indicator (poll). `failed`: show `errorMessage`.
- `completed`: render `ParserComparisonTable`. Optional: a row of `MetricCard`s
  (`components/evaluation/MetricCard.tsx`) with avg similarity per adapter above the table (in scope if
  cheap).

### `ParserComparisonTable.tsx`
- Group results by `evalCaseId`; group header = `filename · dimension`.
- One row per adapter (result): **similarity** via `ScorePill` (`components/evaluation/ScorePill.tsx`),
  then omission, hallucination (formatted numbers), cost (format `cost.usd`), latency (`latencyMs` →
  `ms`/`s`). Adapter label from `PARSER_REGISTRY`.
- Sort rows within a group by similarity desc (best first).

## 8. Reuse summary

| Need | Reuse |
|---|---|
| Status badge | `components/evaluation/EvalStatusBadge.tsx` |
| Score pill | `components/evaluation/ScorePill.tsx` |
| Summary metric cards | `components/evaluation/MetricCard.tsx` |
| Adapter list (label/value) | `PARSER_REGISTRY` in `components/documents/ParseMethodSelector.tsx` |
| Source doc filenames | `useSourceDocuments` / `api/sourceDocuments.ts` |
| Tab shell, page guard | pattern from `pages/ExtractionEvaluationPage.tsx` |

## 9. Acceptance criteria

1. `/evaluation/parser` renders a tabbed page; a **Parsing** nav item links to it.
2. A user can author a `text` case (pick source doc, add per-page ground truth) and see it listed by
   filename + review-status.
3. A user can create a run selecting ≥1 case and ≥2 adapters; the run appears with a live status badge.
4. The run-detail page polls until completion and shows a comparison table grouped by case, one row per
   adapter, with similarity/omission/hallucination/cost/latency; best-similarity row first.
5. A run whose adapter is invalid is impossible from the UI (adapters come from the registry); backend
   422s are surfaced as an error toast if they occur.
6. `npm run lint`, `npm run build`, and `npx vitest run` pass.

## 10. Testing (Vitest + RTL, mirroring `ExtractionEvalRunsTab.test.tsx`)

- `ParserEvalCasesTab`: renders list (mocked), opens dialog, submits a case (per-page textareas →
  `{pages}`), surfaces the duplicate-case conflict.
- `NewRunDialog`: validation (needs ≥1 case + ≥1 adapter); builds `variants` from selected adapters.
- `ParserComparisonTable`: groups by case, orders adapters by similarity, formats cost/latency.
- `ParserEvalRunDetailPage`: polling path (running → completed → table).
- Backend: one router test for the new get-one-run route.

## 11. Open questions / deferred

- **~~Key casing~~ RESOLVED** — the app convention is camelCase JSON via Pydantic aliases. Parser-eval
  backend DTOs are conformed to camelCase (§2a); frontend types are camelCase with no boundary mapping.
- Datasets, `(adapter,config)` editor, bootstrap, verification, delete/edit, extra dimensions — all
  deferred seams per §Scope.
