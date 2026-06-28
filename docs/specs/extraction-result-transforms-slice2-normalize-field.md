# Extraction Result Transforms — Slice 2: `normalize_field`

**Parent spec:** [extraction-result-transform-pipeline.md](extraction-result-transform-pipeline.md)
**Status:** Ready for implementation
**Date:** 2026-06-28
**Scope:** Add the `normalize_field` transform primitive — a composable rule chain that reads a source field, applies ordered normalization rules, and writes the result to a new output column. Produces a derived `ExtractionResult` with all original columns plus the new one. The primary consumer is a downstream `merge_records` step that expects a pre-normalized group key.

---

## Context

Slice 1 shipped `merge_records` and the shared rails (port, registry, preview/apply API, viewer transform action). `merge_records groupBy` takes field names as-is and assumes any normalization has already been applied upstream. `normalize_field` is that upstream step — it produces the pre-normalized reference column that `merge_records` groups by.

---

## The `normalize_field` Primitive

`normalize_field` applies an ordered list of **rules** to a source field, writing the result to a **new named column** on every row. The source field is never mutated. The output is a new `ExtractionResult` with all original columns plus the new one.

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

Downstream transforms (`merge_records`) only reference field names. They assume the column they are told to group or join on already contains the right value.

### Config

```json
{
  "fields": [
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
    },
    {
      "sourceField": "price",
      "outputField": "normalizedPrice",
      "rules": [
        { "type": "trim" },
        { "type": "stripPrefix", "prefix": "$" }
      ]
    }
  ]
}
```

- `fields` — ordered list of field normalization configs. All field normalizations execute within a single `apply()` call and produce one `ExtractionResult`. Fields execute in declaration order; a later field can reference an `outputField` written by an earlier field as its own `sourceField`.
- Per field entry:
  - `sourceField` — the field to read. Never mutated.
  - `outputField` — the new column written on every row. A collision with an existing field name is flagged in the preview table (the user is warned, but the write proceeds).
  - `rules` — ordered list of rule objects (each has `"type"` plus rule-specific keys). Rules execute in declaration order on the string produced by the previous rule.

**Null behavior:** if `sourceField` is `null` (value is `None`) on a row, `outputField` is set to `null` on that row. Null does not propagate across field entries — only within a single field's rule chain.

### Rule vocabulary

| Rule type | Config keys | What it does |
|---|---|---|
| `trim` | `chars?: string` | Strip leading/trailing whitespace (default) or any chars in `chars`. Almost always the first rule. |
| `collapseWhitespace` | — | Collapse internal runs of whitespace (including ` `, `\t`, `\n`) to a single space. Fixes silent groupBy mismatches from multi-line extraction. |
| `lowercase` / `uppercase` / `titlecase` | — | Normalize case. Apply before any pattern-based rule so patterns match predictably. |
| `stripRegex` | `pattern: string` | Remove all substrings matching the regex. E.g. `"\\s+\\d+/\\d+/\\d+"` removes the power token from `"GP-40B 230/50/1 DD"`. |
| `stripTrailingChars` | `chars: string[]` | Remove any trailing characters that are members of `chars` (applied repeatedly until stable). E.g. `["B","D","S","C"]` collapses `"GP-40B"` → `"GP-40"`. |
| `stripPrefix` | `prefix: string` | Remove a fixed known prefix. E.g. `"Model: "` on `"Model: GP-40"` → `"GP-40"`. Simpler UX than regex for non-technical users. |
| `stripSuffix` | `suffix: string` | Remove a fixed known suffix. |
| `split` | `delimiter: string`, `index: int` | Split on `delimiter` and return the token at `index`. `split(" ", 0)` on `"GP-40B 230/50/1 DD"` → `"GP-40B"`. Friendlier than regex for token-based extraction. |
| `regexExtract` | `pattern: string`, `group?: string\|int` | Return the first match (or the named/indexed capture group) rather than removing it. E.g. `"(\\d+\\.?\\d*)"` on `"1500W"` → `"1500"`. Use when you need a sub-value, not a cleaned whole. |
| `replace` | `find: string`, `replacement: string` | Literal string substitution. Maps known noise (`"—"` → `""`, `"&amp;"` → `"&"`). Not regex. |
| `alias` | `map: Record<string,string>` | After all stripping, apply an exact-match lookup map. The designated escape hatch for cases rule-based stripping cannot safely reach. `{"UX-50L": "UX-50 LITE"}` — applied last so the key is the already-stripped value. |
| `nullifyIfIn` | `values: string[]` | If the current value (after prior rules) exactly matches any entry, set field to `null`. Sentinel cleanup at the field level: `["N/A", "-", "0", ""]`. |

**Rule application order guidance** (the config form should nudge this):

```
trim → collapseWhitespace → lowercase/case → [stripRegex | split | regexExtract | replace | stripPrefix/Suffix | stripTrailingChars] → alias → nullifyIfIn
```

Normalize before you extract; alias last so the lookup key is already clean.

---

## Key design constraint: why `alias` is last

By the time `alias` runs, stripping has already produced the canonical short form. The map key is therefore the post-strip value (`"UX-50L"`, not `"UX-50L 230/50/1 DD"`).

**Why `L` is excluded from `stripTrailingChars`:** `UX-50L` is a model line (`→ UX-50 LITE`), not a variant suffix. Stripping `L` would wrongly collapse it into the bare `UX-50`. The `alias` map is the correct tool; `stripTrailingChars` handles only the option-letter suffixes (`B`, `D`, `S`, `C`) that are always variant codes, never model-line markers.

---

## Worked example — Sammic GP-40 (normalize_field step)

Input: raw extraction result R0 where `modelName` = `"GP-40B 230/50/1 DD"`, `"UX-50L 230/50/1"`, etc.

Config:
```json
{
  "fields": [
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
  ]
}
```

Expected outputs:

| modelName (source, unchanged) | baseModel (new column) |
|---|---|
| `"GP-40 230/50/1"` | `"GP-40"` |
| `"GP-40B 230/50/1"` | `"GP-40"` |
| `"GP-40 230/50/1 DD"` | `"GP-40"` |
| `"GP-40B 230/50/1 DD"` | `"GP-40"` |
| `"UX-50L 230/50/1"` | `"UX-50 LITE"` (never `"UX-50"`) |
| `null` | `null` |

The resulting R1 (all original columns + `baseModel`) is the direct input to `merge_records groupBy: ["baseModel"]`.

---

## Frontend

- **Config form:** `NormalizeFieldConfigForm.tsx` — a list of field entries, each with text inputs for `sourceField` and `outputField` and a dynamic rule list; add/remove buttons per field and per rule. At least one field entry is always present.
- **Transform action:** The existing `Transform` button in `ExtractionResultViewer` must be extended to let the user pick between `normalize_field` and `merge_records` (and future primitives), showing the appropriate config form.
- **`config_schema`:** The registry entry for `normalize_field` must include a `config_schema` JSON Schema object that the UI could use for generic form generation.

---

## Acceptance Criteria

1. `normalize_field` primitive exists in the registry (`get_transforms()` returns it; `build_transform("normalize_field")` resolves it).
2. Applying `normalize_field` produces a new `ExtractionResult`; the source result is unchanged.
3. All original columns from the source rows are preserved in the output rows.
4. `sourceField` is never mutated; `outputField` is always present on every output row.
5. If `sourceField` is `null` on a row, `outputField` is `null` on that row.
6. All rule types execute correctly in isolation:
   - `trim` strips leading/trailing whitespace (default) or specified `chars`.
   - `collapseWhitespace` collapses internal whitespace runs to a single space.
   - `lowercase` / `uppercase` / `titlecase` normalize case.
   - `stripRegex` removes all matches of `pattern`.
   - `stripTrailingChars` repeatedly removes trailing chars in `chars` until stable.
   - `stripPrefix` / `stripSuffix` remove a fixed string from start/end.
   - `split` splits on `delimiter` and returns token at `index`.
   - `regexExtract` returns the first match or the named/indexed capture group.
   - `replace` substitutes `find` with `replacement` (literal, not regex).
   - `alias` applies an exact-match lookup map on the current value.
   - `nullifyIfIn` sets the field to `null` if the current value is in `values`.
7. Rules execute in declaration order and compose correctly:
   - `"GP-40B 230/50/1 DD"` with `[trim, collapseWhitespace, stripRegex(powerToken), stripTrailingChars([B,D,S,C])]` → `"GP-40"`.
   - `"UX-50L 230/50/1"` with the above rules + `alias({UX-50L: UX-50 LITE})` → `"UX-50 LITE"` (never `"UX-50"`).
8. `null` propagates: a `null` value at any point in the rule chain causes subsequent rules to be skipped, and `outputField` is `null`.
9. The registry entry includes a `config_schema` JSON Schema object (type `object`).
10. The frontend `NormalizeFieldConfigForm` renders a list of field entries, each with `sourceField`, `outputField`, and a dynamic rule list; add/remove buttons operate at both field and rule level; the `Transform` dialog supports selecting between `normalize_field` and `merge_records`.
11. A single `normalize_field` apply call with N field entries produces exactly one `ExtractionResult` containing all N new output columns.
