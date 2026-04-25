# CDM Viewer — Frontend Spec

> **Status**: Spec for implementation.
> **Scope**: Read-only UI for browsing a document's `ParseRun`s and the resulting `ParsedDocument` content, inside the existing documents-page Sheet drawer.
> **Depends on**: [cdm_viewer_backend.md](cdm_viewer_backend.md) endpoints.
> **Out of scope**: PDF rendering, bbox overlays, block→PDF click-through, re-run-with-different-config (already wired via existing re-parse flow), reading-order tree.
> **Reference**: [cdm_v1.md §11.4](cdm_v1.md).

---

## 1. Goals

1. Let a user open any document and inspect what the CDM parser produced: run metrics, full markdown, full text, per-page block breakdown.
2. Fit into the existing `DocumentsPage` Sheet drawer next to the legacy `ParseResultViewer` — do not redesign the page.
3. Reuse existing components (`Tabs`, `Badge`, `Select`, `Card`, `Skeleton`, `react-markdown`). No new dependencies.

Non-goals: pagination, virtualization for huge docs (v1 assumes ≤100 pages), editing.

---

## 2. Placement

In the documents-page Sheet drawer (see [DocumentsPage.tsx](../../frontend/src/pages/DocumentsPage.tsx)):

- If the document has **≥1 CDM ParseRun**, render the new `<ParsedDocumentViewer documentId={id} />` **above** the legacy `<ParseResultViewer />`.
- If the document has **0 CDM ParseRuns**, render nothing (the legacy viewer handles the pre-CDM case).
- Apply the same logic in [ProjectDocumentsPage.tsx](../../frontend/src/pages/ProjectDocumentsPage.tsx).

No feature flag — presence of CDM runs in the response determines visibility. The legacy viewer stays until the legacy adapter is retired (separate follow-up).

---

## 3. Component: `ParsedDocumentViewer`

File: `frontend/src/components/documents/ParsedDocumentViewer.tsx`.

### 3.1 Header

- Title: "CDM Parse" (distinguishes from legacy "Parse Results").
- Right side: `<Select>` of ParseRuns (if ≥2) — label format `{parser} / {representation_kind} / {startedAt relative time} · {status badge}`. Disabled when only one run exists; the single run is auto-selected.

### 3.2 Run-level metrics strip

Below header, before tabs. Compact horizontal row of labeled values:

- Status badge (success/pending/failed/partial/running — reuse `StatusBadge` styling from `ParseResultViewer`).
- Duration (`1.2s`, `12.4s`).
- Tokens (`1,200 in / 450 out`) — hide if both null.
- Cost (render key/value pairs from `cost` object, e.g. `1.2 credits`) — hide if empty.
- Warning count — clickable; opens a popover listing warnings. Hide if empty.
- Failed pages — small badge `failed: p3, p7`. Hide if empty.

### 3.3 Tabs

Five tabs, `markdown` default:

1. **Markdown** — `full_markdown` rendered with `react-markdown` + `remark-gfm` + `rehype-raw` (match existing viewer styling).
2. **Text** — `full_text` in a `<pre>` with `whitespace-pre-wrap`, monospace.
3. **Pages** — vertical list of pages. Each page is a collapsible card:
   - Header: `Page {index+1}` · `{block_count} blocks` · confidence badge (if present).
   - Body (expanded): list of blocks for that page. Each block shows: role badge, one-line text preview (truncated), optional confidence chip. Click a block to expand its full markdown / text / bbox / native_type.
4. **Metrics** — full dump of ParseRun fields in a key-value list (reuse `DiagnosticsView` pattern). Includes `provider_refs`, `config`, `parser_version`, `error`, raw `warnings`.
5. **Raw JSON** — collapsible `<pre>` of the full `ParsedDocument.content` payload for debugging.

Tab labels get count badges where useful (e.g. `Pages (3)`).

### 3.4 States

- **Loading list**: `<Skeleton>` placeholders matching `ParseResultViewer`.
- **Empty list**: component returns `null` (handled at placement level — see §2).
- **Loading detail** (ParsedDocument fetch): `<Skeleton>` tab body.
- **Run selected but status=failed**: show metrics strip + error message, hide content tabs. `content` endpoint returns 404 for failed runs — don't call it.
- **Run selected but status=running/pending**: spinner + "Parse in progress…". Re-poll every 5 s until `succeeded`/`failed`/`partial`.

---

## 4. API module

File: `frontend/src/api/parseRuns.ts`.

```ts
export async function listParseRuns(documentId: string): Promise<ParseRunListItem[]>
export async function getParsedDocument(parseRunId: string): Promise<ParsedDocumentDetail>
```

Shapes mirror the backend response (§2 of backend spec). Put types in `frontend/src/types/cdm.ts`.

---

## 5. Hook: `useParseRuns`

File: `frontend/src/hooks/useParseRuns.ts`. One hook per feature (project convention).

```ts
useParseRuns(documentId: string): {
  parseRuns: ParseRunListItem[]
  selectedRun: ParseRunListItem | undefined
  parsedDocument: ParsedDocumentDetail | undefined
  isLoading: boolean            // list
  isLoadingContent: boolean     // detail
  error: string | null
  selectRun: (id: string) => void
}
```

Internal behaviour:
- Fetch the list on mount + on `documentId` change.
- Auto-select the newest `succeeded`/`partial` run; fall back to the newest run if none succeeded.
- Fetch `parsedDocument` when a non-failed run is selected.
- Poll the list every 5 s while any run has `status in ("pending","running")`; stop polling otherwise.

No global state manager needed — local state + `useEffect` mirrors `useParseResults`.

---

## 6. Testing

- `ParsedDocumentViewer.test.tsx` — renders metrics strip from ParseRun fields, switches tabs, renders markdown, renders page list, shows failure state for `status=failed`, shows spinner for `status=running`.
- `useParseRuns.test.ts` — auto-selects newest succeeded run, swaps content on selection change, stops polling when all terminal.

Use existing MSW / Vitest setup (mirror `ParseResultViewer.test.tsx`).

---

## 7. Acceptance Criteria

1. Opening a document with ≥1 CDM ParseRun shows the new viewer above the legacy one.
2. All five tabs render and switch correctly against a real `succeeded` run.
3. Failed / running / pending runs render the correct placeholder state; no content fetch is issued for failed runs.
4. Multi-run documents show the run selector; switching runs swaps the content.
5. `npm run lint`, `npm run build`, `npx vitest run` all pass.
6. Existing documents-page behaviour unchanged.
