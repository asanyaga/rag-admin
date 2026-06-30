# fitz_tables Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Register `fitz_tables` as a first-class pipeline table tool using PyMuPDF's `page.find_tables()`, generalize the runner/merger from hardcoded camelot references to a single "table tool" slot, and expose the new tool in the UI.

**Architecture:** `FitzTablesTool` follows the same `LocalTool` protocol as `CamelotTool` — it takes `FitzTablesConfig` + `page_meta`, runs `page.find_tables()` per page, and emits `BlockRole.TABLE` blocks with full CDM `Table` objects. The merger parameter `camelot_result` becomes `table_result` and the raw_output key uses `table_result.tool_id` dynamically. The runner detects any `TABLE_TOOL_IDS` entry instead of matching `"camelot"` by name. Mutual exclusion (only one table tool per config) is enforced at `build_pipeline_config` time.

**Tech Stack:** Python 3.12, PyMuPDF 1.27 (`fitz`), Pydantic v2, pytest-asyncio; React 18, TypeScript, shadcn/ui (Select, Collapsible, Input, Label).

## Global Constraints

- PyMuPDF already installed (`fitz` / `pymupdf`). No new Python dependencies.
- `FitzTablesTool` must implement the `LocalTool` protocol: `tool_id: str` class attr, `run(pdf_path, pages) -> ToolResult`.
- Bbox normalization: fitz uses top-left origin in PDF points — divide `x / width`, `y / height` directly. **No y-flip** (unlike CamelotTool).
- Only one table tool (`camelot` or `fitz_tables`) may appear in a pipeline config. Both together → `ValueError`.
- All test commands: `uv run --directory backend python -m pytest <path> -v -o "addopts="`
- Frontend test command: `npm --prefix frontend run test -- --run`

---

## File Map

| File | Create / Modify |
|------|----------------|
| `backend/app/cdm/adapters/local_pipeline/merger.py` | Modify — rename `camelot_result` → `table_result`, dynamic raw_output key |
| `backend/app/cdm/adapters/local_pipeline/config.py` | Modify — add `FitzTablesConfig`, `TABLE_TOOL_IDS`, register in `TOOL_REGISTRY`, mutual-exclusion guard, instantiate `FitzTablesTool` |
| `backend/app/cdm/adapters/local_pipeline/tools/fitz_tables_tool.py` | **Create** — `FitzTablesTool` class |
| `backend/app/services/parsing/local_pipeline_runner.py` | Modify — `TABLE_TOOL_IDS` detection, rename `camelot_result` → `table_result` |
| `backend/app/cdm/adapters/local_pipeline/probe.py` | Modify — `_recommend()` returns `fitz_tables` instead of `camelot` |
| `backend/tests/cdm/adapters/local_pipeline/test_merger.py` | Modify — add dynamic-key regression test |
| `backend/tests/cdm/adapters/local_pipeline/test_config.py` | Modify — add `FitzTablesConfig` + mutual-exclusion tests |
| `backend/tests/cdm/adapters/local_pipeline/test_fitz_tables_tool.py` | **Create** — full `FitzTablesTool` test suite |
| `backend/tests/services/parsing/test_local_pipeline_runner.py` | Modify — add fitz_tables end-to-end test |
| `backend/tests/cdm/adapters/local_pipeline/test_probe.py` | Modify — add `_recommend` test for fitz_tables |
| `frontend/src/components/documents/parser-configs/LocalPipelineConfig.tsx` | Modify — replace camelot checkbox with table-tool selector + `FitzTablesConfigPanel` |
| `frontend/src/components/documents/parser-configs/LocalPipelineConfig.test.tsx` | Modify — update camelot-checkbox tests, add fitz_tables tests |

---

### Task 1: Merger generalization

**Files:**
- Modify: `backend/app/cdm/adapters/local_pipeline/merger.py`
- Modify: `backend/tests/cdm/adapters/local_pipeline/test_merger.py`

**Interfaces:**
- Produces: `merge(fitz_result: ToolResult, table_result: ToolResult, *, source_document_id: str, eviction_overlap_threshold: float = 0.5) -> MergeResult` — later tasks call this with any table tool result.

- [ ] **Step 1: Write the failing test for the dynamic raw_output key**

Add to `backend/tests/cdm/adapters/local_pipeline/test_merger.py`:

```python
def test_merge_raw_output_key_uses_table_result_tool_id():
    """raw_output["tools"] key is the table tool's tool_id, not the string "camelot"."""
    block = Block(
        id="fitz_tables:0:0", role=BlockRole.TABLE, native_type="table",
        page_index=0, bbox=_bbox(0.1, 0.5, 0.9, 0.7),
    )
    fitz_tables_result = ToolResult(
        tool_id="fitz_tables", blocks=[block], page_meta={},
        raw={"tables": []}, native_by_block={"fitz_tables:0:0": {"rows": 2}},
    )
    result = merge(
        _fitz_result(), fitz_tables_result,
        source_document_id="doc1", eviction_overlap_threshold=0.5,
    )
    assert "fitz_tables" in result.raw_output["tools"]
    assert "camelot" not in result.raw_output["tools"]
```

- [ ] **Step 2: Run to confirm it fails**

```
uv run --directory backend python -m pytest tests/cdm/adapters/local_pipeline/test_merger.py::test_merge_raw_output_key_uses_table_result_tool_id -v -o "addopts="
```

Expected: FAIL — `merge()` currently has `camelot_result` parameter and hardcoded `"camelot"` key.

- [ ] **Step 3: Rewrite `merger.py`**

Replace the entire content of `backend/app/cdm/adapters/local_pipeline/merger.py`:

```python
"""Merge tool outputs into a final ordered block list + an audit raw_output.

Eviction rule: later-declared tools win. A fitz PARAGRAPH block that overlaps
a table block beyond the threshold is evicted (logged, not deleted).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from app.cdm.adapters.local_pipeline.tools.base import ToolResult
from app.cdm.models import BBox, Block


def _area(b: BBox) -> float:
    return max(0.0, b.x1 - b.x0) * max(0.0, b.y1 - b.y0)


def overlap_fraction(table_bbox: BBox, fitz_bbox: BBox) -> float:
    """Intersection area / area(fitz_bbox), in normalized coords."""
    fitz_area = _area(fitz_bbox)
    if fitz_area == 0.0:
        return 0.0
    ix0 = max(table_bbox.x0, fitz_bbox.x0)
    iy0 = max(table_bbox.y0, fitz_bbox.y0)
    ix1 = min(table_bbox.x1, fitz_bbox.x1)
    iy1 = min(table_bbox.y1, fitz_bbox.y1)
    inter = max(0.0, ix1 - ix0) * max(0.0, iy1 - iy0)
    return inter / fitz_area


@dataclass
class MergeResult:
    blocks: List[Block]
    raw_output: Dict[str, Any]


def _sort_key(block: Block) -> Tuple[float, float]:
    if block.bbox is None:
        return (1e9, 1e9)
    return (block.bbox.y0, block.bbox.x0)


def merge(
    fitz_result: ToolResult,
    table_result: ToolResult,
    *,
    source_document_id: str,
    eviction_overlap_threshold: float = 0.5,
) -> MergeResult:
    table_blocks = list(table_result.blocks)

    # 1. Eviction pass — fitz blocks overlapping any table beyond threshold.
    evicted_ids = set()
    eviction_winner: Dict[str, str] = {}
    eviction_overlap: Dict[str, float] = {}
    for fb in fitz_result.blocks:
        if fb.bbox is None:
            continue
        for tb in table_blocks:
            if tb.page_index != fb.page_index or tb.bbox is None:
                continue
            frac = overlap_fraction(tb.bbox, fb.bbox)
            if frac > eviction_overlap_threshold:
                evicted_ids.add(fb.id)
                eviction_winner[fb.id] = tb.id
                eviction_overlap[fb.id] = frac
                break

    surviving_fitz = [b for b in fitz_result.blocks if b.id not in evicted_ids]
    combined = surviving_fitz + table_blocks

    # 2. Mint final ids + reading order, grouped per page.
    by_page: Dict[int, List[Block]] = {}
    for b in combined:
        by_page.setdefault(b.page_index, []).append(b)

    prov_to_final: Dict[str, str] = {}
    final_blocks: List[Block] = []
    for page_index in sorted(by_page.keys()):
        ordered = sorted(by_page[page_index], key=_sort_key)
        for reading_order, block in enumerate(ordered):
            final_id = f"{source_document_id}:{page_index}:{reading_order}"
            prov_to_final[block.id] = final_id
            final_blocks.append(
                block.model_copy(update={"id": final_id, "reading_order": reading_order})
            )

    # 3. Build raw_output (audit trail).
    def _block_map(result: ToolResult) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for prov_id, native in result.native_by_block.items():
            final_id = prov_to_final.get(prov_id)
            if final_id is not None:
                out[final_id] = native
        return out

    evicted_records = [
        {
            "block_id": prov_id,
            "tool": "fitz",
            "reason": "spatial_overlap",
            "won_by": prov_to_final[eviction_winner[prov_id]],
            "overlap_fraction": eviction_overlap[prov_id],
            "raw_block": fitz_result.native_by_block.get(prov_id),
        }
        for prov_id in evicted_ids
    ]

    raw_output = {
        "tools": {
            "fitz": {"raw": fitz_result.raw, "block_map": _block_map(fitz_result)},
            table_result.tool_id: {
                "raw": table_result.raw,
                "block_map": _block_map(table_result),
            },
        },
        "evicted": evicted_records,
    }

    return MergeResult(blocks=final_blocks, raw_output=raw_output)
```

- [ ] **Step 4: Run all merger tests**

```
uv run --directory backend python -m pytest tests/cdm/adapters/local_pipeline/test_merger.py -v -o "addopts="
```

Expected: all PASS. The existing `test_merge_raw_output_has_tool_block_maps` still passes because `_camelot_result()` has `tool_id="camelot"` — the dynamic key is still `"camelot"`.

- [ ] **Step 5: Commit**

```
git add backend/app/cdm/adapters/local_pipeline/merger.py backend/tests/cdm/adapters/local_pipeline/test_merger.py
git commit -m "refactor(merger): generalize camelot_result → table_result with dynamic raw_output key"
```

---

### Task 2: FitzTablesConfig + FitzTablesTool + TOOL_REGISTRY + mutual exclusion

**Files:**
- Modify: `backend/app/cdm/adapters/local_pipeline/config.py`
- Create: `backend/app/cdm/adapters/local_pipeline/tools/fitz_tables_tool.py`
- Modify: `backend/tests/cdm/adapters/local_pipeline/test_config.py`
- Create: `backend/tests/cdm/adapters/local_pipeline/test_fitz_tables_tool.py`

**Interfaces:**
- Produces: `FitzTablesConfig` — Pydantic model, importable from `config.py`
- Produces: `TABLE_TOOL_IDS: frozenset[str]` — importable from `config.py`
- Produces: `FitzTablesTool(config: FitzTablesConfig, page_meta: Dict[int, PageMeta])` — `tool_id = "fitz_tables"`, `run(pdf_path, pages) -> ToolResult`
- Consumes (from Task 1): `merge(fitz_result, table_result, ...)` — no change needed here

- [ ] **Step 1: Write config tests**

Add to `backend/tests/cdm/adapters/local_pipeline/test_config.py`:

```python
from app.cdm.adapters.local_pipeline.config import (
    CamelotConfig,
    FitzConfig,
    FitzTablesConfig,
    LocalPipelineConfig,
    TABLE_TOOL_IDS,
    build_pipeline_config,
)


def test_fitz_tables_config_defaults():
    c = FitzTablesConfig()
    assert c.vertical_strategy == "lines_strict"
    assert c.horizontal_strategy == "lines_strict"
    assert c.snap_tolerance == 3.0
    assert c.join_tolerance == 3.0
    assert c.edge_min_length == 3.0
    assert c.min_words_vertical == 3
    assert c.min_words_horizontal == 1
    assert c.intersection_tolerance == 3.0
    assert c.text_tolerance == 3.0
    # per-axis overrides default to None
    assert c.snap_x_tolerance is None
    assert c.snap_y_tolerance is None
    assert c.join_x_tolerance is None
    assert c.join_y_tolerance is None
    assert c.intersection_x_tolerance is None
    assert c.intersection_y_tolerance is None
    assert c.text_x_tolerance is None
    assert c.text_y_tolerance is None


def test_table_tool_ids_contains_camelot_and_fitz_tables():
    assert "camelot" in TABLE_TOOL_IDS
    assert "fitz_tables" in TABLE_TOOL_IDS


def test_build_pipeline_config_rejects_multiple_table_tools():
    with pytest.raises(ValueError, match="only one table tool allowed"):
        build_pipeline_config({
            "tools": [
                {"tool_id": "fitz", "config": {}},
                {"tool_id": "fitz_tables", "config": {}},
                {"tool_id": "camelot", "config": {}},
            ],
        })


def test_build_pipeline_config_fitz_and_fitz_tables():
    cfg = build_pipeline_config({
        "tools": [
            {"tool_id": "fitz", "config": {}},
            {"tool_id": "fitz_tables", "config": {}},
        ],
    })
    assert [t.tool_id for t in cfg.tools] == ["fitz", "fitz_tables"]
```

Also add `import pytest` at the top of the file if not already present.

- [ ] **Step 2: Run to confirm failures**

```
uv run --directory backend python -m pytest tests/cdm/adapters/local_pipeline/test_config.py -k "fitz_tables or table_tool or multiple_table" -v -o "addopts="
```

Expected: FAIL — `FitzTablesConfig`, `TABLE_TOOL_IDS` not yet defined.

- [ ] **Step 3: Update `config.py`**

Replace the full content of `backend/app/cdm/adapters/local_pipeline/config.py`:

```python
"""Configs for the local pipeline tools and the pipeline itself."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel

from app.cdm.adapters.local_pipeline.tools.base import LocalTool, PageMeta


class FitzConfig(BaseModel):
    min_chars_threshold: int = 10
    include_images: bool = True
    span_detail: bool = False


class CamelotConfig(BaseModel):
    flavor: Literal["lattice", "stream"] = "lattice"
    edge_tol: int = 50
    row_tol: int = 2
    copy_text: List[str] = []


class FitzTablesConfig(BaseModel):
    vertical_strategy: str = "lines_strict"
    horizontal_strategy: str = "lines_strict"
    snap_tolerance: float = 3.0
    snap_x_tolerance: Optional[float] = None
    snap_y_tolerance: Optional[float] = None
    join_tolerance: float = 3.0
    join_x_tolerance: Optional[float] = None
    join_y_tolerance: Optional[float] = None
    edge_min_length: float = 3.0
    min_words_vertical: int = 3
    min_words_horizontal: int = 1
    intersection_tolerance: float = 3.0
    intersection_x_tolerance: Optional[float] = None
    intersection_y_tolerance: Optional[float] = None
    text_tolerance: float = 3.0
    text_x_tolerance: Optional[float] = None
    text_y_tolerance: Optional[float] = None


TABLE_TOOL_IDS: frozenset[str] = frozenset({"camelot", "fitz_tables"})

TOOL_REGISTRY: Dict[str, type[BaseModel]] = {
    "fitz": FitzConfig,
    "camelot": CamelotConfig,
    "fitz_tables": FitzTablesConfig,
}


@dataclass
class LocalPipelineConfig:
    """Runtime pipeline config — ordered tools (later = higher priority)."""
    tools: List[LocalTool]
    eviction_overlap_threshold: float = 0.5


def build_pipeline_config(
    config: Dict[str, Any],
    page_meta: Optional[Dict[int, PageMeta]] = None,
) -> LocalPipelineConfig:
    from app.cdm.adapters.local_pipeline.tools.camelot_tool import CamelotTool
    from app.cdm.adapters.local_pipeline.tools.fitz_tables_tool import FitzTablesTool
    from app.cdm.adapters.local_pipeline.tools.fitz_tool import FitzTool

    tools_cfg = config.get("tools", [])

    table_ids_present = [
        e.get("tool_id") for e in tools_cfg
        if e.get("tool_id") in TABLE_TOOL_IDS
    ]
    if len(table_ids_present) > 1:
        raise ValueError(
            f"only one table tool allowed per pipeline, got: {table_ids_present}"
        )

    tools: List[LocalTool] = []
    for entry in tools_cfg:
        tool_id = entry.get("tool_id")
        raw_cfg = entry.get("config", {}) or {}
        cfg_cls = TOOL_REGISTRY.get(tool_id)
        if cfg_cls is None:
            raise ValueError(f"unknown tool: {tool_id!r}")
        tool_cfg = cfg_cls.model_validate(raw_cfg)
        if tool_id == "fitz":
            tools.append(FitzTool(config=tool_cfg))  # type: ignore[arg-type]
        elif tool_id == "camelot":
            tools.append(CamelotTool(config=tool_cfg, page_meta=page_meta or {}))  # type: ignore[arg-type]
        elif tool_id == "fitz_tables":
            tools.append(FitzTablesTool(config=tool_cfg, page_meta=page_meta or {}))  # type: ignore[arg-type]

    threshold = config.get("eviction_overlap_threshold", 0.5)
    return LocalPipelineConfig(tools=tools, eviction_overlap_threshold=threshold)
```

- [ ] **Step 4: Write the FitzTablesTool tests**

Create `backend/tests/cdm/adapters/local_pipeline/test_fitz_tables_tool.py`:

```python
"""Tests for FitzTablesTool — table extraction via page.find_tables()."""
from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from app.cdm.adapters.local_pipeline.config import FitzTablesConfig
from app.cdm.adapters.local_pipeline.tools.base import PageMeta
from app.cdm.adapters.local_pipeline.tools.fitz_tables_tool import FitzTablesTool
from app.cdm.models import BlockRole


def _make_table_pdf(path: Path) -> None:
    """Write a one-page PDF with a drawn 2-column × 2-row grid table."""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    col_x = [72, 236, 400]
    row_y = [100, 150, 200]
    for x in col_x:
        page.draw_line(
            fitz.Point(x, row_y[0]), fitz.Point(x, row_y[-1]),
            color=(0, 0, 0), width=1,
        )
    for y in row_y:
        page.draw_line(
            fitz.Point(col_x[0], y), fitz.Point(col_x[-1], y),
            color=(0, 0, 0), width=1,
        )
    page.insert_text(fitz.Point(80, 135), "Name", fontsize=11)
    page.insert_text(fitz.Point(244, 135), "Value", fontsize=11)
    page.insert_text(fitz.Point(80, 185), "alpha", fontsize=11)
    page.insert_text(fitz.Point(244, 185), "1", fontsize=11)
    doc.save(str(path))
    doc.close()


@pytest.fixture()
def table_pdf(tmp_path: Path) -> Path:
    p = tmp_path / "table.pdf"
    _make_table_pdf(p)
    return p


@pytest.fixture()
def page_meta() -> dict:
    return {0: PageMeta(index=0, width=595.0, height=842.0)}


def test_fitz_tables_tool_id():
    assert FitzTablesTool().tool_id == "fitz_tables"


def test_fitz_tables_emits_table_blocks(table_pdf, page_meta):
    result = FitzTablesTool(page_meta=page_meta).run(table_pdf)
    tables = [b for b in result.blocks if b.role == BlockRole.TABLE]
    assert len(tables) >= 1


def test_fitz_tables_block_has_normalized_bbox(table_pdf, page_meta):
    result = FitzTablesTool(page_meta=page_meta).run(table_pdf)
    b = next(b for b in result.blocks if b.role == BlockRole.TABLE)
    assert b.bbox is not None
    for v in (b.bbox.x0, b.bbox.y0, b.bbox.x1, b.bbox.y1):
        assert 0.0 <= v <= 1.0
    assert b.bbox.source_space == "pdf_points"


def test_fitz_tables_bbox_no_y_flip(table_pdf, page_meta):
    """Coordinates use top-left origin — source y0 < source y1 (no y-flip)."""
    result = FitzTablesTool(page_meta=page_meta).run(table_pdf)
    b = next(b for b in result.blocks if b.role == BlockRole.TABLE)
    assert b.bbox is not None
    assert b.bbox.source_coords is not None
    x0, y0, x1, y1 = b.bbox.source_coords
    assert y0 < y1  # top-left origin: y increases downward


def test_fitz_tables_block_has_table_cdm(table_pdf, page_meta):
    result = FitzTablesTool(page_meta=page_meta).run(table_pdf)
    b = next(b for b in result.blocks if b.role == BlockRole.TABLE)
    assert b.table is not None
    assert b.table.rows >= 2
    assert b.table.cols >= 2


def test_fitz_tables_cell_text(table_pdf, page_meta):
    result = FitzTablesTool(page_meta=page_meta).run(table_pdf)
    b = next(b for b in result.blocks if b.role == BlockRole.TABLE)
    all_text = " ".join(c.text for c in b.table.cells)
    assert "Name" in all_text or "Value" in all_text


def test_fitz_tables_html_and_markdown(table_pdf, page_meta):
    result = FitzTablesTool(page_meta=page_meta).run(table_pdf)
    b = next(b for b in result.blocks if b.role == BlockRole.TABLE)
    assert b.html is not None and "<table>" in b.html
    assert b.markdown is not None and "|" in b.markdown


def test_fitz_tables_block_id_format(table_pdf, page_meta):
    result = FitzTablesTool(page_meta=page_meta).run(table_pdf)
    b = next(b for b in result.blocks if b.role == BlockRole.TABLE)
    assert b.id.startswith("fitz_tables:0:")


def test_fitz_tables_duration_ms_is_positive(table_pdf, page_meta):
    result = FitzTablesTool(page_meta=page_meta).run(table_pdf)
    assert result.duration_ms >= 0


def test_fitz_tables_native_by_block_keyed_by_prov_id(table_pdf, page_meta):
    result = FitzTablesTool(page_meta=page_meta).run(table_pdf)
    b = next(b for b in result.blocks if b.role == BlockRole.TABLE)
    assert b.id in result.native_by_block


def test_fitz_tables_custom_snap_tolerance_accepted(table_pdf, page_meta):
    cfg = FitzTablesConfig(snap_tolerance=5.0)
    result = FitzTablesTool(config=cfg, page_meta=page_meta).run(table_pdf)
    assert result.tool_id == "fitz_tables"


def test_fitz_tables_empty_pdf_emits_no_table_blocks(tmp_path):
    pdf = tmp_path / "empty.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.save(str(pdf))
    doc.close()
    result = FitzTablesTool().run(pdf)
    assert not any(b.role == BlockRole.TABLE for b in result.blocks)
```

- [ ] **Step 5: Run tool tests to confirm they fail**

```
uv run --directory backend python -m pytest tests/cdm/adapters/local_pipeline/test_fitz_tables_tool.py -v -o "addopts="
```

Expected: FAIL — `fitz_tables_tool` module not found.

- [ ] **Step 6: Create `fitz_tables_tool.py`**

Create `backend/app/cdm/adapters/local_pipeline/tools/fitz_tables_tool.py`:

```python
"""FitzTablesTool — table extraction via PyMuPDF page.find_tables(). Emits CDM TABLE Blocks."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import fitz

from app.cdm.adapters.local_pipeline.config import FitzTablesConfig
from app.cdm.adapters.local_pipeline.tools.base import PageMeta, ToolResult, clamp01
from app.cdm.models import BBox, Block, BlockRole, Cell, Table


def _html(extracted: List[List[Optional[str]]]) -> str:
    rows_html = "".join(
        "<tr>" + "".join(f"<td>{c or ''}</td>" for c in row) + "</tr>"
        for row in extracted
    )
    return f"<table>{rows_html}</table>"


def _markdown(extracted: List[List[Optional[str]]]) -> str:
    if not extracted:
        return ""
    header = "| " + " | ".join(str(c or "") for c in extracted[0]) + " |"
    sep = "| " + " | ".join("---" for _ in extracted[0]) + " |"
    body_rows = [
        "| " + " | ".join(str(c or "") for c in row) + " |"
        for row in extracted[1:]
    ]
    return "\n".join([header, sep] + body_rows)


def _plain_text(extracted: List[List[Optional[str]]]) -> str:
    return "\n".join(
        " | ".join(str(c or "") for c in row) for row in extracted
    )


class FitzTablesTool:
    tool_id = "fitz_tables"

    def __init__(
        self,
        config: Optional[FitzTablesConfig] = None,
        page_meta: Optional[Dict[int, PageMeta]] = None,
    ) -> None:
        self.config = config or FitzTablesConfig()
        self.page_meta = page_meta or {}

    def _config_kwargs(self) -> Dict[str, Any]:
        c = self.config
        kwargs: Dict[str, Any] = {
            "vertical_strategy": c.vertical_strategy,
            "horizontal_strategy": c.horizontal_strategy,
            "snap_tolerance": c.snap_tolerance,
            "join_tolerance": c.join_tolerance,
            "edge_min_length": c.edge_min_length,
            "min_words_vertical": c.min_words_vertical,
            "min_words_horizontal": c.min_words_horizontal,
            "intersection_tolerance": c.intersection_tolerance,
            "text_tolerance": c.text_tolerance,
        }
        for key in (
            "snap_x_tolerance", "snap_y_tolerance",
            "join_x_tolerance", "join_y_tolerance",
            "intersection_x_tolerance", "intersection_y_tolerance",
            "text_x_tolerance", "text_y_tolerance",
        ):
            val = getattr(c, key)
            if val is not None:
                kwargs[key] = val
        return kwargs

    def _norm_bbox(self, raw_bbox: Any, pm: PageMeta) -> BBox:
        x0, y0, x1, y1 = raw_bbox  # fitz top-left origin, PDF points — no y-flip
        return BBox(
            x0=clamp01(x0 / pm.width),
            y0=clamp01(y0 / pm.height),
            x1=clamp01(x1 / pm.width),
            y1=clamp01(y1 / pm.height),
            source_space="pdf_points",
            source_coords=(float(x0), float(y0), float(x1), float(y1)),
        )

    def _build_cells(
        self, table: Any, pm: Optional[PageMeta], extracted: List[List[Optional[str]]]
    ) -> List[Cell]:
        cells: List[Cell] = []
        row_count = table.row_count
        col_count = table.col_count
        raw_cells = table.cells  # list of Rect|None in row-major order
        for r in range(row_count):
            for c in range(col_count):
                idx = r * col_count + c
                text = ""
                if r < len(extracted) and c < len(extracted[r]):
                    text = extracted[r][c] or ""
                bbox = None
                if pm is not None and idx < len(raw_cells) and raw_cells[idx] is not None:
                    bbox = self._norm_bbox(raw_cells[idx], pm)
                cells.append(Cell(row=r, col=c, text=text.strip(), bbox=bbox))
        return cells

    def run(self, pdf_path: Path, pages: Optional[List[int]] = None) -> ToolResult:
        t0 = time.perf_counter()
        blocks: List[Block] = []
        native_by_block: Dict[str, Any] = {}
        warnings: List[str] = []
        kwargs = self._config_kwargs()

        doc = fitz.open(str(pdf_path))
        try:
            for i in range(len(doc)):
                if pages is not None and i not in pages:
                    continue
                page = doc[i]
                pm = self.page_meta.get(i)
                if pm is None:
                    warnings.append(f"page {i}: no page_meta; cell bboxes will be omitted")

                try:
                    finder = page.find_tables(**kwargs)
                    page_tables = finder.tables
                except Exception as exc:
                    warnings.append(f"page {i}: find_tables failed — {exc}")
                    continue

                for seq, table in enumerate(page_tables):
                    extracted = table.extract()
                    row_count = table.row_count
                    col_count = table.col_count
                    cells = self._build_cells(table, pm, extracted)
                    html = _html(extracted)
                    md = _markdown(extracted)
                    text = _plain_text(extracted)
                    cdm_table = Table(
                        rows=row_count,
                        cols=col_count,
                        cells=cells,
                        html=html,
                        markdown=md,
                    )
                    bbox = self._norm_bbox(table.bbox, pm) if pm is not None else None
                    prov_id = f"fitz_tables:{i}:{seq}"
                    block = Block(
                        id=prov_id,
                        role=BlockRole.TABLE,
                        native_type="table",
                        text=text,
                        markdown=md,
                        html=html,
                        page_index=i,
                        bbox=bbox,
                        table=cdm_table,
                        parser_extras={
                            "fitz_tables_row_count": row_count,
                            "fitz_tables_col_count": col_count,
                            "fitz_tables_strategy": f"{self.config.vertical_strategy}/{self.config.horizontal_strategy}",
                        },
                    )
                    blocks.append(block)
                    native_by_block[prov_id] = {
                        "page": i,
                        "seq": seq,
                        "bbox": list(table.bbox),
                        "rows": row_count,
                        "cols": col_count,
                        "html": html,
                    }
        finally:
            doc.close()

        return ToolResult(
            tool_id=self.tool_id,
            blocks=blocks,
            page_meta=self.page_meta,
            raw={"tables": list(native_by_block.values())},
            native_by_block=native_by_block,
            warnings=warnings,
            duration_ms=int((time.perf_counter() - t0) * 1000),
        )
```

- [ ] **Step 7: Run all config and tool tests**

```
uv run --directory backend python -m pytest tests/cdm/adapters/local_pipeline/test_config.py tests/cdm/adapters/local_pipeline/test_fitz_tables_tool.py -v -o "addopts="
```

Expected: all PASS.

- [ ] **Step 8: Commit**

```
git add backend/app/cdm/adapters/local_pipeline/config.py backend/app/cdm/adapters/local_pipeline/tools/fitz_tables_tool.py backend/tests/cdm/adapters/local_pipeline/test_config.py backend/tests/cdm/adapters/local_pipeline/test_fitz_tables_tool.py
git commit -m "feat(pipeline): add FitzTablesConfig, FitzTablesTool, TABLE_TOOL_IDS, mutual-exclusion guard"
```

---

### Task 3: Runner generalization

**Files:**
- Modify: `backend/app/services/parsing/local_pipeline_runner.py`
- Modify: `backend/tests/services/parsing/test_local_pipeline_runner.py`

**Interfaces:**
- Consumes (Task 1): `merge(fitz_result, table_result, ...)` — renamed parameter
- Consumes (Task 2): `TABLE_TOOL_IDS` from `config.py`, `FitzTablesTool` via `build_pipeline_config`

- [ ] **Step 1: Write the failing end-to-end test for fitz_tables**

Add to `backend/tests/services/parsing/test_local_pipeline_runner.py`:

```python
@pytest.mark.asyncio
async def test_run_local_pipeline_fitz_tables_emits_table_blocks(tmp_path):
    """fitz_tables tool runs end-to-end and emits TABLE blocks."""
    pdf = tmp_path / "table_test.pdf"
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    col_x = [72, 236, 400]
    row_y = [100, 150, 200]
    for x in col_x:
        page.draw_line(
            fitz.Point(x, row_y[0]), fitz.Point(x, row_y[-1]),
            color=(0, 0, 0), width=1,
        )
    for y in row_y:
        page.draw_line(
            fitz.Point(col_x[0], y), fitz.Point(col_x[-1], y),
            color=(0, 0, 0), width=1,
        )
    page.insert_text(fitz.Point(80, 135), "Name", fontsize=11)
    page.insert_text(fitz.Point(244, 135), "Value", fontsize=11)
    page.insert_text(fitz.Point(80, 185), "alpha", fontsize=11)
    page.insert_text(fitz.Point(244, 185), "1", fontsize=11)
    doc.save(str(pdf))
    doc.close()

    config = {
        "tools": [
            {"tool_id": "fitz", "config": {}},
            {"tool_id": "fitz_tables", "config": {}},
        ],
        "eviction_overlap_threshold": 0.5,
    }
    run, doc_result = await run_local_pipeline(
        source=_source(),
        file_path=str(pdf),
        representation_kind="extract_rich",
        config=config,
        client=None,
    )
    assert run.status == ParseRunStatus.SUCCEEDED
    assert "fitz_tables" in run.raw_payload["tools"]
    assert any(b.role == BlockRole.TABLE for b in doc_result.blocks)


@pytest.mark.asyncio
async def test_run_local_pipeline_rejects_dual_table_tools():
    config = {
        "tools": [
            {"tool_id": "fitz", "config": {}},
            {"tool_id": "fitz_tables", "config": {}},
            {"tool_id": "camelot", "config": {}},
        ],
    }
    with pytest.raises(LocalPipelineRunError) as ei:
        await run_local_pipeline(
            source=_source(),
            file_path=str(FIXTURES / "simple_text.pdf"),
            representation_kind="extract_rich",
            config=config,
            client=None,
        )
    assert ei.value.run.status == ParseRunStatus.FAILED
```

- [ ] **Step 2: Run to confirm failures**

```
uv run --directory backend python -m pytest tests/services/parsing/test_local_pipeline_runner.py -k "fitz_tables or dual_table" -v -o "addopts="
```

Expected: FAIL.

- [ ] **Step 3: Rewrite `local_pipeline_runner.py`**

Replace the full content of `backend/app/services/parsing/local_pipeline_runner.py`:

```python
"""Drives the local tool pipeline end-to-end: tools → merge → CDM + ParseRun."""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from app.cdm.adapters.base import SourceMeta
from app.cdm.adapters.local_pipeline.adapter import LocalPipelineAdapter
from app.cdm.adapters.local_pipeline.config import TABLE_TOOL_IDS, build_pipeline_config
from app.cdm.adapters.local_pipeline.merger import merge
from app.cdm.adapters.local_pipeline.tools.base import ToolResult
from app.cdm.models import ParsedDocument, ParserKind
from app.cdm.source import ParseRun, ParseRunStatus, SourceDocument
from app.services.parsing.errors import LocalPipelineRunError


async def run_local_pipeline(
    *,
    source: SourceDocument,
    file_path: str,
    representation_kind: str,
    config: Dict[str, Any],
    client: Any = None,
    parse_run_id: Optional[str] = None,
) -> Tuple[ParseRun, ParsedDocument]:
    run_id = parse_run_id or str(uuid.uuid4())
    started_at = datetime.now(timezone.utc)
    t0 = time.perf_counter()

    def _fail(exc: Exception) -> LocalPipelineRunError:
        finished_at = datetime.now(timezone.utc)
        duration_ms = int((time.perf_counter() - t0) * 1000)
        failed = ParseRun(
            id=run_id,
            source_document_id=source.id,
            parser=ParserKind.LOCAL_PIPELINE,
            representation_kind=representation_kind,
            config=config,
            status=ParseRunStatus.FAILED,
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=duration_ms,
            error=f"{type(exc).__name__}: {exc}",
        )
        return LocalPipelineRunError(f"Local pipeline failed: {exc}", run=failed)

    try:
        pdf_path = Path(file_path)

        pipeline = build_pipeline_config(config)

        fitz_tool = next((t for t in pipeline.tools if t.tool_id == "fitz"), None)
        if fitz_tool is None:
            raise ValueError("local pipeline requires a 'fitz' tool")

        fitz_result: ToolResult = fitz_tool.run(pdf_path)
        warnings = list(fitz_result.warnings)

        table_entry = next(
            (e for e in config.get("tools", []) if e.get("tool_id") in TABLE_TOOL_IDS),
            None,
        )
        if table_entry is not None:
            table_pipeline = build_pipeline_config(
                {"tools": [table_entry]}, page_meta=fitz_result.page_meta
            )
            table_tool = table_pipeline.tools[0]
            table_result = table_tool.run(pdf_path)
            warnings.extend(table_result.warnings)
        else:
            table_result = ToolResult(tool_id="none", blocks=[], page_meta={}, raw={})

        merge_result = merge(
            fitz_result,
            table_result,
            source_document_id=source.id,
            eviction_overlap_threshold=pipeline.eviction_overlap_threshold,
        )
    except Exception as exc:  # noqa: BLE001
        raise _fail(exc) from exc

    finished_at = datetime.now(timezone.utc)
    duration_ms = int((time.perf_counter() - t0) * 1000)

    run = ParseRun(
        id=run_id,
        source_document_id=source.id,
        parser=ParserKind.LOCAL_PIPELINE,
        representation_kind=representation_kind,
        config=config,
        status=ParseRunStatus.SUCCEEDED,
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=duration_ms,
        warnings=warnings,
        raw_payload=merge_result.raw_output,
    )

    adapter = LocalPipelineAdapter()
    doc = adapter.adapt(
        {"page_meta": fitz_result.page_meta, "blocks": merge_result.blocks},
        SourceMeta(
            source_document_id=source.id,
            parse_run_id=run.id,
            filename=source.filename,
            sha256=source.sha256,
        ),
    )
    return run, doc
```

- [ ] **Step 4: Run all runner tests**

```
uv run --directory backend python -m pytest tests/services/parsing/test_local_pipeline_runner.py -v -o "addopts="
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```
git add backend/app/services/parsing/local_pipeline_runner.py backend/tests/services/parsing/test_local_pipeline_runner.py
git commit -m "refactor(runner): generalize camelot detection to TABLE_TOOL_IDS; add fitz_tables end-to-end test"
```

---

### Task 4: Probe update

**Files:**
- Modify: `backend/app/cdm/adapters/local_pipeline/probe.py`
- Modify: `backend/tests/cdm/adapters/local_pipeline/test_probe.py`

**Interfaces:**
- No new interfaces. `_recommend()` signature unchanged; return values change.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/cdm/adapters/local_pipeline/test_probe.py`:

```python
def test_recommend_suggests_fitz_tables_for_clean_doc_with_table_signal():
    probe = DocumentProbe()
    # Access the internal _recommend method directly for unit testing
    result = probe._recommend(has_cid=False, has_scanned=False, has_tables=True)
    assert "fitz_tables" in result
    assert "camelot" not in result
    assert "fitz" in result


def test_recommend_fitz_only_for_clean_doc_without_tables():
    probe = DocumentProbe()
    result = probe._recommend(has_cid=False, has_scanned=False, has_tables=False)
    assert result == ["fitz"]
    assert "fitz_tables" not in result
```

- [ ] **Step 2: Run to confirm failures**

```
uv run --directory backend python -m pytest tests/cdm/adapters/local_pipeline/test_probe.py -k "recommend" -v -o "addopts="
```

Expected: `test_recommend_suggests_fitz_tables_for_clean_doc_with_table_signal` FAIL (currently returns `camelot`).

- [ ] **Step 3: Update `_recommend` in `probe.py`**

In `backend/app/cdm/adapters/local_pipeline/probe.py`, replace the `_recommend` method:

```python
def _recommend(self, has_cid: bool, has_scanned: bool, has_tables: bool) -> List[str]:
    if has_cid or has_scanned:
        tools = ["paddleocr"]
        if has_tables:
            tools.append("paddleocr_pp_structure")
    else:
        tools = ["fitz"]
        if has_tables:
            tools.append("fitz_tables")
    return tools
```

- [ ] **Step 4: Run all probe tests**

```
uv run --directory backend python -m pytest tests/cdm/adapters/local_pipeline/test_probe.py -v -o "addopts="
```

Expected: all PASS. Note: `test_run_recommended_tools_not_empty` still passes (`fitz_tables` is non-empty). `test_recommended_tools_is_list_of_strings` still passes. The `_make_document_profile()` fixture hard-codes `recommended_tools=["fitz", "camelot"]` on the model directly — this is unaffected by the `_recommend` change.

- [ ] **Step 5: Commit**

```
git add backend/app/cdm/adapters/local_pipeline/probe.py backend/tests/cdm/adapters/local_pipeline/test_probe.py
git commit -m "feat(probe): recommend fitz_tables instead of camelot for clean docs with table signal"
```

---

### Task 5: UI — table tool selector in LocalPipelineConfig

**Files:**
- Modify: `frontend/src/components/documents/parser-configs/LocalPipelineConfig.tsx`
- Modify: `frontend/src/components/documents/parser-configs/LocalPipelineConfig.test.tsx`

**Interfaces:**
- Produces: `LocalPipelineConfig` component — unchanged props signature. When `tool_id: "fitz_tables"` is in `config.tools`, a `FitzTablesConfigPanel` renders with all 17 config params.
- The `handleTableToolChange(value: 'none' | 'fitz_tables' | 'camelot')` handler enforces mutual exclusion by removing any existing table tool before adding the new one.

- [ ] **Step 1: Write the new component tests**

Replace the full content of `frontend/src/components/documents/parser-configs/LocalPipelineConfig.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { LocalPipelineConfig } from './LocalPipelineConfig'

const fitzOnly = {
  tools: [
    {
      tool_id: 'fitz',
      config: { include_images: true, span_detail: false, min_chars_threshold: 10 },
    },
  ],
  eviction_overlap_threshold: 0.5,
}

const withFitzTables = {
  ...fitzOnly,
  tools: [
    ...fitzOnly.tools,
    {
      tool_id: 'fitz_tables',
      config: { vertical_strategy: 'lines_strict', horizontal_strategy: 'lines_strict' },
    },
  ],
}

const withCamelot = {
  ...fitzOnly,
  tools: [
    ...fitzOnly.tools,
    { tool_id: 'camelot', config: { flavor: 'lattice', edge_tol: 50, row_tol: 2 } },
  ],
}

describe('LocalPipelineConfig', () => {
  it('renders fitz section as always-on and a table-tool selector', () => {
    render(<LocalPipelineConfig config={fitzOnly} onChange={vi.fn()} />)
    expect(screen.getByText(/fitz \(text \+ images\)/i)).toBeInTheDocument()
    expect(screen.getByText(/table extraction/i)).toBeInTheDocument()
  })

  it('selecting fitz_tables adds it to tools list', async () => {
    const onChange = vi.fn()
    render(<LocalPipelineConfig config={fitzOnly} onChange={onChange} />)
    await userEvent.click(screen.getByRole('combobox', { name: /table extraction/i }))
    await userEvent.click(screen.getByText(/fitz_tables/i))
    const next = onChange.mock.calls[0][0]
    expect(next.tools.map((t: { tool_id: string }) => t.tool_id)).toContain('fitz_tables')
    expect(next.tools.map((t: { tool_id: string }) => t.tool_id)).not.toContain('camelot')
  })

  it('selecting camelot adds it to tools list', async () => {
    const onChange = vi.fn()
    render(<LocalPipelineConfig config={fitzOnly} onChange={onChange} />)
    await userEvent.click(screen.getByRole('combobox', { name: /table extraction/i }))
    await userEvent.click(screen.getByText(/camelot/i))
    const next = onChange.mock.calls[0][0]
    expect(next.tools.map((t: { tool_id: string }) => t.tool_id)).toContain('camelot')
    expect(next.tools.map((t: { tool_id: string }) => t.tool_id)).not.toContain('fitz_tables')
  })

  it('selecting none removes existing table tool', async () => {
    const onChange = vi.fn()
    render(<LocalPipelineConfig config={withFitzTables} onChange={onChange} />)
    await userEvent.click(screen.getByRole('combobox', { name: /table extraction/i }))
    await userEvent.click(screen.getByRole('option', { name: /none/i }))
    const next = onChange.mock.calls[0][0]
    expect(next.tools.map((t: { tool_id: string }) => t.tool_id)).not.toContain('fitz_tables')
    expect(next.tools.map((t: { tool_id: string }) => t.tool_id)).not.toContain('camelot')
  })

  it('switching from camelot to fitz_tables removes camelot', async () => {
    const onChange = vi.fn()
    render(<LocalPipelineConfig config={withCamelot} onChange={onChange} />)
    await userEvent.click(screen.getByRole('combobox', { name: /table extraction/i }))
    await userEvent.click(screen.getByText(/fitz_tables/i))
    const next = onChange.mock.calls[0][0]
    const ids = next.tools.map((t: { tool_id: string }) => t.tool_id)
    expect(ids).toContain('fitz_tables')
    expect(ids).not.toContain('camelot')
  })

  it('shows fitz_tables config panel when fitz_tables is selected', () => {
    render(<LocalPipelineConfig config={withFitzTables} onChange={vi.fn()} />)
    expect(screen.getByText(/vertical strategy/i)).toBeInTheDocument()
    expect(screen.getByText(/snap tolerance/i)).toBeInTheDocument()
  })

  it('shows camelot flavor select when camelot is selected', () => {
    render(<LocalPipelineConfig config={withCamelot} onChange={vi.fn()} />)
    expect(screen.getByText('Flavor')).toBeInTheDocument()
  })

  it('hides edge_tol/row_tol for camelot lattice flavor', () => {
    render(<LocalPipelineConfig config={withCamelot} onChange={vi.fn()} />)
    expect(screen.queryByText('edge_tol')).not.toBeInTheDocument()
    expect(screen.queryByText('row_tol')).not.toBeInTheDocument()
  })

  it('shows edge_tol/row_tol for camelot stream flavor', () => {
    const withStream = {
      ...fitzOnly,
      tools: [
        ...fitzOnly.tools,
        { tool_id: 'camelot', config: { flavor: 'stream', edge_tol: 50, row_tol: 2 } },
      ],
    }
    render(<LocalPipelineConfig config={withStream} onChange={vi.fn()} />)
    expect(screen.getByText('edge_tol')).toBeInTheDocument()
    expect(screen.getByText('row_tol')).toBeInTheDocument()
  })

  it('shows suggested-tools hint when a profile is provided', () => {
    render(
      <LocalPipelineConfig
        config={fitzOnly}
        onChange={vi.fn()}
        profile={{
          source_document_id: 'd',
          filename: 'x.pdf',
          page_count: 1,
          pages: [],
          has_text_layer: true,
          has_scanned_pages: false,
          has_cid_corruption: false,
          table_signal: true,
          recommended_tools: ['fitz', 'fitz_tables'],
          duration_ms: 10,
          probed_at: '2026-06-25T00:00:00Z',
        }}
      />
    )
    expect(screen.getByText(/fitz, fitz_tables/i)).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run to confirm failures**

```
npm --prefix frontend run test -- --run src/components/documents/parser-configs/LocalPipelineConfig.test.tsx
```

Expected: multiple FAIL — old tests expect a checkbox for camelot; new tests expect a combobox.

- [ ] **Step 3: Rewrite `LocalPipelineConfig.tsx`**

Replace the full content of `frontend/src/components/documents/parser-configs/LocalPipelineConfig.tsx`:

```tsx
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Slider } from '@/components/ui/slider'
import type { ParseConfig } from '@/types/parsing'
import type { DocumentProfile } from '@/types/probe'

interface ToolEntry {
  tool_id: string
  config: Record<string, unknown>
}

interface LocalPipelineConfigProps {
  config: ParseConfig
  onChange: (config: ParseConfig) => void
  disabled?: boolean
  profile?: DocumentProfile | null
}

type TableTool = 'none' | 'fitz_tables' | 'camelot'

const FITZ_TABLES_DEFAULTS: Record<string, unknown> = {
  vertical_strategy: 'lines_strict',
  horizontal_strategy: 'lines_strict',
  snap_tolerance: 3,
  join_tolerance: 3,
  edge_min_length: 3,
  min_words_vertical: 3,
  min_words_horizontal: 1,
  intersection_tolerance: 3,
  text_tolerance: 3,
}

const CAMELOT_DEFAULTS = { flavor: 'lattice', edge_tol: 50, row_tol: 2 }

function FitzTablesConfigPanel({
  config,
  onChange,
  disabled,
}: {
  config: Record<string, unknown>
  onChange: (patch: Record<string, unknown>) => void
  disabled: boolean
}) {
  const num = (key: string, def: number) =>
    (config[key] as number | undefined) ?? def

  const numField = (
    key: string,
    def: number,
    label: string,
    description: string,
  ) => (
    <div className="space-y-1">
      <Label htmlFor={`ft-${key}`}>{label}</Label>
      <Input
        id={`ft-${key}`}
        type="number"
        step="0.5"
        value={num(key, def)}
        onChange={(e) => onChange({ [key]: Number(e.target.value) })}
        disabled={disabled}
      />
      <p className="text-xs text-muted-foreground">{description}</p>
    </div>
  )

  const axisField = (key: string, label: string) => (
    <div className="space-y-1">
      <Label htmlFor={`ft-${key}`}>{label}</Label>
      <Input
        id={`ft-${key}`}
        type="number"
        step="0.5"
        placeholder="inherit"
        value={(config[key] as number | null | undefined) ?? ''}
        onChange={(e) => {
          const v = e.target.value === '' ? null : Number(e.target.value)
          onChange({ [key]: v })
        }}
        disabled={disabled}
      />
    </div>
  )

  const strategy = (axis: 'vertical' | 'horizontal') => {
    const key = `${axis}_strategy`
    return (
      <div className="space-y-1">
        <Label htmlFor={`ft-${key}`}>
          {axis === 'vertical' ? 'Vertical strategy' : 'Horizontal strategy'}
        </Label>
        <Select
          value={(config[key] as string) ?? 'lines_strict'}
          onValueChange={(v) => onChange({ [key]: v })}
          disabled={disabled}
        >
          <SelectTrigger id={`ft-${key}`}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="lines_strict">lines_strict (explicit lines only)</SelectItem>
            <SelectItem value="lines">lines (lines + inferred gutters)</SelectItem>
            <SelectItem value="text">text (whitespace gaps)</SelectItem>
            <SelectItem value="explicit">explicit</SelectItem>
          </SelectContent>
        </Select>
        <p className="text-xs text-muted-foreground">
          {axis === 'vertical'
            ? 'How column separators are detected'
            : 'How row separators are detected'}
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-4 pl-6">
      <div className="grid grid-cols-2 gap-3">
        {strategy('vertical')}
        {strategy('horizontal')}
      </div>

      <div className="grid grid-cols-2 gap-3">
        {numField('snap_tolerance', 3, 'Snap tolerance', 'Lines within this distance (pts) are merged into one edge')}
        {numField('join_tolerance', 3, 'Join tolerance', 'Max gap (pts) between line endpoints to be joined')}
        {numField('edge_min_length', 3, 'Min edge length', 'Lines shorter than this (pts) are ignored as table edges')}
        {numField('intersection_tolerance', 3, 'Intersection tolerance', 'Precision for finding line crossings that form cell corners')}
        {numField('text_tolerance', 3, 'Text tolerance', 'How loosely text is assigned to cells')}
        {numField('min_words_vertical', 3, 'Min words (vertical)', 'Min words per column — text strategy only')}
        {numField('min_words_horizontal', 1, 'Min words (horizontal)', 'Min words per row — text strategy only')}
      </div>

      <Collapsible>
        <CollapsibleTrigger className="text-xs text-muted-foreground hover:text-foreground">
          Per-axis overrides (advanced)
        </CollapsibleTrigger>
        <CollapsibleContent className="pt-2">
          <div className="grid grid-cols-2 gap-3">
            {axisField('snap_x_tolerance', 'Snap X tolerance')}
            {axisField('snap_y_tolerance', 'Snap Y tolerance')}
            {axisField('join_x_tolerance', 'Join X tolerance')}
            {axisField('join_y_tolerance', 'Join Y tolerance')}
            {axisField('intersection_x_tolerance', 'Intersection X tolerance')}
            {axisField('intersection_y_tolerance', 'Intersection Y tolerance')}
            {axisField('text_x_tolerance', 'Text X tolerance')}
            {axisField('text_y_tolerance', 'Text Y tolerance')}
          </div>
        </CollapsibleContent>
      </Collapsible>
    </div>
  )
}

export function LocalPipelineConfig({
  config,
  onChange,
  disabled = false,
  profile,
}: LocalPipelineConfigProps) {
  const tools = (config.tools as ToolEntry[] | undefined) ?? []
  const threshold = (config.eviction_overlap_threshold as number | undefined) ?? 0.5

  const fitz = tools.find((t) => t.tool_id === 'fitz')
  const fitzTables = tools.find((t) => t.tool_id === 'fitz_tables')
  const camelot = tools.find((t) => t.tool_id === 'camelot')

  const activeTableTool: TableTool = fitzTables
    ? 'fitz_tables'
    : camelot
      ? 'camelot'
      : 'none'

  const setTools = (next: ToolEntry[]) => onChange({ ...config, tools: next })

  const updateTool = (toolId: string, patch: Record<string, unknown>) => {
    setTools(
      tools.map((t) =>
        t.tool_id === toolId ? { ...t, config: { ...t.config, ...patch } } : t,
      ),
    )
  }

  const handleTableToolChange = (value: TableTool) => {
    const withoutTableTools = tools.filter(
      (t) => t.tool_id !== 'fitz_tables' && t.tool_id !== 'camelot',
    )
    if (value === 'fitz_tables') {
      setTools([
        ...withoutTableTools,
        { tool_id: 'fitz_tables', config: { ...FITZ_TABLES_DEFAULTS } },
      ])
    } else if (value === 'camelot') {
      setTools([
        ...withoutTableTools,
        { tool_id: 'camelot', config: { ...CAMELOT_DEFAULTS } },
      ])
    } else {
      setTools(withoutTableTools)
    }
  }

  return (
    <div className="space-y-4">
      {profile && (
        <p className="text-sm text-muted-foreground">
          Suggested tools:{' '}
          <span className="font-medium">{profile.recommended_tools.join(', ')}</span>
        </p>
      )}

      {/* Fitz — always on */}
      <div className="space-y-2 rounded-md border p-3">
        <div className="flex items-center justify-between">
          <Label>fitz (text + images)</Label>
          <span className="text-xs text-muted-foreground">always on</span>
        </div>
        <div className="flex items-center gap-2">
          <Checkbox
            id="fitz-include-images"
            checked={(fitz?.config.include_images as boolean) ?? true}
            onCheckedChange={(c) => updateTool('fitz', { include_images: !!c })}
            disabled={disabled}
          />
          <Label htmlFor="fitz-include-images">Include images (FIGURE blocks)</Label>
        </div>
        <div className="flex items-center gap-2">
          <Checkbox
            id="fitz-span-detail"
            checked={(fitz?.config.span_detail as boolean) ?? false}
            onCheckedChange={(c) => updateTool('fitz', { span_detail: !!c })}
            disabled={disabled}
          />
          <Label htmlFor="fitz-span-detail">Record span detail</Label>
        </div>
      </div>

      {/* Table extraction — mutually exclusive selector */}
      <div className="space-y-2 rounded-md border p-3">
        <div className="space-y-2">
          <Label htmlFor="table-tool-select">Table extraction</Label>
          <Select
            value={activeTableTool}
            onValueChange={(v) => handleTableToolChange(v as TableTool)}
            disabled={disabled}
          >
            <SelectTrigger id="table-tool-select" aria-label="Table extraction">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="none">None</SelectItem>
              <SelectItem value="fitz_tables">
                fitz_tables — fast, DRM-safe, no extra deps
              </SelectItem>
              <SelectItem value="camelot">
                camelot — accurate grid detection, requires open PDF
              </SelectItem>
            </SelectContent>
          </Select>
        </div>

        {activeTableTool === 'fitz_tables' && fitzTables && (
          <FitzTablesConfigPanel
            config={fitzTables.config}
            onChange={(patch) => updateTool('fitz_tables', patch)}
            disabled={disabled}
          />
        )}

        {activeTableTool === 'camelot' && camelot && (
          <div className="space-y-3 pl-6">
            <div className="space-y-1">
              <Label htmlFor="camelot-flavor">Flavor</Label>
              <Select
                value={(camelot.config.flavor as string) ?? 'lattice'}
                onValueChange={(v) => updateTool('camelot', { flavor: v })}
                disabled={disabled}
              >
                <SelectTrigger id="camelot-flavor">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="lattice">lattice (ruled tables)</SelectItem>
                  <SelectItem value="stream">stream (borderless tables)</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {(camelot.config.flavor as string) === 'stream' && (
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label htmlFor="camelot-edge-tol">edge_tol</Label>
                  <Input
                    id="camelot-edge-tol"
                    type="number"
                    value={(camelot.config.edge_tol as number) ?? 50}
                    onChange={(e) => updateTool('camelot', { edge_tol: Number(e.target.value) })}
                    disabled={disabled}
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="camelot-row-tol">row_tol</Label>
                  <Input
                    id="camelot-row-tol"
                    type="number"
                    value={(camelot.config.row_tol as number) ?? 2}
                    onChange={(e) => updateTool('camelot', { row_tol: Number(e.target.value) })}
                    disabled={disabled}
                  />
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Eviction threshold */}
      <div className="space-y-2">
        <Label htmlFor="eviction-threshold">
          Eviction overlap threshold: {threshold.toFixed(2)}
        </Label>
        <Slider
          id="eviction-threshold"
          min={0}
          max={1}
          step={0.05}
          value={[threshold]}
          onValueChange={([v]) => onChange({ ...config, eviction_overlap_threshold: v })}
          disabled={disabled}
        />
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Run frontend tests**

```
npm --prefix frontend run test -- --run src/components/documents/parser-configs/LocalPipelineConfig.test.tsx
```

Expected: all PASS.

- [ ] **Step 5: Run full frontend lint + build**

```
npm --prefix frontend run lint
npm --prefix frontend run build
```

Expected: no errors.

- [ ] **Step 6: Commit**

```
git add frontend/src/components/documents/parser-configs/LocalPipelineConfig.tsx frontend/src/components/documents/parser-configs/LocalPipelineConfig.test.tsx
git commit -m "feat(ui): replace camelot checkbox with table-tool selector; add FitzTablesConfigPanel"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Task |
|---|---|
| `FitzTablesConfig` with all `page.find_tables()` params | Task 2 |
| `FitzTablesTool` — `tool_id`, `run()`, top-left bbox, no y-flip | Task 2 |
| TOOL_REGISTRY + `"fitz_tables"` | Task 2 |
| Mutual-exclusion guard | Task 2 |
| Merger `camelot_result` → `table_result` rename | Task 1 |
| Merger dynamic `tool_id` key in `raw_output` | Task 1 |
| Runner `TABLE_TOOL_IDS` detection | Task 3 |
| Runner `camelot_result` → `table_result` rename | Task 3 |
| Probe `_recommend()` returns `fitz_tables` for clean+table doc | Task 4 |
| UI: table-tool selector (none/fitz_tables/camelot) | Task 5 |
| UI: inline descriptions for all `FitzTablesConfig` params | Task 5 |
| UI: per-axis overrides in Advanced collapsible | Task 5 |

All spec requirements are covered. ✓

**Type consistency check:**

- `FitzTablesTool.__init__` takes `FitzTablesConfig` → used in `build_pipeline_config` `elif tool_id == "fitz_tables"` branch. ✓
- `FitzTablesTool.run()` returns `ToolResult` → passed to `merge(fitz_result, table_result)`. ✓
- `TABLE_TOOL_IDS` defined in `config.py`, imported in `local_pipeline_runner.py`. ✓
- Merger param renamed to `table_result` — runner calls `merge(fitz_result, table_result, ...)` positionally. ✓
- `FitzTablesConfig` imported in `LocalPipelineConfig.tsx` indirectly via the tool entry's `config` dict. No TypeScript type needed — backend-driven shape. ✓
