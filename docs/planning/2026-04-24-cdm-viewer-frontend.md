# CDM Viewer Frontend — ParsedDocument Viewer in Documents Sheet

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render the two CDM backend endpoints inside the existing documents-page Sheet drawer: run selector + metrics strip + tabs for Markdown / Text / Pages / Metrics / Raw JSON. Depends on the backend PR (sibling plan). Re-parse is already wired via the existing upload flow and is out of scope.

**Architecture:** One API module, one hook, one component. Reuses `Tabs`, `Badge`, `Select`, `Card`, `Skeleton`, `react-markdown`. No new dependencies. Mirrors the shape and pattern of `useParseResults` + `ParseResultViewer`.

**Tech Stack:** React 18, TypeScript, Vite, shadcn/ui, Tailwind CSS, Vitest.

**Spec:** [docs/specs/cdm_viewer_frontend.md](../specs/cdm_viewer_frontend.md)

---

## File Structure

**Create:**
- `frontend/src/types/cdm.ts` — `ParseRunListItem`, `ParsedDocumentDetail`
- `frontend/src/api/parseRuns.ts` — `listParseRuns`, `getParsedDocument`
- `frontend/src/hooks/useParseRuns.ts`
- `frontend/src/components/documents/ParsedDocumentViewer.tsx`
- `frontend/src/components/documents/ParsedDocumentViewer.test.tsx`
- `frontend/src/hooks/useParseRuns.test.ts`

**Modify:**
- `frontend/src/pages/DocumentsPage.tsx` — render `ParsedDocumentViewer` in Sheet drawer
- `frontend/src/pages/ProjectDocumentsPage.tsx` — same

---

## Preflight

- [ ] **Preflight 1: Backend PR merged (or available on a branch)**

Confirm `GET /documents/{id}/parse-runs` and `GET /parse-runs/{id}/parsed-document` return the shapes in the backend spec. If developing in parallel, stub the API locally via MSW.

- [ ] **Preflight 2: Branch from main**

```bash
git -C /c/Repos/rag-admin checkout -b feat/cdm-viewer-frontend main
```

- [ ] **Preflight 3: Baseline frontend checks**

```bash
npm --prefix /c/Repos/rag-admin/frontend run lint
npm --prefix /c/Repos/rag-admin/frontend run build
npx --prefix /c/Repos/rag-admin/frontend vitest run
```

Expected: all green.

---

## Task 1 — Types + API module

- [ ] Create `frontend/src/types/cdm.ts` with:

```ts
export interface ParseRunListItem {
  id: string
  sourceDocumentId: string
  parser: string
  parserVersion: string | null
  representationKind: string
  status: 'pending' | 'running' | 'succeeded' | 'failed' | 'partial'
  startedAt: string
  finishedAt: string | null
  durationMs: number | null
  inputTokens: number | null
  outputTokens: number | null
  cost: Record<string, unknown>
  warnings: string[]
  failedPages: number[]
  providerRefs: Record<string, unknown>
  error: string | null
  config: Record<string, unknown>
  createdAt: string
}

export interface ParsedDocumentDetail {
  parseRunId: string
  sourceDocumentId: string
  pageCount: number
  blockCount: number
  fullText: string | null
  fullMarkdown: string | null
  content: Record<string, unknown>   // full ParsedDocument JSON
}
```

- [ ] Create `frontend/src/api/parseRuns.ts` with `listParseRuns(documentId)` and `getParsedDocument(parseRunId)` using `apiClient` (mirror `frontend/src/api/parsing.ts`).

---

## Task 2 — `useParseRuns` hook

- [ ] Create `frontend/src/hooks/useParseRuns.ts`.
- [ ] Local state: `parseRuns`, `selectedRunId`, `parsedDocument`, loading flags, error.
- [ ] Effect 1: on `documentId` change, call `listParseRuns`; on success, auto-select newest `succeeded` or `partial`; if none, newest run of any status.
- [ ] Effect 2: on `selectedRunId` change, if the selected run's `status` is not `failed`, call `getParsedDocument`. For `failed`, clear `parsedDocument`.
- [ ] Poll: while any run has `status in ("pending","running")`, refresh the list every 5000 ms via `setInterval`; clear when terminal. Clean up on unmount.
- [ ] Return the shape in spec §5.

- [ ] Create `frontend/src/hooks/useParseRuns.test.ts` covering:
  - auto-selects newest succeeded run
  - clears `parsedDocument` and does not fetch when selecting a failed run
  - stops polling when all runs are terminal

---

## Task 3 — `ParsedDocumentViewer` component

- [ ] Create `frontend/src/components/documents/ParsedDocumentViewer.tsx`.
- [ ] Props: `{ documentId: string }`.
- [ ] Uses `useParseRuns(documentId)`.
- [ ] Early returns:
  - loading → `<Skeleton>` card
  - error → destructive `<Card>` with error
  - `parseRuns.length === 0` → `return null` (parent handles absence)

- [ ] Render the layout described in spec §3:
  1. Header row: `<h3>CDM Parse</h3>` + `<Select>` of runs (if ≥2).
  2. Metrics strip (status badge, duration, tokens, cost, warnings, failed_pages).
  3. If `selectedRun.status in ("pending","running")`: spinner + "Parse in progress…" and stop here.
  4. If `selectedRun.status === "failed"`: show `error` and stop.
  5. Otherwise: `<Tabs defaultValue="markdown">` with five tabs per spec §3.3.
  6. Pages tab: map `(content.pages as Page[])` to a list of collapsible cards; each card lists `content.blocks` filtered by `page_index`.

- [ ] Extract helpers where clean: `RunMetricsStrip`, `PageBlockList`.

- [ ] Create `ParsedDocumentViewer.test.tsx`:
  - renders run selector when 2 runs
  - switches tabs
  - renders markdown via react-markdown
  - shows failed-run error state (no content fetch)
  - shows pending spinner

Run `npx vitest run` in the frontend directory; fix until green.

---

## Task 4 — Wire into pages

- [ ] In `frontend/src/pages/DocumentsPage.tsx`, locate the Sheet body where `<ParseResultViewer documentId=... />` is rendered. Add `<ParsedDocumentViewer documentId=... />` immediately above it. The component itself returns `null` when no CDM runs exist, so no extra guard is needed.
- [ ] Repeat in `frontend/src/pages/ProjectDocumentsPage.tsx`.

---

## Task 5 — Full regression

- [ ] Run all frontend checks:

```bash
npm --prefix /c/Repos/rag-admin/frontend run lint
npm --prefix /c/Repos/rag-admin/frontend run build
npx --prefix /c/Repos/rag-admin/frontend vitest run
```

Expected: all green.

- [ ] Manual smoke test via Docker local stack (see CLAUDE.md "Local Testing"): upload a PDF with `USE_CDM_PARSER=true`, open the documents Sheet, verify:
  - viewer appears above legacy viewer
  - run selector visible once ≥2 runs exist (re-parse to create one)
  - all five tabs render
  - metrics strip shows duration + tokens
  - failed runs show error state without crashing

---

## Task 6 — PR

- [ ] Commit on `feat/cdm-viewer-frontend`.
- [ ] Open PR titled `feat(cdm): ParsedDocument viewer in documents sheet`, linked to the GitHub issue.
- [ ] Body: link spec, screenshots of the five tabs, confirm lint/build/test output.
- [ ] Do not merge. Wait for user to review.
