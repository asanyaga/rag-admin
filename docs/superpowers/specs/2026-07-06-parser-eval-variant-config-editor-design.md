# Parser Eval — Variant Config Editor (Design)

**Date:** 2026-07-06
**Status:** Draft for review
**Author:** brainstorming session (asanyaga)
**Depends on:** parser-eval frontend (merged PR #146) · canonical model `docs/architecture/eval-entity-model.md`

## Problem

The New Run dialog can only compare **adapters at their default config** — it renders adapter
checkboxes and sends `variants: adapters.map(a => ({ adapter: a, config: {} }))`. That leaves the
core capability of the `(adapter, config)` variant model unusable: you cannot compare the **same
adapter under different configs** (the motivating example — `custom_pipeline` with pdfplumber vs. with
fitz). This spec adds a config editor by turning the adapter section into a **variant list**.

## Scope

**Frontend-only.** The backend already accepts arbitrary `config`, derives `variant_key` from
`(adapter, config)`, and enforces `unique(run, eval_case, variant_key)`; it validates only the adapter
name against `ParserKind`. So the parse configs the UI emits must match what the parse pipeline expects
— which is guaranteed by reusing the **same** config components the parse flow uses.

In scope:
- Replace the adapter checkboxes in `NewRunDialog` with an ordered **variant list** (`(adapter, config)`
  rows); the same adapter may appear multiple times with different configs.
- Reuse `ParseMethodSelector` (adapter dropdown + per-adapter structured config editor) per row.
- Client-side **duplicate-variant guard** so identical `(adapter, config)` rows can't reach the backend.

Out of scope (non-goals): per-variant names/labels, row reordering, config presets/templates, backend
config-schema validation, applying configs outside runs, and all previously deferred parser-eval seams
(datasets UI, bootstrap, verification, extra dimensions).

## Reused building blocks

- **`ParseMethodSelector`** (`components/documents/ParseMethodSelector.tsx`, exported) — props
  `{ parserType, config, onParserTypeChange, onConfigChange, disabled?, compact? }`. Renders the
  adapter `Select` + the matching config sub-form (`LlamaParseConfig` / `LandingAIConfig` /
  `CustomPipelineConfig`); `simple`/`docling` have no sub-form. On adapter change it already resets the
  row's config to that adapter's `defaultConfig` (`PARSER_REGISTRY[type].defaultConfig`).
- **`ParseConfig`** type from `@/types/parsing`.
- **`PARSER_REGISTRY`** — labels + `defaultConfig` per adapter.

## Component changes (`components/parser-eval/NewRunDialog.tsx`)

State: replace `adapters: string[]` with

```ts
type Variant = { adapter: string; config: ParseConfig }
const [variants, setVariants] = useState<Variant[]>([])
```

UI — replace the adapter checkbox block with a **Variants** section:
- One row per variant: `ParseMethodSelector` (`compact`) bound to `variants[i]` via
  `onParserTypeChange`/`onConfigChange` that update element `i`, plus a **Remove** button.
- **Add variant** button appends `{ adapter: 'docling', config: {} }`.
- Submit sends `variants` directly (already `{ adapter, config }[]`).

The Cases multi-select, Name field, and dialog scaffolding are unchanged.

### Row wiring

```ts
const setVariant = (i: number, patch: Partial<Variant>) =>
  setVariants((vs) => vs.map((v, idx) => (idx === i ? { ...v, ...patch } : v)))

// per row i:
<ParseMethodSelector
  compact
  parserType={variants[i].adapter}
  config={variants[i].config}
  onParserTypeChange={(adapter) => setVariant(i, { adapter })}
  onConfigChange={(config) => setVariant(i, { config })}
/>
```

> Note: `ParseMethodSelector.handleParserChange` calls both `onParserTypeChange` and `onConfigChange`
> (resetting config to the new adapter's default), so changing a row's adapter also resets its config —
> desired behavior. The two `setVariant` calls collapse into one updated row.

## Duplicate-variant guard

Two rows with identical `(adapter, config)` yield the same `variant_key`; the backend's
`unique(run, eval_case, variant_key)` would reject the second `insert_result` mid-run and fail the whole
run. Prevent it in the UI with a canonical per-row key:

```ts
const variantKey = (v: Variant) => `${v.adapter}|${stableStringify(v.config)}`
```

- `stableStringify` is a small helper that serializes an object with keys sorted **at every level**
  (recursively), so two configs that differ only in key order are equal. `custom_pipeline` configs nest
  (`tools: [...]`), so top-level-only sorting (e.g. `JSON.stringify`'s replacer-array form) is
  insufficient — the recursive helper is required.
- Equality only — this does **not** need to reproduce the backend's sha256 `variant_key`; it just
  detects duplicate rows.
- If any two rows share a key, mark them and **disable Run**, showing an inline warning naming the
  duplicated adapter (e.g. "Duplicate variant: custom_pipeline appears twice with the same config —
  change or remove one").

## Validation & gating

Run is enabled when **all** hold: ≥1 case selected, ≥1 variant, and no duplicate variants. Name stays
optional. The existing disabled-reason hint is extended:
- no case / no variant → "Select at least one case and add at least one variant to run."
- duplicate present → the duplicate warning above.

## Acceptance criteria

1. The New Run dialog shows a **Variants** list with an **Add variant** button; each row lets you pick an
   adapter and edit its config via the existing per-adapter config components.
2. Adding two rows with the **same adapter** but **different configs** produces two variants; the run's
   comparison table shows both as distinct rows (distinct `variant_key`).
3. `simple`/`docling` rows show no config sub-form; `llamaparse`/`landing_ai`/`custom_pipeline` show
   theirs, prefilled from `defaultConfig`.
4. Two identical `(adapter, config)` rows disable Run and show a duplicate warning; no failed run reaches
   the backend from the UI.
5. Run requires ≥1 case and ≥1 (non-duplicate) variant.
6. `npm run lint`, `npm run build`, and `npx vitest run` pass.

## Testing (`NewRunDialog.test.tsx`, updated)

- Add a variant → its default adapter (`docling`) appears; selecting a case → Run enables.
- Add a second **identical** variant → Run disables + duplicate warning shows; changing that row's
  adapter re-enables Run.
- Submit builds `variants: [{ adapter, config }, …]` from the rows (assert the payload shape).
- Per-adapter config components remain covered by their own existing tests; this suite mocks
  `useParserEvalCases`/`useSourceDocuments` as today.

## Deferred / open

- Backend config-schema validation (backend still trusts the config shape — same as the parse flow).
- Variant naming, reordering, presets — non-goals.
