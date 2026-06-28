# Extraction Result Transforms — `join_results`

**Parent spec:** [extraction-result-transform-pipeline.md](extraction-result-transform-pipeline.md)
**Status:** Draft — pending GitHub issue + user confirmation
**Date:** 2026-06-28
**Scope:** Add the `join_results` transform primitive — join 2–5 clean, single-schema `ExtractionResult` inputs on a shared key column, producing one wider result whose columns are the union of all input schemas.

---

## Context

The original `merge_records` design assumed a single-shot extraction whose output contained mixed rows (e.g. spec rows and price rows interleaved). Testing showed that splitting extractions by schema — running a focused price extraction and a focused spec extraction separately — yields faster, more accurate results using small, non-reasoning models, while avoiding token-size and rate limits on large source documents.

`join_results` is the composition step that makes this architecture viable: assemble the target record from N clean, purpose-built extraction results. Each input result is authoritative for its own columns. No row collapse, no conflict resolution, no spine detection — just a join.

This primitive replaces the multi-input `merge_records` cross-schema use case (Slice 5 of the parent spec).

---

## The `join_results` Primitive

Takes 2–5 `ExtractionResult` inputs and joins them on a shared key column. The output is a new `ExtractionResult` whose rows contain the union of all input columns, with each input result contributing its own columns exclusively.

### Architectural pattern

```
focused extraction → R_price  (sku, model, series, price)
focused extraction → R_spec   (series, height, width, weight)
                         │
                         │  join_results
                         │    joinKey: "series"
                         │    joinType: "left"
                         ▼
                   R_joined  (sku, model, series, price, height, width, weight)
                         │
                         │  strip_records / project_to_schema / export
                         ▼
```

Downstream primitives (`strip_records`, `project_to_schema`) operate on `R_joined` as an ordinary `ExtractionResult`.

### Config

```json
{
  "joinKey": "series",
  "joinType": "left",
  "resultIds": ["<price_result_id>", "<spec_result_id>"]
}
```

- `joinKey` — the field present in all input results used to match rows. Must exist in every result; validated before preview or apply.
- `joinType` — `"left"` or `"inner"`.
  - `"left"`: all rows from the first (left) result are kept; rows with no match in a right result have that result's columns set to `null` and are flagged `unmatched`.
  - `"inner"`: only rows with a match in every right result are kept. Null-key left rows are still passed through and flagged `null_key` so the user can see and handle them in preview.
- `resultIds` — ordered list of 2–5 result ids. The **first** id is the left (primary) result; the remaining are right (lookup) results. Order determines both join direction and output column order.

**v1 constraint and forward path:** `joinKey` is a single field name in v1. Composite join keys (`joinKeys: string[]`) are anticipated as a future extension if a single key proves insufficient. Internally, matching treats `joinKey` as a single-element key tuple so the extension to N keys is additive — the API surface stays `joinKey: string` for v1; a future slice adds `joinKeys: string[]` as an alternative with both validated mutually exclusive.

### Output column order

1. All columns from the left result, in their original order.
2. For each right result (in `resultIds` order): all columns from that result, in their original order, **excluding** `joinKey` (which is already present from the left result).

The join key appears exactly once in the output.

---

## Validation — errors returned before any data is written

The following conditions are checked during both `preview` and `apply`. If any condition is met the call returns a validation error; no result is persisted.

| Condition | Error |
|---|---|
| `joinKey` is absent from any input result's schema | `join_key_missing` — names the offending result(s) |
| A non-join-key column name appears in 2+ input results | `column_conflict` — lists the conflicting column name(s) and which results contain them |
| `resultIds` contains fewer than 2 or more than 5 entries | `invalid_result_count` |

These are hard errors. There is no automatic column renaming and no silent data loss. The expected remedy for `column_conflict` is to fix the upstream extraction schemas so they are non-overlapping, or to add a `normalize_field` step upstream to rename the conflicting column before joining.

**Note:** a right-side result with duplicate `joinKey` values is not a hard error — it produces an `ambiguous_right` row flag (see below). The preview table surfaces it; the user decides whether to fix the upstream extraction or accept first-match behavior.

---

## Row-level flags

| Flag | Condition |
|---|---|
| `unmatched` | A left row's `joinKey` value had no matching row in one or more right results (`joinType: left` only). Right-side columns from the unmatched result(s) are `null`. |
| `null_key` | A left-result row has a `null` value for `joinKey`. The row is passed through with right-side columns `null` and flagged `null_key` — for **both** `joinType: left` and `joinType: inner`. The row always appears in the output so the user can see and handle it in preview. Right-side rows with a `null` `joinKey` are dead lookup entries that never match; they produce no output row and no flag. |
| `ambiguous_right` | A right result had 2+ rows with the same `joinKey` value; the first matching row's values were used. All left rows that matched this key are flagged. The user should inspect in preview and decide whether to fix the upstream extraction or accept first-match behavior. |

Flags are attached to each output row (consistent with `merge_records` row-flag pattern) and are surfaced in the preview table's flag filter.

---

## Provenance

Each cell in the output carries `{sourceResultId, sourcePage}` from its origin result. Left-result cells retain their original provenance. Right-result cells carry the provenance of the matched right row. `null`-filled cells (unmatched) carry `{sourceResultId: null, sourcePage: null}`.

---

## Worked example

**Input: R_price** (focused price extraction)

| sku | model | series | price |
|---|---|---|---|
| 12345 | gp-30b | gp-30 | 1000 |
| 54321 | gp-30a | gp-30 | 2000 |

**Input: R_spec** (focused spec extraction)

| series | height | width | weight |
|---|---|---|---|
| gp-30 | 100 | 200 | 20 |

**Config:**
```json
{
  "joinKey": "series",
  "joinType": "left",
  "resultIds": ["<R_price_id>", "<R_spec_id>"]
}
```

**Output: R_joined**

| sku | model | series | price | height | width | weight |
|---|---|---|---|---|---|---|
| 12345 | gp-30b | gp-30 | 1000 | 100 | 200 | 20 |
| 54321 | gp-30a | gp-30 | 2000 | 100 | 200 | 20 |

Both price rows match the single spec row on `series = "gp-30"`. The join key `series` appears once. No flags on either row.

---

## Worked example — unmatched and null key rows

**Input: R_price** (extended)

| sku | model | series | price |
|---|---|---|---|
| 12345 | gp-30b | gp-30 | 1000 |
| 99999 | xx-10 | xx-10 | 500 |
| 77777 | gp-40a | `null` | 750 |

**Input: R_spec** (same as above — only gp-30)

| series | height | width | weight |
|---|---|---|---|
| gp-30 | 100 | 200 | 20 |

**Output: R_joined** (`joinType: left`)

| sku | model | series | price | height | width | weight | flags |
|---|---|---|---|---|---|---|---|
| 12345 | gp-30b | gp-30 | 1000 | 100 | 200 | 20 | — |
| 99999 | xx-10 | xx-10 | 500 | `null` | `null` | `null` | `unmatched` |
| 77777 | gp-40a | `null` | 750 | `null` | `null` | `null` | `null_key` |

---

## Frontend

- **Config form:** `JoinResultsConfigForm.tsx`
  - Multi-select result picker for `resultIds` with drag-to-reorder (first = left/primary; visual label "Primary" vs "Lookup").
  - `joinKey` field selector: text input, ideally with a dropdown populated from the intersection of all selected results' fields. Labelled as single-key for v1; composite key support is a future extension.
  - `joinType` radio: `left` (default) / `inner`.
  - Inline validation: surface `column_conflict` and `join_key_missing` errors as the user selects results, before they hit Preview.
- **Preview table:** flag chips (`unmatched`, `null_key`, `ambiguous_right`) per row; source coloring per cell (which input result the value came from); filter/sort by flag. `ambiguous_right` chip should link to the right-side result and the duplicated key value to help the user diagnose the upstream extraction.
- **Transform menu:** `join_results` added to the `Transform ▾` primitive selector in `ExtractionResultViewer`.
- **`config_schema`:** registry entry includes a JSON Schema object for generic form generation.

---

## Acceptance Criteria

1. `join_results` primitive exists in the registry; `get_transforms()` returns it; `build_transform("join_results")` resolves it.
2. Applying `join_results` is non-destructive: all input results are unchanged; output is a new `ExtractionResult` with `extraction_method = "transform"` and `extraction_metadata.lineage = { sourceResultIds: [...], transform: { type: "join_results", config: {...} } }`.
3. Output column order: left result columns in original order, then each right result's columns in original order (excluding `joinKey`), for each right result in `resultIds` order. `joinKey` appears exactly once.
4. **Validation errors (returned by both preview and apply, nothing persisted):**
   - `join_key_missing` when `joinKey` is absent from any input result's schema.
   - `column_conflict` when a non-join-key column name appears in 2+ input results.
   - `invalid_result_count` when `resultIds` has fewer than 2 or more than 5 entries.
5. `joinType: left` — all left rows appear in the output; rows with no match in a right result have that result's columns set to `null` and are flagged `unmatched`.
6. `joinType: inner` — only rows with a match in every right result appear in the output, except null-key left rows (see AC 7).
7. A left-result row with a `null` `joinKey` value is passed through with right-side columns `null` and flagged `null_key` for **both** `joinType: left` and `joinType: inner`. It always appears in the output.
8. A right result with 2+ rows sharing the same `joinKey` value is not a hard error. The first matching row is used; all left rows that matched that key are flagged `ambiguous_right`.
9. Provenance per cell: left-result cells carry their original `{sourceResultId, sourcePage}`; right-result cells carry the matched row's `{sourceResultId, sourcePage}`; `null`-filled cells carry `{sourceResultId: null, sourcePage: null}`.
10. Worked example: R_price (sku, model, series, price) joined with R_spec (series, height, width, weight) on `series`, `joinType: left`, produces R_joined with all 7 columns and both price rows enriched with the single matching spec row.
11. Unmatched, null-key, and ambiguous_right rows produce the correct output and flags as shown in the worked examples.
12. `JoinResultsConfigForm` renders result multi-select with drag-reorder, `joinKey` field input, `joinType` radio; `column_conflict` and `join_key_missing` errors are surfaced before Preview. Preview table shows `unmatched`, `null_key`, and `ambiguous_right` flag chips with source coloring; `ambiguous_right` chip identifies the right-side result and duplicated key value.
