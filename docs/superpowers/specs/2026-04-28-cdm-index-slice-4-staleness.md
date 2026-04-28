# CDM Index — Slice 4: Staleness + Config Change UX

**Date:** 2026-04-28
**Master spec:** [CDM-Based Index Configuration](./2026-04-28-cdm-index-master-design.md)
**Depends on:** [Slice 1 — Foundation](./2026-04-28-cdm-index-slice-1-foundation.md)

---

## Scope

- `config_dirty` flag lifecycle: set on config change, cleared on reprocess
- `PATCH /indexes/{id}/config` — dedicated endpoint for config changes; returns impact summary; enforces confirmation for chunk-invalidating changes
- Staleness fields pattern on `IndexResponse` and downstream output responses
- UI: `config_dirty` amber banner on index detail; `IndexVersionBadge` component; index list dirty indicator

---

## What this slice does NOT include

- Parser + config selector, document parse run mismatch handling (Slice 5)
- Actual downstream output pages (evals, retrieval logs) — pattern is established but consumers not built yet

---

## Backend

### Config change endpoint

```
PATCH /projects/{projectId}/indexes/{indexId}/config
```

**Request body:**

```python
class IndexConfigUpdateRequest(BaseModel):
    config: IndexConfig
    confirm: bool = Field(default=False)
    # Must be True to apply chunk-invalidating changes.
```

**Chunk-invalidating fields** — changes to any of these require `confirm = True`:
- `source_representation`
- `chunking_strategy`
- `parser`
- `parse_config_hash`
- `chunk_size`, `chunk_overlap`, `chunk_unit`
- `split_heading_level`, `max_section_chars`
- `group_by_heading`, `max_blocks_per_chunk`, `block_role_filter`
- `embedding_provider`, `embedding_model`, `embedding_dimensions`

**Non-invalidating fields** — applied immediately without confirmation:
- (None in current config — all config fields affect chunking or embedding)

**Behaviour:**

1. If any chunk-invalidating field changed and `confirm = False`:
   - Return `409 Conflict` with impact summary:
     ```json
     {
       "error": "config_change_requires_confirmation",
       "message": "Changing this configuration will invalidate all existing chunks and mark downstream outputs as stale.",
       "affected": {
         "chunks": 1842,
         "downstream_outputs": 3
       },
       "action_required": "Re-send with confirm=true to proceed."
     }
     ```
   - Do not apply the change.
2. If `confirm = True` (or no invalidating fields changed):
   - Apply the config change
   - Set `index.config_dirty = True`
   - Return updated `IndexResponse`

**Note:** This endpoint is separate from `PATCH /indexes/{id}` (name/description). Config and metadata are distinct update surfaces.

### Staleness fields on `IndexResponse`

```python
class IndexResponse(BaseModel):
    ...
    version: int
    config_dirty: bool = Field(..., alias="configDirty")
    last_processed_at: datetime | None = Field(None, alias="lastProcessedAt")
    # last_processed_at = created_at of the most recent index_events row
```

### Staleness fields pattern for downstream outputs

Not yet consumed by real pages, but the helper function and schema pattern are established in this slice.

```python
class IndexVersionInfo(BaseModel):
    """Embedded in downstream output responses to surface staleness."""
    index_id: UUID = Field(..., alias="indexId")
    output_index_version: int = Field(..., alias="outputIndexVersion")
    current_index_version: int = Field(..., alias="currentIndexVersion")
    is_stale: bool = Field(..., alias="isStale")
    stale_since_version: int | None = Field(None, alias="staleSinceVersion")
    # stale_since_version: first index version after output_index_version
    # derived from index_events: MIN(version) WHERE version > output_index_version
```

Helper: `IndexRepository.get_version_info(index_id, output_version) -> IndexVersionInfo`.

---

## Frontend

### `config_dirty` banner

On the index detail page, when `configDirty = true`, show an amber banner below the page header:

> **Configuration updated** — reprocess to apply changes. Existing chunks and downstream outputs will be affected. [Reprocess now]

"Reprocess now" triggers `POST /indexes/{id}/process`. Banner disappears when `configDirty = false` (after successful reprocess).

### `IndexVersionBadge` component

Reusable component for downstream output rows.

Props:
```typescript
interface IndexVersionBadgeProps {
  outputIndexVersion: number
  currentIndexVersion: number
  isStale: boolean
  staleSinceVersion?: number
  reprocessedAt?: string   // ISO date of stale_since_version event
}
```

Renders:
- **Current**: `v3` — muted text, no icon
- **Stale**: `v1 · stale` — amber badge. Tooltip: *"Index reprocessed to v{currentVersion} on {date}. Results reflect chunks from v{outputVersion}."*

### Index list page — dirty indicator

On the index list, rows where `configDirty = true` show a small amber dot (●) to the right of the index name. No text. Tooltip on hover: *"Configuration updated — reprocess pending."*

---

## Tests

### Backend

- `test_config_update_invalidating_without_confirm`: returns `409` with impact summary; config not changed
- `test_config_update_invalidating_with_confirm`: config applied, `config_dirty = true`
- `test_config_update_non_invalidating`: applied immediately (N/A for current fields — documented as placeholder)
- `test_reprocess_clears_config_dirty`: after successful reprocess, `config_dirty = false`
- `test_get_version_info_current`: `is_stale = false` when `output_version == current_version`
- `test_get_version_info_stale`: `is_stale = true`, `stale_since_version` correct

### Frontend

- Banner renders when `configDirty = true`; hidden when `false`
- `IndexVersionBadge` renders current state correctly
- `IndexVersionBadge` renders stale state with tooltip
- Index list dirty dot renders for dirty indexes

---

## E2E Validation Checklist

1. Create and process an index (v1)
2. `PATCH /config` with a changed `chunking_strategy` without `confirm` → verify `409` with chunk count
3. Re-send with `confirm = true` → verify `config_dirty = true` in response
4. Verify amber banner appears on index detail page
5. Trigger reprocess → verify `config_dirty = false`, `version = 2`, banner gone
6. Simulate a downstream output row with `index_version = 1` → verify `IndexVersionBadge` shows stale with correct tooltip
7. Verify index list page shows amber dot on dirty index
