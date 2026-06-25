# Delete Parse Run — Design

**Date:** 2026-06-25

## Goal

Allow users to delete a parse run from two surfaces: the `RunTimeline` (document detail page) and the `RunHeader` (parse run detail page). Deletion is blocked when any dependent entity still references the run; the UI surfaces exactly what is blocking.

## Downstream Impact

Deleting a parse run has the following effects:

| Table | FK behavior | Effect |
|---|---|---|
| `parsed_documents` | CASCADE | Content blob (text, markdown, blocks) is deleted |
| `index_documents` | CASCADE (but blocked) | Would drop the document from the index |
| `classification_runs` | CASCADE (but blocked) | Would delete classification runs |
| `extraction_results` | SET NULL (but blocked) | Would null the source parse run reference |

Because we block before deleting, the only cascade that actually fires on a successful delete is `parsed_documents`.

## Backend

### New endpoint

`DELETE /parse-runs/{id}` in `backend/app/routers/parse_runs.py`.

Auth follows the existing `_user_owns_source` pattern — same ownership check as the GET endpoints.

### New repository method

`ParseRunRepository.get_blockers(run_id) -> dict` counts rows in the three dependent tables:

```python
{
  "index_documents": int,
  "classification_runs": int,
  "extraction_results": int,
}
```

### Delete logic

1. Fetch the run; 404 if missing.
2. Ownership check via `_user_owns_source`; 403 if unauthorized.
3. Call `get_blockers`. If any count > 0, return `409 Conflict`:
```json
{
  "detail": "Parse run has dependent entities that must be removed first.",
  "blockers": {
    "index_documents": 2,
    "classification_runs": 1,
    "extraction_results": 0
  }
}
```
4. If all counts are 0, delete the row. `parsed_documents` is CASCADE-deleted by the DB.

## Frontend

### API

New `deleteParseRun(runId: string): Promise<void>` in `frontend/src/api/parseRuns.ts`. Throws on non-2xx; caller reads the 409 body to get blocker counts.

### Component: `ParseRunDeleteDialog`

`frontend/src/components/parse-runs/ParseRunDeleteDialog.tsx`

A confirmation dialog with two states:

**Default state** — "Delete this parse run? This cannot be undone." — Confirm (destructive) + Cancel buttons.

**Blocked state (409)** — replaces body with blocker message, e.g.:
> "This run is in use and cannot be deleted: 2 index document(s), 1 classification run(s). Remove these references first."
> Confirm button is hidden. Only Cancel is shown.

Props:
```ts
interface ParseRunDeleteDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  runId: string
  onDeleted: () => void
}
```

### RunTimeline changes

Add a trash icon `Button` at the end of each row (alongside "Open viewer"). Clicking opens `ParseRunDeleteDialog` for that run's id. `onDeleted` calls `refresh()` to reload the list in place.

### RunHeader changes

Add a Delete button next to the existing Re-parse button. Clicking opens `ParseRunDeleteDialog`. `onDeleted` navigates to `/documents`.

## Error handling

| Scenario | Handling |
|---|---|
| Run not found | 404 — dialog shows generic error |
| Not authorized | 403 — dialog shows generic error |
| Blocked by dependencies | 409 — dialog shows blocker counts |
| Unexpected server error | 500 — dialog shows generic error |
