# fitz_tables — Feature Spec

**Status:** Approved  
**Date:** 2026-06-30  
**Parent spec:** [2026-06-30-custom-pipeline-design.md](2026-06-30-custom-pipeline-design.md)

---

## Overview

Register `fitz_tables` as a new local pipeline tool (Tier 2) that uses PyMuPDF's built-in `page.find_tables()` to extract tables from PDFs. It slots into the same "table tool" position as `camelot` (Tier 3), but is DRM-safe, faster, and requires no additional dependencies beyond PyMuPDF 1.23+.

The runner and merger are generalized from hardcoded camelot references to a single "table tool" slot. Only one table tool may be active per pipeline config.

---

## Scope

In scope:
- `FitzTablesTool` + `FitzTablesConfig` implementation
- TOOL_REGISTRY registration and mutual-exclusion enforcement
- Runner + merger generalization (rename `camelot_result` → `table_result`)
- Probe `_recommend()` update: suggest `fitz_tables` instead of `camelot` for clean docs with table signal
- UI: expose all `FitzTablesConfig` params with inline descriptions

Out of scope:
- `local_pipeline` → `custom_pipeline` rename (separate scope item)
- Docling tool registration (separate scope item)
- `copy_restricted` probe field (separate scope item)

---

## Architecture

### New file

| File | Purpose |
|------|---------|
| `backend/app/cdm/adapters/local_pipeline/tools/fitz_tables_tool.py` | `FitzTablesTool` class |

### Modified files

| File | Change |
|------|--------|
| `config.py` | Add `FitzTablesConfig`; register `"fitz_tables"` in `TOOL_REGISTRY`; add mutual-exclusion guard; instantiate `FitzTablesTool` in `build_pipeline_config` |
| `local_pipeline_runner.py` | Replace hardcoded camelot detection with `TABLE_TOOL_IDS` lookup; rename `camelot_result` → `table_result` |
| `merger.py` | Rename `camelot_result` parameter → `table_result`; use `table_result.tool_id` dynamically in `raw_output` |
| `probe.py` | `_recommend()`: suggest `["fitz", "fitz_tables"]` instead of `["fitz", "camelot"]` when `table_signal=True` and document is clean |

No schema migrations. No new CDM types. `BlockRole.TABLE`, `Table`, `Cell`, and `BBox` are already the correct shape.

---

## FitzTablesConfig

All `page.find_tables()` parameters are exposed with their PyMuPDF defaults. `clip` is omitted — it is a per-page spatial rect, not a serializable pipeline-level knob.

```python
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
```

---

## FitzTablesTool

**Protocol:** implements `LocalTool` — `tool_id = "fitz_tables"`, `run(pdf_path, pages) -> ToolResult`.

**Constructor:** takes `FitzTablesConfig` and `page_meta: Dict[int, PageMeta]`. `page_meta` is required for bbox normalization (supplied by the runner after FitzTool completes, same pattern as CamelotTool).

**Run loop:**
1. Open PDF with `fitz.open()`
2. For each page (filtered by `pages` arg if supplied):
   - Call `page.find_tables(**config_kwargs)` — passing all non-None config fields as kwargs
   - For each found table, build a `BlockRole.TABLE` block:
     - **Bbox:** fitz uses top-left origin in PDF points — no y-flip. Normalize directly: `x / width`, `y / height`
     - **Cells:** from `table.cells` (2D list of `Rect | None`); `None` entries (merged cells) get no bbox
     - **Cell text:** from `table.extract()` — list-of-lists of strings, aligned to the cells grid
     - **HTML/markdown:** constructed from the extracted cell data
     - **Block id:** `fitz_tables:{page_index}:{table_seq}`
3. Close PDF in `finally`

**Output:** `ToolResult` with `tool_id="fitz_tables"`, `blocks` (TABLE only), `page_meta` (passed through), `raw`, `native_by_block`, `warnings`, `duration_ms`.

---

## Runner Generalization

```python
TABLE_TOOL_IDS = frozenset({"camelot", "fitz_tables"})

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

merge_result = merge(fitz_result, table_result, ...)
```

The runner still requires `fitz` to be present (existing guard unchanged).

---

## Mutual-Exclusion Enforcement

In `build_pipeline_config`, before instantiating tools:

```python
table_ids_present = [
    e["tool_id"] for e in config.get("tools", [])
    if e.get("tool_id") in TABLE_TOOL_IDS
]
if len(table_ids_present) > 1:
    raise ValueError(
        f"only one table tool allowed per pipeline, got: {table_ids_present}"
    )
```

This propagates as a `FAILED` ParseRun via the runner's existing `_fail()` wrapper.

---

## Merger Generalization

Signature change only — logic is unchanged:

```python
def merge(
    fitz_result: ToolResult,
    table_result: ToolResult,   # was camelot_result
    *,
    source_document_id: str,
    eviction_overlap_threshold: float = 0.5,
) -> MergeResult:
```

In `raw_output`, the tool key is dynamic:

```python
raw_output = {
    "tools": {
        "fitz": {"raw": fitz_result.raw, "block_map": _block_map(fitz_result)},
        table_result.tool_id: {"raw": table_result.raw, "block_map": _block_map(table_result)},
    },
    "evicted": evicted_records,
}
```

---

## Probe Update

```python
def _recommend(self, has_cid: bool, has_scanned: bool, has_tables: bool) -> List[str]:
    if has_cid or has_scanned:
        tools = ["paddleocr"]
        if has_tables:
            tools.append("paddleocr_pp_structure")
    else:
        tools = ["fitz"]
        if has_tables:
            tools.append("fitz_tables")   # was "camelot"
    return tools
```

Camelot remains in the registry and is selectable manually; it is no longer auto-recommended.

---

## UI — Config Parameter Descriptions

Rendered as inline helper text in the parse config editor. Per-axis overrides are collapsed in an "Advanced" expander.

| Parameter | UI label | Description |
|---|---|---|
| `vertical_strategy` | Vertical strategy | How column separators are detected: `lines_strict` (explicit drawn lines only), `lines` (lines + inferred gutters), `text` (whitespace gaps between words) |
| `horizontal_strategy` | Horizontal strategy | Same options, applied to row detection |
| `snap_tolerance` | Snap tolerance | Lines within this distance (pts) are merged into one edge |
| `snap_x_tolerance` | Snap X tolerance | Horizontal-only override for snap tolerance |
| `snap_y_tolerance` | Snap Y tolerance | Vertical-only override for snap tolerance |
| `join_tolerance` | Join tolerance | Max gap (pts) between line endpoints to be joined into a continuous edge |
| `join_x_tolerance` | Join X tolerance | Horizontal-only override for join tolerance |
| `join_y_tolerance` | Join Y tolerance | Vertical-only override for join tolerance |
| `edge_min_length` | Min edge length | Lines shorter than this (pts) are ignored as table edges |
| `min_words_vertical` | Min words (vertical) | Minimum words per column to infer a column separator — text strategy only |
| `min_words_horizontal` | Min words (horizontal) | Minimum words per row to infer a row separator — text strategy only |
| `intersection_tolerance` | Intersection tolerance | How precisely line crossings must align to form cell corners |
| `intersection_x_tolerance` | Intersection X tolerance | Horizontal-only override |
| `intersection_y_tolerance` | Intersection Y tolerance | Vertical-only override |
| `text_tolerance` | Text tolerance | How loosely text is assigned to cells when no explicit borders exist |
| `text_x_tolerance` | Text X tolerance | Horizontal-only override for text tolerance |
| `text_y_tolerance` | Text Y tolerance | Vertical-only override for text tolerance |

---

## Error Handling

| Situation | Behaviour |
|---|---|
| `page.find_tables()` raises on a specific page | Skip that page; append warning to `ToolResult.warnings`; run continues |
| Both `camelot` and `fitz_tables` in one config | `ValueError` in `build_pipeline_config`; propagates as `FAILED` ParseRun |
| No tables found on a page | No blocks emitted; no warning (normal case) |
| Missing `page_meta` for a page | Cell bboxes omitted for that page; warning appended |

---

## Testing

| Test file | What it covers |
|---|---|
| `test_fitz_tables_tool.py` | `FitzTablesTool.run()` against fixture PDF: block count, `BlockRole.TABLE`, bbox normalization (no y-flip), cell text, html/markdown presence |
| `test_config_mutual_exclusion.py` | `build_pipeline_config` raises `ValueError` when both `camelot` and `fitz_tables` are present |
| `test_merger_table_tool_id.py` | `raw_output` key uses `table_result.tool_id` dynamically; regression for the rename |
| `test_probe_recommend.py` | `_recommend()` returns `["fitz", "fitz_tables"]` for clean docs with `table_signal=True` |
