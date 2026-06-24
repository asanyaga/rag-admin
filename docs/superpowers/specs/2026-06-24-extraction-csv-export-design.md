# Extraction CSV Export — Design

**Date:** 2026-06-24
**Scope:** Export a single extraction result's `structuredData` to a CSV file, triggered from the frontend with no backend changes.

---

## Overview

Users want to download extracted structured data as a CSV for use in Excel or Google Sheets. Export is scoped to a single `ExtractionResult` and is triggered from two places in the UI: the result detail viewer and the history list row.

---

## CSV Flattening Utility

**File:** `frontend/src/lib/exportCsv.ts`

Pure function signature:
```ts
exportResultToCsv(structuredData: Record<string, unknown>, filename: string): void
```

### Shape detection

Inspect top-level values of `structuredData`:
- **Candidate arrays** — keys whose value is an array where every element is a plain object
- **Flat fields** — keys whose value is a scalar (string, number, boolean, null)
- **Other** — nested objects or arrays of non-objects; serialized as JSON strings in cells

### Row building

1. If candidate arrays exist, pick the **largest** one as the primary table
2. Each object in that array becomes one CSV row
3. Flat sibling fields are appended as **extra columns on every row** (constant value across rows)
4. If no candidate arrays exist, emit a **single row** of all flat fields
5. Fallback: if no flat fields or valid arrays are found, emit a single row with a `data` column containing the full JSON-serialized object

### CSV serialization (RFC 4180)

- First row is the header
- Each cell is wrapped in double-quotes if it contains a comma, double-quote, or newline
- Embedded double-quotes are escaped as `""`
- Nested objects and remaining arrays (not selected as the primary table) are serialized as JSON strings

### Download trigger

```ts
const blob = new Blob([csvString], { type: 'text/csv;charset=utf-8;' })
const url = URL.createObjectURL(blob)
const a = document.createElement('a')
a.href = url; a.download = filename; a.click()
URL.revokeObjectURL(url)
```

**Filename pattern:** `{schema_name}_{result_id_prefix}.csv` (first 8 chars of result ID).

---

## UI Placement

### ExtractionResultViewer (detail view)

- Add a `Download` icon button with label "Export CSV" to the `CardHeader` row, alongside the status/method badges
- Visible only when `result.status === 'completed'` and `result.structuredData` is non-null and non-empty
- Calls `exportResultToCsv` directly — data is already in memory, no fetch needed
- Schema name for filename is passed as a new optional prop `schemaName?: string`

### ExtractionHistory (list row)

- Add a small `Download` icon button to the hover action row on each list item, between the expand trigger and the trash icon
- Visible only for `completed` results
- New prop: `onExportResult: (resultId: string) => void`
- Handler owned by `ExtractionPage`:
  - If the result is already selected (full data loaded), use it directly
  - Otherwise fetch via `getExtractionResult(resultId)`, then call `exportResultToCsv`
  - While fetching: disable the button
  - On fetch error: `toast.error('Failed to fetch result for export')`

---

## Error Handling & Edge Cases

| Scenario | Behaviour |
|---|---|
| `structuredData` is null or empty object | Export button hidden; no action |
| All values are nested objects / arrays of non-objects | Emit single row: `data` column containing full JSON string |
| Fetch fails (list-row path) | `toast.error(...)`, no file download |
| Cell contains comma, quote, or newline | RFC 4180 quoting applied |
| Multiple candidate arrays | Pick the largest array as primary table |

---

## Files Changed

| File | Change |
|---|---|
| `frontend/src/lib/exportCsv.ts` | New — CSV generation utility |
| `frontend/src/components/extraction/ExtractionResultViewer.tsx` | Add Export CSV button to CardHeader |
| `frontend/src/components/extraction/ExtractionHistory.tsx` | Add download icon to hover row; new `onExportResult` prop |
| `frontend/src/pages/ExtractionPage.tsx` | Wire `onExportResult` handler |

No backend changes. No new dependencies.

---

## Out of Scope

- Bulk/batch export across multiple documents or runs
- Excel (`.xlsx`) format
- Column ordering customization
- Server-side CSV generation
