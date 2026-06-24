---
title: Delete Extraction Runs
date: 2026-06-24
issue: https://github.com/asanyaga/rag-admin/issues/106
---

# Delete Extraction Runs

Allow users to delete previous extraction runs from the Extraction page.

## Scope

Single extraction result deletion. Batch delete is out of scope. Pending runs cannot be deleted (a background task is actively working on them).

## Backend

### Repository — `ExtractionResultRepository`

Add:

```python
async def delete(self, result_id: UUID) -> bool:
    """Delete an extraction result. Returns True if deleted, False if not found."""
```

Uses a `DELETE` statement; returns `False` if no row matched (caller decides whether to raise).

### Service — `ExtractionService`

Add:

```python
async def delete_result(self, result_id: UUID, user_id: UUID) -> None:
    """Delete an extraction result. Raises NotFoundError if not found."""
```

No ownership check needed beyond existence — extraction results are project-scoped and the user is already authenticated. Raises `NotFoundError` if the result does not exist.

### Router — `extraction.py`

New endpoint:

```
DELETE /extraction-results/{result_id}
→ 204 No Content on success
→ 404 if not found
```

Follows the existing `DELETE /extraction-schemas/{schema_id}` pattern exactly.

No database migration required.

## Frontend

### API — `api/extraction.ts`

Add:

```ts
export async function deleteExtractionResult(resultId: string): Promise<void>
```

Calls `DELETE /extraction-results/{resultId}`.

### Hook — `useExtractionResults.ts`

Expose:

```ts
deleteResult: (resultId: string) => Promise<void>
```

On success:
- Remove the item from `results` state
- If `selectedResult?.id === resultId`, clear `selectedResult` to `null`
- Call `toast.success('Extraction deleted')`

On error: call `toast.error(...)` with the error message.

### Component — `ExtractionHistory.tsx`

**Structural change:** each row is currently a `<Button>` used as a `CollapsibleTrigger`. A `<button>` cannot contain another `<button>`, so the row must be restructured.

New layout per row:

```
<div class="flex items-center rounded-md hover:bg-muted/50">
  <CollapsibleTrigger asChild>
    <button class="flex-1 text-left py-2.5 pl-3 pr-2">
      [chevron] [schema name] [method badge] [status badge] [date]
    </button>
  </CollapsibleTrigger>

  <button class="shrink-0 pr-2 text-muted-foreground hover:text-destructive" aria-label="Delete">
    <Trash2 class="h-3.5 w-3.5" />
  </button>
</div>
```

- Delete button is **not rendered** when `status === 'pending'`
- Delete fires immediately (no confirmation dialog) — the action is easily reversible by re-running the extraction
- `toast.success` confirms the deletion

### Page — `ExtractionPage.tsx`

Pass `onDeleteResult` down to `ExtractionHistory`:

```ts
const handleDeleteResult = async (resultId: string) => {
  await deleteResult(resultId)
}
```

`useExtractionResults` exposes `deleteResult`; the page threads it to the component.

## Error handling

- 404 from the API → `toast.error('Extraction run not found')`
- Other errors → `toast.error('Failed to delete extraction run', { description: message })`

## Testing

- Backend: unit test for the new repository `delete` method and service `delete_result`
- Frontend: existing `useExtractionResults.test.ts` — add a test for `deleteResult` updating state correctly
