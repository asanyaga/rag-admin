# CDM Index — Slice 5: UI Polish

**Date:** 2026-04-28
**Master spec:** [CDM-Based Index Configuration](./2026-04-28-cdm-index-master-design.md)
**Depends on:** [Slices 1–4](./2026-04-28-cdm-index-master-design.md#implementation-slices)

---

**Depends on:** [Parser & Config Selector](./2026-04-29-cdm-index-parser-config-selector.md) — the parser+config selector and `parse_run_ids` binding must be complete before this slice.

## Scope

- Add-documents dialog: parse run mismatch error + inline parse action (for adding docs to existing indexes)
- Index list: `config_dirty` dot indicator (already in Slice 4 backend; this slice adds the API query support)
- Reprocess history panel on index detail page

> **Not in scope:** Parser+config selector and representation availability badges have been extracted to a dedicated spec: [CDM Index — Parser & Config Selector](./2026-04-29-cdm-index-parser-config-selector.md).

---

## Backend

### New endpoint: documents missing a matching parse run

```
POST /projects/{projectId}/indexes/{indexId}/documents/check-parse-runs
```

**Request:** `{ document_ids: [UUID] }`

**Response:**

```python
class ParseRunCheckResult(BaseModel):
    document_id: UUID
    has_matching_run: bool
    latest_matching_run: ParseRunSummary | None
    available_runs: list[ParseRunSummary]  # runs from other configs, for reference
```

Used by the add-documents dialog to show which documents need parsing before they can be added. Checks against the `(parser, config_hash)` stored in the index's config.

---

## Frontend

### Add-documents dialog — parse run mismatch handling

When adding documents to a CDM-mode index:

1. Dialog calls `POST /check-parse-runs` for selected documents
2. Documents with `has_matching_run = true` show a green check and the run date
3. Documents with `has_matching_run = false` show an amber warning:
   *"No LlamaParse / premium run found"*
   With a **[Parse now]** button that opens the parse dialog pre-filled with the required parser + config
4. The **Add to index** button is disabled until all selected documents have a matching run (or the user deselects the unready ones)

### Reprocess history panel

On the index detail page, a collapsible *"Version history"* section listing `index_events` rows:

| Version | Parser | Config | Documents | Processed |
|---|---|---|---|---|
| v3 (current) | LlamaParse | premium | 12 | Apr 28, 2026 |
| v2 | LlamaParse | premium | 10 | Apr 21, 2026 |
| v1 | — (raw text) | — | 8 | Apr 14, 2026 |

Clicking a row shows the full `config_snapshot` in a read-only JSON viewer (reusing the existing CDM viewer pattern).

---

## Tests

### Backend

- `test_check_parse_runs_all_match`: all documents return `has_matching_run = true`
- `test_check_parse_runs_missing`: documents without matching run return `has_matching_run = false` with `available_runs` populated

### Frontend

- Add-documents dialog: unready documents show amber warning and parse button
- Add button disabled until all documents have matching runs
- Version history panel renders `index_events` rows
- Config snapshot expandable in version history

---

## E2E Validation Checklist

1. Create and process a CDM-mode index (requires parser+config selector from the preceding spec)
2. Add a new document to the existing index — include one without a matching parse run → verify mismatch warning appears in the add-documents dialog
3. Click [Parse now] → confirm parse dialog is pre-filled with the index's parser+config
4. After parsing the document → re-open add dialog → verify document now shows green check
5. Complete adding the document and reprocess
6. Open index detail → expand version history → verify correct config snapshot shown for each version
7. Change config → reprocess → verify version history gains a new row
