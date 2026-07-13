# Layout Analysis — Structure Capability Slot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Collapse `text_extraction` into a single required, block-producing `layout_analysis` (structure) slot, with fitz as the tier-0 tool and docling as the tier-1 authoritative producer, so parsing approaches can be composed and compared on the local→AI ladder.

**Architecture:** Two sequential PRs. **PR A** is a pure, behaviour-preserving refactor: rename the capability, keep fitz's output byte-identical (verified against goldens captured from the current pipeline). **PR B** adds docling as an authoritative structure tool, makes the merger honour a producer's intrinsic reading order (the multi-column L2 fix), offloads tool runs off the event loop, and retires the standalone `ParserKind.DOCLING` method.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, PyMuPDF (`fitz`), pypdf, docling; React 18 + TypeScript + Vite + shadcn/ui; pytest, vitest.

**Spec:** [docs/superpowers/specs/2026-07-11-layout-analysis-capability-design.md](../specs/2026-07-11-layout-analysis-capability-design.md)

## Global Constraints

- **Pre-implementation gate (CLAUDE.md):** before writing code for each PR, create a GitHub issue with acceptance criteria derived from this plan and confirm it with the user. Work on a feature branch. Two PRs → two issues.
- Backend tests run on SQLite in-memory; run with `cd backend && uv run python -m pytest -o "addopts=" <path>`.
- All DB/async code uses type hints; services raise, routers catch (not exercised here — this is adapter/runner code).
- Frontend: shadcn/ui + Tailwind only; `cd frontend && npm run lint && npm run build && npx vitest run` must pass.
- `datetime.now(timezone.utc)` — never `datetime.utcnow()` (deprecated on 3.12).
- No DB migration and no legacy-config compat shim: this is a sole-user prototype; stale dev runs are wiped/ignored.
- Capability name is **`layout_analysis`** (not `structure`); the slot label in the UI is "Layout analysis".

---

# PR A — Unify the capability model (pure refactor)

**Branch:** `feat/layout-analysis-pr-a-unify`
**Acceptance:** for every fixture and every pipeline expressible today, the new pipeline produces content-identical `ParsedDocument`s (proven against captured goldens); full backend + frontend suites green.

## Task A1: Capture equivalence goldens from the current pipeline

Capture the *current* (pre-refactor) output so the rename can be proven equivalent. This task makes **no production change** — it only adds shared fixture builders and committed golden JSONs.

**Files:**
- Create: `backend/tests/cdm/adapters/custom_pipeline/fixtures/equivalence_fixtures.py`
- Create: `backend/tests/cdm/adapters/custom_pipeline/fixtures/equivalence/` (golden JSONs land here)
- Create: `backend/scripts/capture_equivalence_golden.py`

**Interfaces:**
- Produces: `build_text_pdf(path: Path) -> None`, `build_table_pdf(path: Path) -> None`, `EQUIV_CONFIGS: dict[str, dict]` (config keyed by golden name, using the **current** `text_extraction` contract), `content_projection(doc) -> dict`.

- [ ] **Step 1: Write the shared fixture builders + projection helper**

Create `backend/tests/cdm/adapters/custom_pipeline/fixtures/equivalence_fixtures.py`:

```python
"""Shared fixtures for the PR A equivalence gate.

Both the golden-capture script (run once, pre-refactor) and the post-refactor
comparison test import these, so the two sides can never drift.
"""
from __future__ import annotations

from pathlib import Path

import fitz


def build_text_pdf(path: Path) -> None:
    """Two text blocks, no table — exercises plain text_extraction."""
    d = fitz.open()
    page = d.new_page(width=595, height=842)
    page.insert_text(fitz.Point(72, 72), "Quarterly revenue report", fontsize=14)
    page.insert_text(fitz.Point(72, 110), "Figures are provisional.", fontsize=10)
    d.save(str(path)); d.close()


def build_table_pdf(path: Path) -> None:
    """Text plus a ruled grid — exercises text + table_detection + eviction."""
    d = fitz.open()
    page = d.new_page(width=595, height=842)
    page.insert_text(fitz.Point(72, 72), "Quarterly revenue report", fontsize=14)
    col_x, row_y = [72, 236, 400], [200, 250, 300]
    for x in col_x:
        page.draw_line(fitz.Point(x, row_y[0]), fitz.Point(x, row_y[-1]), width=1)
    for y in row_y:
        page.draw_line(fitz.Point(col_x[0], y), fitz.Point(col_x[-1], y), width=1)
    page.insert_text(fitz.Point(80, 235), "Name", fontsize=11)
    page.insert_text(fitz.Point(244, 235), "Value", fontsize=11)
    page.insert_text(fitz.Point(80, 285), "alpha", fontsize=11)
    page.insert_text(fitz.Point(244, 285), "1", fontsize=11)
    d.save(str(path)); d.close()


# Config keyed by golden name. NOTE: written in the *current* contract
# (capabilities.text_extraction). Task A5's comparison test rewrites the key to
# layout_analysis and asserts the produced content still matches these goldens —
# proving the rename changed nothing.
EQUIV_CONFIGS: dict[str, dict] = {
    "text_only": {
        "tools": {"fitz": {"tool": "fitz", "config": {}}},
        "capabilities": {"text_extraction": "fitz"},
    },
    "text_plus_table": {
        "tools": {"fitz": {"tool": "fitz", "config": {}},
                  "tbl": {"tool": "fitz_tables", "config": {}}},
        "capabilities": {"text_extraction": "fitz", "table_detection": "tbl"},
    },
}

_BUILDERS = {"text_only": build_text_pdf, "text_plus_table": build_table_pdf}


def build_for(name: str, path: Path) -> None:
    _BUILDERS[name](path)


def content_projection(doc) -> dict:
    """Stable, volatile-field-free projection of a ParsedDocument.

    Excludes `id` and `parse_run_id` (random/UUID per run); everything that
    describes *content* — pages, blocks, text, markdown — is deterministic
    because block ids derive from the fixed source_document_id.
    """
    return doc.model_dump(
        mode="json",
        include={"page_count", "pages", "blocks", "full_text", "full_markdown"},
    )
```

- [ ] **Step 2: Write the capture script**

Create `backend/scripts/capture_equivalence_golden.py`:

```python
"""Run ONCE on the pre-refactor branch to snapshot current pipeline output.

    cd backend && uv run python scripts/capture_equivalence_golden.py

Writes tests/.../fixtures/equivalence/<name>.json. Commit the results; Task A5's
test compares the post-refactor pipeline against them.
"""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.cdm.source import SourceDocument
from app.services.parsing.custom_pipeline_runner import run_custom_pipeline
from tests.cdm.adapters.custom_pipeline.fixtures.equivalence_fixtures import (
    EQUIV_CONFIGS, build_for, content_projection,
)

GOLDEN_DIR = (Path(__file__).resolve().parents[1]
              / "tests/cdm/adapters/custom_pipeline/fixtures/equivalence")


def _source() -> SourceDocument:
    return SourceDocument(
        id="src-1", sha256="b" * 64, filename="equiv.pdf",
        mime_type="application/pdf", byte_size=1234,
        created_at=datetime.now(timezone.utc),
    )


async def main() -> None:
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    for name, config in EQUIV_CONFIGS.items():
        pdf = GOLDEN_DIR / f"{name}.pdf"
        build_for(name, pdf)
        _, parsed = await run_custom_pipeline(
            source=_source(), file_path=str(pdf),
            representation_kind="extract_rich", config=config, client=None)
        (GOLDEN_DIR / f"{name}.json").write_text(
            json.dumps(content_projection(parsed), indent=2, sort_keys=True))
        pdf.unlink(missing_ok=True)
        print(f"captured {name}")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 3: Run the capture script**

Run: `cd backend && uv run python scripts/capture_equivalence_golden.py`
Expected: prints `captured text_only` and `captured text_plus_table`; two `.json` files appear in `fixtures/equivalence/`.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/cdm/adapters/custom_pipeline/fixtures/equivalence_fixtures.py \
        backend/scripts/capture_equivalence_golden.py \
        backend/tests/cdm/adapters/custom_pipeline/fixtures/equivalence/
git commit -m "test: capture pre-refactor equivalence goldens for layout_analysis rename"
```

## Task A2: Collapse the capability enum

**Files:**
- Modify: `backend/app/cdm/adapters/custom_pipeline/capabilities.py`
- Test: `backend/tests/cdm/adapters/custom_pipeline/test_capabilities.py`

**Interfaces:**
- Produces: `Capability.LAYOUT_ANALYSIS` is block-producing; `Capability.TEXT_EXTRACTION` no longer exists; `resolve_precedence` ranks `LAYOUT_ANALYSIS` where it ranked `TEXT_EXTRACTION`.

- [ ] **Step 1: Update the failing test first**

Edit `backend/tests/cdm/adapters/custom_pipeline/test_capabilities.py` — replace every `Capability.TEXT_EXTRACTION` with `Capability.LAYOUT_ANALYSIS`, and assert layout is block-producing. Add:

```python
from app.cdm.adapters.custom_pipeline.capabilities import (
    BLOCK_PRODUCING, STAGING, Capability, resolve_precedence,
)


def test_layout_analysis_is_block_producing():
    assert Capability.LAYOUT_ANALYSIS in BLOCK_PRODUCING
    assert Capability.LAYOUT_ANALYSIS not in STAGING


def test_text_extraction_is_gone():
    assert not hasattr(Capability, "TEXT_EXTRACTION")


def test_precedence_ranks_layout_below_tables():
    ranks = resolve_precedence(cid_corrupt=False, ocr_prefer=False)
    assert ranks[Capability.TABLE_DETECTION] > ranks[Capability.LAYOUT_ANALYSIS]
    assert ranks[Capability.LAYOUT_ANALYSIS] > ranks[Capability.TEXT_OCR]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/cdm/adapters/custom_pipeline/test_capabilities.py -v`
Expected: FAIL — `AttributeError: LAYOUT_ANALYSIS`/`TEXT_EXTRACTION` still referenced.

- [ ] **Step 3: Rewrite `capabilities.py`**

```python
"""IDP capabilities and their precedence.

One tool fills at most one capability slot. Blocks are tagged with the
capability that produced them; the merger ranks blocks by that tag.
"""
from __future__ import annotations

from enum import Enum
from typing import Dict


class Capability(str, Enum):
    LAYOUT_ANALYSIS = "layout_analysis"   # required structure slot (fitz tier-0, docling tier-1)
    TABLE_DETECTION = "table_detection"
    TEXT_OCR = "text_ocr"


#: Capabilities whose blocks compete for page area (governed by precedence).
BLOCK_PRODUCING = frozenset({
    Capability.LAYOUT_ANALYSIS,
    Capability.TABLE_DETECTION,
    Capability.TEXT_OCR,
})

#: Capabilities that order/route rather than compete. Empty for now — the
#: router slice refills this with bbox+label-only layout detectors.
STAGING: frozenset[Capability] = frozenset()


def resolve_precedence(*, cid_corrupt: bool, ocr_prefer: bool) -> Dict[Capability, int]:
    """Rank block-producing capabilities for one page. Higher wins.

    Structure always beats loose text. The only variable is whether OCR sits
    above or below the structure text — the CID flip and `prefer` are the same
    mechanism, applied per-page vs per-run.
    """
    ocr_outranks_text = ocr_prefer or cid_corrupt
    if ocr_outranks_text:
        return {
            Capability.TABLE_DETECTION: 3,
            Capability.TEXT_OCR: 2,
            Capability.LAYOUT_ANALYSIS: 1,
        }
    return {
        Capability.TABLE_DETECTION: 3,
        Capability.LAYOUT_ANALYSIS: 2,
        Capability.TEXT_OCR: 1,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/cdm/adapters/custom_pipeline/test_capabilities.py -v`
Expected: PASS. (Other modules still reference `TEXT_EXTRACTION` and will fail their own suites until Task A3/A4 — that's expected; do not run the full suite yet.)

- [ ] **Step 5: Commit**

```bash
git add backend/app/cdm/adapters/custom_pipeline/capabilities.py \
        backend/tests/cdm/adapters/custom_pipeline/test_capabilities.py
git commit -m "refactor: collapse text_extraction into block-producing layout_analysis"
```

## Task A3: Point config, fitz, and base at `layout_analysis`

**Files:**
- Modify: `backend/app/cdm/adapters/custom_pipeline/config.py:120` (required-slot check)
- Modify: `backend/app/cdm/adapters/custom_pipeline/tools/fitz_tool.py:61,72` (`provides`, default `emit`)
- Modify: `backend/app/cdm/adapters/custom_pipeline/tools/base.py:22-23` (PageMeta docstring)
- Test: `backend/tests/cdm/adapters/custom_pipeline/test_config.py`, `backend/tests/cdm/adapters/custom_pipeline/test_fitz_tool.py`

**Interfaces:**
- Consumes: `Capability.LAYOUT_ANALYSIS` (Task A2).
- Produces: `build_pipeline_config` requires `layout_analysis`; `FitzTool.provides == {LAYOUT_ANALYSIS}`.

- [ ] **Step 1: Update the failing tests**

In `backend/tests/cdm/adapters/custom_pipeline/test_config.py`: replace every `"text_extraction"` config key with `"layout_analysis"` and every `Capability.TEXT_EXTRACTION` with `Capability.LAYOUT_ANALYSIS`. Update the two tests whose meaning inverts:

```python
def test_layout_analysis_slot_is_required():
    with pytest.raises(ValueError, match="layout_analysis"):
        build_pipeline_config({"tools": {}, "capabilities": {}})


def test_layout_analysis_is_fillable_now():
    # Was test_staging_capability_has_no_tools_yet — layout is block-producing now.
    cfg = {"tools": {"f": {"tool": "fitz"}},
           "capabilities": {"layout_analysis": "f"}}
    p = build_pipeline_config(cfg)
    assert p.for_capability(Capability.LAYOUT_ANALYSIS).key == "f"
```

Delete the old `test_staging_capability_has_no_tools_yet`. In `test_fitz_tool.py`, replace `Capability.TEXT_EXTRACTION` with `Capability.LAYOUT_ANALYSIS` throughout.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/cdm/adapters/custom_pipeline/test_config.py tests/cdm/adapters/custom_pipeline/test_fitz_tool.py -v`
Expected: FAIL — required-slot check still says `text_extraction`; `FitzTool.provides` still `{TEXT_EXTRACTION}`.

- [ ] **Step 3: Edit `config.py`**

Change the required-slot guard (was `config.py:120-121`):

```python
    if Capability.LAYOUT_ANALYSIS not in slots:
        raise ValueError("capability 'layout_analysis' is required")
```

(No other change needed in `config.py` — the staging-rejection guard at the top of the loop now permits `layout_analysis` automatically because it is in `BLOCK_PRODUCING`.)

- [ ] **Step 4: Edit `fitz_tool.py`**

```python
    tool_id = "fitz"
    provides = frozenset({Capability.LAYOUT_ANALYSIS})
```

And the `run` default emit (was `fitz_tool.py:72`) and the returned `blocks_by_capability` key (was `fitz_tool.py:151`):

```python
        emit: frozenset[Capability] = frozenset({Capability.LAYOUT_ANALYSIS}),
```
```python
            blocks_by_capability={Capability.LAYOUT_ANALYSIS: blocks},
```

- [ ] **Step 5: Edit `base.py` PageMeta docstring**

```python
class PageMeta(BaseModel):
    """Authoritative page geometry, sourced from the structure (layout_analysis) tool."""
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/cdm/adapters/custom_pipeline/test_config.py tests/cdm/adapters/custom_pipeline/test_fitz_tool.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/cdm/adapters/custom_pipeline/config.py \
        backend/app/cdm/adapters/custom_pipeline/tools/fitz_tool.py \
        backend/app/cdm/adapters/custom_pipeline/tools/base.py \
        backend/tests/cdm/adapters/custom_pipeline/test_config.py \
        backend/tests/cdm/adapters/custom_pipeline/test_fitz_tool.py
git commit -m "refactor: require layout_analysis slot; fitz provides it"
```

## Task A4: Rename the runner's structure instance

**Files:**
- Modify: `backend/app/services/parsing/custom_pipeline_runner.py:57-62`
- Test: `backend/tests/services/parsing/test_custom_pipeline_runner.py`

**Interfaces:**
- Consumes: `Capability.LAYOUT_ANALYSIS`.
- Produces: runner resolves the structure instance via `LAYOUT_ANALYSIS`, still runs it first and supplies its `page_meta`.

- [ ] **Step 1: Update the failing test**

In `test_custom_pipeline_runner.py`, replace `"text_extraction"` config keys with `"layout_analysis"` and any `Capability.TEXT_EXTRACTION` with `Capability.LAYOUT_ANALYSIS`.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/parsing/test_custom_pipeline_runner.py -v`
Expected: FAIL — runner still looks up `TEXT_EXTRACTION`.

- [ ] **Step 3: Edit the runner**

Replace `custom_pipeline_runner.py:57-62`:

```python
        structure_instance = pipeline.for_capability(Capability.LAYOUT_ANALYSIS)
        # build_pipeline_config guarantees this, but fail loudly if it ever does not.
        if structure_instance is None:
            raise ValueError("capability 'layout_analysis' is required")

        structure_result = structure_instance.tool.run(pdf_path, emit=structure_instance.emit)
        results = [structure_result]
        warnings = list(structure_result.warnings)
```

Then in the loop and the adapter call, rename `text_instance` → `structure_instance` and `text_result` → `structure_result` (was `custom_pipeline_runner.py:70,78,112`):

```python
        for inst in pipeline.instances:
            if inst is structure_instance:
                continue
```
```python
            r = inst.tool.run(
                pdf_path, pages=pages, page_meta=structure_result.page_meta, emit=inst.emit)
```
```python
    doc = adapter.adapt(
        {"page_meta": structure_result.page_meta, "blocks": merge_result.blocks},
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/parsing/test_custom_pipeline_runner.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/parsing/custom_pipeline_runner.py \
        backend/tests/services/parsing/test_custom_pipeline_runner.py
git commit -m "refactor: runner resolves the structure instance via layout_analysis"
```

## Task A5: Prove equivalence + green the whole backend

**Files:**
- Modify: `backend/tests/cdm/adapters/custom_pipeline/test_refactor_equivalence.py`

**Interfaces:**
- Consumes: goldens from Task A1; `content_projection`, `EQUIV_CONFIGS`, `build_for`.

- [ ] **Step 1: Update the existing behavioural equivalence tests**

In `test_refactor_equivalence.py`, replace every `"text_extraction"` config key with `"layout_analysis"` (lines 56, 77, 103, 107). The structural asserts (reading order contiguous, `src-1:0:0` id scheme, table eviction records) are unchanged.

- [ ] **Step 2: Add the golden-snapshot test**

Append to `test_refactor_equivalence.py`:

```python
import json
from pathlib import Path

import pytest

from tests.cdm.adapters.custom_pipeline.fixtures.equivalence_fixtures import (
    EQUIV_CONFIGS, build_for, content_projection,
)

_GOLDEN_DIR = Path(__file__).parent / "fixtures" / "equivalence"


def _relabel(config: dict) -> dict:
    """Rewrite the captured text_extraction key to layout_analysis."""
    caps = dict(config["capabilities"])
    caps["layout_analysis"] = caps.pop("text_extraction")
    return {**config, "capabilities": caps}


@pytest.mark.asyncio
@pytest.mark.parametrize("name", list(EQUIV_CONFIGS))
async def test_output_matches_pre_refactor_golden(name, tmp_path):
    golden = json.loads((_GOLDEN_DIR / f"{name}.json").read_text())
    pdf = tmp_path / f"{name}.pdf"
    build_for(name, pdf)
    _, parsed = await run_custom_pipeline(
        source=_source(), file_path=str(pdf),
        representation_kind="extract_rich",
        config=_relabel(EQUIV_CONFIGS[name]), client=None)
    assert content_projection(parsed) == golden
```

- [ ] **Step 3: Run the equivalence suite**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/cdm/adapters/custom_pipeline/test_refactor_equivalence.py -v`
Expected: PASS — content-identical to the goldens captured in Task A1.

- [ ] **Step 4: Run the full parsing + cdm backend suites**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/cdm tests/services/parsing -q`
Expected: PASS. (Note: `tests/cdm/adapters/test_docling_adapter.py` still passes — it targets the untouched standalone `DoclingAdapter`, retired in PR B.)

- [ ] **Step 5: Commit**

```bash
git add backend/tests/cdm/adapters/custom_pipeline/test_refactor_equivalence.py
git commit -m "test: prove layout_analysis rename is content-equivalent to pre-refactor"
```

## Task A6: Frontend — relabel the slot as Layout analysis

**Files:**
- Modify: `frontend/src/components/documents/parser-configs/CustomPipelineConfig.tsx` (`:363-368`, `:404-407`, `:483-484`, `:525-540`)
- Modify: `frontend/src/components/documents/ParseMethodSelector.tsx:51`
- Test: `frontend/src/components/documents/parser-configs/CustomPipelineConfig.test.tsx`

**Interfaces:**
- Produces: config emits `capabilities.layout_analysis`; UI slot titled "Layout analysis".

- [ ] **Step 1: Update the failing test**

In `CustomPipelineConfig.test.tsx`, change assertions referencing the "Text extraction" label/slot to "Layout analysis", and any emitted `capabilities.text_extraction` to `capabilities.layout_analysis`. (Open the file and update the specific queries — `getByLabelText('Text extraction')` → `getByLabelText('Layout analysis')`, and config-shape assertions.)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/documents/parser-configs/CustomPipelineConfig.test.tsx`
Expected: FAIL — component still renders "Text extraction" and emits `text_extraction`.

- [ ] **Step 3: Edit `CustomPipelineConfig.tsx`**

`CAPABILITY_BY_TOOL` (`:363`):

```tsx
const CAPABILITY_BY_TOOL: Record<string, string> = {
  fitz: 'layout_analysis',
  pdfplumber: 'layout_analysis',
  fitz_tables: 'table_detection',
  camelot: 'table_detection',
}
```

The required-slot guarantee in `normalizeCustomPipelineConfig` (`:404-407`):

```tsx
  // Guarantee the required layout_analysis slot.
  if (!capabilities.layout_analysis) {
    if (!tools.fitz) tools.fitz = { tool: 'fitz', config: {} }
    capabilities.layout_analysis = 'fitz'
  }
```

The slot key read (`:483`):

```tsx
  const textKey = capabilities.layout_analysis ?? 'fitz'
```

The slot header block (`:525-540`) — label, help text, and `aria-label`:

```tsx
      {/* Layout analysis — the required structure slot */}
      <div className="space-y-2 rounded-md border p-3">
        <div className="space-y-1">
          <Label htmlFor="layout-tool-select">Layout analysis</Label>
          <p className="text-xs text-muted-foreground">
            Turns each page into ordered, labelled regions. Required — every pipeline fills this slot.
            fitz is fast, local, and text-only (no real layout yet).
          </p>
          <Select value={textKey} onValueChange={() => {}} disabled={disabled}>
            <SelectTrigger id="layout-tool-select" aria-label="Layout analysis">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="fitz">fitz (text + images)</SelectItem>
            </SelectContent>
          </Select>
        </div>
```

(Leave the fitz `include_images` / `span_detail` checkboxes below it unchanged. The `onValueChange={() => {}}` stays inert in PR A — fitz is still the only option; PR B Task B5 makes it a real selector.)

- [ ] **Step 4: Edit `ParseMethodSelector.tsx`**

The `custom_pipeline` default config's `capabilities` key (`:51`):

```tsx
      capabilities: { layout_analysis: 'fitz' },
```

- [ ] **Step 5: Run test, lint, build**

Run: `cd frontend && npx vitest run src/components/documents/parser-configs/CustomPipelineConfig.test.tsx && npm run lint && npm run build`
Expected: PASS on all three.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/documents/parser-configs/CustomPipelineConfig.tsx \
        frontend/src/components/documents/parser-configs/CustomPipelineConfig.test.tsx \
        frontend/src/components/documents/ParseMethodSelector.tsx
git commit -m "refactor(ui): rename text extraction slot to Layout analysis"
```

**PR A is complete.** Open the PR, confirm the equivalence gate is green, and merge before starting PR B.

---

# PR B — Docling as the tier-1 authoritative tool

**Branch:** `feat/layout-analysis-pr-b-docling`
**Acceptance:** a two-column fixture parses with docling into correct cross-column order; fitz output unchanged (goldens still pass); standalone `ParserKind.DOCLING` removed; suites green.

## Task B1: Merger honours intrinsic reading order

**Files:**
- Modify: `backend/app/cdm/adapters/custom_pipeline/merger.py:40-43`
- Test: `backend/tests/cdm/adapters/custom_pipeline/test_merger.py`

**Interfaces:**
- Produces: within a page, blocks with a non-`None` `reading_order` sort by it; blocks without fall back to `(bbox.y0, bbox.x0)`, ordered after the intrinsic ones.

- [ ] **Step 1: Write the failing test**

Add to `test_merger.py`:

```python
from app.cdm.adapters.custom_pipeline.merger import _sort_key
from app.cdm.models import BBox, Block, BlockRole


def _blk(bid, y0, order=None):
    return Block(id=bid, role=BlockRole.TEXT, native_type="text", text=bid,
                 page_index=0, bbox=BBox(x0=0.0, y0=y0, x1=1.0, y1=y0 + 0.1),
                 reading_order=order)


def test_sort_key_honours_intrinsic_order_over_geometry():
    # Higher on the page (smaller y0) but LATER intrinsic order -> sorts later.
    top_late = _blk("a", y0=0.1, order=5)
    bottom_early = _blk("b", y0=0.8, order=1)
    ordered = sorted([top_late, bottom_early], key=_sort_key)
    assert [b.id for b in ordered] == ["b", "a"]


def test_sort_key_falls_back_to_geometry_without_order():
    top = _blk("a", y0=0.1, order=None)
    bottom = _blk("b", y0=0.8, order=None)
    ordered = sorted([bottom, top], key=_sort_key)
    assert [b.id for b in ordered] == ["a", "b"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/cdm/adapters/custom_pipeline/test_merger.py::test_sort_key_honours_intrinsic_order_over_geometry -v`
Expected: FAIL — current `_sort_key` ignores `reading_order`.

- [ ] **Step 3: Edit `_sort_key` in `merger.py`**

```python
def _sort_key(block: Block) -> Tuple[float, float, float]:
    # A producer that supplies its own reading order (e.g. a layout model that
    # crosses columns correctly) is honoured; producers that don't (fitz) fall
    # back to top-to-bottom, left-to-right geometry and sort after.
    order = float(block.reading_order) if block.reading_order is not None else 1e9
    if block.bbox is None:
        return (order, 1e9, 1e9)
    return (order, block.bbox.y0, block.bbox.x0)
```

- [ ] **Step 4: Run the merger + ocr + equivalence suites**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/cdm/adapters/custom_pipeline/test_merger.py tests/cdm/adapters/custom_pipeline/test_ocr_reconciliation.py tests/cdm/adapters/custom_pipeline/test_refactor_equivalence.py -v`
Expected: PASS — fitz/OCR blocks carry no `reading_order`, so the fallback preserves existing behaviour and the goldens still match.

- [ ] **Step 5: Commit**

```bash
git add backend/app/cdm/adapters/custom_pipeline/merger.py \
        backend/tests/cdm/adapters/custom_pipeline/test_merger.py
git commit -m "feat: merger honours a producer's intrinsic reading order (multi-column fix)"
```

## Task B2: DoclingTool + DoclingConfig + registry

Reuses the pure helpers already in `app/cdm/adapters/docling.py` (`_to_cdm_bbox`, `_map_role`, `_map_table`) — those stay put; only the `DoclingAdapter` class and the standalone runner are removed later (Task B4).

**Files:**
- Create: `backend/app/cdm/adapters/custom_pipeline/tools/docling_tool.py`
- Modify: `backend/app/cdm/adapters/custom_pipeline/config.py:19-57` (add `DoclingConfig`), `:67-82` (register in `_tool_registry`)
- Test: `backend/tests/cdm/adapters/custom_pipeline/tools/test_docling_tool.py`

**Interfaces:**
- Consumes: `PipelineTool`, `ToolResult`, `PageMeta`, `Capability.LAYOUT_ANALYSIS`; helpers from `app.cdm.adapters.docling`.
- Produces: `DoclingTool(config: DoclingConfig)` with `tool_id="docling"`, `provides=frozenset({LAYOUT_ANALYSIS})`, and `run(pdf_path, *, pages=None, page_meta=None, emit) -> ToolResult` whose blocks carry provisional ids `docling:{page}:{order}` and a populated `reading_order`. `DoclingConfig(page_batch_size: int = 20)`.

- [ ] **Step 1: Write the failing unit test**

Create `backend/tests/cdm/adapters/custom_pipeline/tools/test_docling_tool.py` (reuses the fake-doc helpers pattern from `tests/cdm/adapters/test_docling_adapter.py`):

```python
"""DoclingTool — unit tests using a fake DoclingDocument (no docling binary)."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.cdm.adapters.custom_pipeline.capabilities import Capability
from app.cdm.adapters.custom_pipeline.config import DoclingConfig
from app.cdm.models import BlockRole


def _fake_bbox(l=50.0, t=750.0, r=545.0, b=700.0):
    return SimpleNamespace(l=l, t=t, r=r, b=b, coord_origin="BOTTOMLEFT")


def _fake_text_item(text, label="text", page_no=1):
    return SimpleNamespace(
        label=SimpleNamespace(value=label), text=text,
        prov=[SimpleNamespace(page_no=page_no, bbox=_fake_bbox())],
        export_to_markdown=lambda: text)


def _fake_doc(items, width=595.0, height=842.0):
    return SimpleNamespace(
        pages={1: SimpleNamespace(size=SimpleNamespace(width=width, height=height))},
        iterate_items=lambda: iter([(it, 0) for it in items]),
        export_to_markdown=lambda: "\n\n".join(i.text for i in items),
        model_dump_json=lambda: "{}",
    )


@pytest.fixture
def tool_result(monkeypatch, tmp_path):
    from app.cdm.adapters.custom_pipeline.tools import docling_tool
    items = [_fake_text_item("Annual Report", "title"),
             _fake_text_item("Body one", "text"),
             _fake_text_item("Body two", "text")]
    # Stub the heavy conversion: return one batch's fake document.
    monkeypatch.setattr(docling_tool, "_convert_batch",
                        lambda path: _fake_doc(items))
    pdf = tmp_path / "doc.pdf"; pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")
    monkeypatch.setattr(docling_tool, "_split_pages",
                        lambda path, size: [(path, 0)])
    tool = docling_tool.DoclingTool(config=DoclingConfig())
    return tool.run(pdf, emit=frozenset({Capability.LAYOUT_ANALYSIS}))


def test_emits_layout_analysis_blocks(tool_result):
    blocks = tool_result.blocks_by_capability[Capability.LAYOUT_ANALYSIS]
    assert [b.role for b in blocks][0] == BlockRole.TITLE
    assert len(blocks) == 3


def test_blocks_carry_intrinsic_reading_order(tool_result):
    blocks = tool_result.blocks_by_capability[Capability.LAYOUT_ANALYSIS]
    assert [b.reading_order for b in blocks] == [0, 1, 2]


def test_provisional_ids_and_page_meta(tool_result):
    blocks = tool_result.blocks_by_capability[Capability.LAYOUT_ANALYSIS]
    assert blocks[0].id == "docling:0:0"
    assert tool_result.page_meta[0].width == 595.0


def test_bboxes_normalized(tool_result):
    for b in tool_result.blocks_by_capability[Capability.LAYOUT_ANALYSIS]:
        assert 0.0 <= b.bbox.x0 <= b.bbox.x1 <= 1.0
        assert 0.0 <= b.bbox.y0 <= b.bbox.y1 <= 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/cdm/adapters/custom_pipeline/tools/test_docling_tool.py -v`
Expected: FAIL — `docling_tool` module does not exist.

- [ ] **Step 3: Create `docling_tool.py`**

```python
"""DoclingTool — tier-1 authoritative layout analysis for the custom pipeline.

Docling's `iterate_items()` order IS reading order (it crosses columns
correctly), so blocks are emitted with an intrinsic `reading_order` the merger
honours. Text, headings, and tables all come out of a single conversion pass;
this tool fills only the layout_analysis slot for now (table content flows
through as ordinary BlockRole.TABLE blocks).
"""
from __future__ import annotations

import json
import logging
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.cdm.adapters.custom_pipeline.capabilities import Capability
from app.cdm.adapters.custom_pipeline.tools.base import PageMeta, ToolResult
from app.cdm.adapters.docling import _map_role, _map_table, _to_cdm_bbox
from app.cdm.models import Block, BlockRole

logger = logging.getLogger(__name__)

# Docling is memory-hungry; serialize concurrent conversions. run() executes in
# a worker thread (the runner offloads it via asyncio.to_thread), so a threading
# lock is the right primitive. Fixed at 1 for this slice; revisited with the job
# queue. See design §4.
_DOCLING_LOCK = threading.Lock()


def _split_pages(pdf_path: Path, batch_size: int) -> List[Tuple[Path, int]]:
    """Split into (batch_path, page_offset). One batch => original file, offset 0."""
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(str(pdf_path))
    total = len(reader.pages)
    if total <= batch_size:
        return [(pdf_path, 0)]

    batches: List[Tuple[Path, int]] = []
    for start in range(0, total, batch_size):
        writer = PdfWriter()
        for i in range(start, min(start + batch_size, total)):
            writer.add_page(reader.pages[i])
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            writer.write(tmp)
            batches.append((Path(tmp.name), start))
    return batches


def _convert_batch(pdf_path: Path) -> Any:
    """Heavy docling conversion. Returns a DoclingDocument."""
    from docling.document_converter import DocumentConverter
    return DocumentConverter().convert(str(pdf_path)).document


class DoclingConfig:
    """Kept minimal on purpose; add knobs when we learn what matters."""
    def __init__(self, page_batch_size: int = 20) -> None:
        self.page_batch_size = page_batch_size

    @classmethod
    def model_validate(cls, data: Dict[str, Any]) -> "DoclingConfig":
        return cls(page_batch_size=int((data or {}).get("page_batch_size", 20)))


class DoclingTool:
    tool_id = "docling"
    provides = frozenset({Capability.LAYOUT_ANALYSIS})

    def __init__(self, config: Optional[DoclingConfig] = None) -> None:
        self.config = config or DoclingConfig()

    def run(
        self,
        pdf_path: Path,
        *,
        pages: Optional[List[int]] = None,       # ignored: docling is the source
        page_meta: Optional[Dict[int, PageMeta]] = None,  # ignored: docling is the source
        emit: frozenset[Capability] = frozenset({Capability.LAYOUT_ANALYSIS}),
    ) -> ToolResult:
        if not emit <= self.provides:
            raise ValueError(f"{self.tool_id} cannot emit {set(emit - self.provides)}")

        t0 = time.perf_counter()
        blocks: List[Block] = []
        page_meta_out: Dict[int, PageMeta] = {}
        native_by_block: Dict[str, Any] = {}
        warnings: List[str] = []
        raw_batches: List[Any] = []

        batches = _split_pages(pdf_path, self.config.page_batch_size)
        made_temp = len(batches) > 1
        try:
            with _DOCLING_LOCK:
                for batch_path, page_offset in batches:
                    doc = _convert_batch(batch_path)
                    raw_batches.append(doc)
                    self._collect(doc, page_offset, blocks, page_meta_out,
                                  native_by_block, warnings)
        finally:
            if made_temp:
                for batch_path, _ in batches:
                    Path(batch_path).unlink(missing_ok=True)

        raw: Any = None
        try:
            raw = ([json.loads(d.model_dump_json()) for d in raw_batches]
                   if len(raw_batches) != 1 else json.loads(raw_batches[0].model_dump_json()))
        except Exception as exc:  # noqa: BLE001
            logger.warning("docling: raw serialization failed: %s", exc)

        return ToolResult(
            tool_id=self.tool_id,
            blocks_by_capability={Capability.LAYOUT_ANALYSIS: blocks},
            page_meta=page_meta_out,
            raw=raw,
            native_by_block=native_by_block,
            warnings=warnings,
            duration_ms=int((time.perf_counter() - t0) * 1000),
        )

    def _collect(self, doc, page_offset, blocks, page_meta_out,
                 native_by_block, warnings) -> None:
        page_sizes: Dict[int, Tuple[float, float]] = {}
        for page_no, page_item in doc.pages.items():
            size = getattr(page_item, "size", None)
            w = size.width if size else 595.0
            h = size.height if size else 842.0
            idx = (int(page_no) - 1) + page_offset
            page_sizes[int(page_no)] = (w, h)
            page_meta_out[idx] = PageMeta(index=idx, width=w, height=h)

        for order, (item, depth) in enumerate(doc.iterate_items()):
            prov_list = getattr(item, "prov", None) or []
            if not prov_list:
                continue
            prov = prov_list[0]
            page_no = int(prov.page_no)
            page_index = (page_no - 1) + page_offset
            w, h = page_sizes.get(page_no, (595.0, 842.0))

            bbox = None
            raw_bbox = getattr(prov, "bbox", None)
            if raw_bbox is not None:
                try:
                    bbox = _to_cdm_bbox(raw_bbox, w, h)
                except Exception:  # noqa: BLE001
                    pass

            role = _map_role(item.label)
            table = None
            if role == BlockRole.TABLE:
                try:
                    table = _map_table(item)
                except Exception:  # noqa: BLE001
                    pass

            md = None
            try:
                md = item.export_to_markdown() or None
            except Exception:  # noqa: BLE001
                pass
            text = getattr(item, "text", "") or (md or "")

            prov_id = f"{self.tool_id}:{page_index}:{order}"
            blocks.append(Block(
                id=prov_id, role=role, native_type=item.label.value,
                text=text, markdown=md, page_index=page_index, bbox=bbox,
                reading_order=order,
                depth=depth if role == BlockRole.HEADING else None,
                table=table,
                parser_extras={"producer": "docling", "capability": "layout_analysis"},
            ))
            native_by_block[prov_id] = {"label": item.label.value, "markdown": md}
```

- [ ] **Step 4: Register the tool in `config.py`**

Add `DoclingConfig` import isn't needed (it lives in the tool module). In `_tool_registry()` (`config.py:67-82`), add the docling import and entry:

```python
    from app.cdm.adapters.custom_pipeline.tools.docling_tool import DoclingConfig, DoclingTool
```
```python
        "docling": ToolSpec(DoclingConfig, DoclingTool.provides,
                            lambda c: DoclingTool(config=c)),
```

Re-export `DoclingConfig` from `config` for the test import — add at the bottom of `config.py`:

```python
def _docling_config_cls():
    from app.cdm.adapters.custom_pipeline.tools.docling_tool import DoclingConfig
    return DoclingConfig
```

Actually simpler and consistent with the test: import it at module top of `config.py` is circular (config imports tool, tool imports nothing from config). The tool module does **not** import `config`, so add a direct top-level re-export in `config.py`:

```python
from app.cdm.adapters.custom_pipeline.tools.docling_tool import DoclingConfig  # re-export
```

Place this import with the other tool imports is unsafe (they're lazy to avoid heavy deps). Instead, update the test import to `from app.cdm.adapters.custom_pipeline.tools.docling_tool import DoclingConfig` and **remove** the re-export idea. (Fix the Step-1 test import accordingly: it already imports from `...config import DoclingConfig` — change it to import from `...tools.docling_tool`.)

- [ ] **Step 5: Run the DoclingTool unit test**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/cdm/adapters/custom_pipeline/tools/test_docling_tool.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/cdm/adapters/custom_pipeline/tools/docling_tool.py \
        backend/app/cdm/adapters/custom_pipeline/config.py \
        backend/tests/cdm/adapters/custom_pipeline/tools/test_docling_tool.py
git commit -m "feat: DoclingTool fills the layout_analysis slot (tier-1 authoritative)"
```

## Task B3: Runner offloads tool runs off the event loop

**Files:**
- Modify: `backend/app/services/parsing/custom_pipeline_runner.py:62,77`
- Test: `backend/tests/services/parsing/test_custom_pipeline_runner.py`

**Interfaces:**
- Produces: every `tool.run(...)` is awaited via `asyncio.to_thread`, so a heavy parse never blocks the event loop (design §4; fixes review §2.1 for the pipeline path).

- [ ] **Step 1: Write the failing test**

Add to `test_custom_pipeline_runner.py`:

```python
import asyncio


@pytest.mark.asyncio
async def test_tool_run_is_offloaded_to_a_thread(monkeypatch, tmp_path):
    """The event-loop thread must not be the one executing tool.run."""
    import app.services.parsing.custom_pipeline_runner as runner_mod

    loop_thread_id = None

    async def _capture():
        nonlocal loop_thread_id
        import threading
        loop_thread_id = threading.get_ident()
    await _capture()

    seen: dict = {}
    real_to_thread = asyncio.to_thread

    async def _tracking_to_thread(fn, *a, **k):
        import threading
        seen["ran_off_loop"] = threading.get_ident() != loop_thread_id
        return await real_to_thread(fn, *a, **k)

    monkeypatch.setattr(runner_mod.asyncio, "to_thread", _tracking_to_thread)

    pdf = tmp_path / "x.pdf"
    import fitz
    d = fitz.open(); p = d.new_page(); p.insert_text(fitz.Point(72, 72), "hi"); d.save(str(pdf)); d.close()

    from app.cdm.source import SourceDocument
    from datetime import datetime, timezone
    src = SourceDocument(id="src-1", sha256="b" * 64, filename="x.pdf",
                         mime_type="application/pdf", byte_size=1,
                         created_at=datetime.now(timezone.utc))
    await runner_mod.run_custom_pipeline(
        source=src, file_path=str(pdf), representation_kind="extract_rich",
        config={"tools": {"fitz": {"tool": "fitz", "config": {}}},
                "capabilities": {"layout_analysis": "fitz"}}, client=None)
    assert seen.get("ran_off_loop") is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/parsing/test_custom_pipeline_runner.py::test_tool_run_is_offloaded_to_a_thread -v`
Expected: FAIL — `asyncio.to_thread` is never called (runs are inline).

- [ ] **Step 3: Add `import asyncio` and offload the two run sites**

At the top of `custom_pipeline_runner.py` add `import asyncio`. Replace the structure run (was `:62`):

```python
        structure_result = await asyncio.to_thread(
            structure_instance.tool.run, pdf_path, emit=structure_instance.emit)
```

And the loop run (was `:77-78`):

```python
            r = await asyncio.to_thread(
                inst.tool.run, pdf_path, pages=pages,
                page_meta=structure_result.page_meta, emit=inst.emit)
```

- [ ] **Step 4: Run the runner suite**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/parsing/test_custom_pipeline_runner.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/parsing/custom_pipeline_runner.py \
        backend/tests/services/parsing/test_custom_pipeline_runner.py
git commit -m "perf: offload custom-pipeline tool runs off the event loop"
```

## Task B4: Retire the standalone docling parse method (D1)

**Files:**
- Modify: `backend/app/cdm/models.py:20` (remove `DOCLING` from `ParserKind`)
- Modify: `backend/app/services/parsing/parsing_service.py:23,37` (remove import + `_RUNNERS` entry)
- Delete: `backend/app/services/parsing/docling_runner.py`
- Modify: `backend/app/services/parsing/errors.py:25-26` (remove `DoclingRunError`)
- Modify: `backend/app/cdm/adapters/docling.py` (delete the `DoclingAdapter` class + `_mint_block_id`; keep pure helpers `_ROLE_MAP`, `_map_role`, `_to_cdm_bbox`, `_clamp`, `_map_table`)
- Delete: `backend/tests/services/parsing/test_docling_runner.py`
- Modify: `backend/tests/cdm/adapters/test_docling_adapter.py` (drop Task-1 `ParserKind.DOCLING`/`DoclingRunError` tests and the Task-3 `DoclingAdapter.adapt` tests; keep the helper tests for `_to_cdm_bbox`/`_map_role`)

**Interfaces:**
- Produces: docling is reachable **only** via `custom_pipeline` with `layout_analysis: docling`. The pure helpers remain importable from `app.cdm.adapters.docling` (DoclingTool depends on them).

- [ ] **Step 1: Delete the standalone-docling tests first**

Delete `backend/tests/services/parsing/test_docling_runner.py`.

In `test_docling_adapter.py`, delete: `test_parser_kind_docling_value`, `test_docling_run_error_is_parse_run_error`, `test_docling_run_error_carries_run`, the `from app.services.parsing.errors import DoclingRunError, ParseRunError` line, the entire "Task 3: DoclingAdapter.adapt() tests" section (fixtures `simple_doc`/`adapted` and every test using them), and the `_fake_table_item`/`_make_fake_doc`/`_fake_page_item` helpers if now unused. **Keep**: `_fake_bbox`, `_fake_prov`, `_fake_text_item` (if referenced), and all `test_to_cdm_bbox_*`, `test_map_role_*`, `test_mint_block_id_format` → **remove** `test_mint_block_id_format` (that helper is deleted). Rename the file's module docstring to "Tests for docling helper functions."

- [ ] **Step 2: Run the trimmed helper tests to verify they fail to import**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/cdm/adapters/test_docling_adapter.py -v`
Expected: FAIL at collection — still imports `DoclingRunError`, or references removed symbols. (If you removed all such references cleanly, it may instead PASS; proceed either way — the production deletions below are what make it authoritative.)

- [ ] **Step 3: Remove `DOCLING` from `ParserKind`**

In `backend/app/cdm/models.py`, delete line `DOCLING = "docling"` from `class ParserKind`.

- [ ] **Step 4: Remove the runner wiring**

In `parsing_service.py`, delete `from app.services.parsing.docling_runner import run_docling` (`:23`) and the `ParserKind.DOCLING: run_docling,` line in `_RUNNERS` (`:37`).

- [ ] **Step 5: Delete the runner + error**

```bash
git rm backend/app/services/parsing/docling_runner.py
```

In `errors.py`, delete the `DoclingRunError` class (`:25-26`).

- [ ] **Step 6: Trim `docling.py` to helpers only**

Delete the `DoclingAdapter` class and `_mint_block_id` from `app/cdm/adapters/docling.py`. Keep the module docstring (reword to "Docling → CDM mapping helpers, shared by DoclingTool."), the imports still used by the kept helpers, and `_ROLE_MAP`, `_map_role`, `_clamp`, `_to_cdm_bbox`, `_map_table`.

- [ ] **Step 7: Run the affected suites**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/cdm/adapters/test_docling_adapter.py tests/cdm/adapters/custom_pipeline tests/services/parsing tests/models -q`
Expected: PASS. If any test still references `ParserKind.DOCLING` or `DoclingRunError`, fix that reference (search: `grep -rn "DOCLING\|DoclingRunError\|run_docling\|DoclingAdapter" backend/tests backend/app`).

- [ ] **Step 8: Commit**

```bash
git add -A backend/app/cdm/models.py backend/app/services/parsing/parsing_service.py \
        backend/app/services/parsing/errors.py backend/app/cdm/adapters/docling.py \
        backend/tests/cdm/adapters/test_docling_adapter.py
git rm backend/app/services/parsing/docling_runner.py backend/tests/services/parsing/test_docling_runner.py
git commit -m "refactor: retire standalone ParserKind.DOCLING; docling is a pipeline tool"
```

## Task B5: Frontend — docling option in the layout slot + eval default

**Files:**
- Modify: `frontend/src/components/documents/parser-configs/CustomPipelineConfig.tsx` (real layout selector + docling panel)
- Modify: `frontend/src/components/documents/ParseMethodSelector.tsx:36-40` (remove top-level `docling` method)
- Modify: `frontend/src/components/parser-eval/NewRunDialog.tsx:16` (`DEFAULT_ADAPTER`)
- Test: `frontend/src/components/documents/parser-configs/CustomPipelineConfig.test.tsx`, `frontend/src/components/parser-eval/NewRunDialog.test.tsx`

**Interfaces:**
- Produces: the Layout analysis select offers `fitz` and `docling`; choosing docling emits `capabilities.layout_analysis: 'docling'` with a docling instance; eval "Add variant" defaults to a `custom_pipeline` variant.

- [ ] **Step 1: Update the failing tests**

In `CustomPipelineConfig.test.tsx`, add a test that selecting `docling` in the "Layout analysis" combobox emits `capabilities.layout_analysis === 'docling'` and a `tools.docling` instance. In `NewRunDialog.test.tsx`, update the two `docling`/`{}` expectations (`:36,:53`) to the new default adapter `custom_pipeline` and its default config (import `PARSER_REGISTRY` to reference `PARSER_REGISTRY.custom_pipeline.defaultConfig`).

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/components/documents/parser-configs/CustomPipelineConfig.test.tsx src/components/parser-eval/NewRunDialog.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Make the layout selector real in `CustomPipelineConfig.tsx`**

Add a `DOCLING_DEFAULTS` const and a handler, and replace the inert select. Near the other defaults:

```tsx
const DOCLING_DEFAULTS = { page_batch_size: 20 }
```

Replace the layout `Select` (the `onValueChange={() => {}}` block from Task A6) with a real slot swap and a conditional panel:

```tsx
          <Select
            value={textKey}
            onValueChange={(v) =>
              onChange(setSlot(cfg, 'layout_analysis', v,
                v === 'docling' ? { ...DOCLING_DEFAULTS } : {}) as unknown as ParseConfig)
            }
            disabled={disabled}
          >
            <SelectTrigger id="layout-tool-select" aria-label="Layout analysis">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="fitz">fitz — fast, local, text-only</SelectItem>
              <SelectItem value="docling">docling — ML layout + reading order + tables</SelectItem>
            </SelectContent>
          </Select>
```

Guard the fitz-only checkboxes so they show only for fitz, and add a docling panel:

```tsx
        {fitz?.tool === 'fitz' && (
          <>
            {/* existing include_images + span_detail checkboxes */}
          </>
        )}
        {fitz?.tool === 'docling' && (
          <NumField
            id="docling-batch"
            label="Page batch size"
            description="Pages per docling conversion batch"
            value={(fitz?.config.page_batch_size as number) ?? 20}
            onChange={(v) => updateTool(textKey, { page_batch_size: Math.round(v) })}
            disabled={disabled}
          />
        )}
```

- [ ] **Step 4: Remove the top-level docling method + fix eval default**

In `ParseMethodSelector.tsx`, delete the `docling: { … }` entry from `PARSER_REGISTRY` (`:36-40`). **Keep** any `'Docling'` label mapping in `ParserComparisonTable` so historical eval rows still render (verify: `grep -n "Docling" frontend/src/components/parser-eval/ParserComparisonTable.tsx` — leave that map untouched).

In `NewRunDialog.tsx:16`:

```tsx
const DEFAULT_ADAPTER = 'custom_pipeline'
```

- [ ] **Step 5: Run tests, lint, build**

Run: `cd frontend && npx vitest run && npm run lint && npm run build`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/documents/parser-configs/CustomPipelineConfig.tsx \
        frontend/src/components/documents/parser-configs/CustomPipelineConfig.test.tsx \
        frontend/src/components/documents/ParseMethodSelector.tsx \
        frontend/src/components/parser-eval/NewRunDialog.tsx \
        frontend/src/components/parser-eval/NewRunDialog.test.tsx
git commit -m "feat(ui): docling as a layout_analysis option; eval defaults to custom_pipeline"
```

## Task B6: Docling integration test (the L2 fix, demonstrated)

**Files:**
- Create: `backend/tests/services/parsing/test_docling_pipeline_integration.py`

**Interfaces:**
- Consumes: `run_custom_pipeline` with `layout_analysis: docling`.

- [ ] **Step 1: Write the integration test (guarded)**

```python
"""End-to-end docling via the custom pipeline. Skipped where docling is absent."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

docling = pytest.importorskip("docling")  # skip whole module if not installed

import fitz

from app.cdm.source import ParseRunStatus, SourceDocument
from app.services.parsing.custom_pipeline_runner import run_custom_pipeline


def _two_column_pdf(path):
    d = fitz.open()
    page = d.new_page(width=595, height=842)
    # Left column then right column — reading order must be L-col then R-col,
    # which a naive (y0, x0) sort interleaves incorrectly.
    for i, y in enumerate(range(120, 400, 40)):
        page.insert_text(fitz.Point(72, y), f"Left line {i}", fontsize=11)
    for i, y in enumerate(range(120, 400, 40)):
        page.insert_text(fitz.Point(340, y), f"Right line {i}", fontsize=11)
    d.save(str(path)); d.close()


def _source():
    return SourceDocument(id="src-1", sha256="b" * 64, filename="cols.pdf",
                          mime_type="application/pdf", byte_size=1,
                          created_at=datetime.now(timezone.utc))


@pytest.mark.asyncio
async def test_docling_reading_order_is_column_aware(tmp_path):
    pdf = tmp_path / "cols.pdf"; _two_column_pdf(pdf)
    _, parsed = await run_custom_pipeline(
        source=_source(), file_path=str(pdf), representation_kind="extract_rich",
        config={"tools": {"docling": {"tool": "docling", "config": {}}},
                "capabilities": {"layout_analysis": "docling"}}, client=None)
    text = parsed.full_text
    # All left-column lines precede all right-column lines in reading order.
    assert text.index("Left line 0") < text.index("Right line 0")
    assert text.index("Left line 3") < text.index("Right line 0")


@pytest.mark.asyncio
async def test_docling_run_succeeds_and_populates_blocks(tmp_path):
    pdf = tmp_path / "cols.pdf"; _two_column_pdf(pdf)
    run, parsed = await run_custom_pipeline(
        source=_source(), file_path=str(pdf), representation_kind="extract_rich",
        config={"tools": {"docling": {"tool": "docling", "config": {}}},
                "capabilities": {"layout_analysis": "docling"}}, client=None)
    assert run.status == ParseRunStatus.SUCCEEDED
    assert len(parsed.blocks) > 0
    assert all(b.id.startswith("src-1:") for b in parsed.blocks)
```

- [ ] **Step 2: Run it**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/parsing/test_docling_pipeline_integration.py -v`
Expected: PASS if docling is installed in the env (it is in the backend image); otherwise SKIPPED. If the column-order assert fails, docling batching/`reading_order` wiring in Task B2 is wrong — debug there, not by weakening the assert.

- [ ] **Step 3: Full backend + frontend green**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests -q`
Then: `cd frontend && npx vitest run && npm run lint && npm run build`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/services/parsing/test_docling_pipeline_integration.py
git commit -m "test: docling via custom pipeline yields column-aware reading order"
```

**PR B is complete.** Open the PR; the two-column integration test + unchanged goldens are the acceptance evidence.

---

## Self-Review (completed)

**Spec coverage:** §3 (PR A rename) → A2–A6; the double-duty page-geometry role → A4. §4 (merger reading order) → B1; DoclingTool → B2; threading/semaphore → B2 (`_DOCLING_LOCK`) + B3 (offload); D1 retirement → B4. §5 (config UI) → A6 + B5. §6 (eval follow-throughs) → B5 (DEFAULT_ADAPTER, ParseMethodSelector, ParserComparisonTable label kept). §7 (testing) → A1/A5 goldens, B1 pure-function, B2 tool unit, B6 integration. §8 limitations are accepted (no tasks): composition unwired, STAGING empty, fitz naive, routing out, docling multi-capability deferred.

**Placeholder scan:** no TBDs; every code step carries full code. One deliberately conditional step: B4 Step 2 notes the trimmed test may pass or fail at collection depending on cleanup order — both outcomes are handled.

**Type consistency:** `Capability.LAYOUT_ANALYSIS` used uniformly after A2; `structure_instance`/`structure_result` names consistent across A4/B3; `DoclingConfig`/`DoclingTool` imported from `...tools.docling_tool` in both the registry and the unit test (B2 Step 4 corrects the test import); `_sort_key` returns a 3-tuple used only inside `merge`. `content_projection`/`build_for`/`EQUIV_CONFIGS` names match between A1 (definition) and A5 (use).
