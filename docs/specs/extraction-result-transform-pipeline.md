# Extraction Result Transforms (HITL, Interactive)

**Status:** Draft — pending GitHub issue + user confirmation
**Date:** 2026-06-27
**Scope:** An interactive, human-driven post-extraction capability: apply one configurable `ExtractionResultTransform` primitive at a time to selected extraction result(s), inspecting the new result after each step. Each application is non-destructive and produces a new, lineage-tracked `ExtractionResult`. The recorded sequence of human decisions is the seed for later automation. First primitives target collapsing scattered brochure rows (base↔variant) into a coherent record set.

---

## Problem

Extraction output frequently needs reshaping before it is a usable record set:

- A document scatters a record's fields across pages — specs on one page, price + SKU on another — producing **partial rows** that must be collapsed.
- Spec rows carry a **base** model (`GP-40`); price rows carry **base + configuration** (`GP-40B 230/50/1 DD`) plus the real SKU. Matching is base↔variant, never exact.
- Brand/vendor may be present on only some rows and must be propagated.
- For **batching**, a project may run several extractions (price-only, spec-only) and need to merge them.

But **many projects need none of this** — e.g. a financial-statement project whose block ranges are already identified extracts single-shot straight to the target schema. So post-processing must be **opt-in and never baked into extraction**.

And — the key shaping insight for v1 — we do not yet know the right sequence of operations for any given document. So rather than pre-declaring a pipeline, a human applies **one primitive at a time**, inspects, and decides the next. Watching which primitive sequences recur is how we discover what to automate.

## Approach: interactive, one transform at a time

A human works against extraction results step by step:

```
run extraction ─► ExtractionResult R0
   │  (inspect R0)
   ├─ pick a transform primitive + config ─► preview ─► apply ─► R1   (derived from R0)
   │  (inspect R1)
   ├─ pick another primitive + config ─────► preview ─► apply ─► R2   (derived from R1)
   │  (inspect R2) … until the records are right
   └─ export R_n  (CSV / xlsx / data store, via existing export)
```

Each primitive has one uniform contract:

```
transform(results: list[ExtractionResult], config: dict) -> ExtractionResult
```

- It takes **one or more** results (one for iterative cleanup; several for a cross-run merge) and yields **one** new result.
- The application is **non-destructive**: inputs are immutable; the output is a *new* `ExtractionResult` whose lineage records its source(s) + the transform `{type, config}`. This gives free branch/undo and a complete audit trail.
- There is **no pre-declared chain.** The "pipeline" is the emergent lineage DAG of these steps.

A project that needs no post-processing simply never applies a transform — its extraction output is the target, untouched.

### Naming convention (records a decision; applies beyond this feature)

Transforms are named for the artifact they consume and produce: **`<Artifact>Transform`**, keeping a recurring "transform" concept self-disambiguating across the IDP app.

| Contract | Name | Status |
|---|---|---|
| `ParsedDocument → ParsedDocument` | `ParsedDocumentTransform` | exists unnamed (`slice_doc`, extractor preprocess) — may be unified later |
| `ExtractionResult → ExtractionResult` | **`ExtractionResultTransform`** | this spec |

### HITL-first, then automation (explicit ordering)

v1 is **fully manual and fully configurable**: every primitive's behavior is driven by a config the human edits, previews, and applies by hand. We deliberately build **no** auto-sequencing, auto-config, or rule-learning in v1. The recorded lineages are the dataset for a later phase that (a) replays a saved sequence as an autonomous pipeline and (b) suggests configs/recipes. **HITL first, then automation.**

### Non-goals (v1)

| Deferred | v1 behavior |
|---|---|
| Sentinel/zero cleanup | Solved upstream: target fields `nullable`, prompt says "emit null when unsure". Optional `coalesce_sentinels` primitive exists as a fallback, applied by hand only if needed |
| Autonomous / pre-declared pipelines | Human applies one primitive at a time; the chain is emergent lineage, replayable later |
| Auto-learned aliases / option alphabets / recipe suggestion | Human enters them in each primitive's config; harvesting recurring sequences is a later phase |
| Fuzzy base-key matching | Exact match after configurable token-strip + alias map; misses flagged, human resolves |
| Reference data-store lookup (vendor/brand hierarchy) | Brand propagated by a `broadcast_field` primitive; gaps → human fills |
| Page-viewer click-through | Provenance captured (each row carries `sourcePage`); record→pages shown as text; viewer wiring later |
| Transforms / lineage as a first-class table | Output is a derived `ExtractionResult`; source ids + transform spec live in its metadata |

---

## Architecture

```
            ExtractionResult(s)                    one ExtractionResultTransform                 derived
            (selected by human)        ┌─────────────────────────────────────────────┐       ExtractionResult
   ┌──────────────────────────┐        │  apply_transform(results, type, config)      │       ┌──────────────┐
   │ a single result, OR      │ ─────► │  preview (no persist) → apply (persist)      │ ────► │ structured_  │
   │ price-only + spec-only   │        │  primitives: strip · derive · merge ·        │       │ data + lineage│
   └──────────────────────────┘        │              broadcast · strip_records · …   │       └──────┬───────┘
                ▲                       └─────────────────────────────────────────────┘              │
                └──────────────  human inspects, picks the next primitive  ◄───────────────────────┘
                                              (repeat until correct → export)
```

Mirrors the existing **input-side** idiom — `PipelineExtractor` applies config-driven `preprocess` steps via `apply_preprocess` ([pipeline.py](backend/app/adapters/extraction/pipeline.py)); chunking strategies come from a `build_strategy(name, config)` registry ([chunking/registry.py](backend/app/adapters/extraction/chunking/registry.py)). This is the symmetric output-side registry, but applied **one step at a time under human control** rather than folded automatically.

### Reused infrastructure

| Component | Location | Usage |
|---|---|---|
| `ExtractionResult` model | `app/models/extraction_result.py` | Input(s) and every derived output — reused as-is |
| `ExtractionOutput` / `FieldCitation` | `app/ports/data_extraction.py` | Per-field page provenance carried through transforms |
| `merge_outputs` scalar logic | `app/adapters/extraction/chunking/merge.py` | Reference for first-non-null / conflict capture |
| Chunking registry pattern | `app/adapters/extraction/chunking/registry.py` | Template for the transform registry + `config_schema` UI |
| Export (data store) | `app/services/export_mapping_service.py`, `field_mapper.py` | CSV/store export of the chosen result |
| HITL precedent | `app/services/agent/*`, `AgentRunDetailPage.tsx` | preview → apply UX |
| `ExtractionResultViewer` | `frontend/src/components/extraction/ExtractionResultViewer.tsx` | Base for the result/preview table |

---

## The Port

**File:** `app/services/extraction/transforms/base.py`

```python
class ExtractionResultTransform(ABC):
    @property
    @abstractmethod
    def transform_type(self) -> str: ...           # registry key, e.g. "merge_records"

    @abstractmethod
    def apply(
        self,
        results: list[ExtractionResult],
        config: dict[str, Any],
    ) -> ExtractionResult: ...                       # one new result, with lineage attached
```

**Registry** (`app/services/extraction/transforms/registry.py`):
- `get_transforms() -> list[dict]` — catalog: `transform_type`, name, description, `config_schema` (drives the UI config form, like `get_chunk_strategies()`).
- `build_transform(transform_type) -> ExtractionResultTransform`.

There is **no** `apply_chain` in v1 — the orchestrator is the human, applying primitives one call at a time. (A future automation phase replays a recorded lineage by calling `apply` in sequence.)

Every primitive operates on each result's `structured_data` (the rows array) and **preserves/merges provenance** (`citations` + each row's `sourcePage`).

### Primitive catalog (v1) — small, single-purpose, composable

| `transform_type` | Inputs | Job |
|---|---|---|
| `normalize_field` | 1 | Normalize a source field via a rule chain, writing the result to a new named column. The resulting `ExtractionResult` (with the added column) is the input for downstream transforms that assume pre-normalized reference fields (e.g. `merge_records groupBy`). Source field is never mutated. |
| `join_results` | 2..5 | Assemble the target record from N clean, focused single-schema extractions by joining on a shared key column. Each input result is authoritative for its own columns — no spine detection or conflict resolution needed. The composition step for the focused-extraction architecture (extract price schema → extract spec schema → join). → See [join_results spec](extraction-result-transforms-join-results.md) |
| `merge_records` | 1..N | Group rows by key field(s); collapse non-spine rows into spine rows; configurable conflict policy (the base↔variant / cross-run merge). Expects fields to already be normalized — normalization is a pre-step via `normalize_field`. |
| `strip_records` | 1 | Drop rows matching a predicate (e.g. leftover spec-only rows; null-SKU rows) |
| `dedupe_records` | 1 | Drop duplicate rows by key |
| `broadcast_field` | 1 | Fill a field across rows (e.g. `brand`) from a single value or the group's mode |
| `project_to_schema` | 1 | Keep only target-schema fields (park extras under `extended_specs` if declared) |
| `coalesce_sentinels` | 1 | *Fallback, manual only.* Map `0` / "not available…" → null |

These compose into the base↔variant collapse — but each is independently applied and inspected, which is the point.

### Key primitive: `merge_records`

Covers both worked scenarios ("collapse the no-SKU row into the SKU row" and "merge a price run with a spec run").

```json
{
  "groupBy": ["baseModel"],
  "spine": { "whereFieldsPresent": ["sku"] },
  "conflict": "prefer_spine",
  "onGroupWithoutSpine": "keep"
}
```

All field references in the config — `groupBy`, `spine.whereFieldsPresent` — are **arbitrary user-selected fields**, nothing hardcoded; `baseModel`/`sku` are merely this fixture's choices. Another project might group by `partNumber` and spine on `unitPrice`.

**Empty/absent value definition:** a field is considered absent if its value is `null`, `""`, `0`, or `"0"`. This applies to both spine detection (`whereFieldsPresent`) and fill-from-non-spine logic.

Behavior, per group:
0. A row whose every `groupBy` field is absent (by the definition above) cannot be grouped — it is output as-is with an `unjoinable` flag and excluded from all groups.
1. Output records = **spine** rows (those where all `spine.whereFieldsPresent` fields are non-absent).
2. Fill each spine row's absent fields from the group's non-spine rows; if both are non-absent and unequal, resolve by `conflict` (`prefer_spine` | `first_non_null`) and record a `conflict` flag. `prefer_spine` keeps the spine value; `first_non_null` also keeps the first non-absent value seen (which is the spine value, since it was processed first).
3. A spine row that had no non-spine rows merge into it (i.e. no records contributed additional field values to it) is flagged `not_enriched`.
4. A group with **no** spine row → keep its rows as standalone records (`keep`, flagged `no_spine`) or drop (`drop`).
5. Pool spans **all input results**, so a price-only result + a spec-only result merge exactly like one mixed result.
6. Provenance per surviving field = the source row's `{sourceResultId, sourcePage}`; updated when a field is filled from a non-spine row.

---

## Key primitive: `normalize_field`

> **Design note (emerged during Slice 1):** `strip_field_tokens` (in-place field cleanup) and `derive_field` (compute new column from another) were originally two distinct primitives. Implementation revealed they serve the same purpose: produce a normalized version of a field for downstream consumption. Merged into `normalize_field`. The rule vocabulary below is unchanged. `merge_records` no longer does any inline normalization — it takes field names as-is and expects upstream `normalize_field` steps to have already produced the reference columns it groups by.

`normalize_field` applies an ordered list of **rules** to a source field, writing the result to a **new named column** on every row. The source field is never mutated. The output is a new `ExtractionResult` with all original columns plus the new one — the starting point for any downstream transform that references that column.

### Architectural pattern

```
R_n  (extraction result with raw fields)
 │  normalize_field  outputField ← sourceField  (rule chain)
 ▼
R_n+1  all original fields preserved + new outputField column on every row
 │  merge_records  groupBy: [outputField]  (field name taken as-is; no inline normalization)
 ▼
R_n+2  collapsed records
```

Downstream transforms (`merge_records`, future `merge_results`) only reference field names. They assume the column they are told to group or join on already contains the right value. Normalization is always a separate, explicit, inspectable step before them.

### Rule vocabulary

| Rule type | Config keys | What it does |
|---|---|---|
| `trim` | `chars?: string` | Strip leading/trailing whitespace (default) or any chars in `chars`. Almost always the first rule. |
| `collapseWhitespace` | — | Collapse internal runs of whitespace (including ` `, `\t`, `\n`) to a single space. Fixes silent groupBy mismatches from multi-line extraction. |
| `lowercase` / `uppercase` / `titlecase` | — | Normalize case. Apply before any pattern-based rule so patterns match predictably. |
| `stripRegex` | `pattern: string` | Remove all substrings matching the regex. E.g. `"\\s+\\d+/\\d+/\\d+"` removes the power token from `"GP-40B 230/50/1 DD"`. |
| `stripTrailingChars` | `chars: string[]` | Remove any trailing characters that are members of `chars` (applied repeatedly until stable). E.g. `["B","D","S","C"]` collapses `"GP-40B"` → `"GP-40"`. |
| `stripPrefix` | `prefix: string` | Remove a fixed known prefix. E.g. `"Model: "` on `"Model: GP-40"` → `"GP-40"`. Simpler UX than regex for non-technical users. |
| `stripSuffix` | `suffix: string` | Remove a fixed known suffix. |
| `split` | `delimiter: string`, `index: int` | Split on `delimiter` and return the token at `index`. `split(" ", 0)` on `"GP-40B 230/50/1 DD"` → `"GP-40B"`. Friendlier than regex for token-based extraction. |
| `regexExtract` | `pattern: string`, `group?: string\|int` | Return the first match (or the named/indexed capture group) rather than removing it. E.g. `"(\\d+\\.?\\d*)"` on `"1500W"` → `"1500"`. Use when you need a sub-value, not a cleaned whole. |
| `replace` | `find: string`, `replacement: string` | Literal string substitution. Maps known noise (`"—"` → `""`, `"&amp;"` → `"&"`). Not regex. |
| `alias` | `map: Record<string,string>` | After all stripping, apply an exact-match lookup map. The designated escape hatch for cases rule-based stripping cannot safely reach. `{"UX-50L": "UX-50 LITE"}` — applied last so the key is the already-stripped value. |
| `nullifyIfIn` | `values: string[]` | If the current value (after prior rules) exactly matches any entry, set field to `null`. Sentinel cleanup at the field level: `["N/A", "-", "0", ""]`. Lighter than the whole-result `coalesce_sentinels` primitive. |

**Rule application order guidance** (the config form should nudge this):

```
trim → collapseWhitespace → lowercase/case → [stripRegex | split | regexExtract | replace | stripPrefix/Suffix | stripTrailingChars] → alias → nullifyIfIn
```

Normalize before you extract; alias last so the lookup key is already clean.

---

### Config

```json
{
  "sourceField": "modelName",
  "outputField": "baseModel",
  "rules": [
    { "type": "trim" },
    { "type": "collapseWhitespace" },
    { "type": "stripRegex", "pattern": "\\s+\\d+/\\d+/\\d+" },
    { "type": "stripTrailingChars", "chars": ["B", "D", "S", "C"] },
    { "type": "alias", "map": { "UX-50L": "UX-50 LITE" } }
  ]
}
```

- `sourceField` — the field to read. Never mutated.
- `outputField` — the new column written on every row. The preview table flags collisions with existing schema fields the human intends to keep.
- `rules` — ordered list of rule objects (each has `"type"` plus rule-specific keys). Rules execute in declaration order on the string produced by the previous rule.

Behavior: if `sourceField` is `null`, `outputField` is set to `null`.

**Why `alias` is last:** by the time `alias` runs, stripping has already produced the canonical short form. The map key is therefore the post-strip value (`"UX-50L"`, not `"UX-50L 230/50/1 DD"`).

**Why `L` is excluded from `stripTrailingChars`:** `UX-50L` is a model line (`→ UX-50 LITE`), not a variant suffix. Stripping `L` would wrongly collapse it into the bare `UX-50`. The `alias` map is the correct tool; `stripTrailingChars` handles only the option-letter suffixes (`B`, `D`, `S`, `C`) that are always variant codes, never model-line markers.

---

## Primitive: `join_results`

Joins 2–5 `ExtractionResult` inputs on a shared key column, producing a wider result whose columns are the union of all input schemas. Each input result is authoritative for its own columns — there is no spine detection, conflict policy, or row collapse. Columns are expected to be non-overlapping by design.

This is the composition primitive for the **focused-extraction architecture**: run one small, fast, accurate extraction per schema, then join. It replaces the multi-input `merge_records` cross-run use case (Slice 5) for projects that deliberately split extraction by schema rather than extracting everything in a single shot.

```json
{
  "joinKey": "series",
  "joinType": "left",
  "resultIds": ["<price_result_id>", "<spec_result_id>"]
}
```

- `joinKey` — field present in all inputs used to match rows across results.
- `joinType` — `left` (keep all rows from the first result; fill columns from others where matched) or `inner` (only rows with a match across all inputs).
- `resultIds` — 2 to 5 source result ids, ordered left-to-right (first = primary/left side).

→ Full spec: [extraction-result-transforms-join-results.md](extraction-result-transforms-join-results.md)

---

## Worked composition — Sammic GP-40 (base↔variant)

The human discovers this sequence interactively; it is not pre-declared:

```
R0  (raw extraction: mixed spec + price rows; modelName e.g. "GP-40B 230/50/1 DD")
 │ normalize_field  baseModel ← modelName  (trim, stripRegex[powerToken], stripTrailingChars[B,D,S,C], alias{UX-50L→UX-50 LITE})
 ▼
R1  every row now has baseModel ("GP-40", "GP-40", … ; "GP-40" for the spec row)
 │ merge_records  groupBy[baseModel], spine=has sku, conflict=prefer_spine, onGroupWithoutSpine=keep
 ▼
R2  4 GP-40 records (one per priced SKU), specs filled from the base spec row
 │ broadcast_field  brand ← "Sammic" (or group mode) where null
 ▼
R3  brand populated
 │ strip_records  drop rows where sku is null  (removes base spec leftovers already merged)
 │ project_to_schema  target columns only
 ▼
R4  clean per-SKU record set → export CSV
```

Why `L` is excluded from `stripTrailingLetters`: `UX-50L` is a model line (→ `UX-50 LITE`), not an option; stripping `L` would wrongly collapse it into the pricier bare `UX-50`. So it routes through the human-seeded `aliases` map instead. This option-cluster-vs-model-line split is precisely the kind of rule the interactive loop is meant to surface.

**Output grain:** one record per saleable SKU, specs inherited from base; variant-less base products kept standalone.

---

## Data Model

**No new table.** Every transform output is a derived `ExtractionResult`:
- `structured_data` = the post-transform rows,
- `extraction_method = "transform"`,
- `extraction_metadata.lineage = { "sourceResultIds": [...], "transform": { "type": "...", "config": {...} } }`.

A result with no `lineage.transform` is an original extraction. The lineage DAG (and thus the emergent "pipeline") is reconstructable by walking `sourceResultIds` backward — and is the artifact a later automation phase replays. (If "list all transformed results" becomes a hot query, promote `source_result_ids` to a nullable column — YAGNI for v1.)

---

## API

Router: `app/routers/result_transforms.py` (project-scoped; service raises, router maps to HTTP).

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/result-transforms/catalog` | Available primitives + `config_schema` (drives the config form) |
| `POST` | `/projects/{projectId}/result-transforms/preview` | `{ sourceResultIds[], transformType, config }` → run one primitive in-memory, return resulting rows + flags + provenance (no persistence) |
| `POST` | `/projects/{projectId}/result-transforms/apply` | Same body → persist the result as a derived `ExtractionResult` with lineage; returns its id |
| `GET` | `/extraction-results/{id}/lineage` | The derivation chain for a result (for the history view) |

The persisted output is an ordinary `ExtractionResult`, so existing result + export endpoints serve and export it unchanged.

---

## Frontend — Visualization & HITL

Pattern: extend the existing result viewer; shadcn/ui + Tailwind; one hook per feature.

- **Result viewer + transform action.** On any `ExtractionResult`, a `Transform ▾` menu lists the catalog. Choosing a primitive opens a config form generated from its `config_schema`.
- `TransformConfigPanel.tsx` — edit config; **Preview** calls `/preview`.
- `TransformPreviewTable.tsx` — the rich result grid:
  - **source coloring** per cell (which source result / row supplied the value),
  - **flag chips** per row (`conflict`, `unjoinable`, `no_spine`, `not_enriched`, `edited`),
  - **filter/sort by flag**,
  - **provenance popover** per cell (source page number(s) + confidence; disabled "view in page" affordance for later wiring),
  - **merge inspector** — expand a record to see the spine row + the rows merged into it (spot bad merges).
- **Apply** persists the derived result and navigates to it; the human continues from there.
- `LineagePanel.tsx` — breadcrumb/tree of the result's derivation (R0→R1→…), with each step's `{type, config}`; supports going back to branch.
- `frontend/src/api/resultTransforms.ts`, `frontend/src/hooks/useResultTransform.ts`.

---

## Acceptance Criteria

1. `ExtractionResultTransform` port + registry exist; `build_transform` resolves a primitive; `get_transforms` returns the catalog with `config_schema`.
2. Applying a primitive is **non-destructive**: inputs are unchanged; output is a new `ExtractionResult` whose `extraction_metadata.lineage` records `sourceResultIds` + `{type, config}`.
3. `preview` returns the resulting rows + flags + provenance **without** persisting; `apply` persists.
4. `normalize_field` applies a rule chain to `sourceField`, writes the result to a new `outputField` column on every row, and returns a new `ExtractionResult` with all original columns plus `outputField`. `sourceField` is never mutated. If `sourceField` is null, `outputField` is null.
5. `merge_records groupBy` references field names as-is; it performs no normalization. Pre-normalized fields produced by a prior `normalize_field` step are the expected input.
6. Rule vocabulary executes correctly in isolation and in composition (rules execute in declaration order):
   - `trim` strips leading/trailing whitespace (default) or specified `chars`.
   - `collapseWhitespace` collapses internal whitespace runs to a single space.
   - `lowercase` / `uppercase` / `titlecase` normalize case.
   - `stripRegex` removes all matches of `pattern` (e.g. `"\\s+\\d+/\\d+/\\d+"` removes the power token from `"GP-40B 230/50/1 DD"` → `"GP-40B"`).
   - `stripTrailingChars` repeatedly removes trailing chars in `chars` until stable.
   - `stripPrefix` / `stripSuffix` remove a fixed string from start/end.
   - `split` splits on `delimiter` and returns token at `index`.
   - `regexExtract` returns the first match or the named/indexed capture group.
   - `replace` substitutes `find` with `replacement` (literal, not regex).
   - `alias` applies an exact-match lookup map on the current value after prior rules.
   - `nullifyIfIn` sets the field to null if the current value is in `values`.
7. `normalize_field` on `modelName` → `baseModel` with rules `[trim, stripRegex(powerToken), stripTrailingChars([B,D,S,C]), alias({UX-50L: UX-50 LITE})]` produces correct base keys: `"GP-40B 230/50/1 DD"` → `"GP-40"`, `"UX-50L 230/50/1"` → `"UX-50 LITE"` (never `"UX-50"`).
8. `merge_records` groups by key, collapses non-spine rows into spine rows (`whereFieldsPresent: ["sku"]`), resolves conflicts by policy (`prefer_spine` | `first_non_null`), and keeps/drops spine-less groups per config — across one **or multiple** input results identically. Rows with no non-absent `groupBy` values are flagged `unjoinable` and passed through ungrouped. Spine rows that had no non-spine rows contribute additional field values to them are flagged `not_enriched`.
9. `broadcast_field` fills `brand` where null.
10. `strip_records` / `project_to_schema` drop rows by predicate / restrict to target columns.
11. Provenance `{sourceResultId, sourcePage}` is preserved through every primitive; a record exposes the union of its fields' pages.
12. Applying the worked sequence (normalize_field → merge_records → broadcast_field → strip_records → project_to_schema) to the Sammic CSV fixture yields one record per saleable SKU with inherited specs (GP-40 → 4 records); Electrolux co-located rows pass through needing only a trivial sequence.
13. A result's `/lineage` reconstructs its derivation chain; the UI shows the history and lets the user branch.
14. UI: view a result → pick a primitive → edit config (from `config_schema`) → preview (with source coloring, flag filter, provenance popover, merge inspector) → apply → land on the new result.

## Delivery — Vertical Slices (one primitive per slice, each end-to-end)

Each slice ships backend + frontend + tests and is independently demoable. Slice 1 carries the shared rails (port, registry, `apply`/`preview`/`catalog` API, the result-viewer transform action + preview table, lineage metadata); later slices are thin increments that add one primitive + its config form + tests.

- **Slice 1 — Merge a single-shot result to one record per selected identity field** (`merge_records`, incl. shared rails). The current concrete problem: a master-schema extraction whose base rows must collapse into the identity-bearing rows. The group key and the spine/identity field(s) are **user-selected config** (this fixture uses model as the group key and `sku` as the identity field, but both are selectable). `merge_records groupBy` takes field names as-is — it assumes any normalization has already been applied by an upstream `normalize_field` step. Spine = rows where the selected identity field is present, `conflict: prefer_spine`. **Acceptance:** the GP-40 / GP-35 / GP-50 / AX-40 families in `price list_2f0e0d93.csv` each collapse to one record per priced SKU with inherited specs (using a pre-normalized groupBy field); Electrolux co-located rows pass through. (The `normalize_field` step that produces the groupBy key is Slice 2.)
- **Slice 2 — Normalize a field to a new column** (`normalize_field`): a composable rule chain (`trim`, `collapseWhitespace`, `lowercase`/`uppercase`/`titlecase`, `stripRegex`, `stripTrailingChars`, `stripPrefix`, `stripSuffix`, `split`, `regexExtract`, `replace`, `alias`, `nullifyIfIn`) applied to a `sourceField`, written to a new `outputField` column. Source is never mutated. The output `ExtractionResult` (with the new column) feeds downstream transforms that assume pre-normalized reference fields. **Acceptance:** `normalize_field` on `modelName` → `baseModel` with stripRegex (power token) + stripTrailingChars `[B,D,S,C]` + alias `{UX-50L → UX-50 LITE}` produces the correct base keys; `UX-50L` is never collapsed to `UX-50`; all rules execute correctly in isolation and in composition; `sourceField: null` → `outputField: null`; config form driven by `config_schema`. → **[Slice 2 spec](extraction-result-transforms-slice2-normalize-field.md)**
- **Slice 3 — Broadcast a field** (`broadcast_field`): propagate `brand`/vendor where null (e.g. spec-only standalone rows).
- **Slice 4 — Prune to target shape** (`strip_records`, `project_to_schema`): drop merged-away rows; restrict to target columns; export the result via the existing path.
- **Slice 5 — Join focused single-schema extractions** (`join_results`): assemble the target record from N clean, single-schema extraction results joined on a shared key column. Replaces the multi-input `merge_records` cross-run approach — see [extraction-result-transforms-join-results.md](extraction-result-transforms-join-results.md) for the full spec.
- **Slice 6 — Lineage & rich viz polish:** full lineage panel + branch; source coloring, merge inspector, provenance popover.
- **Future (not v1):** record/replay a lineage as an autonomous pipeline; recipe + config suggestion. HITL first, then automation.

**Fixtures, not design inputs:** Electrolux (co-located → trivial pass-through) and Sammic / `price list_2f0e0d93.csv` (split → base↔variant via the primitive sequence, incl. the `UX-50L` alias and unmatched paths) validate the primitives as reference cases.
