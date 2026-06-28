# join_results Primitive Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `join_results` as an `ExtractionResultTransform` primitive — join 2–5 clean single-schema ExtractionResults on a shared key column to assemble a target record.

**Architecture:** The primitive lives in `backend/app/services/extraction/transforms/join_results.py`, registered in the existing catalog alongside `normalize_field` and `merge_records`. Frontend adds `JoinResultsConfigForm` and wires it into the existing Transform dialog in `ExtractionResultViewer`, which now accepts an `availableResults` prop threaded down from `ExtractionHistory`.

**Tech Stack:** Python 3.12 / FastAPI / Pydantic (backend); React 18 / TypeScript / Vite / shadcn/ui / Tailwind (frontend); Vitest / Testing Library (frontend tests); pytest (backend tests).

## Global Constraints

- Backend tests run with: `uv run --directory backend python -m pytest tests/services/extraction/transforms/ -o "addopts=" -v`
- Frontend tests run with: `npx --prefix frontend vitest run`
- Frontend lint: `npm --prefix frontend run lint`
- All new primitives must implement the `ExtractionResultTransform` Protocol (`transform_type` + `apply`)
- `_provenance` / `_META = "_provenance"` is the per-row provenance key — exclude from column names, carry through all transforms
- Flag structure: `{"rowIndex": int, "flag": str}` appended to `TransformResult.flags`
- No `cd X && Y` compound commands — use absolute paths or `--directory` flags

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| Modify | `backend/app/services/extraction/transforms/base.py` | Add `TransformValidationError` |
| Create | `backend/app/services/extraction/transforms/join_results.py` | `JoinResults` primitive |
| Modify | `backend/app/services/extraction/transforms/registry.py` | Register `join_results` + config schema |
| Modify | `backend/app/routers/result_transforms.py` | Catch `TransformValidationError` → 422 |
| Create | `backend/tests/services/extraction/transforms/test_join_results.py` | Primitive unit tests |
| Modify | `backend/tests/services/extraction/transforms/test_registry.py` | Catalog + build tests for `join_results` |
| Modify | `frontend/src/types/resultTransform.ts` | Add `JoinResultsConfig` |
| Create | `frontend/src/components/extraction/transforms/JoinResultsConfigForm.tsx` | Config form component |
| Create | `frontend/src/components/extraction/transforms/JoinResultsConfigForm.test.tsx` | Form tests |
| Modify | `frontend/src/components/extraction/ExtractionResultViewer.tsx` | Wire `join_results` into transform dialog |
| Modify | `frontend/src/components/extraction/ExtractionHistory.tsx` | Thread `availableResults` prop to viewer |

---

## Task 1: `TransformValidationError` + `join_results` primitive (TDD)

**Files:**
- Modify: `backend/app/services/extraction/transforms/base.py`
- Create: `backend/app/services/extraction/transforms/join_results.py`
- Create: `backend/tests/services/extraction/transforms/test_join_results.py`

**Interfaces:**
- Produces: `JoinResults` class with `transform_type = "join_results"` and `apply(inputs: list[TransformInput], config: dict) -> TransformResult`
- Produces: `TransformValidationError(code: str, detail: str)` in `base.py`
- Config shape consumed: `{"joinKey": str, "joinType": "left"|"inner"}`

- [ ] **Step 1: Write all failing tests**

Create `backend/tests/services/extraction/transforms/test_join_results.py`:

```python
import pytest
from app.services.extraction.transforms.base import TransformInput, TransformValidationError
from app.services.extraction.transforms.join_results import JoinResults

_META = "_provenance"

# ── Fixtures ──────────────────────────────────────────────────────────────────

PRICE_ROWS = [
    {"sku": "12345", "model": "gp-30b", "series": "gp-30", "price": 1000, "sourcePage": "Page 1"},
    {"sku": "54321", "model": "gp-30a", "series": "gp-30", "price": 2000, "sourcePage": "Page 1"},
]

SPEC_ROWS = [
    {"series": "gp-30", "height": 100, "width": 200, "weight": 20, "sourcePage": "Page 2"},
]

PRICE_INPUT = TransformInput(rows=PRICE_ROWS, source_result_id="r_price")
SPEC_INPUT = TransformInput(rows=SPEC_ROWS, source_result_id="r_spec")

CFG_LEFT = {"joinKey": "series", "joinType": "left"}
CFG_INNER = {"joinKey": "series", "joinType": "inner"}


# ── Happy path ─────────────────────────────────────────────────────────────────

def test_left_join_basic_output():
    out = JoinResults().apply([PRICE_INPUT, SPEC_INPUT], CFG_LEFT)
    assert len(out.rows) == 2
    for row in out.rows:
        assert row["height"] == 100
        assert row["width"] == 200
        assert row["weight"] == 20
    skus = {r["sku"] for r in out.rows}
    assert skus == {"12345", "54321"}


def test_left_join_no_flags_on_matched_rows():
    out = JoinResults().apply([PRICE_INPUT, SPEC_INPUT], CFG_LEFT)
    assert out.flags == []


def test_column_order_left_first_then_right_excl_join_key():
    out = JoinResults().apply([PRICE_INPUT, SPEC_INPUT], CFG_LEFT)
    cols = [k for k in out.rows[0] if k != _META]
    # left cols: sku, model, series, price, sourcePage (from PRICE_ROWS)
    # right cols excl series: height, width, weight, sourcePage
    left_pos = cols.index("series")
    height_pos = cols.index("height")
    assert left_pos < height_pos, "left columns must precede right columns"
    assert "series" not in cols[height_pos:], "join key must not repeat"


def test_provenance_left_cells_track_left_result():
    out = JoinResults().apply([PRICE_INPUT, SPEC_INPUT], CFG_LEFT)
    row = out.rows[0]
    assert row[_META]["sku"]["sourceResultId"] == "r_price"
    assert row[_META]["sku"]["sourcePage"] == "Page 1"


def test_provenance_right_cells_track_right_result():
    out = JoinResults().apply([PRICE_INPUT, SPEC_INPUT], CFG_LEFT)
    row = out.rows[0]
    assert row[_META]["height"]["sourceResultId"] == "r_spec"
    assert row[_META]["height"]["sourcePage"] == "Page 2"


# ── inner join ─────────────────────────────────────────────────────────────────

def test_inner_join_excludes_unmatched_left_rows():
    unmatched_price = [
        {"sku": "12345", "model": "gp-30b", "series": "gp-30", "price": 1000},
        {"sku": "99999", "model": "xx-10", "series": "xx-10", "price": 500},  # no spec match
    ]
    out = JoinResults().apply(
        [TransformInput(rows=unmatched_price, source_result_id="rp"), SPEC_INPUT],
        CFG_INNER,
    )
    assert len(out.rows) == 1
    assert out.rows[0]["sku"] == "12345"


def test_inner_join_null_key_rows_always_pass_through():
    rows_with_null = [
        {"sku": "12345", "model": "gp-30b", "series": "gp-30", "price": 1000},
        {"sku": "77777", "model": "gp-40a", "series": None, "price": 750},
    ]
    out = JoinResults().apply(
        [TransformInput(rows=rows_with_null, source_result_id="rp"), SPEC_INPUT],
        CFG_INNER,
    )
    assert len(out.rows) == 2
    null_row = next(r for r in out.rows if r["sku"] == "77777")
    assert null_row["height"] is None
    assert any(f["flag"] == "null_key" for f in out.flags)


# ── Flags ──────────────────────────────────────────────────────────────────────

def test_unmatched_flag_for_left_join_no_match():
    price_with_unknown = PRICE_ROWS + [
        {"sku": "99999", "model": "xx-10", "series": "xx-10", "price": 500}
    ]
    out = JoinResults().apply(
        [TransformInput(rows=price_with_unknown, source_result_id="rp"), SPEC_INPUT],
        CFG_LEFT,
    )
    assert len(out.rows) == 3
    unmatched_idx = next(i for i, r in enumerate(out.rows) if r["sku"] == "99999")
    assert {"rowIndex": unmatched_idx, "flag": "unmatched"} in out.flags
    assert out.rows[unmatched_idx]["height"] is None


def test_null_key_flag_left_join():
    rows = PRICE_ROWS + [{"sku": "77777", "model": "gp-40a", "series": None, "price": 750}]
    out = JoinResults().apply(
        [TransformInput(rows=rows, source_result_id="rp"), SPEC_INPUT],
        CFG_LEFT,
    )
    null_idx = next(i for i, r in enumerate(out.rows) if r["sku"] == "77777")
    assert {"rowIndex": null_idx, "flag": "null_key"} in out.flags
    assert out.rows[null_idx]["height"] is None


def test_null_key_provenance_is_null_for_right_cells():
    rows = [{"sku": "X", "series": None}]
    out = JoinResults().apply(
        [TransformInput(rows=rows, source_result_id="rp"), SPEC_INPUT],
        CFG_LEFT,
    )
    row = out.rows[0]
    assert row[_META]["height"]["sourceResultId"] is None
    assert row[_META]["height"]["sourcePage"] is None


def test_ambiguous_right_flag_uses_first_match():
    dup_spec = [
        {"series": "gp-30", "height": 100, "width": 200, "weight": 20},
        {"series": "gp-30", "height": 999, "width": 888, "weight": 77},  # duplicate key
    ]
    out = JoinResults().apply(
        [PRICE_INPUT, TransformInput(rows=dup_spec, source_result_id="rs")],
        CFG_LEFT,
    )
    assert len(out.rows) == 2
    for row in out.rows:
        assert row["height"] == 100  # first match used
    ambiguous_indices = {f["rowIndex"] for f in out.flags if f["flag"] == "ambiguous_right"}
    assert ambiguous_indices == {0, 1}  # both left rows flagged


# ── Validation errors ──────────────────────────────────────────────────────────

def test_invalid_result_count_too_few():
    with pytest.raises(TransformValidationError) as exc_info:
        JoinResults().apply([PRICE_INPUT], CFG_LEFT)
    assert exc_info.value.code == "invalid_result_count"


def test_invalid_result_count_too_many():
    with pytest.raises(TransformValidationError) as exc_info:
        JoinResults().apply([PRICE_INPUT] * 6, CFG_LEFT)
    assert exc_info.value.code == "invalid_result_count"


def test_join_key_missing_from_input():
    no_series = TransformInput(
        rows=[{"sku": "A", "price": 10}],
        source_result_id="r1",
    )
    with pytest.raises(TransformValidationError) as exc_info:
        JoinResults().apply([no_series, SPEC_INPUT], CFG_LEFT)
    assert exc_info.value.code == "join_key_missing"


def test_column_conflict_raises():
    conflicting = TransformInput(
        rows=[{"series": "gp-30", "height": 50, "notes": "spec notes"}],
        source_result_id="rs",
    )
    price_with_notes = TransformInput(
        rows=[{"sku": "X", "series": "gp-30", "price": 100, "notes": "price notes"}],
        source_result_id="rp",
    )
    with pytest.raises(TransformValidationError) as exc_info:
        JoinResults().apply([price_with_notes, conflicting], CFG_LEFT)
    assert exc_info.value.code == "column_conflict"


# ── Three-input join ───────────────────────────────────────────────────────────

def test_three_input_join():
    dims_rows = [{"series": "gp-30", "depth": 300}]
    dims_input = TransformInput(rows=dims_rows, source_result_id="r_dims")
    out = JoinResults().apply([PRICE_INPUT, SPEC_INPUT, dims_input], CFG_LEFT)
    assert len(out.rows) == 2
    for row in out.rows:
        assert row["height"] == 100
        assert row["depth"] == 300
```

- [ ] **Step 2: Run tests to confirm they all fail**

```
uv run --directory backend python -m pytest tests/services/extraction/transforms/test_join_results.py -o "addopts=" -v
```

Expected: `ModuleNotFoundError` or `ImportError` — `join_results` and `TransformValidationError` do not exist yet.

- [ ] **Step 3: Add `TransformValidationError` to `base.py`**

Current `base.py` ends at line 25. Add after the existing classes:

```python
class TransformValidationError(Exception):
    """Raised by a primitive when config or input data fails structural validation."""

    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")
```

Full updated `backend/app/services/extraction/transforms/base.py`:

```python
"""Port + DTOs for ExtractionResult transforms. Primitives are pure functions over rows."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class TransformInput:
    rows: list[dict]
    source_result_id: str | None = None


@dataclass
class TransformResult:
    rows: list[dict]
    flags: list[dict] = field(default_factory=list)


@runtime_checkable
class ExtractionResultTransform(Protocol):
    @property
    def transform_type(self) -> str: ...

    def apply(self, inputs: list[TransformInput], config: dict[str, Any]) -> TransformResult: ...


class TransformValidationError(Exception):
    """Raised by a primitive when config or input data fails structural validation."""

    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")
```

- [ ] **Step 4: Create `join_results.py`**

Create `backend/app/services/extraction/transforms/join_results.py`:

```python
"""join_results: assemble target records from N focused single-schema ExtractionResults.

Each input result is authoritative for its own columns. No spine detection or conflict
resolution — columns must be non-overlapping (validated). Flags: unmatched, null_key,
ambiguous_right.
"""
from __future__ import annotations

from typing import Any

from app.services.extraction.transforms.base import (
    TransformInput,
    TransformResult,
    TransformValidationError,
)

_META = "_provenance"


def _input_columns(inp: TransformInput) -> list[str]:
    """Ordered column list from all rows of an input (excluding _META)."""
    seen: dict[str, None] = {}
    for row in inp.rows:
        for k in row:
            if k != _META:
                seen[k] = None
    return list(seen.keys())


def _prov_from_row(row: dict, rid: str | None) -> dict:
    page = row.get("sourcePage")
    return {k: {"sourceResultId": rid, "sourcePage": page} for k in row if k != _META}


def _null_prov(cols: list[str]) -> dict:
    return {c: {"sourceResultId": None, "sourcePage": None} for c in cols}


class JoinResults:
    transform_type = "join_results"

    def apply(self, inputs: list[TransformInput], config: dict[str, Any]) -> TransformResult:
        join_key: str = config["joinKey"]
        join_type: str = config.get("joinType", "left")

        # ── Validation ────────────────────────────────────────────────────────
        if len(inputs) < 2 or len(inputs) > 5:
            raise TransformValidationError(
                "invalid_result_count",
                f"join_results requires 2–5 inputs, got {len(inputs)}",
            )

        input_cols: list[list[str]] = [_input_columns(inp) for inp in inputs]

        for i, cols in enumerate(input_cols):
            if join_key not in cols:
                raise TransformValidationError(
                    "join_key_missing",
                    f"joinKey {join_key!r} not found in input {i}",
                )

        seen_in: dict[str, list[int]] = {}
        for i, cols in enumerate(input_cols):
            for c in cols:
                if c == join_key:
                    continue
                seen_in.setdefault(c, []).append(i)
        conflicts = {c: idxs for c, idxs in seen_in.items() if len(idxs) > 1}
        if conflicts:
            detail = "; ".join(
                f"{c!r} in inputs {idxs}" for c, idxs in conflicts.items()
            )
            raise TransformValidationError("column_conflict", detail)

        # ── Setup ─────────────────────────────────────────────────────────────
        left_inp = inputs[0]
        right_inps = inputs[1:]
        right_cols_per: list[list[str]] = [
            [c for c in cols if c != join_key]
            for cols in input_cols[1:]
        ]

        # right lookup: {str(key_value): [row, ...]}; track ambiguous keys
        right_lookups: list[dict[str, list[dict]]] = []
        ambiguous_keys_per: list[set[str]] = []
        for inp in right_inps:
            lookup: dict[str, list[dict]] = {}
            for row in inp.rows:
                kv = row.get(join_key)
                if kv is None:
                    continue  # dead entry — null right keys never match
                lookup.setdefault(str(kv), []).append(row)
            right_lookups.append(lookup)
            ambiguous_keys_per.append({k for k, rows in lookup.items() if len(rows) > 1})

        # ── Join ──────────────────────────────────────────────────────────────
        out_rows: list[dict] = []
        flags: list[dict] = []

        for left_row in left_inp.rows:
            key_val = left_row.get(join_key)
            row_flags: list[str] = []

            merged = {k: v for k, v in left_row.items() if k != _META}
            prov = _prov_from_row(left_row, left_inp.source_result_id)

            if key_val is None:
                # null_key: always pass through regardless of join type
                for rc in right_cols_per:
                    for c in rc:
                        merged[c] = None
                    prov.update(_null_prov(rc))
                row_flags.append("null_key")
            else:
                key_str = str(key_val)
                skip_for_inner = False

                for rc, right_inp, lookup, amb in zip(
                    right_cols_per, right_inps, right_lookups, ambiguous_keys_per
                ):
                    matches = lookup.get(key_str, [])
                    if not matches:
                        for c in rc:
                            merged[c] = None
                        prov.update(_null_prov(rc))
                        if join_type == "inner":
                            skip_for_inner = True
                        else:
                            row_flags.append("unmatched")
                    else:
                        right_row = matches[0]
                        for c in rc:
                            merged[c] = right_row.get(c)
                        right_prov = _prov_from_row(right_row, right_inp.source_result_id)
                        for c in rc:
                            prov[c] = right_prov.get(
                                c, {"sourceResultId": None, "sourcePage": None}
                            )
                        if key_str in amb:
                            row_flags.append("ambiguous_right")

                if skip_for_inner:
                    continue

            idx = len(out_rows)
            merged[_META] = prov
            out_rows.append(merged)
            for f in row_flags:
                flags.append({"rowIndex": idx, "flag": f})

        # ── Column reorder: left cols, then right cols (excl join_key) ────────
        col_order = input_cols[0] + [c for rc in right_cols_per for c in rc]
        reordered = []
        for row in out_rows:
            new_row = {c: row.get(c) for c in col_order}
            new_row[_META] = row[_META]
            reordered.append(new_row)

        return TransformResult(rows=reordered, flags=flags)
```

- [ ] **Step 5: Run tests — expect most to pass**

```
uv run --directory backend python -m pytest tests/services/extraction/transforms/test_join_results.py -o "addopts=" -v
```

Expected: all tests PASS. Fix any failures before continuing.

- [ ] **Step 6: Commit**

```
git add backend/app/services/extraction/transforms/base.py backend/app/services/extraction/transforms/join_results.py backend/tests/services/extraction/transforms/test_join_results.py
git commit -m "feat(transforms): add join_results primitive with validation and provenance"
```

---

## Task 2: Register `join_results` + router error handling

**Files:**
- Modify: `backend/app/services/extraction/transforms/registry.py`
- Modify: `backend/app/routers/result_transforms.py`
- Modify: `backend/tests/services/extraction/transforms/test_registry.py`

**Interfaces:**
- Consumes: `JoinResults` from `join_results.py`, `TransformValidationError` from `base.py`
- Produces: `get_transforms()` returns entry for `join_results` with `config_schema`; `build_transform("join_results")` returns `JoinResults()`. Router maps `TransformValidationError` → HTTP 422.

- [ ] **Step 1: Write failing registry tests**

Append to `backend/tests/services/extraction/transforms/test_registry.py`:

```python
def test_catalog_lists_join_results_with_config_schema():
    types = {t["transform_type"]: t for t in get_transforms()}
    assert "join_results" in types
    schema = types["join_results"]["config_schema"]
    assert schema["type"] == "object"
    assert "joinKey" in schema["properties"]
    assert "joinType" in schema["properties"]


def test_build_join_results():
    assert build_transform("join_results").transform_type == "join_results"
```

- [ ] **Step 2: Run registry tests to confirm they fail**

```
uv run --directory backend python -m pytest tests/services/extraction/transforms/test_registry.py -o "addopts=" -v
```

Expected: two new tests FAIL.

- [ ] **Step 3: Update `registry.py`**

Add import, schema constant, and catalog/factory entries:

```python
"""Catalogue + factory for ExtractionResult transforms (mirrors chunking registry)."""
from __future__ import annotations

from app.services.extraction.transforms.base import ExtractionResultTransform
from app.services.extraction.transforms.join_results import JoinResults
from app.services.extraction.transforms.merge_records import MergeRecords
from app.services.extraction.transforms.normalize_field import NormalizeField

_RULE_TYPES = [
    "trim", "collapseWhitespace", "lowercase", "uppercase", "titlecase",
    "stripRegex", "stripTrailingChars", "stripPrefix", "stripSuffix",
    "split", "regexExtract", "replace", "alias", "nullifyIfIn",
]

_FIELD_ENTRY_SCHEMA = {
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

_NORMALIZE_FIELD_SCHEMA = {
    "type": "object",
    "properties": {
        "fields": {
            "type": "array",
            "minItems": 1,
            "items": _FIELD_ENTRY_SCHEMA,
            "description": "Ordered list of field normalizations. All run in one apply call producing one ExtractionResult.",
        },
    },
    "required": ["fields"],
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

_JOIN_RESULTS_SCHEMA = {
    "type": "object",
    "properties": {
        "joinKey": {
            "type": "string",
            "description": "Field present in all inputs used to match rows.",
        },
        "joinType": {
            "type": "string",
            "enum": ["left", "inner"],
            "default": "left",
            "description": "left: keep all left rows; inner: only matched rows (null-key rows always pass through).",
        },
    },
    "required": ["joinKey"],
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
            "transform_type": "join_results",
            "name": "Join results",
            "description": "Assemble target records from 2–5 focused single-schema extractions joined on a shared key column.",
            "config_schema": _JOIN_RESULTS_SCHEMA,
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
    if transform_type == "join_results":
        return JoinResults()
    if transform_type == "merge_records":
        return MergeRecords()
    raise ValueError(f"Unknown transform type: {transform_type!r}")
```

- [ ] **Step 4: Run registry tests to confirm they pass**

```
uv run --directory backend python -m pytest tests/services/extraction/transforms/test_registry.py -o "addopts=" -v
```

Expected: all PASS.

- [ ] **Step 5: Update router to handle `TransformValidationError`**

Modify `backend/app/routers/result_transforms.py` — add import and two `except` clauses:

```python
"""ExtractionResult transform API."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_active_user
from app.models import User
from app.repositories.extraction_result_repository import ExtractionResultRepository
from app.schemas.extraction_result import ExtractionResultResponse
from app.schemas.result_transform import (
    TransformApplyRequest,
    TransformPreviewRequest,
    TransformPreviewResponse,
)
from app.services.exceptions import NotFoundError
from app.services.extraction.transforms.base import TransformValidationError
from app.services.extraction.transforms.registry import get_transforms
from app.services.result_transform_service import ResultTransformService

router = APIRouter(tags=["result-transforms"])


def get_result_transform_service(db: AsyncSession = Depends(get_db)) -> ResultTransformService:
    return ResultTransformService(result_repo=ExtractionResultRepository(db))


@router.get("/result-transforms/catalog", summary="List available transforms")
async def transforms_catalog(
    current_user: User = Depends(get_current_active_user),
):
    return get_transforms()


@router.post(
    "/projects/{project_id}/result-transforms/preview",
    response_model=TransformPreviewResponse,
    summary="Preview a transform (no persistence)",
)
async def preview_transform(
    project_id: UUID,
    body: TransformPreviewRequest,
    current_user: User = Depends(get_current_active_user),
    service: ResultTransformService = Depends(get_result_transform_service),
):
    try:
        out = await service.preview(body.source_result_ids, body.transform_type, body.config)
        return TransformPreviewResponse(**out)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except TransformValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": e.code, "detail": e.detail},
        )


@router.post(
    "/projects/{project_id}/result-transforms/apply",
    response_model=ExtractionResultResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Apply a transform and persist a derived result",
)
async def apply_transform(
    project_id: UUID,
    body: TransformApplyRequest,
    current_user: User = Depends(get_current_active_user),
    service: ResultTransformService = Depends(get_result_transform_service),
):
    try:
        result = await service.apply(
            body.source_result_ids,
            body.transform_type,
            body.config,
            user_id=current_user.id,
            target_schema_id=body.target_schema_id,
        )
        return ExtractionResultResponse.from_orm_model(result)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except TransformValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": e.code, "detail": e.detail},
        )
```

- [ ] **Step 6: Run full transform test suite to confirm no regressions**

```
uv run --directory backend python -m pytest tests/services/extraction/transforms/ -o "addopts=" -v
```

Expected: all PASS.

- [ ] **Step 7: Commit**

```
git add backend/app/services/extraction/transforms/registry.py backend/app/routers/result_transforms.py backend/tests/services/extraction/transforms/test_registry.py
git commit -m "feat(transforms): register join_results in catalog; router maps TransformValidationError to 422"
```

---

## Task 3: Frontend types + config form

**Files:**
- Modify: `frontend/src/types/resultTransform.ts`
- Create: `frontend/src/components/extraction/transforms/JoinResultsConfigForm.tsx`
- Create: `frontend/src/components/extraction/transforms/JoinResultsConfigForm.test.tsx`

**Interfaces:**
- Produces: `JoinResultsConfig { joinKey: string; joinType: 'left' | 'inner'; lookupResultIds: string[] }` in `resultTransform.ts`
- Produces: `JoinResultsConfigForm` component with props `value: JoinResultsConfig`, `onChange: (v: JoinResultsConfig) => void`, `primaryResultId: string`, `availableResults: ExtractionResultListItem[]`

- [ ] **Step 1: Add `JoinResultsConfig` type**

Append to `frontend/src/types/resultTransform.ts`:

```typescript
export interface JoinResultsConfig {
  joinKey: string
  joinType: 'left' | 'inner'
  lookupResultIds: string[]
}
```

- [ ] **Step 2: Write failing form tests**

Create `frontend/src/components/extraction/transforms/JoinResultsConfigForm.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { JoinResultsConfigForm } from './JoinResultsConfigForm'
import type { JoinResultsConfig } from '@/types/resultTransform'
import type { ExtractionResultListItem } from '@/types/extraction'

const DEFAULT: JoinResultsConfig = { joinKey: '', joinType: 'left', lookupResultIds: [] }

const AVAILABLE: ExtractionResultListItem[] = [
  {
    id: 'r2', documentId: 'doc1', extractionSchemaId: 'schema1',
    extractionMethod: 'llm', status: 'completed', statusMessage: null,
    timeoutMinutes: null, createdAt: '2024-01-01',
  },
  {
    id: 'r3', documentId: 'doc1', extractionSchemaId: 'schema2',
    extractionMethod: 'llm', status: 'completed', statusMessage: null,
    timeoutMinutes: null, createdAt: '2024-01-01',
  },
]

describe('JoinResultsConfigForm', () => {
  it('renders join key input', () => {
    render(<JoinResultsConfigForm value={DEFAULT} onChange={() => {}} primaryResultId="r1" availableResults={AVAILABLE} />)
    expect(screen.getByPlaceholderText(/e\.g\. series/i)).toBeInTheDocument()
  })

  it('calls onChange when joinKey is edited', () => {
    const onChange = vi.fn()
    render(<JoinResultsConfigForm value={DEFAULT} onChange={onChange} primaryResultId="r1" availableResults={AVAILABLE} />)
    fireEvent.change(screen.getByPlaceholderText(/e\.g\. series/i), { target: { value: 'series' } })
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ joinKey: 'series' }))
  })

  it('shows primary result label as non-interactive', () => {
    render(<JoinResultsConfigForm value={DEFAULT} onChange={() => {}} primaryResultId="r1" availableResults={AVAILABLE} />)
    expect(screen.getByText(/primary/i)).toBeInTheDocument()
  })

  it('adds a lookup result from available list', () => {
    const onChange = vi.fn()
    render(
      <JoinResultsConfigForm
        value={DEFAULT}
        onChange={onChange}
        primaryResultId="r1"
        availableResults={AVAILABLE}
      />
    )
    fireEvent.click(screen.getByRole('button', { name: /add lookup/i }))
    // After clicking add, onChange is called with r2 added to lookupResultIds
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ lookupResultIds: ['r2'] })
    )
  })

  it('removes a lookup result', () => {
    const onChange = vi.fn()
    const value: JoinResultsConfig = { joinKey: 'series', joinType: 'left', lookupResultIds: ['r2'] }
    render(
      <JoinResultsConfigForm
        value={value}
        onChange={onChange}
        primaryResultId="r1"
        availableResults={AVAILABLE}
      />
    )
    fireEvent.click(screen.getByTitle(/remove lookup/i))
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ lookupResultIds: [] }))
  })

  it('changing joinType calls onChange with updated value', () => {
    const onChange = vi.fn()
    render(<JoinResultsConfigForm value={DEFAULT} onChange={onChange} primaryResultId="r1" availableResults={AVAILABLE} />)
    // The inner join radio/button
    fireEvent.click(screen.getByRole('button', { name: /inner/i }))
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ joinType: 'inner' }))
  })

  it('does not offer already-selected results as available to add again', () => {
    const value: JoinResultsConfig = { joinKey: '', joinType: 'left', lookupResultIds: ['r2'] }
    render(
      <JoinResultsConfigForm
        value={value}
        onChange={() => {}}
        primaryResultId="r1"
        availableResults={AVAILABLE}
      />
    )
    // Clicking add should only offer r3, not r2
    fireEvent.click(screen.getByRole('button', { name: /add lookup/i }))
    // r3 is offered; r2 is already selected
    expect(screen.queryByText('r2')).not.toBeInTheDocument()
  })
})
```

- [ ] **Step 3: Run tests to confirm they fail**

```
npx --prefix frontend vitest run src/components/extraction/transforms/JoinResultsConfigForm.test.tsx
```

Expected: FAIL — `JoinResultsConfigForm` does not exist yet.

- [ ] **Step 4: Create `JoinResultsConfigForm.tsx`**

Create `frontend/src/components/extraction/transforms/JoinResultsConfigForm.tsx`:

```tsx
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Trash2, Plus } from 'lucide-react'
import type { JoinResultsConfig } from '@/types/resultTransform'
import type { ExtractionResultListItem } from '@/types/extraction'

interface Props {
  value: JoinResultsConfig
  onChange: (v: JoinResultsConfig) => void
  primaryResultId: string
  availableResults: ExtractionResultListItem[]
}

export function JoinResultsConfigForm({ value, onChange, primaryResultId, availableResults }: Props) {
  const unselected = availableResults.filter((r) => !value.lookupResultIds.includes(r.id))

  const addLookup = () => {
    if (unselected.length === 0) return
    onChange({ ...value, lookupResultIds: [...value.lookupResultIds, unselected[0].id] })
  }

  const removeLookup = (id: string) => {
    onChange({ ...value, lookupResultIds: value.lookupResultIds.filter((r) => r !== id) })
  }

  return (
    <div className="space-y-4">
      {/* Result ordering */}
      <div className="space-y-2">
        <Label className="text-sm font-medium">Results (left → right)</Label>
        <p className="text-xs text-muted-foreground">
          First result is Primary (left). Lookup results supply additional columns.
        </p>

        {/* Primary — always first, read-only */}
        <div className="flex items-center gap-2 border rounded px-3 py-2 bg-muted/40">
          <Badge variant="secondary" className="text-xs shrink-0">Primary</Badge>
          <span className="text-sm font-mono text-muted-foreground truncate">{primaryResultId}</span>
        </div>

        {/* Lookup results */}
        {value.lookupResultIds.map((id) => (
          <div key={id} className="flex items-center gap-2 border rounded px-3 py-2">
            <Badge variant="outline" className="text-xs shrink-0">Lookup</Badge>
            <span className="text-sm font-mono text-muted-foreground truncate flex-1">{id}</span>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 shrink-0"
              onClick={() => removeLookup(id)}
              title="Remove lookup"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          </div>
        ))}

        {/* Add lookup button — hidden when no more unselected results or at 4 lookups (5 total) */}
        {unselected.length > 0 && value.lookupResultIds.length < 4 && (
          <Button
            variant="outline"
            size="sm"
            className="w-full h-8 text-xs gap-1.5"
            onClick={addLookup}
          >
            <Plus className="h-3.5 w-3.5" />
            Add lookup
          </Button>
        )}
      </div>

      {/* Join key */}
      <div className="space-y-1.5">
        <Label htmlFor="joinKey">Join key</Label>
        <Input
          id="joinKey"
          placeholder="e.g. series"
          value={value.joinKey}
          onChange={(e) => onChange({ ...value, joinKey: e.target.value })}
        />
        <p className="text-xs text-muted-foreground">
          Field present in all results used to match rows. Must be identical across results (use Normalize field upstream if needed).
        </p>
      </div>

      {/* Join type */}
      <div className="space-y-1.5">
        <Label>Join type</Label>
        <div className="flex gap-2">
          <Button
            variant={value.joinType === 'left' ? 'default' : 'outline'}
            size="sm"
            onClick={() => onChange({ ...value, joinType: 'left' })}
          >
            Left
          </Button>
          <Button
            variant={value.joinType === 'inner' ? 'default' : 'outline'}
            size="sm"
            onClick={() => onChange({ ...value, joinType: 'inner' })}
          >
            Inner
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">
          <strong>Left:</strong> keep all primary rows (unmatched right columns → null).{' '}
          <strong>Inner:</strong> only rows with a match in every lookup result. Rows with a null join key always appear.
        </p>
      </div>
    </div>
  )
}
```

- [ ] **Step 5: Run form tests**

```
npx --prefix frontend vitest run src/components/extraction/transforms/JoinResultsConfigForm.test.tsx
```

Expected: all PASS. Fix any failures before continuing.

- [ ] **Step 6: Lint**

```
npm --prefix frontend run lint
```

Expected: no errors.

- [ ] **Step 7: Commit**

```
git add frontend/src/types/resultTransform.ts frontend/src/components/extraction/transforms/JoinResultsConfigForm.tsx frontend/src/components/extraction/transforms/JoinResultsConfigForm.test.tsx
git commit -m "feat(transforms): JoinResultsConfigForm + JoinResultsConfig type"
```

---

## Task 4: Wire `join_results` into ExtractionResultViewer

**Files:**
- Modify: `frontend/src/components/extraction/ExtractionResultViewer.tsx`
- Modify: `frontend/src/components/extraction/ExtractionHistory.tsx`

**Interfaces:**
- Consumes: `JoinResultsConfig` from `resultTransform.ts`, `JoinResultsConfigForm` from `JoinResultsConfigForm.tsx`
- `ExtractionResultViewer` gains prop: `availableResults?: ExtractionResultListItem[]`
- `ExtractionHistory` passes its `results` array as `availableResults` to the viewer

- [ ] **Step 1: Update `ExtractionResultViewer.tsx`**

The changes are:
1. Import `JoinResultsConfigForm` and `JoinResultsConfig`
2. Import `ExtractionResultListItem`
3. Add `availableResults?: ExtractionResultListItem[]` to `ExtractionResultViewerProps`
4. Extend `transformType` state to include `'join_results'`
5. Add `joinConfig` state with default
6. Update the reset logic in `onOpenChange`
7. Add `join_results` to the `<Select>` options
8. Render `JoinResultsConfigForm` when `join_results` is selected
9. Update `handlePreview` and `handleApply` to build the correct `sourceResultIds` and `config`

Apply these diffs:

**Add imports** (after the existing transform imports near line 44):
```tsx
import { JoinResultsConfigForm } from './transforms/JoinResultsConfigForm'
import type { JoinResultsConfig } from '@/types/resultTransform'
import type { ExtractionResultListItem } from '@/types/extraction'
```

**Update props interface** (replace existing interface at ~line 50):
```tsx
interface ExtractionResultViewerProps {
  result: ExtractionResult | null
  isLoading?: boolean
  schemaName?: string
  projectId?: string
  availableResults?: ExtractionResultListItem[]
}
```

**Add default config constant** (after `DEFAULT_NORMALIZE_CONFIG` at ~line 403):
```tsx
const DEFAULT_JOIN_CONFIG: JoinResultsConfig = {
  joinKey: '',
  joinType: 'left',
  lookupResultIds: [],
}
```

**Update function signature and add state** (replace the state/hook block starting at ~line 411):
```tsx
export function ExtractionResultViewer({
  result,
  isLoading,
  schemaName,
  projectId,
  availableResults,
}: ExtractionResultViewerProps) {
  const navigate = useNavigate()
  const [transformOpen, setTransformOpen] = useState(false)
  const [transformType, setTransformType] = useState<'normalize_field' | 'merge_records' | 'join_results'>('normalize_field')
  const [normalizeConfig, setNormalizeConfig] = useState<NormalizeFieldConfig>(DEFAULT_NORMALIZE_CONFIG)
  const [mergeConfig, setMergeConfig] = useState<MergeRecordsConfig>(DEFAULT_MERGE_CONFIG)
  const [joinConfig, setJoinConfig] = useState<JoinResultsConfig>(DEFAULT_JOIN_CONFIG)
  const transform = useResultTransform(projectId ?? '')
```

**Replace `handlePreview`** (lines ~418-425):
```tsx
  const handlePreview = async () => {
    if (!result) return
    let config: Record<string, unknown>
    let sourceResultIds: string[]
    if (transformType === 'normalize_field') {
      config = normalizeConfig as unknown as Record<string, unknown>
      sourceResultIds = [result.id]
    } else if (transformType === 'merge_records') {
      config = { groupBy: mergeConfig.groupBy, spine: mergeConfig.spine, conflict: mergeConfig.conflict, onGroupWithoutSpine: mergeConfig.onGroupWithoutSpine }
      sourceResultIds = [result.id]
    } else {
      config = { joinKey: joinConfig.joinKey, joinType: joinConfig.joinType }
      sourceResultIds = [result.id, ...joinConfig.lookupResultIds]
    }
    await transform.preview({ sourceResultIds, transformType, config })
  }
```

**Replace `handleApply`** (lines ~427-434):
```tsx
  const handleApply = async () => {
    if (!result) return
    let config: Record<string, unknown>
    let sourceResultIds: string[]
    if (transformType === 'normalize_field') {
      config = normalizeConfig as unknown as Record<string, unknown>
      sourceResultIds = [result.id]
    } else if (transformType === 'merge_records') {
      config = { groupBy: mergeConfig.groupBy, spine: mergeConfig.spine, conflict: mergeConfig.conflict, onGroupWithoutSpine: mergeConfig.onGroupWithoutSpine }
      sourceResultIds = [result.id]
    } else {
      config = { joinKey: joinConfig.joinKey, joinType: joinConfig.joinType }
      sourceResultIds = [result.id, ...joinConfig.lookupResultIds]
    }
    const derived = await transform.apply({ sourceResultIds, transformType, config })
    setTransformOpen(false)
    navigate(`/extraction?resultId=${derived.id}`)
  }
```

**Update dialog `onOpenChange`** reset (line ~490, the `onOpenChange` prop):
```tsx
onOpenChange={(open) => {
  setTransformOpen(open)
  if (!open) {
    setTransformType('normalize_field')
    setNormalizeConfig(DEFAULT_NORMALIZE_CONFIG)
    setMergeConfig(DEFAULT_MERGE_CONFIG)
    setJoinConfig(DEFAULT_JOIN_CONFIG)
  }
}}
```

**Add `join_results` to Select options** (after the `merge_records` `<SelectItem>` at ~line 509):
```tsx
<SelectItem value="join_results">Join results</SelectItem>
```

**Add `join_results` form branch** (after the `merge_records` form branch, before `{transform.error`):
```tsx
{transformType === 'join_results' && result && (
  <JoinResultsConfigForm
    value={joinConfig}
    onChange={setJoinConfig}
    primaryResultId={result.id}
    availableResults={(availableResults ?? []).filter((r) => r.id !== result.id)}
  />
)}
```

- [ ] **Step 2: Update `ExtractionHistory.tsx`**

Pass `results` as `availableResults` to the viewer. Find the `<ExtractionResultViewer` usage (~line 176) and add the prop:

```tsx
<ExtractionResultViewer
  result={selectedResult}
  isLoading={false}
  schemaName={schemas?.find((s) => s.id === r.extractionSchemaId)?.name}
  projectId={projectId}
  availableResults={results}
/>
```

- [ ] **Step 3: Lint**

```
npm --prefix frontend run lint
```

Expected: no errors.

- [ ] **Step 4: Type-check via build**

```
npm --prefix frontend run build
```

Expected: successful build with no TypeScript errors.

- [ ] **Step 5: Commit**

```
git add frontend/src/components/extraction/ExtractionResultViewer.tsx frontend/src/components/extraction/ExtractionHistory.tsx
git commit -m "feat(transforms): wire join_results into ExtractionResultViewer; thread availableResults from ExtractionHistory"
```

---

## Self-review

**Spec coverage check:**

| Spec requirement | Task |
|---|---|
| Primitive in registry, `build_transform` resolves it | Task 2 |
| Non-destructive apply, lineage in output | Covered by existing `ResultTransformService.apply()` — no changes needed |
| `invalid_result_count` error | Task 1 |
| `join_key_missing` error | Task 1 |
| `column_conflict` error | Task 1 |
| `ambiguous_right_key` → `ambiguous_right` flag, first-match | Task 1 |
| `joinType: left` — unmatched rows pass with null cols + `unmatched` flag | Task 1 |
| `joinType: inner` — unmatched excluded; null-key always passes | Task 1 |
| `null_key` flag both join types | Task 1 |
| Provenance per cell (sourceResultId + sourcePage) | Task 1 |
| Column order: left first, then right excl join_key | Task 1 |
| 422 response for validation errors | Task 2 |
| Config schema in catalog | Task 2 |
| `JoinResultsConfigForm` with result picker, join key, join type | Task 3 |
| `column_conflict`/`join_key_missing` errors surfaced | Via `transform.error` displayed in dialog (existing pattern) |
| Flag chips in preview table | `TransformPreviewTable` already renders all flags generically |
| `join_results` in transform type selector | Task 4 |
| `availableResults` threaded from `ExtractionHistory` | Task 4 |

**Type consistency check:**
- `TransformValidationError(code, detail)` defined in Task 1, imported in Task 2 — consistent.
- `JoinResultsConfig.lookupResultIds` used in Task 3 form and Task 4 viewer — consistent.
- `sourceResultIds = [result.id, ...joinConfig.lookupResultIds]` matches `TransformPreviewRequest.sourceResultIds: string[]` — consistent.
- Backend `config` for `join_results` = `{joinKey, joinType}` — matches `_JOIN_RESULTS_SCHEMA` required field `joinKey` — consistent.

---

**Plan complete and saved to `docs/superpowers/plans/2026-06-28-join-results-primitive.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — fresh subagent per task, review between tasks

**2. Inline Execution** — execute tasks in this session using executing-plans

Which approach?
