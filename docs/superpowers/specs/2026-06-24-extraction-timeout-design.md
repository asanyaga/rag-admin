# Configurable Extraction Timeout

**Date:** 2026-06-24
**Status:** Approved

## Problem

Extraction jobs on large files fail with a timeout error before processing completes. Both limits are hard-coded:

| Layer | Current value | Behaviour |
|---|---|---|
| Backend stale-job reaper | 10 minutes | Marks pending jobs `failed` |
| Frontend polling | 5 minutes | Stops polling, shows "Processing timeout" |

The frontend times out first (5 min), even though the backend would allow 10 min. Users have no way to extend either limit.

## Solution

Add an optional `timeout_minutes` field to `RunExtractionRequest`. The value is stored on the `ExtractionResult` row and used by both the backend reaper and the frontend polling hook to determine when a job has truly stalled.

**Defaults:** backend keeps 10 minutes. Frontend fallback aligns to 10 minutes (fixing the current 5-min mismatch). **Max:** 120 minutes, enforced by backend validation.

---

## Data Model

### New column: `extraction_results.timeout_minutes`

- Type: `Integer`, nullable
- `NULL` means "use default" (10 minutes)
- Added via Alembic migration

### Schema placement

`timeout_minutes` is a **top-level field on `RunExtractionRequest`**, not nested inside `ChunkingConfig`. It is a job execution concern, not a chunking concern. In the UI it appears in the large-file processing section alongside "Max tokens / minute", but the wire format sends it at the root:

```json
{
  "parse_run_id": "...",
  "extraction_schema_id": "...",
  "extraction_method": "llm",
  "chunking": { "strategy": "token_budget_pages", "maxTokensPerMinute": 50000 },
  "timeout_minutes": 45
}
```

---

## Backend Changes

### `backend/app/schemas/extraction_result.py`

Add to `RunExtractionRequest`:

```python
timeout_minutes: int | None = Field(default=None, ge=1, le=120)
```

Pydantic returns `422 Unprocessable Entity` for values outside 1–120.

### `backend/app/routers/extraction.py`

Extract `timeout_minutes` from the request and pass it to the result-creation call.

### `backend/app/repositories/extraction_result_repository.py`

`create()` accepts `timeout_minutes: int | None` and writes it to the new column.

### `backend/app/services/extraction_service.py`

**`_reap_stale()`** — replace hardcoded `STALE_TIMEOUT` with a per-job value:

```python
timeout = timedelta(minutes=result.timeout_minutes or 10)
if age > timeout:
    ...message = f"Extraction job timed out (exceeded {result.timeout_minutes or 10} minutes)"
```

The module-level `STALE_TIMEOUT` constant is removed.

### `backend/app/schemas/extraction_result.py` — response

Add to `ExtractionResultResponse`:

```python
timeout_minutes: int | None
```

Serialised via `from_orm_model()` so the frontend receives the value.

---

## Frontend Changes

### `frontend/src/types/extraction.ts`

- Add `timeoutMinutes?: number` to `RunExtractionRequest` (not `ChunkingConfig`)
- Add `timeoutMinutes: number | null` to `ExtractionResultResponse`

### `frontend/src/components/extraction/ExtractionForm.tsx`

Add a number input "Timeout (minutes)" in the large-file processing section, below "Max tokens / minute":

- Placeholder: `10`
- Min: `1`, Max: `120`
- Sent in the request body only when set

### `frontend/src/hooks/useExtractionResults.ts`

Replace the hardcoded `EXTRACTION_POLLING_TIMEOUT` (5 min) and `PARSE_TIMEOUT` (10 min) constants. After the first successful poll, derive the deadline from the job itself:

```ts
const deadlineMs = (result.timeoutMinutes ?? 10) * 60 * 1000;
```

This aligns the frontend fallback default (10 min) with the backend default, fixing the current mismatch where the frontend was cutting off 5 minutes earlier than the backend reaper.

---

## Error Handling & Edge Cases

| Scenario | Behaviour |
|---|---|
| `timeout_minutes` outside 1–120 | Backend returns `422` |
| `NULL` timeout on existing/new rows | Reaper and hook both fall back to 10 minutes |
| Frontend receives `null` timeout | Hook uses `10 * 60 * 1000` ms fallback |
| Job completes before timeout | Polling stops on `completed`/`failed` — timeout is a ceiling only |
| User submits without setting timeout | Field omitted from request; column stays `NULL` |

---

## Testing

### Backend unit — `_reap_stale`

Parametrise over `timeout_minutes` values (`None`, `5`, `60`). Assert the correct `timedelta` is applied and the error message reflects the actual value.

### Backend unit — Pydantic schema

Assert `422` for `timeout_minutes=0` and `timeout_minutes=121`. Assert valid for `timeout_minutes=30`.

### Backend integration — full run

Create a result with `timeout_minutes=1`, advance mock time past 1 minute, poll via the GET endpoint, assert status is `failed` with `"exceeded 1 minutes"` in the message.

### Frontend — hook

- Mock a result response with `timeoutMinutes: 20`; assert polling deadline is `20 * 60 * 1000` ms.
- Mock `timeoutMinutes: null`; assert fallback is `10 * 60 * 1000` ms.
