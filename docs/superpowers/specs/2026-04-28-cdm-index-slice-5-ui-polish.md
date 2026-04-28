# CDM Index — Slice 5: UI Polish

**Date:** 2026-04-28
**Master spec:** [CDM-Based Index Configuration](./2026-04-28-cdm-index-master-design.md)
**Depends on:** [Slices 1–4](./2026-04-28-cdm-index-master-design.md#implementation-slices)

---

## Scope

- Parser + config selector: dropdown of `(parser, config_hash)` combinations from project parse runs
- Representation availability badges per selected parser config
- Add-documents dialog: parse run mismatch error + inline parse action
- Index list: `config_dirty` dot indicator (already in Slice 4 backend; this slice adds the API query support)
- Reprocess history panel on index detail page

---

## Backend

### New endpoint: available parser configs for a project

```
GET /projects/{projectId}/parse-configs
```

Returns distinct `(parser, parse_config_hash)` combinations that have at least one successful parse run across all documents in the project.

```python
class ParseConfigOption(BaseModel):
    parser: str
    parse_config_hash: str
    label: str          # human-readable: "LlamaParse — premium" derived from config fields
    document_count: int # how many project documents have a run with this config
    representations: list[str]  # which representations are available: ["full_text", "full_markdown", "blocks"]
    latest_run_at: datetime
```

`representations` is derived by inspecting `parsed_documents` rows for runs matching this config — checking which fields are non-null / non-empty.

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

Used by the add-documents dialog to show which documents need parsing before they can be added.

---

## Frontend

### Parser + config selector

In the index creation form, when `source_representation != "raw_text"`:

Replace the plain `parser` text input with a dropdown populated from `GET /parse-configs`.

Each option shows:
- Parser name (e.g. *"LlamaParse"*)
- Config label (e.g. *"premium"*, derived from key config fields)
- Document coverage: *"12 of 15 documents parsed"*
- Representation badges: `[blocks]` `[markdown]` `[text]` — greyed out if not available

Selecting an option auto-populates `IndexConfig.parser` and `IndexConfig.parse_config_hash`. The source representation selector then shows only representations available for the selected config.

If no parse configs exist for the project yet, show an empty state: *"No parse runs found for this project. Parse your documents first."* with a link to the documents page.

### Source representation selector — availability badges

Once a parser config is selected, the representation options show availability inline:

- `[✓ blocks]` — available, selectable
- `[✓ markdown]` — available, selectable
- `[✓ text]` — available, selectable
- `[— blocks]` — not available (greyed), tooltip: *"This parser config did not produce blocks. Re-parse with a configuration that enables block extraction."*

Auto-selects the richest available representation. User can override.

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

- `test_parse_configs_returns_distinct_combinations`: distinct `(parser, config_hash)` pairs returned with correct `document_count` and `representations`
- `test_parse_configs_empty_project`: empty list returned when no parse runs exist
- `test_check_parse_runs_all_match`: all documents return `has_matching_run = true`
- `test_check_parse_runs_missing`: documents without matching run return `has_matching_run = false` with `available_runs` populated

### Frontend

- Parser config selector populates from API
- Representation badges show correct availability
- Empty state renders when no parse configs
- Add-documents dialog: unready documents show amber warning and parse button
- Add button disabled until all documents have matching runs
- Version history panel renders `index_events` rows
- Config snapshot expandable in version history

---

## E2E Validation Checklist

1. Parse some documents with LlamaParse (premium) and some with LandingAI (standard)
2. Open index creation form → verify parser config dropdown shows both options with correct document counts
3. Select LlamaParse / premium → verify representation badges reflect actual availability
4. Add documents — include one without a LlamaParse premium run → verify mismatch warning appears
5. Click [Parse now] → confirm parse dialog is pre-filled correctly
6. After parsing the document → re-open add dialog → verify document now shows green check
7. Complete index creation and processing
8. Open index detail → expand version history → verify correct config snapshot shown
9. Change config → reprocess → verify version history has new row
