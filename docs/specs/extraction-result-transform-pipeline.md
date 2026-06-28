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
| `strip_field_tokens` | 1 | Remove regex matches from a field (e.g. strip `\d+/\d+/\d+` from `modelName`); write in place or to a new field |
| `derive_field` | 1 | Compute a field from another via rules (e.g. `baseModel` from `modelName`: strip power token, strip trailing option letters, apply aliases) |
| `merge_records` | 1..N | Group rows by key field(s); collapse non-spine rows into spine rows; configurable conflict policy (the base↔variant / cross-run merge) |
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
  "collapseInto": "spine",
  "conflict": "prefer_spine",
  "onGroupWithoutSpine": "keep"
}
```

All field references in the config — `groupBy`, `spine.whereFieldsPresent` — are **arbitrary user-selected fields**, nothing hardcoded; `baseModel`/`sku` are merely this fixture's choices. Another project might group by `partNumber` and spine on `unitPrice`.

Behavior, per group:
1. Output records = **spine** rows (those with `spine.whereFieldsPresent` non-null — the selected identity field(s), e.g. `sku` here).
2. Fill each spine row's null fields from the group's non-spine rows; if both non-null and unequal, resolve by `conflict` (`prefer_spine` | `first_non_null` | `prefer_enrichment`) and record a `conflict` flag.
3. A group with **no** spine row → keep its rows as standalone records (`keep`) or drop (`drop`).
4. Pool spans **all input results**, so a price-only result + a spec-only result merge exactly like one mixed result.
5. Provenance per surviving field = the source row's `{sourceResultId, sourcePage}`.

---

## Worked composition — Sammic GP-40 (base↔variant)

The human discovers this sequence interactively; it is not pre-declared:

```
R0  (raw extraction: mixed spec + price rows; modelName e.g. "GP-40B 230/50/1 DD")
 │ derive_field  baseModel ← modelName  (stripPowerToken, stripTrailingLetters[B,D,S,C], aliases{UX-50L→UX-50 LITE})
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
  - **flag chips** per row (`conflict`, `unjoinable`, `no_specs`, `edited`),
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
4. `strip_field_tokens` removes a regex (e.g. `\d+/\d+/\d+`) from a field.
5. `derive_field` produces `baseModel` via stripPowerToken + stripTrailingLetters + aliases; `UX-50L → UX-50 LITE` (never bare `UX-50`).
6. `merge_records` groups by key, collapses non-spine rows into spine rows (`whereFieldsPresent: ["sku"]`), resolves conflicts by policy (`prefer_spine`), and keeps/drops spine-less groups per config — across one **or multiple** input results identically.
7. `broadcast_field` fills `brand` where null.
8. `strip_records` / `project_to_schema` drop rows by predicate / restrict to target columns.
9. Provenance `{sourceResultId, sourcePage}` is preserved through every primitive; a record exposes the union of its fields' pages.
10. Applying the worked sequence (derive → merge → broadcast → strip_records → project) to the Sammic CSV fixture yields one record per saleable SKU with inherited specs (GP-40 → 4 records); Electrolux co-located rows pass through needing only a trivial sequence.
11. A result's `/lineage` reconstructs its derivation chain; the UI shows the history and lets the user branch.
12. UI: view a result → pick a primitive → edit config (from `config_schema`) → preview (with source coloring, flag filter, provenance popover, merge inspector) → apply → land on the new result.

## Delivery — Vertical Slices (one primitive per slice, each end-to-end)

Each slice ships backend + frontend + tests and is independently demoable. Slice 1 carries the shared rails (port, registry, `apply`/`preview`/`catalog` API, the result-viewer transform action + preview table, lineage metadata); later slices are thin increments that add one primitive + its config form + tests.

- **Slice 1 — Merge a single-shot result to one record per selected identity field** (`merge_records`, incl. shared rails). The current concrete problem: a master-schema extraction whose base rows must collapse into the identity-bearing rows. The group key and the spine/identity field(s) are **user-selected config** (this fixture uses model as the group key and `sku` as the identity field, but both are selectable). `merge_records` groups by a normalized key (`groupBy` accepts inline normalization — trim/casefold/regex strip of power token + option letters `{B,D,S,C}`), spine = rows where the selected identity field is present, `conflict: prefer_spine`. **Acceptance:** the GP-40 / GP-35 / GP-50 / AX-40 families in `price list_2f0e0d93.csv` each collapse to one record per priced SKU with inherited specs; Electrolux co-located rows pass through. (Model-line alias cases like `UX-50L → UX-50 LITE` are explicitly Slice 2.)
- **Slice 2 — Derive / strip a field** (`derive_field`, `strip_field_tokens`): explicit, inspectable derived key columns + alias maps for cases inline normalization can't reach (`UX-50L → UX-50 LITE`).
- **Slice 3 — Broadcast a field** (`broadcast_field`): propagate `brand`/vendor where null (e.g. spec-only standalone rows).
- **Slice 4 — Prune to target shape** (`strip_records`, `project_to_schema`): drop merged-away rows; restrict to target columns; export the result via the existing path.
- **Slice 5 — Cross-run merge** (multi-select inputs): merge a price-only result with a spec-only result — `merge_records` over N inputs plus the multi-select UX.
- **Slice 6 — Lineage & rich viz polish:** full lineage panel + branch; source coloring, merge inspector, provenance popover.
- **Future (not v1):** record/replay a lineage as an autonomous pipeline; recipe + config suggestion. HITL first, then automation.

**Fixtures, not design inputs:** Electrolux (co-located → trivial pass-through) and Sammic / `price list_2f0e0d93.csv` (split → base↔variant via the primitive sequence, incl. the `UX-50L` alias and unmatched paths) validate the primitives as reference cases.
