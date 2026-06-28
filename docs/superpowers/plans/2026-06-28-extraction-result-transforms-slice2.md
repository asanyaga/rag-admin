# Extraction Result Transforms — Slice 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the `normalize_field` transform end-to-end — a composable rule chain that reads a source field, applies normalization rules in order, and writes the result to a new output column — plus the frontend config form and transform-type selector in the viewer.

**Architecture:** A pure-function `NormalizeField` class under `app/services/extraction/transforms/` with a `_apply_rules` helper (stateless, no I/O); the existing registry, service, router, and API are untouched except to register the new primitive. The frontend extends the existing `Transform` dialog with a type selector and a new `NormalizeFieldConfigForm`. GitHub issue: #[TBD — create before starting].

**Tech Stack:** Python 3.12, pytest; React 18, TypeScript, Vite, shadcn/ui, Tailwind, vitest.

## Global Constraints

- Backend tests: `uv run --directory backend python -m pytest -o "addopts=" <path>`
- Frontend lint/build/test: `npm run lint`, `npm run build`, `npx vitest run` (from `frontend/`)
- No `cd X && Y` compound commands; use absolute paths or tool working-dir flags.
- Primitives are **pure** (no DB, no I/O) and **non-destructive**: `sourceField` is never mutated; output rows are new dicts.
- `normalize_field` takes exactly **one** input (`TransformInput`).
- Rules execute in declaration order; a `null` value causes remaining rules to be skipped and `outputField` is set to `null`.
- Spec: `docs/specs/extraction-result-transforms-slice2-normalize-field.md`

---

### Task 1: `normalize_field` primitive

**Files:**
- Create: `backend/app/services/extraction/transforms/normalize_field.py`
- Test: `backend/tests/services/extraction/transforms/test_normalize_field.py`

**Interfaces:**
- Produces:
  - `_apply_rules(value: str | None, rules: list[dict]) -> str | None` — internal helper, exported for direct testing.
  - `class NormalizeField` with `transform_type = "normalize_field"` and `apply(inputs: list[TransformInput], config: dict) -> TransformResult`. Config keys: `sourceField: str`, `outputField: str`, `rules: list[dict]`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/services/extraction/transforms/test_normalize_field.py
import pytest
from app.services.extraction.transforms.base import TransformInput
from app.services.extraction.transforms.normalize_field import NormalizeField, _apply_rules


# ── Rule isolation tests ──────────────────────────────────────────────────────

def test_trim_default():
    assert _apply_rules("  hello  ", [{"type": "trim"}]) == "hello"


def test_trim_custom_chars():
    assert _apply_rules("***hello***", [{"type": "trim", "chars": "*"}]) == "hello"


def test_collapse_whitespace():
    assert _apply_rules("a  b\t\nc", [{"type": "collapseWhitespace"}]) == "a b c"


def test_lowercase():
    assert _apply_rules("GP-40B", [{"type": "lowercase"}]) == "gp-40b"


def test_uppercase():
    assert _apply_rules("gp-40b", [{"type": "uppercase"}]) == "GP-40B"


def test_titlecase():
    assert _apply_rules("gp-40b model", [{"type": "titlecase"}]) == "Gp-40B Model"


def test_strip_regex():
    assert _apply_rules("GP-40B 230/50/1 DD", [{"type": "stripRegex", "pattern": r"\s+\d+/\d+/\d+.*"}]) == "GP-40B"


def test_strip_regex_only_power_token():
    # Matches only the power token pattern, not the DD suffix
    assert _apply_rules("GP-40B 230/50/1 DD", [{"type": "stripRegex", "pattern": r"\s+\d+/\d+/\d+"}]) == "GP-40B DD"


def test_strip_trailing_chars_single():
    assert _apply_rules("GP-40B", [{"type": "stripTrailingChars", "chars": ["B", "D", "S", "C"]}]) == "GP-40"


def test_strip_trailing_chars_multiple_stacked():
    assert _apply_rules("GP-40BC", [{"type": "stripTrailingChars", "chars": ["B", "D", "S", "C"]}]) == "GP-40"


def test_strip_trailing_chars_preserves_non_option_letter_l():
    # 'L' is not in the strip set — UX-50L must not collapse
    assert _apply_rules("UX-50L", [{"type": "stripTrailingChars", "chars": ["B", "D", "S", "C"]}]) == "UX-50L"


def test_strip_prefix():
    assert _apply_rules("Model: GP-40", [{"type": "stripPrefix", "prefix": "Model: "}]) == "GP-40"


def test_strip_suffix():
    assert _apply_rules("GP-40 Unit", [{"type": "stripSuffix", "suffix": " Unit"}]) == "GP-40"


def test_split_first_token():
    assert _apply_rules("GP-40B 230/50/1 DD", [{"type": "split", "delimiter": " ", "index": 0}]) == "GP-40B"


def test_split_second_token():
    assert _apply_rules("GP-40B 230/50/1 DD", [{"type": "split", "delimiter": " ", "index": 1}]) == "230/50/1"


def test_regex_extract_group():
    assert _apply_rules("1500W model", [{"type": "regexExtract", "pattern": r"(\d+\.?\d*)", "group": 1}]) == "1500"


def test_regex_extract_no_match_returns_original():
    assert _apply_rules("no-digits", [{"type": "regexExtract", "pattern": r"\d+"}]) == "no-digits"


def test_replace_literal():
    assert _apply_rules("N—A", [{"type": "replace", "find": "—", "replacement": ""}]) == "NA"


def test_alias_match():
    assert _apply_rules("UX-50L", [{"type": "alias", "map": {"UX-50L": "UX-50 LITE"}}]) == "UX-50 LITE"


def test_alias_no_match_passthrough():
    assert _apply_rules("UX-60", [{"type": "alias", "map": {"UX-50L": "UX-50 LITE"}}]) == "UX-60"


def test_nullify_if_in_match():
    assert _apply_rules("N/A", [{"type": "nullifyIfIn", "values": ["N/A", "-", ""]}]) is None


def test_nullify_if_in_no_match():
    assert _apply_rules("GP-40", [{"type": "nullifyIfIn", "values": ["N/A"]}]) == "GP-40"


def test_unknown_rule_type_raises():
    with pytest.raises(ValueError, match="Unknown rule type"):
        _apply_rules("x", [{"type": "bogus"}])


# ── Composition tests ─────────────────────────────────────────────────────────

def test_sammic_gp40_variants_to_base():
    rules = [
        {"type": "trim"},
        {"type": "collapseWhitespace"},
        {"type": "stripRegex", "pattern": r"\s+\d+/\d+/\d+"},
        {"type": "stripTrailingChars", "chars": ["B", "D", "S", "C"]},
    ]
    assert _apply_rules("GP-40 230/50/1", rules) == "GP-40"
    assert _apply_rules("GP-40B 230/50/1", rules) == "GP-40"
    assert _apply_rules("GP-40 230/50/1 DD", rules) == "GP-40"
    assert _apply_rules("GP-40B 230/50/1 DD", rules) == "GP-40"


def test_ux50l_alias_never_collapses_to_bare_ux50():
    rules = [
        {"type": "trim"},
        {"type": "collapseWhitespace"},
        {"type": "stripRegex", "pattern": r"\s+\d+/\d+/\d+"},
        {"type": "stripTrailingChars", "chars": ["B", "D", "S", "C"]},
        {"type": "alias", "map": {"UX-50L": "UX-50 LITE"}},
    ]
    assert _apply_rules("UX-50L 230/50/1", rules) == "UX-50 LITE"
    assert _apply_rules("UX-50L", rules) == "UX-50 LITE"


def test_null_propagates_through_rule_chain():
    assert _apply_rules(None, [{"type": "trim"}, {"type": "lowercase"}]) is None


def test_nullify_mid_chain_stops_further_processing():
    # nullifyIfIn sets to None; subsequent rules must be skipped (no AttributeError)
    rules = [
        {"type": "nullifyIfIn", "values": ["N/A"]},
        {"type": "lowercase"},
    ]
    assert _apply_rules("N/A", rules) is None


# ── NormalizeField primitive ──────────────────────────────────────────────────

_RULES = [
    {"type": "trim"},
    {"type": "collapseWhitespace"},
    {"type": "stripRegex", "pattern": r"\s+\d+/\d+/\d+"},
    {"type": "stripTrailingChars", "chars": ["B", "D", "S", "C"]},
    {"type": "alias", "map": {"UX-50L": "UX-50 LITE"}},
]
_CFG = {"sourceField": "modelName", "outputField": "baseModel", "rules": _RULES}
_ROWS = [
    {"modelName": "GP-40 230/50/1", "sku": "1303050", "sourcePage": "Page 7"},
    {"modelName": "GP-40B 230/50/1 DD", "sku": "1303056", "sourcePage": "Page 7"},
    {"modelName": "UX-50L 230/50/1", "sku": "1406010", "sourcePage": "Page 8"},
    {"modelName": None, "sku": None, "sourcePage": "Page 9"},
]


def test_output_field_present_on_every_row():
    out = NormalizeField().apply([TransformInput(rows=_ROWS, source_result_id="r1")], _CFG)
    assert all("baseModel" in r for r in out.rows)


def test_source_field_not_mutated():
    out = NormalizeField().apply([TransformInput(rows=_ROWS, source_result_id="r1")], _CFG)
    for i, row in enumerate(out.rows):
        assert row["modelName"] == _ROWS[i]["modelName"]


def test_all_original_columns_preserved():
    out = NormalizeField().apply([TransformInput(rows=_ROWS, source_result_id="r1")], _CFG)
    for orig, new in zip(_ROWS, out.rows):
        for key in orig:
            assert key in new


def test_null_source_yields_null_output():
    out = NormalizeField().apply([TransformInput(rows=_ROWS, source_result_id="r1")], _CFG)
    null_row = next(r for r in out.rows if r["modelName"] is None)
    assert null_row["baseModel"] is None


def test_gp40_variant_produces_correct_base_key():
    out = NormalizeField().apply([TransformInput(rows=_ROWS, source_result_id="r1")], _CFG)
    row = next(r for r in out.rows if r.get("sku") == "1303056")
    assert row["baseModel"] == "GP-40"


def test_ux50l_maps_to_lite_not_bare_ux50():
    out = NormalizeField().apply([TransformInput(rows=_ROWS, source_result_id="r1")], _CFG)
    row = next(r for r in out.rows if r.get("sku") == "1406010")
    assert row["baseModel"] == "UX-50 LITE"
    assert row["baseModel"] != "UX-50"


def test_row_count_unchanged():
    out = NormalizeField().apply([TransformInput(rows=_ROWS, source_result_id="r1")], _CFG)
    assert len(out.rows) == len(_ROWS)


def test_no_flags_emitted():
    out = NormalizeField().apply([TransformInput(rows=_ROWS, source_result_id="r1")], _CFG)
    assert out.flags == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory backend python -m pytest -o "addopts=" tests/services/extraction/transforms/test_normalize_field.py -v`
Expected: FAIL — `ModuleNotFoundError: app.services.extraction.transforms.normalize_field`

- [ ] **Step 3: Write the implementation**

```python
# backend/app/services/extraction/transforms/normalize_field.py
"""normalize_field: apply a rule chain to a source field, write result to a new output column.

Source field is never mutated. If source value is null, output is null.
Rules execute in declaration order; null propagates (remaining rules skipped).
"""
from __future__ import annotations

import re
from typing import Any

from app.services.extraction.transforms.base import TransformInput, TransformResult

_META = "_provenance"


def _apply_rule(value: str, rule: dict) -> str | None:
    t = rule["type"]
    if t == "trim":
        chars = rule.get("chars")
        return value.strip(chars) if chars else value.strip()
    if t == "collapseWhitespace":
        return re.sub(r"\s+", " ", value)
    if t == "lowercase":
        return value.lower()
    if t == "uppercase":
        return value.upper()
    if t == "titlecase":
        return value.title()
    if t == "stripRegex":
        return re.sub(rule["pattern"], "", value)
    if t == "stripTrailingChars":
        chars: list[str] = rule["chars"]
        charset = set(chars)
        prev = None
        while prev != value:
            prev = value
            if value and value[-1] in charset:
                value = value[:-1]
        return value
    if t == "stripPrefix":
        return value.removeprefix(rule["prefix"])
    if t == "stripSuffix":
        return value.removesuffix(rule["suffix"])
    if t == "split":
        parts = value.split(rule["delimiter"])
        idx = rule["index"]
        return parts[idx] if 0 <= idx < len(parts) else value
    if t == "regexExtract":
        m = re.search(rule["pattern"], value)
        if m is None:
            return value
        group = rule.get("group", 0)
        return m.group(group)
    if t == "replace":
        return value.replace(rule["find"], rule["replacement"])
    if t == "alias":
        return rule["map"].get(value, value)
    if t == "nullifyIfIn":
        return None if value in rule["values"] else value
    raise ValueError(f"Unknown rule type: {t!r}")


def _apply_rules(value: str | None, rules: list[dict]) -> str | None:
    for rule in rules:
        if value is None:
            return None
        value = _apply_rule(value, rule)
    return value


class NormalizeField:
    transform_type = "normalize_field"

    def apply(self, inputs: list[TransformInput], config: dict[str, Any]) -> TransformResult:
        if len(inputs) != 1:
            raise ValueError("normalize_field requires exactly one input")

        source_field: str = config["sourceField"]
        output_field: str = config["outputField"]
        rules: list[dict] = config.get("rules", [])

        inp = inputs[0]
        out_rows: list[dict] = []

        for row in inp.rows:
            new_row = dict(row)
            raw = row.get(source_field)
            if raw is None:
                new_row[output_field] = None
            else:
                new_row[output_field] = _apply_rules(str(raw), rules)

            # Carry provenance forward; tag outputField with sourceField's provenance
            existing_prov = dict(row.get(_META) or {})
            src_prov = existing_prov.get(
                source_field,
                {"sourceResultId": inp.source_result_id, "sourcePage": row.get("sourcePage")},
            )
            existing_prov[output_field] = src_prov
            new_row[_META] = existing_prov

            out_rows.append(new_row)

        return TransformResult(rows=out_rows, flags=[])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --directory backend python -m pytest -o "addopts=" tests/services/extraction/transforms/test_normalize_field.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/extraction/transforms/normalize_field.py backend/tests/services/extraction/transforms/test_normalize_field.py
git commit -m "feat(transforms): normalize_field primitive with full rule vocabulary (#[issue])"
```

---

### Task 2: Registry update

**Files:**
- Modify: `backend/app/services/extraction/transforms/registry.py`
- Modify: `backend/tests/services/extraction/transforms/test_registry.py`

**Interfaces:**
- Consumes: `NormalizeField` (Task 1).
- Produces: `get_transforms()` now includes `normalize_field` with `config_schema`; `build_transform("normalize_field")` returns a `NormalizeField` instance.

- [ ] **Step 1: Write the failing test** (add to existing test file — do not replace it)

```python
# Append to backend/tests/services/extraction/transforms/test_registry.py

def test_catalog_lists_normalize_field_with_config_schema():
    types = {t["transform_type"]: t for t in get_transforms()}
    assert "normalize_field" in types
    schema = types["normalize_field"]["config_schema"]
    assert schema["type"] == "object"
    assert "sourceField" in schema["properties"]
    assert "outputField" in schema["properties"]
    assert "rules" in schema["properties"]


def test_build_normalize_field():
    assert build_transform("normalize_field").transform_type == "normalize_field"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory backend python -m pytest -o "addopts=" tests/services/extraction/transforms/test_registry.py -v`
Expected: FAIL — `AssertionError: "normalize_field" not in types`

- [ ] **Step 3: Write the updated registry**

Replace the full content of `backend/app/services/extraction/transforms/registry.py`:

```python
# backend/app/services/extraction/transforms/registry.py
"""Catalogue + factory for ExtractionResult transforms (mirrors chunking registry)."""
from __future__ import annotations

from app.services.extraction.transforms.base import ExtractionResultTransform
from app.services.extraction.transforms.merge_records import MergeRecords
from app.services.extraction.transforms.normalize_field import NormalizeField

_RULE_TYPES = [
    "trim", "collapseWhitespace", "lowercase", "uppercase", "titlecase",
    "stripRegex", "stripTrailingChars", "stripPrefix", "stripSuffix",
    "split", "regexExtract", "replace", "alias", "nullifyIfIn",
]

_NORMALIZE_FIELD_SCHEMA = {
    "type": "object",
    "properties": {
        "sourceField": {"type": "string", "description": "Field to read. Never mutated."},
        "outputField": {"type": "string", "description": "New column to write on every row."},
        "rules": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": _RULE_TYPES},
                    "chars": {},
                    "pattern": {"type": "string"},
                    "prefix": {"type": "string"},
                    "suffix": {"type": "string"},
                    "delimiter": {"type": "string"},
                    "index": {"type": "integer"},
                    "group": {"oneOf": [{"type": "string"}, {"type": "integer"}]},
                    "find": {"type": "string"},
                    "replacement": {"type": "string"},
                    "map": {"type": "object"},
                    "values": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["type"],
            },
        },
    },
    "required": ["sourceField", "outputField", "rules"],
}

_MERGE_RECORDS_SCHEMA = {
    "type": "object",
    "properties": {
        "groupBy": {"type": "array", "items": {"type": "string"}},
        "spine": {
            "type": "object",
            "properties": {"whereFieldsPresent": {"type": "array", "items": {"type": "string"}}},
            "required": ["whereFieldsPresent"],
        },
        "conflict": {"type": "string", "enum": ["prefer_spine", "first_non_null"], "default": "prefer_spine"},
        "onGroupWithoutSpine": {"type": "string", "enum": ["keep", "drop"], "default": "keep"},
    },
    "required": ["groupBy", "spine"],
}


def get_transforms() -> list[dict]:
    return [
        {
            "transform_type": "normalize_field",
            "name": "Normalize field",
            "description": "Apply a rule chain to a source field and write the result to a new output column.",
            "config_schema": _NORMALIZE_FIELD_SCHEMA,
        },
        {
            "transform_type": "merge_records",
            "name": "Merge records",
            "description": "Group rows by a normalized key and collapse non-spine rows into spine rows.",
            "config_schema": _MERGE_RECORDS_SCHEMA,
        },
    ]


def build_transform(transform_type: str) -> ExtractionResultTransform:
    if transform_type == "normalize_field":
        return NormalizeField()
    if transform_type == "merge_records":
        return MergeRecords()
    raise ValueError(f"Unknown transform type: {transform_type!r}")
```

- [ ] **Step 4: Run all transform tests to verify they pass**

Run: `uv run --directory backend python -m pytest -o "addopts=" tests/services/extraction/transforms/ -v`
Expected: all PASS (including existing merge_records and base tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/extraction/transforms/registry.py backend/tests/services/extraction/transforms/test_registry.py
git commit -m "feat(transforms): register normalize_field in catalog (#[issue])"
```

---

### Task 3: Frontend types

**Files:**
- Modify: `frontend/src/types/resultTransform.ts`

**Interfaces:**
- Consumes: existing `TransformCatalogItem`, `TransformPreviewRequest`, `TransformPreview`.
- Produces: `NormalizeFieldRule` (loose tagged-union), `NormalizeFieldConfig` type.

- [ ] **Step 1: Add types** (no failing test — these are consumed by Task 4)

Open `frontend/src/types/resultTransform.ts` and append:

```typescript
// Append to frontend/src/types/resultTransform.ts

export interface NormalizeFieldRule {
  type: string
  // trim
  chars?: string | string[]
  // stripRegex | regexExtract
  pattern?: string
  // regexExtract
  group?: string | number
  // stripPrefix | stripSuffix
  prefix?: string
  suffix?: string
  // split
  delimiter?: string
  index?: number
  // replace
  find?: string
  replacement?: string
  // alias
  map?: Record<string, string>
  // nullifyIfIn | stripTrailingChars
  values?: string[]
}

export interface NormalizeFieldConfig {
  sourceField: string
  outputField: string
  rules: NormalizeFieldRule[]
}
```

- [ ] **Step 2: Build to verify no type errors**

Run (from `frontend/`): `npm run build`
Expected: clean build (no TypeScript errors)

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types/resultTransform.ts
git commit -m "feat(transforms): NormalizeFieldConfig + NormalizeFieldRule types (#[issue])"
```

---

### Task 4: `NormalizeFieldConfigForm`

**Files:**
- Create: `frontend/src/components/extraction/transforms/NormalizeFieldConfigForm.tsx`
- Create: `frontend/src/components/extraction/transforms/NormalizeFieldConfigForm.test.tsx`

**Interfaces:**
- Consumes: `NormalizeFieldConfig`, `NormalizeFieldRule` (Task 3).
- Produces: `NormalizeFieldConfigForm({ value, onChange })` — controlled form component.

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/components/extraction/transforms/NormalizeFieldConfigForm.test.tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { NormalizeFieldConfigForm } from './NormalizeFieldConfigForm'
import type { NormalizeFieldConfig } from '@/types/resultTransform'

const DEFAULT: NormalizeFieldConfig = { sourceField: '', outputField: '', rules: [] }

describe('NormalizeFieldConfigForm', () => {
  it('renders sourceField and outputField inputs', () => {
    render(<NormalizeFieldConfigForm value={DEFAULT} onChange={() => {}} />)
    expect(screen.getByLabelText(/source field/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/output field/i)).toBeInTheDocument()
  })

  it('calls onChange when sourceField is edited', () => {
    const onChange = vi.fn()
    render(<NormalizeFieldConfigForm value={DEFAULT} onChange={onChange} />)
    fireEvent.change(screen.getByLabelText(/source field/i), { target: { value: 'modelName' } })
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ sourceField: 'modelName' }))
  })

  it('renders Add rule button and shows a new rule entry when clicked', async () => {
    const onChange = vi.fn()
    render(<NormalizeFieldConfigForm value={DEFAULT} onChange={onChange} />)
    fireEvent.click(screen.getByRole('button', { name: /add rule/i }))
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ rules: [expect.objectContaining({ type: 'trim' })] }),
    )
  })

  it('renders existing rules in the list', () => {
    const value: NormalizeFieldConfig = {
      sourceField: 'modelName',
      outputField: 'baseModel',
      rules: [{ type: 'trim' }, { type: 'lowercase' }],
    }
    render(<NormalizeFieldConfigForm value={value} onChange={() => {}} />)
    // Two rule entries visible
    expect(screen.getAllByRole('combobox')).toHaveLength(2)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `frontend/`): `npx vitest run src/components/extraction/transforms/NormalizeFieldConfigForm.test.tsx`
Expected: FAIL — `Cannot find module './NormalizeFieldConfigForm'`

- [ ] **Step 3: Implement the component**

```tsx
// frontend/src/components/extraction/transforms/NormalizeFieldConfigForm.tsx
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Trash2, Plus } from 'lucide-react'
import type { NormalizeFieldConfig, NormalizeFieldRule } from '@/types/resultTransform'

const RULE_TYPES = [
  'trim', 'collapseWhitespace', 'lowercase', 'uppercase', 'titlecase',
  'stripRegex', 'stripTrailingChars', 'stripPrefix', 'stripSuffix',
  'split', 'regexExtract', 'replace', 'alias', 'nullifyIfIn',
]

interface RuleRowProps {
  rule: NormalizeFieldRule
  onChange: (r: NormalizeFieldRule) => void
  onRemove: () => void
}

function RuleRow({ rule, onChange, onRemove }: RuleRowProps) {
  const patch = (p: Partial<NormalizeFieldRule>) => onChange({ ...rule, ...p })
  return (
    <div className="border rounded p-3 space-y-2 bg-muted/30">
      <div className="flex items-center gap-2">
        <Select value={rule.type} onValueChange={(v) => onChange({ type: v })}>
          <SelectTrigger className="h-8 text-sm flex-1">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {RULE_TYPES.map((t) => (
              <SelectItem key={t} value={t}>{t}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button variant="ghost" size="icon" className="h-8 w-8 shrink-0" onClick={onRemove} title="Remove rule">
          <Trash2 className="h-3.5 w-3.5" />
        </Button>
      </div>

      {rule.type === 'trim' && (
        <Input
          placeholder="chars to strip (optional, default: whitespace)"
          value={typeof rule.chars === 'string' ? rule.chars : ''}
          onChange={(e) => patch({ chars: e.target.value || undefined })}
        />
      )}
      {(rule.type === 'stripRegex' || rule.type === 'regexExtract') && (
        <Input
          placeholder="regex pattern"
          value={rule.pattern ?? ''}
          onChange={(e) => patch({ pattern: e.target.value })}
        />
      )}
      {rule.type === 'regexExtract' && (
        <Input
          placeholder="capture group (name or index, default 0)"
          value={rule.group != null ? String(rule.group) : ''}
          onChange={(e) => patch({ group: e.target.value || undefined })}
        />
      )}
      {rule.type === 'stripTrailingChars' && (
        <Input
          placeholder="chars to strip, comma-separated (e.g. B,D,S,C)"
          value={Array.isArray(rule.chars) ? rule.chars.join(',') : ''}
          onChange={(e) =>
            patch({ chars: e.target.value.split(',').map((s) => s.trim()).filter(Boolean) })
          }
        />
      )}
      {rule.type === 'stripPrefix' && (
        <Input
          placeholder="prefix to remove"
          value={rule.prefix ?? ''}
          onChange={(e) => patch({ prefix: e.target.value })}
        />
      )}
      {rule.type === 'stripSuffix' && (
        <Input
          placeholder="suffix to remove"
          value={rule.suffix ?? ''}
          onChange={(e) => patch({ suffix: e.target.value })}
        />
      )}
      {rule.type === 'split' && (
        <div className="flex gap-2">
          <Input
            placeholder="delimiter"
            value={rule.delimiter ?? ''}
            onChange={(e) => patch({ delimiter: e.target.value })}
            className="flex-1"
          />
          <Input
            placeholder="index"
            type="number"
            value={rule.index != null ? String(rule.index) : ''}
            onChange={(e) => patch({ index: parseInt(e.target.value, 10) })}
            className="w-20"
          />
        </div>
      )}
      {rule.type === 'replace' && (
        <div className="flex gap-2">
          <Input
            placeholder="find (literal)"
            value={rule.find ?? ''}
            onChange={(e) => patch({ find: e.target.value })}
            className="flex-1"
          />
          <Input
            placeholder="replacement"
            value={rule.replacement ?? ''}
            onChange={(e) => patch({ replacement: e.target.value })}
            className="flex-1"
          />
        </div>
      )}
      {rule.type === 'alias' && (
        <div className="space-y-1">
          <p className="text-xs text-muted-foreground">One mapping per line: <code>from → to</code></p>
          <textarea
            className="w-full text-sm font-mono border rounded p-2 min-h-[4rem] bg-background"
            placeholder={'UX-50L → UX-50 LITE\nGP-40 LITE → GP-40L'}
            value={Object.entries(rule.map ?? {}).map(([k, v]) => `${k} → ${v}`).join('\n')}
            onChange={(e) => {
              const map: Record<string, string> = {}
              for (const line of e.target.value.split('\n')) {
                const [k, ...rest] = line.split('→')
                if (k && rest.length) map[k.trim()] = rest.join('→').trim()
              }
              patch({ map })
            }}
          />
        </div>
      )}
      {rule.type === 'nullifyIfIn' && (
        <Input
          placeholder="values to nullify, comma-separated (e.g. N/A,-,0)"
          value={Array.isArray(rule.values) ? rule.values.join(',') : ''}
          onChange={(e) =>
            patch({ values: e.target.value.split(',').map((s) => s.trim()).filter(Boolean) })
          }
        />
      )}
    </div>
  )
}

interface Props {
  value: NormalizeFieldConfig
  onChange: (v: NormalizeFieldConfig) => void
}

export function NormalizeFieldConfigForm({ value, onChange }: Props) {
  const updateRule = (i: number, rule: NormalizeFieldRule) => {
    const rules = [...value.rules]
    rules[i] = rule
    onChange({ ...value, rules })
  }
  const removeRule = (i: number) => {
    const rules = value.rules.filter((_, idx) => idx !== i)
    onChange({ ...value, rules })
  }
  const addRule = () => {
    onChange({ ...value, rules: [...value.rules, { type: 'trim' }] })
  }

  return (
    <div className="space-y-4">
      <div className="space-y-1.5">
        <Label htmlFor="sourceField">Source field</Label>
        <Input
          id="sourceField"
          placeholder="e.g. modelName"
          value={value.sourceField}
          onChange={(e) => onChange({ ...value, sourceField: e.target.value })}
        />
        <p className="text-xs text-muted-foreground">The field to read. Its value is never modified.</p>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="outputField">Output field</Label>
        <Input
          id="outputField"
          placeholder="e.g. baseModel"
          value={value.outputField}
          onChange={(e) => onChange({ ...value, outputField: e.target.value })}
        />
        <p className="text-xs text-muted-foreground">New column written to every row.</p>
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label>Rules</Label>
          <Button variant="outline" size="sm" className="h-7 text-xs gap-1" onClick={addRule}>
            <Plus className="h-3 w-3" />
            Add rule
          </Button>
        </div>
        {value.rules.length === 0 && (
          <p className="text-xs text-muted-foreground italic">No rules yet — add at least one.</p>
        )}
        {value.rules.map((rule, i) => (
          <RuleRow key={i} rule={rule} onChange={(r) => updateRule(i, r)} onRemove={() => removeRule(i)} />
        ))}
        <p className="text-xs text-muted-foreground">
          Rules execute in order: trim → collapseWhitespace → case → strip → alias → nullifyIfIn
        </p>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Run test to verify it passes**

Run (from `frontend/`): `npx vitest run src/components/extraction/transforms/NormalizeFieldConfigForm.test.tsx`
Expected: all PASS

- [ ] **Step 5: Lint + build**

Run (from `frontend/`): `npm run lint` then `npm run build`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/extraction/transforms/NormalizeFieldConfigForm.tsx frontend/src/components/extraction/transforms/NormalizeFieldConfigForm.test.tsx
git commit -m "feat(transforms): NormalizeFieldConfigForm with full rule vocabulary (#[issue])"
```

---

### Task 5: Wire normalize_field into the Transform dialog

**Files:**
- Modify: `frontend/src/components/extraction/ExtractionResultViewer.tsx`

**Interfaces:**
- Consumes: `NormalizeFieldConfigForm`, `NormalizeFieldConfig` (Task 4), `MergeRecordsConfigForm`, `MergeRecordsConfig` (Slice 1).
- Produces: `Transform` dialog with a type selector; shows `NormalizeFieldConfigForm` when `normalize_field` is selected, `MergeRecordsConfigForm` when `merge_records` is selected. Preview and Apply dispatch the selected config.

- [ ] **Step 1: Update the viewer**

In `ExtractionResultViewer.tsx`, apply the following changes (these are all the necessary modifications):

**a) Add import** after the existing `MergeRecordsConfigForm` import line:
```typescript
import { NormalizeFieldConfigForm } from './transforms/NormalizeFieldConfigForm'
import type { NormalizeFieldConfig } from '@/types/resultTransform'
```

**b) Add default normalize config** alongside `DEFAULT_MERGE_CONFIG`:
```typescript
const DEFAULT_NORMALIZE_CONFIG: NormalizeFieldConfig = {
  sourceField: '',
  outputField: '',
  rules: [],
}
```

**c) Replace the existing state declarations** for `mergeConfig` and the single `transformOpen` state — add a `transformType` selector:

Find this block in the component body:
```typescript
  const [transformOpen, setTransformOpen] = useState(false)
  const [mergeConfig, setMergeConfig] = useState<MergeRecordsConfig>(DEFAULT_MERGE_CONFIG)
```

Replace with:
```typescript
  const [transformOpen, setTransformOpen] = useState(false)
  const [transformType, setTransformType] = useState<'normalize_field' | 'merge_records'>('normalize_field')
  const [normalizeConfig, setNormalizeConfig] = useState<NormalizeFieldConfig>(DEFAULT_NORMALIZE_CONFIG)
  const [mergeConfig, setMergeConfig] = useState<MergeRecordsConfig>(DEFAULT_MERGE_CONFIG)
```

**d) Replace `handlePreview`** to dispatch based on `transformType`:
```typescript
  const handlePreview = async () => {
    if (!result) return
    const config =
      transformType === 'normalize_field'
        ? { sourceField: normalizeConfig.sourceField, outputField: normalizeConfig.outputField, rules: normalizeConfig.rules }
        : { groupBy: mergeConfig.groupBy, spine: mergeConfig.spine, conflict: mergeConfig.conflict, onGroupWithoutSpine: mergeConfig.onGroupWithoutSpine }
    await transform.preview({ sourceResultIds: [result.id], transformType, config })
  }
```

**e) Replace `handleApply`** to dispatch based on `transformType`:
```typescript
  const handleApply = async () => {
    if (!result) return
    const config =
      transformType === 'normalize_field'
        ? { sourceField: normalizeConfig.sourceField, outputField: normalizeConfig.outputField, rules: normalizeConfig.rules }
        : { groupBy: mergeConfig.groupBy, spine: mergeConfig.spine, conflict: mergeConfig.conflict, onGroupWithoutSpine: mergeConfig.onGroupWithoutSpine }
    const derived = await transform.apply({ sourceResultIds: [result.id], transformType, config })
    setTransformOpen(false)
    navigate(`/extraction?resultId=${derived.id}`)
  }
```

**f) Update the `onOpenChange` handler** to reset both configs:
```typescript
  onOpenChange={(open) => {
    setTransformOpen(open)
    if (!open) {
      setTransformType('normalize_field')
      setNormalizeConfig(DEFAULT_NORMALIZE_CONFIG)
      setMergeConfig(DEFAULT_MERGE_CONFIG)
    }
  }}
```

**g) Replace the dialog body** — add a type selector above the config form:

Replace the existing:
```tsx
                    <DialogTitle>Merge Records Transform</DialogTitle>
                  </DialogHeader>
                  <div className="space-y-4 py-2">
                    <MergeRecordsConfigForm value={mergeConfig} onChange={setMergeConfig} />
```

With:
```tsx
                    <DialogTitle>Transform Result</DialogTitle>
                  </DialogHeader>
                  <div className="space-y-4 py-2">
                    <div className="space-y-1.5">
                      <label className="text-sm font-medium">Transform type</label>
                      <Select value={transformType} onValueChange={(v) => setTransformType(v as typeof transformType)}>
                        <SelectTrigger className="h-8 text-sm">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="normalize_field">Normalize field</SelectItem>
                          <SelectItem value="merge_records">Merge records</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    {transformType === 'normalize_field' ? (
                      <NormalizeFieldConfigForm value={normalizeConfig} onChange={setNormalizeConfig} />
                    ) : (
                      <MergeRecordsConfigForm value={mergeConfig} onChange={setMergeConfig} />
                    )}
```

Verify that `Select`, `SelectTrigger`, `SelectContent`, `SelectItem`, `SelectValue` are already imported in the file — they are not present in the current imports, so add them:

```typescript
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
```

- [ ] **Step 2: Lint + build**

Run (from `frontend/`): `npm run lint` then `npm run build`
Expected: clean (no TypeScript errors or lint warnings).

- [ ] **Step 3: Run all frontend tests**

Run (from `frontend/`): `npx vitest run`
Expected: all PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/extraction/ExtractionResultViewer.tsx
git commit -m "feat(transforms): transform type selector in viewer; wire normalize_field (#[issue])"
```

---

### Task 6: End-to-end verification

- [ ] **Step 1: Full backend suite (all transform tests)**

Run: `uv run --directory backend python -m pytest -o "addopts=" tests/services/extraction/transforms/ tests/services/test_result_transform_service.py tests/routers/test_result_transforms.py -v`
Expected: all PASS

- [ ] **Step 2: Full frontend suite + build**

Run (from `frontend/`): `npx vitest run` then `npm run build`
Expected: all PASS, clean build

- [ ] **Step 3: Manual smoke**

Start the dev server:
```bash
# Build frontend first (CLAUDE.md local testing)
# Then: docker compose -f docker-compose.local.yml -p rag-admin up --build -d
```

1. Open an extraction result with `modelName` values like `"GP-40B 230/50/1 DD"`.
2. Click **Transform → Normalize field**.
3. Set `sourceField = modelName`, `outputField = baseModel`.
4. Add rules: `trim`, `collapseWhitespace`, `stripRegex` (pattern `\s+\d+/\d+/\d+`), `stripTrailingChars` (chars `B,D,S,C`), `alias` (map `UX-50L → UX-50 LITE`).
5. Click **Preview** → confirm the `baseModel` column appears with `"GP-40"` for all GP-40 variants, `"UX-50 LITE"` for `"UX-50L 230/50/1"`.
6. Click **Apply** → land on the derived result (all original columns + `baseModel`).
7. On the derived result, click **Transform → Merge records** → set `groupBy = baseModel`, `spine.whereFieldsPresent = sku`, Preview → confirm collapse works end-to-end.

- [ ] **Step 4: Comment on the GitHub issue**

```bash
gh issue comment [issue-number] --repo asanyaga/rag-admin --body "Slice 2 implemented: normalize_field primitive with full rule vocabulary (13 rule types), registry update, NormalizeFieldConfigForm, transform type selector in viewer. Backend + frontend suites green."
```

---

## Self-Review

**Spec coverage:**
- AC1 (registry) → Task 2
- AC2 (non-destructive) → Task 1 (new dict per row)
- AC3 (all columns preserved) → Task 1 + tests
- AC4 (sourceField not mutated, outputField present) → Task 1 + tests
- AC5 (null source → null output) → Task 1 + tests
- AC6 (each rule type in isolation) → Task 1 tests (one test per rule type)
- AC7 (rule composition: GP-40B → GP-40, UX-50L → UX-50 LITE) → Task 1 composition tests
- AC8 (null propagates through chain) → Task 1 `test_nullify_mid_chain_stops_further_processing`
- AC9 (config_schema in registry) → Task 2
- AC10 (frontend config form + transform type selector) → Tasks 4 + 5

**No placeholders:** all code is complete and runnable.

**Type consistency:**
- `NormalizeFieldConfig.rules` is `NormalizeFieldRule[]` throughout Tasks 3–5.
- `transform_type = "normalize_field"` matches in Python class, registry, TypeScript type selector, and API dispatch.
- `_apply_rules` / `_apply_rule` are the same names used in tests and implementation.
