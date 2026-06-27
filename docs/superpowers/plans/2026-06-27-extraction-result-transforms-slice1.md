# Extraction Result Transforms — Slice 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the `merge_records` transform end-to-end — collapse a single extraction result's base rows into identity-bearing rows by a user-selected, normalized group key — plus the shared rails (port, registry, preview/apply API, result-viewer transform action, lineage metadata).

**Architecture:** A pure-function transform layer (`ExtractionResultTransform` primitives operate on plain row dicts, mirroring `merge_outputs`) under `app/services/extraction/transforms/`, a thin `ResultTransformService` that maps ORM `ExtractionResult` ↔ pure rows and persists derived results with lineage, a project-scoped router, and a React config-form + preview-table reachable from the existing result viewer. GitHub issue: #120.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 (async), Pydantic v2, pytest; React 18, TypeScript, Vite, shadcn/ui, Tailwind, vitest.

## Global Constraints

- Backend tests run: `uv run --directory backend python -m pytest -o "addopts=" <path>`
- Frontend lint/build/test: `npm run lint`, `npm run build`, `npx vitest run` (from `frontend/`)
- No `cd X && Y` compound commands; use tool working-dir flags / absolute paths.
- Data flow: router → service → repository → models. Services raise (`NotFoundError`); routers map to HTTP.
- Primitives are **pure** (no DB, no I/O) and **non-destructive**; provenance (`sourceResultId`, `sourcePage`) is preserved.
- All field references (`groupBy`, spine field) are **user-selected config** — nothing hardcoded to `sku`/`model`.

---

### Task 1: `normalize_key` helper

**Files:**
- Create: `backend/app/services/extraction/transforms/__init__.py` (empty)
- Create: `backend/app/services/extraction/transforms/keys.py`
- Test: `backend/tests/services/extraction/transforms/test_keys.py`

**Interfaces:**
- Produces: `normalize_key(value: Any, config: dict) -> str`. Config keys: `casefold: bool=True`, `trim: bool=True`, `collapseWhitespace: bool=True`, `firstTokenOnly: bool=False`, `stripTrailingLetters: list[str]=[]`, `stripPatterns: list[str]=[]` (regex removed before tokenizing). Non-str input is stringified; `None` → `""`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/services/extraction/transforms/test_keys.py
from app.services.extraction.transforms.keys import normalize_key


def test_first_token_and_option_letters_collapse_variants():
    cfg = {"firstTokenOnly": True, "stripTrailingLetters": ["B", "D", "S", "C"]}
    assert normalize_key("GP-40 230/50/1", cfg) == "gp-40"
    assert normalize_key("GP-40B 230/50/1", cfg) == "gp-40"
    assert normalize_key("UX-40SBC 230/50/1 DD", cfg) == "ux-40"


def test_model_line_letter_l_is_preserved():
    cfg = {"firstTokenOnly": True, "stripTrailingLetters": ["B", "D", "S", "C"]}
    # 'L' (LITE) is not an option letter -> must NOT collapse into bare UX-50
    assert normalize_key("UX-50L 230/50/1", cfg) == "ux-50l"
    assert normalize_key("UX-50 LITE", {"firstTokenOnly": True}) == "ux-50"


def test_trim_casefold_and_none():
    assert normalize_key("  GP-35 ", {}) == "gp-35"
    assert normalize_key(None, {}) == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory backend python -m pytest -o "addopts=" tests/services/extraction/transforms/test_keys.py -v`
Expected: FAIL — `ModuleNotFoundError: app.services.extraction.transforms.keys`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/services/extraction/transforms/keys.py
"""Pure key-normalization for grouping rows in transforms."""
from __future__ import annotations

import re
from typing import Any


def normalize_key(value: Any, config: dict) -> str:
    if value is None:
        return ""
    text = str(value)
    for pat in config.get("stripPatterns", []):
        text = re.sub(pat, "", text)
    if config.get("trim", True):
        text = text.strip()
    if config.get("collapseWhitespace", True):
        text = re.sub(r"\s+", " ", text)
    if config.get("firstTokenOnly", False):
        text = text.split(" ")[0] if text else text
    letters = config.get("stripTrailingLetters", [])
    if letters:
        charset = "".join(letters)
        text = re.sub(rf"[{re.escape(charset)}]+$", "", text)
    if config.get("casefold", True):
        text = text.casefold()
    return text
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --directory backend python -m pytest -o "addopts=" tests/services/extraction/transforms/test_keys.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/extraction/transforms/__init__.py backend/app/services/extraction/transforms/keys.py backend/tests/services/extraction/transforms/test_keys.py
git commit -m "feat(transforms): normalize_key helper for grouping (#120)"
```

---

### Task 2: Transform port + DTOs

**Files:**
- Create: `backend/app/services/extraction/transforms/base.py`
- Test: `backend/tests/services/extraction/transforms/test_base.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) TransformInput { rows: list[dict]; source_result_id: str | None = None }`
  - `@dataclass TransformResult { rows: list[dict]; flags: list[dict] }` — `flags` entries: `{"rowIndex": int, "flag": str}`.
  - `class ExtractionResultTransform(Protocol)` with `transform_type: str` property and `apply(self, inputs: list[TransformInput], config: dict) -> TransformResult`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/services/extraction/transforms/test_base.py
from app.services.extraction.transforms.base import (
    TransformInput, TransformResult, ExtractionResultTransform,
)


class _Echo:
    transform_type = "echo"

    def apply(self, inputs, config):
        rows = [r for i in inputs for r in i.rows]
        return TransformResult(rows=rows, flags=[])


def test_protocol_is_satisfied_and_apply_pools_rows():
    t: ExtractionResultTransform = _Echo()
    out = t.apply([TransformInput(rows=[{"a": 1}]), TransformInput(rows=[{"a": 2}])], {})
    assert out.rows == [{"a": 1}, {"a": 2}]
    assert out.flags == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory backend python -m pytest -o "addopts=" tests/services/extraction/transforms/test_base.py -v`
Expected: FAIL — `ModuleNotFoundError: ...transforms.base`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/services/extraction/transforms/base.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --directory backend python -m pytest -o "addopts=" tests/services/extraction/transforms/test_base.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/extraction/transforms/base.py backend/tests/services/extraction/transforms/test_base.py
git commit -m "feat(transforms): ExtractionResultTransform port + DTOs (#120)"
```

---

### Task 3: `merge_records` primitive

**Files:**
- Create: `backend/app/services/extraction/transforms/merge_records.py`
- Test: `backend/tests/services/extraction/transforms/test_merge_records.py`

**Interfaces:**
- Consumes: `TransformInput`, `TransformResult` (Task 2), `normalize_key` (Task 1).
- Produces: `class MergeRecords` (`transform_type = "merge_records"`). Config: `groupBy: list[str]`, `keyNormalize: dict` (passed to `normalize_key`), `spine: {"whereFieldsPresent": list[str]}`, `conflict: "prefer_spine"|"first_non_null"`, `onGroupWithoutSpine: "keep"|"drop"`. Output rows carry `_provenance: {field: {"sourceResultId": str|None, "sourcePage": Any}}`; flags emitted: `conflict`, `no_specs`, `unjoinable`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/services/extraction/transforms/test_merge_records.py
from app.services.extraction.transforms.base import TransformInput
from app.services.extraction.transforms.merge_records import MergeRecords

CFG = {
    "groupBy": ["modelName"],
    "keyNormalize": {"firstTokenOnly": True, "stripTrailingLetters": ["B", "D", "S", "C"]},
    "spine": {"whereFieldsPresent": ["sku"]},
    "conflict": "prefer_spine",
    "onGroupWithoutSpine": "keep",
}

# Mirrors price list_2f0e0d93.csv GP-40 family: one base spec row + 4 priced variants.
GP40 = [
    {"sku": None, "modelName": "GP-40", "widthMm": 470, "netWeightKg": 41, "listPrice": 0, "sourcePage": "Page 6"},
    {"sku": "1303050", "modelName": "GP-40 230/50/1", "listPrice": 1908, "sourcePage": "Page 7"},
    {"sku": "1303054", "modelName": "GP-40B 230/50/1", "listPrice": 2140, "sourcePage": "Page 7"},
    {"sku": "1303052", "modelName": "GP-40 230/50/1 DD", "listPrice": 2081, "sourcePage": "Page 7"},
    {"sku": "1303056", "modelName": "GP-40B 230/50/1 DD", "listPrice": 2313, "sourcePage": "Page 7"},
]


def test_collapses_base_spec_into_each_priced_variant():
    out = MergeRecords().apply([TransformInput(rows=GP40, source_result_id="r1")], CFG)
    assert len(out.rows) == 4
    for row in out.rows:
        assert row["sku"] is not None
        assert row["widthMm"] == 470          # inherited from base spec row
        assert row["netWeightKg"] == 41
    prices = sorted(r["listPrice"] for r in out.rows)
    assert prices == [1908, 2081, 2140, 2313]


def test_provenance_tracks_source_page_per_field():
    out = MergeRecords().apply([TransformInput(rows=GP40, source_result_id="r1")], CFG)
    row = next(r for r in out.rows if r["sku"] == "1303050")
    assert row["_provenance"]["widthMm"]["sourcePage"] == "Page 6"
    assert row["_provenance"]["listPrice"]["sourcePage"] == "Page 7"


def test_group_without_spine_kept_and_flagged():
    rows = [{"sku": None, "modelName": "ZZ-1", "widthMm": 5, "sourcePage": "Page 1"}]
    out = MergeRecords().apply([TransformInput(rows=rows, source_result_id="r1")], CFG)
    assert len(out.rows) == 1
    assert any(f["flag"] == "no_spine" for f in out.flags)


def test_unjoinable_when_group_key_empty():
    rows = [{"sku": "X1", "modelName": "", "listPrice": 9, "sourcePage": "Page 2"}]
    out = MergeRecords().apply([TransformInput(rows=rows, source_result_id="r1")], CFG)
    assert any(f["flag"] == "unjoinable" for f in out.flags)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory backend python -m pytest -o "addopts=" tests/services/extraction/transforms/test_merge_records.py -v`
Expected: FAIL — `ModuleNotFoundError: ...merge_records`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/services/extraction/transforms/merge_records.py
"""merge_records: group rows by a normalized key; collapse non-spine rows into spine rows."""
from __future__ import annotations

from typing import Any

from app.services.extraction.transforms.base import TransformInput, TransformResult
from app.services.extraction.transforms.keys import normalize_key

_META = "_provenance"


def _is_present(row: dict, fields: list[str]) -> bool:
    return all(row.get(f) not in (None, "", 0) for f in fields)


def _group_key(row: dict, group_by: list[str], norm_cfg: dict) -> str:
    return "|".join(normalize_key(row.get(f), norm_cfg) for f in group_by)


class MergeRecords:
    transform_type = "merge_records"

    def apply(self, inputs: list[TransformInput], config: dict[str, Any]) -> TransformResult:
        group_by = config["groupBy"]
        norm_cfg = config.get("keyNormalize", {})
        spine_fields = config["spine"]["whereFieldsPresent"]
        conflict = config.get("conflict", "prefer_spine")
        on_no_spine = config.get("onGroupWithoutSpine", "keep")

        # pool rows, tagging each with its source result id
        pooled: list[tuple[dict, str | None]] = [
            (row, inp.source_result_id) for inp in inputs for row in inp.rows
        ]

        groups: dict[str, list[tuple[dict, str | None]]] = {}
        out_rows: list[dict] = []
        flags: list[dict] = []

        for row, rid in pooled:
            key = _group_key(row, group_by, norm_cfg)
            if key == "" or key == "|".join([""] * len(group_by)):
                idx = len(out_rows)
                out_rows.append({**{k: v for k, v in row.items() if k != _META},
                                 _META: self._prov(row, rid)})
                flags.append({"rowIndex": idx, "flag": "unjoinable"})
                continue
            groups.setdefault(key, []).append((row, rid))

        for key, members in groups.items():
            spine = [(r, rid) for r, rid in members if _is_present(r, spine_fields)]
            enrich = [(r, rid) for r, rid in members if not _is_present(r, spine_fields)]

            if not spine:
                if on_no_spine == "drop":
                    continue
                for r, rid in members:
                    idx = len(out_rows)
                    out_rows.append({**{k: v for k, v in r.items() if k != _META},
                                     _META: self._prov(r, rid)})
                    flags.append({"rowIndex": idx, "flag": "no_spine"})
                continue

            for r, rid in spine:
                merged = {k: v for k, v in r.items() if k != _META}
                prov = self._prov(r, rid)
                had_enrich = False
                for er, erid in enrich:
                    had_enrich = True
                    for k, v in er.items():
                        if k == _META or v in (None, "", 0):
                            continue
                        cur = merged.get(k)
                        if cur in (None, "", 0):
                            merged[k] = v
                            prov[k] = {"sourceResultId": erid, "sourcePage": er.get("sourcePage")}
                        elif cur != v and conflict == "first_non_null":
                            pass  # keep spine value; first-non-null already satisfied
                        elif cur != v:
                            flags.append({"rowIndex": len(out_rows), "flag": "conflict"})
                idx = len(out_rows)
                merged[_META] = prov
                out_rows.append(merged)
                if not had_enrich:
                    flags.append({"rowIndex": idx, "flag": "no_specs"})

        return TransformResult(rows=out_rows, flags=flags)

    @staticmethod
    def _prov(row: dict, rid: str | None) -> dict:
        page = row.get("sourcePage")
        return {k: {"sourceResultId": rid, "sourcePage": page}
                for k in row if k != _META}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --directory backend python -m pytest -o "addopts=" tests/services/extraction/transforms/test_merge_records.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/extraction/transforms/merge_records.py backend/tests/services/extraction/transforms/test_merge_records.py
git commit -m "feat(transforms): merge_records primitive with provenance + flags (#120)"
```

---

### Task 4: Transform registry

**Files:**
- Create: `backend/app/services/extraction/transforms/registry.py`
- Test: `backend/tests/services/extraction/transforms/test_registry.py`

**Interfaces:**
- Consumes: `MergeRecords` (Task 3).
- Produces: `get_transforms() -> list[dict]` (each: `transform_type`, `name`, `description`, `config_schema`); `build_transform(transform_type: str) -> ExtractionResultTransform` (raises `ValueError` on unknown).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/services/extraction/transforms/test_registry.py
import pytest
from app.services.extraction.transforms.registry import get_transforms, build_transform


def test_catalog_lists_merge_records_with_config_schema():
    types = {t["transform_type"]: t for t in get_transforms()}
    assert "merge_records" in types
    assert types["merge_records"]["config_schema"]["type"] == "object"


def test_build_known_and_unknown():
    assert build_transform("merge_records").transform_type == "merge_records"
    with pytest.raises(ValueError):
        build_transform("nope")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory backend python -m pytest -o "addopts=" tests/services/extraction/transforms/test_registry.py -v`
Expected: FAIL — `ModuleNotFoundError: ...registry`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/services/extraction/transforms/registry.py
"""Catalogue + factory for ExtractionResult transforms (mirrors chunking registry)."""
from __future__ import annotations

from app.services.extraction.transforms.base import ExtractionResultTransform
from app.services.extraction.transforms.merge_records import MergeRecords

_MERGE_RECORDS_SCHEMA = {
    "type": "object",
    "properties": {
        "groupBy": {"type": "array", "items": {"type": "string"}},
        "keyNormalize": {
            "type": "object",
            "properties": {
                "firstTokenOnly": {"type": "boolean", "default": False},
                "stripTrailingLetters": {"type": "array", "items": {"type": "string"}},
                "stripPatterns": {"type": "array", "items": {"type": "string"}},
                "casefold": {"type": "boolean", "default": True},
            },
        },
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
            "transform_type": "merge_records",
            "name": "Merge records",
            "description": "Group rows by a normalized key and collapse non-spine rows into spine rows.",
            "config_schema": _MERGE_RECORDS_SCHEMA,
        },
    ]


def build_transform(transform_type: str) -> ExtractionResultTransform:
    if transform_type == "merge_records":
        return MergeRecords()
    raise ValueError(f"Unknown transform type: {transform_type!r}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --directory backend python -m pytest -o "addopts=" tests/services/extraction/transforms/test_registry.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/extraction/transforms/registry.py backend/tests/services/extraction/transforms/test_registry.py
git commit -m "feat(transforms): registry (catalog + build_transform) (#120)"
```

---

### Task 5: CSV fixture integration test

**Files:**
- Create: `backend/tests/fixtures/sammic_price_list.csv` (copy of `price list_2f0e0d93.csv`)
- Test: `backend/tests/services/extraction/transforms/test_merge_records_fixture.py`

**Interfaces:**
- Consumes: `MergeRecords`, `TransformInput`. Validates acceptance criterion #5 against real data.

- [ ] **Step 1: Copy the CSV fixture**

```bash
mkdir -p backend/tests/fixtures
cp "/c/Users/Asa/Downloads/price list_2f0e0d93.csv" backend/tests/fixtures/sammic_price_list.csv
```

- [ ] **Step 2: Write the failing test**

```python
# backend/tests/services/extraction/transforms/test_merge_records_fixture.py
import csv
from pathlib import Path

from app.services.extraction.transforms.base import TransformInput
from app.services.extraction.transforms.merge_records import MergeRecords

FIXTURE = Path(__file__).parents[3] / "fixtures" / "sammic_price_list.csv"
CFG = {
    "groupBy": ["modelName"],
    "keyNormalize": {"firstTokenOnly": True, "stripTrailingLetters": ["B", "D", "S", "C"]},
    "spine": {"whereFieldsPresent": ["sku"]},
    "conflict": "prefer_spine",
    "onGroupWithoutSpine": "keep",
}


def _load_rows() -> list[dict]:
    with FIXTURE.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        # numeric sentinel sku values (model placeholders) are not real identities
        if not (r["sku"] or "").strip().isdigit():
            r["sku"] = None
    return rows


def test_gp40_family_collapses_to_four_priced_records():
    rows = _load_rows()
    out = MergeRecords().apply([TransformInput(rows=rows, source_result_id="r1")], CFG)
    gp40 = [r for r in out.rows if str(r.get("modelName", "")).startswith("GP-40")]
    assert len(gp40) == 4
    assert all(r["widthMm"] in ("470", 470) for r in gp40)  # inherited base spec
```

- [ ] **Step 3: Run test to verify it fails, then passes**

Run: `uv run --directory backend python -m pytest -o "addopts=" tests/services/extraction/transforms/test_merge_records_fixture.py -v`
Expected: FAIL if fixture missing; PASS once CSV copied and merge logic correct. If the spine filter needs the digit-sku coercion above, that lives in the test loader (extraction-side null handling is out of scope for Slice 1).

- [ ] **Step 4: Commit**

```bash
git add backend/tests/fixtures/sammic_price_list.csv backend/tests/services/extraction/transforms/test_merge_records_fixture.py
git commit -m "test(transforms): merge_records against real Sammic CSV fixture (#120)"
```

---

### Task 6: `ResultTransformService` (preview + apply + lineage)

**Files:**
- Create: `backend/app/services/result_transform_service.py`
- Test: `backend/tests/services/test_result_transform_service.py`

**Interfaces:**
- Consumes: `build_transform`, `TransformInput`, `ExtractionResultRepository` (`get_by_id`, `create`, `update_result`).
- Produces: `class ResultTransformService(result_repo)` with
  - `async preview(source_result_ids: list[UUID], transform_type: str, config: dict) -> dict` → `{"rows": [...], "flags": [...]}` (no persistence; raises `NotFoundError` if a source is missing).
  - `async apply(source_result_ids, transform_type, config, user_id, target_schema_id=None) -> ExtractionResult` → persists a derived result (`extraction_method="transform"`, `extraction_metadata.lineage = {sourceResultIds, transform:{type,config}}`).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/services/test_result_transform_service.py
import pytest
from uuid import uuid4
from app.services.result_transform_service import ResultTransformService
from app.services.exceptions import NotFoundError


class _Result:
    def __init__(self, rows, rid=None):
        self.id = rid or uuid4()
        self.structured_data = {"records": rows}
        self.document_id = uuid4()
        self.extraction_schema_id = uuid4()
        self.schema_definition_snapshot = {"type": "object"}
        self.extraction_metadata = None


class _Repo:
    def __init__(self, results):
        self._results = {r.id: r for r in results}
        self.created = None
        self.updated = None

    async def get_by_id(self, rid):
        return self._results.get(rid)

    async def create(self, **kwargs):
        self.created = type("R", (), {"id": uuid4(), **kwargs})()
        return self.created

    async def update_result(self, result_id, structured_data, extraction_metadata=None, **_):
        self.updated = {"id": result_id, "structured_data": structured_data,
                        "extraction_metadata": extraction_metadata}
        obj = type("R", (), {"id": result_id, "structured_data": structured_data,
                             "extraction_metadata": extraction_metadata})()
        return obj


CFG = {"groupBy": ["modelName"], "keyNormalize": {"firstTokenOnly": True, "stripTrailingLetters": ["B"]},
       "spine": {"whereFieldsPresent": ["sku"]}}
ROWS = [
    {"sku": None, "modelName": "GP-40", "widthMm": 470, "sourcePage": "Page 6"},
    {"sku": "1303050", "modelName": "GP-40 230/50/1", "listPrice": 1908, "sourcePage": "Page 7"},
]


@pytest.mark.asyncio
async def test_preview_does_not_persist():
    src = _Result(ROWS)
    repo = _Repo([src])
    svc = ResultTransformService(result_repo=repo)
    out = await svc.preview([src.id], "merge_records", CFG)
    assert len(out["rows"]) == 1
    assert out["rows"][0]["widthMm"] == 470
    assert repo.created is None


@pytest.mark.asyncio
async def test_apply_persists_with_lineage():
    src = _Result(ROWS)
    repo = _Repo([src])
    svc = ResultTransformService(result_repo=repo)
    await svc.apply([src.id], "merge_records", CFG, user_id=uuid4())
    lineage = repo.updated["extraction_metadata"]["lineage"]
    assert lineage["transform"]["type"] == "merge_records"
    assert str(src.id) in [str(x) for x in lineage["sourceResultIds"]]


@pytest.mark.asyncio
async def test_missing_source_raises():
    svc = ResultTransformService(result_repo=_Repo([]))
    with pytest.raises(NotFoundError):
        await svc.preview([uuid4()], "merge_records", CFG)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory backend python -m pytest -o "addopts=" tests/services/test_result_transform_service.py -v`
Expected: FAIL — `ModuleNotFoundError: app.services.result_transform_service`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/services/result_transform_service.py
"""Service: run an ExtractionResultTransform over selected results; persist derived results."""
from __future__ import annotations

from uuid import UUID

from app.services.exceptions import NotFoundError
from app.services.extraction.transforms.base import TransformInput
from app.services.extraction.transforms.registry import build_transform

_RECORDS_KEY = "records"


class ResultTransformService:
    def __init__(self, result_repo):
        self.result_repo = result_repo

    async def _load_inputs(self, source_result_ids: list[UUID]) -> list[tuple[object, TransformInput]]:
        loaded = []
        for rid in source_result_ids:
            result = await self.result_repo.get_by_id(rid)
            if result is None:
                raise NotFoundError(f"Extraction result {rid} not found")
            rows = (result.structured_data or {}).get(_RECORDS_KEY, [])
            loaded.append((result, TransformInput(rows=rows, source_result_id=str(rid))))
        return loaded

    async def preview(self, source_result_ids, transform_type, config) -> dict:
        loaded = await self._load_inputs(source_result_ids)
        out = build_transform(transform_type).apply([ti for _, ti in loaded], config)
        return {"rows": out.rows, "flags": out.flags}

    async def apply(self, source_result_ids, transform_type, config, user_id, target_schema_id=None):
        loaded = await self._load_inputs(source_result_ids)
        primary, _ = loaded[0]
        out = build_transform(transform_type).apply([ti for _, ti in loaded], config)

        created = await self.result_repo.create(
            document_id=primary.document_id,
            extraction_schema_id=target_schema_id or primary.extraction_schema_id,
            schema_definition_snapshot=primary.schema_definition_snapshot,
            extraction_method="transform",
            created_by=user_id,
            config={"transformType": transform_type, "config": config},
        )
        return await self.result_repo.update_result(
            result_id=created.id,
            structured_data={_RECORDS_KEY: out.rows},
            extraction_metadata={
                "flags": out.flags,
                "lineage": {
                    "sourceResultIds": [str(x) for x in source_result_ids],
                    "transform": {"type": transform_type, "config": config},
                },
            },
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --directory backend python -m pytest -o "addopts=" tests/services/test_result_transform_service.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/result_transform_service.py backend/tests/services/test_result_transform_service.py
git commit -m "feat(transforms): ResultTransformService preview/apply with lineage (#120)"
```

---

### Task 7: Schemas + router + wiring

**Files:**
- Create: `backend/app/schemas/result_transform.py`
- Create: `backend/app/routers/result_transforms.py`
- Modify: `backend/app/main.py` (register router — match existing `include_router` block)
- Test: `backend/tests/routers/test_result_transforms.py`

**Interfaces:**
- Consumes: `ResultTransformService`, `ExtractionResultRepository`, `get_current_active_user`, `get_db`.
- Produces endpoints: `GET /result-transforms/catalog`; `POST /projects/{project_id}/result-transforms/preview`; `POST /projects/{project_id}/result-transforms/apply`.

- [ ] **Step 1: Write the failing test** (catalog endpoint is auth-free of project scope; assert it lists merge_records)

```python
# backend/tests/routers/test_result_transforms.py
import pytest


@pytest.mark.asyncio
async def test_catalog_lists_merge_records(async_client, auth_headers):
    resp = await async_client.get("/result-transforms/catalog", headers=auth_headers)
    assert resp.status_code == 200
    assert any(t["transform_type"] == "merge_records" for t in resp.json())
```

> Note: reuse the project's existing `async_client` / `auth_headers` fixtures from `backend/tests/conftest.py` (same as other router tests). If the catalog route is unauthenticated, drop `auth_headers`.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory backend python -m pytest -o "addopts=" tests/routers/test_result_transforms.py -v`
Expected: FAIL — 404 (route not registered)

- [ ] **Step 3: Write schemas**

```python
# backend/app/schemas/result_transform.py
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict


class TransformPreviewRequest(BaseModel):
    source_result_ids: list[UUID] = Field(..., alias="sourceResultIds")
    transform_type: str = Field(..., alias="transformType")
    config: dict
    model_config = ConfigDict(populate_by_name=True)


class TransformApplyRequest(TransformPreviewRequest):
    target_schema_id: UUID | None = Field(None, alias="targetSchemaId")


class TransformPreviewResponse(BaseModel):
    rows: list[dict]
    flags: list[dict]
```

- [ ] **Step 4: Write router**

```python
# backend/app/routers/result_transforms.py
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
    TransformPreviewRequest, TransformApplyRequest, TransformPreviewResponse,
)
from app.services.exceptions import NotFoundError
from app.services.extraction.transforms.registry import get_transforms
from app.services.result_transform_service import ResultTransformService

router = APIRouter(tags=["result-transforms"])


def get_result_transform_service(db: AsyncSession = Depends(get_db)) -> ResultTransformService:
    return ResultTransformService(result_repo=ExtractionResultRepository(db))


@router.get("/result-transforms/catalog", summary="List available transforms")
async def transforms_catalog(current_user: User = Depends(get_current_active_user)):
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
            body.source_result_ids, body.transform_type, body.config,
            user_id=current_user.id, target_schema_id=body.target_schema_id,
        )
        return ExtractionResultResponse.from_orm_model(result)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
```

> Confirm `ExtractionResultResponse.from_orm_model` exists (used in `extraction_service.py`); if its constructor differs, mirror `get_extraction_result`'s return path.

- [ ] **Step 5: Register router in `app/main.py`**

Add alongside the other `app.include_router(...)` calls:

```python
from app.routers import result_transforms
app.include_router(result_transforms.router)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run --directory backend python -m pytest -o "addopts=" tests/routers/test_result_transforms.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/result_transform.py backend/app/routers/result_transforms.py backend/app/main.py backend/tests/routers/test_result_transforms.py
git commit -m "feat(transforms): preview/apply/catalog API (#120)"
```

---

### Task 8: Frontend — types + API client

**Files:**
- Create: `frontend/src/types/resultTransform.ts`
- Create: `frontend/src/api/resultTransforms.ts`
- Test: `frontend/src/api/resultTransforms.test.ts`

**Interfaces:**
- Produces: `getTransformCatalog()`, `previewTransform(projectId, body)`, `applyTransform(projectId, body)` returning typed responses; `TransformCatalogItem`, `TransformPreview`, `MergeRecordsConfig` types.

- [ ] **Step 1: Write the failing test** (mock `apiClient`, assert URL + payload)

```typescript
// frontend/src/api/resultTransforms.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import apiClient from './client'
import { previewTransform } from './resultTransforms'

vi.mock('./client')

describe('resultTransforms api', () => {
  beforeEach(() => vi.clearAllMocks())

  it('posts preview to the project-scoped endpoint', async () => {
    ;(apiClient.post as any).mockResolvedValue({ data: { rows: [], flags: [] } })
    await previewTransform('p1', {
      sourceResultIds: ['r1'], transformType: 'merge_records', config: {},
    })
    expect(apiClient.post).toHaveBeenCalledWith(
      '/projects/p1/result-transforms/preview',
      { sourceResultIds: ['r1'], transformType: 'merge_records', config: {} },
    )
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `frontend/`): `npx vitest run src/api/resultTransforms.test.ts`
Expected: FAIL — module not found.

- [ ] **Step 3: Write types + client**

```typescript
// frontend/src/types/resultTransform.ts
export interface TransformCatalogItem {
  transform_type: string
  name: string
  description: string
  config_schema: Record<string, unknown>
}
export interface TransformPreviewRequest {
  sourceResultIds: string[]
  transformType: string
  config: Record<string, unknown>
}
export interface TransformPreview {
  rows: Record<string, unknown>[]
  flags: { rowIndex: number; flag: string }[]
}
```

```typescript
// frontend/src/api/resultTransforms.ts
import apiClient from './client'
import type {
  TransformCatalogItem, TransformPreviewRequest, TransformPreview,
} from '@/types/resultTransform'
import type { ExtractionResult } from '@/types/extraction'

export async function getTransformCatalog(): Promise<TransformCatalogItem[]> {
  const { data } = await apiClient.get<TransformCatalogItem[]>('/result-transforms/catalog')
  return data
}

export async function previewTransform(
  projectId: string, body: TransformPreviewRequest,
): Promise<TransformPreview> {
  const { data } = await apiClient.post<TransformPreview>(
    `/projects/${projectId}/result-transforms/preview`, body)
  return data
}

export async function applyTransform(
  projectId: string, body: TransformPreviewRequest & { targetSchemaId?: string },
): Promise<ExtractionResult> {
  const { data } = await apiClient.post<ExtractionResult>(
    `/projects/${projectId}/result-transforms/apply`, body)
  return data
}
```

- [ ] **Step 4: Run test to verify it passes**

Run (from `frontend/`): `npx vitest run src/api/resultTransforms.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types/resultTransform.ts frontend/src/api/resultTransforms.ts frontend/src/api/resultTransforms.test.ts
git commit -m "feat(transforms): frontend types + api client (#120)"
```

---

### Task 9: Frontend — `useResultTransform` hook

**Files:**
- Create: `frontend/src/hooks/useResultTransform.ts`
- Test: `frontend/src/hooks/useResultTransform.test.ts`

**Interfaces:**
- Produces: `useResultTransform(projectId)` → `{ catalog, preview, apply, previewData, flags, isLoading, error }`. `preview(body)` calls `previewTransform`; `apply(body)` calls `applyTransform`. Mirror an existing hook's structure (see `frontend/src/hooks/useExtractionEval.ts`).

- [ ] **Step 1: Write the failing test** (render hook, call `preview`, assert `previewData` populates — mock the api module)

```typescript
// frontend/src/hooks/useResultTransform.test.ts
import { describe, it, expect, vi } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import * as api from '@/api/resultTransforms'
import { useResultTransform } from './useResultTransform'

vi.mock('@/api/resultTransforms')

it('populates previewData after preview()', async () => {
  ;(api.previewTransform as any).mockResolvedValue({ rows: [{ sku: 'X' }], flags: [] })
  const { result } = renderHook(() => useResultTransform('p1'))
  await act(async () => {
    await result.current.preview({ sourceResultIds: ['r1'], transformType: 'merge_records', config: {} })
  })
  await waitFor(() => expect(result.current.previewData?.rows).toHaveLength(1))
})
```

- [ ] **Step 2: Run test, see it fail; Step 3: implement the hook; Step 4: run test, see it pass.**

Run (from `frontend/`): `npx vitest run src/hooks/useResultTransform.test.ts`

```typescript
// frontend/src/hooks/useResultTransform.ts
import { useState, useCallback } from 'react'
import { previewTransform, applyTransform, getTransformCatalog } from '@/api/resultTransforms'
import type { TransformPreview, TransformPreviewRequest, TransformCatalogItem } from '@/types/resultTransform'

export function useResultTransform(projectId: string) {
  const [catalog, setCatalog] = useState<TransformCatalogItem[]>([])
  const [previewData, setPreviewData] = useState<TransformPreview | null>(null)
  const [isLoading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadCatalog = useCallback(async () => setCatalog(await getTransformCatalog()), [])
  const preview = useCallback(async (body: TransformPreviewRequest) => {
    setLoading(true); setError(null)
    try { setPreviewData(await previewTransform(projectId, body)) }
    catch (e) { setError(String(e)) } finally { setLoading(false) }
  }, [projectId])
  const apply = useCallback(
    (body: TransformPreviewRequest & { targetSchemaId?: string }) => applyTransform(projectId, body),
    [projectId])

  return { catalog, loadCatalog, preview, apply, previewData,
           flags: previewData?.flags ?? [], isLoading, error }
}
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/hooks/useResultTransform.ts frontend/src/hooks/useResultTransform.test.ts
git commit -m "feat(transforms): useResultTransform hook (#120)"
```

---

### Task 10: Frontend — config form + preview table + viewer action

**Files:**
- Create: `frontend/src/components/extraction/transforms/MergeRecordsConfigForm.tsx`
- Create: `frontend/src/components/extraction/transforms/TransformPreviewTable.tsx`
- Modify: `frontend/src/components/extraction/ExtractionResultViewer.tsx` (add a `Transform ▾` action that opens the config form + preview + apply)
- Test: `frontend/src/components/extraction/transforms/TransformPreviewTable.test.tsx`

**Interfaces:**
- `MergeRecordsConfigForm`: props `{ value, onChange }` editing `{ groupBy, keyNormalize, spine, conflict, onGroupWithoutSpine }`; the user picks group key field + identity field via inputs/selects over the result's column names.
- `TransformPreviewTable`: props `{ rows, flags }` — renders a grid with a flag chip per flagged row (`conflict`, `no_specs`, `unjoinable`).

- [ ] **Step 1: Write the failing test** (render `TransformPreviewTable` with one flagged row; assert a flag chip shows)

```tsx
// frontend/src/components/extraction/transforms/TransformPreviewTable.test.tsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { TransformPreviewTable } from './TransformPreviewTable'

it('renders a flag chip for a flagged row', () => {
  render(<TransformPreviewTable
    rows={[{ sku: 'X', modelName: 'GP-40' }]}
    flags={[{ rowIndex: 0, flag: 'no_specs' }]} />)
  expect(screen.getByText('no_specs')).toBeInTheDocument()
})
```

- [ ] **Step 2: Run test (fail) → Step 3: implement → Step 4: run (pass).**

Run (from `frontend/`): `npx vitest run src/components/extraction/transforms/TransformPreviewTable.test.tsx`

```tsx
// frontend/src/components/extraction/transforms/TransformPreviewTable.tsx
import { Badge } from '@/components/ui/badge'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'

interface Props {
  rows: Record<string, unknown>[]
  flags: { rowIndex: number; flag: string }[]
}

export function TransformPreviewTable({ rows, flags }: Props) {
  const cols = Array.from(
    new Set(rows.flatMap((r) => Object.keys(r).filter((k) => k !== '_provenance'))),
  )
  const flagsByRow = flags.reduce<Record<number, string[]>>((acc, f) => {
    ;(acc[f.rowIndex] ??= []).push(f.flag); return acc
  }, {})
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Flags</TableHead>
          {cols.map((c) => <TableHead key={c}>{c}</TableHead>)}
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((row, i) => (
          <TableRow key={i}>
            <TableCell className="space-x-1">
              {(flagsByRow[i] ?? []).map((f) => (
                <Badge key={f} variant="outline">{f}</Badge>
              ))}
            </TableCell>
            {cols.map((c) => <TableCell key={c}>{String(row[c] ?? '')}</TableCell>)}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
```

> `MergeRecordsConfigForm` and the `ExtractionResultViewer` `Transform ▾` wiring follow the existing component idiom (shadcn `Select`/`Input`, a `DropdownMenu` action that opens a `Dialog` hosting the form → `Preview` button calls `preview` → `TransformPreviewTable` → `Apply` calls `apply` then navigates to the returned result id). Verify the shadcn `badge`/`table` components exist under `frontend/src/components/ui/`; add via the shadcn MCP if missing.

- [ ] **Step 5: Lint + build + commit**

Run (from `frontend/`): `npm run lint` then `npm run build`
Expected: clean.

```bash
git add frontend/src/components/extraction/transforms/ frontend/src/components/extraction/ExtractionResultViewer.tsx
git commit -m "feat(transforms): merge config form, preview table, viewer action (#120)"
```

---

### Task 11: End-to-end verification

- [ ] **Step 1: Backend suite**

Run: `uv run --directory backend python -m pytest -o "addopts=" tests/services/extraction/transforms tests/services/test_result_transform_service.py tests/routers/test_result_transforms.py -v`
Expected: all PASS.

- [ ] **Step 2: Frontend suite + build**

Run (from `frontend/`): `npx vitest run` then `npm run build`
Expected: all PASS, clean build.

- [ ] **Step 3: Manual smoke (Docker, per CLAUDE.md local testing)**

Build frontend, start the local stack, run a single-shot extraction producing mixed spec/price rows, open the result, `Transform ▾ → Merge records`, set group key = `modelName` (firstTokenOnly + option letters `B,D,S,C`), identity field = `sku`, Preview → confirm GP-40 collapses to 4 rows, Apply → land on the derived result.

- [ ] **Step 4: Update the issue**

```bash
gh issue comment 120 --repo asanyaga/rag-admin --body "Slice 1 implemented: merge_records end-to-end (port, registry, preview/apply API, viewer action). Backend + frontend suites green."
```

---

## Self-Review Notes

- **Spec coverage:** AC1 (port/registry) → T2/T4; AC2 (merge_records config) → T3; AC3 (lineage, non-destructive) → T6; AC4 (preview no-persist) → T6/T7; AC5 (CSV fixture) → T5; AC6 (API) → T7; AC7–8 (frontend) → T8–T10. Provenance preserved → T3.
- **Open verifications for the implementer:** confirm `ExtractionResultResponse.from_orm_model` signature; confirm `async_client`/`auth_headers` fixtures in `backend/tests/conftest.py`; confirm shadcn `badge`/`table`/`dialog`/`dropdown-menu` present under `components/ui/`.
- **Deliberately deferred to later slices:** `derive_field`/aliases (`UX-50L→UX-50 LITE`), `broadcast_field`, `strip_records`/`project_to_schema`, cross-run multi-input UX, lineage panel/branch, source coloring / merge inspector / provenance popover, export wiring.
