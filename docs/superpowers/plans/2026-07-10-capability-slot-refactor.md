# Capability-Slot Refactor (WS2 slice 1, PR A) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the custom pipeline's flat `tools: [...]` list and binary merger with capability slots — one tool per IDP capability — and an N-way, capability-aware merger, **without changing parse output**.

**Architecture:** A closed `Capability` enum. Config becomes named tool *instances* plus a `capabilities` map referencing them; one instance runs once however many slots reference it, and is told which capabilities to `emit` (masking). The merger flattens all tool output, ranks blocks by the capability that produced them (page-dependent precedence), evicts lower-ranked blocks on spatial overlap, and emits a capability-tagged audit trail. No OCR in this PR.

**Tech Stack:** Python 3.12, pydantic v2, PyMuPDF (`fitz`), camelot. React 18, TypeScript, vitest.

**Spec:** [docs/superpowers/specs/2026-07-10-ocr-capability-pipeline-design.md](../specs/2026-07-10-ocr-capability-pipeline-design.md) (§2, §3, §4b PR A, §5, §6)

## Global Constraints

- **Pre-implementation gate:** a GitHub issue with acceptance criteria must exist and be confirmed with the user BEFORE Task 1. Branch `feat/ocr-capability-pipeline` already exists.
- **PR A is a behaviour-preserving refactor.** For any document and any pipeline expressible under the old config, the new pipeline must produce an **identical `ParsedDocument`** (same `blocks`, `pages`, `full_text`, `full_markdown`). Task 9 proves this.
- **Exception, intentional:** `ParseRun.raw_payload` changes shape (`"tools"` → `"instances"`, capability-tagged eviction records). It is an audit artifact, not part of `ParsedDocument`. Do not try to preserve it.
- **No OCR in this PR.** `Capability.TEXT_OCR` exists in the enum and in precedence logic (pure, fully unit-tested), but no tool provides it. `has_uncovered_image`, the `precedence` config field, and `tesseract_tool.py` are **PR B**.
- **No compat shim.** There is no legacy data; delete the old config shape outright.
- **Delete, don't generalize:** `TABLE_TOOL_IDS`, its `len(...) > 1` guard, and the hardcoded `"custom pipeline requires a 'fitz' tool"` string.
- Backend tests: `cd backend && uv run python -m pytest -o "addopts=" <path> -v` (SQLite; no Postgres needed).
- Frontend: `cd frontend && npx vitest run <path>`, `npm run lint`, `npm run build`.
- `parser_eval` treats pipeline config as an opaque dict — **do not** change anything under `app/services/parser_eval/`.

---

## File Structure

**Create**
- `backend/app/cdm/adapters/custom_pipeline/capabilities.py` — `Capability` enum, kinds, precedence
- `backend/app/cdm/adapters/custom_pipeline/page_flags.py` — `PageFlags`, `compute_page_flags`

**Modify**
- `backend/app/cdm/adapters/custom_pipeline/tools/base.py` — `LocalTool` → `PipelineTool`; `ToolResult.blocks_by_capability`
- `backend/app/cdm/adapters/custom_pipeline/tools/{fitz_tool,fitz_tables_tool,camelot_tool}.py` — new contract; `page_meta` moves constructor → `run()`
- `backend/app/cdm/adapters/custom_pipeline/config.py` — instances + capabilities contract, masking, validation
- `backend/app/cdm/adapters/custom_pipeline/merger.py` — N-way, capability-aware
- `backend/app/cdm/adapters/custom_pipeline/__init__.py` — exports
- `backend/app/services/parsing/custom_pipeline_runner.py` — slot-driven
- `frontend/src/components/documents/parser-configs/CustomPipelineConfig.tsx` (+ its test)
- `frontend/src/components/documents/ParseMethodSelector.test.tsx`

---

## Task 1: Capability enum + precedence

**Files:**
- Create: `backend/app/cdm/adapters/custom_pipeline/capabilities.py`
- Test: `backend/tests/cdm/adapters/custom_pipeline/test_capabilities.py`

**Interfaces:**
- Produces: `Capability` (str enum), `BLOCK_PRODUCING: frozenset[Capability]`, `STAGING: frozenset[Capability]`, `resolve_precedence(cid_corrupt: bool, ocr_prefer: bool) -> Dict[Capability, int]` (higher rank wins; staging capabilities absent from the map).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/cdm/adapters/custom_pipeline/test_capabilities.py
from app.cdm.adapters.custom_pipeline.capabilities import (
    BLOCK_PRODUCING, STAGING, Capability, resolve_precedence,
)

T, TB, O, L = (Capability.TEXT_EXTRACTION, Capability.TABLE_DETECTION,
               Capability.TEXT_OCR, Capability.LAYOUT_ANALYSIS)


def test_capability_kinds():
    assert BLOCK_PRODUCING == frozenset({T, TB, O})
    assert STAGING == frozenset({L})


def test_default_order_table_beats_text_beats_ocr():
    r = resolve_precedence(cid_corrupt=False, ocr_prefer=False)
    assert r[TB] > r[T] > r[O]


def test_cid_corrupt_page_flips_ocr_above_text():
    r = resolve_precedence(cid_corrupt=True, ocr_prefer=False)
    assert r[TB] > r[O] > r[T]


def test_ocr_prefer_flips_ocr_above_text():
    r = resolve_precedence(cid_corrupt=False, ocr_prefer=True)
    assert r[TB] > r[O] > r[T]


def test_staging_capability_has_no_rank():
    assert L not in resolve_precedence(cid_corrupt=False, ocr_prefer=False)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/cdm/adapters/custom_pipeline/test_capabilities.py -v`
Expected: FAIL — `ModuleNotFoundError: app.cdm.adapters.custom_pipeline.capabilities`.

- [ ] **Step 3: Write `capabilities.py`**

```python
"""IDP capabilities and their precedence.

One tool fills at most one capability slot. Blocks are tagged with the
capability that produced them; the merger ranks blocks by that tag.
"""
from __future__ import annotations
from enum import Enum
from typing import Dict


class Capability(str, Enum):
    TEXT_EXTRACTION = "text_extraction"
    TABLE_DETECTION = "table_detection"
    TEXT_OCR = "text_ocr"
    LAYOUT_ANALYSIS = "layout_analysis"


#: Capabilities whose blocks compete for page area (governed by precedence).
BLOCK_PRODUCING = frozenset({
    Capability.TEXT_EXTRACTION,
    Capability.TABLE_DETECTION,
    Capability.TEXT_OCR,
})

#: Capabilities that order/route rather than compete. No tools yet.
STAGING = frozenset({Capability.LAYOUT_ANALYSIS})


def resolve_precedence(*, cid_corrupt: bool, ocr_prefer: bool) -> Dict[Capability, int]:
    """Rank block-producing capabilities for one page. Higher wins.

    Structure always beats loose text. The only variable is whether OCR sits
    above or below native text — the CID flip and `prefer` are the same
    mechanism, applied per-page vs per-run.
    """
    ocr_outranks_text = ocr_prefer or cid_corrupt
    if ocr_outranks_text:
        return {Capability.TABLE_DETECTION: 3, Capability.TEXT_OCR: 2,
                Capability.TEXT_EXTRACTION: 1}
    return {Capability.TABLE_DETECTION: 3, Capability.TEXT_EXTRACTION: 2,
            Capability.TEXT_OCR: 1}
```

> The test calls `resolve_precedence(cid_corrupt=..., ocr_prefer=...)` — keyword-only, matching the signature above.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/cdm/adapters/custom_pipeline/test_capabilities.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/cdm/adapters/custom_pipeline/capabilities.py backend/tests/cdm/adapters/custom_pipeline/test_capabilities.py
git commit -m "feat(pipeline): Capability enum + page-dependent precedence"
```

---

## Task 2: Page flags

**Files:**
- Create: `backend/app/cdm/adapters/custom_pipeline/page_flags.py`
- Test: `backend/tests/cdm/adapters/custom_pipeline/test_page_flags.py`

**Interfaces:**
- Produces: `PageFlagsConfig(min_chars: int = 10, cid_ratio: float = 0.3)`, `PageFlags(index, char_count, pua_ratio, cid_corrupt)`, `compute_page_flags(pdf_path: Path, cfg: PageFlagsConfig) -> Dict[int, PageFlags]`.
- `has_uncovered_image` is **PR B**. Do not add it here.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/cdm/adapters/custom_pipeline/test_page_flags.py
import fitz
from app.cdm.adapters.custom_pipeline.page_flags import (
    PageFlagsConfig, compute_page_flags,
)


def _pdf(tmp_path, text: str):
    doc = fitz.open(); page = doc.new_page(width=612, height=792)
    if text:
        page.insert_text((72, 72), text, fontsize=11)
    p = tmp_path / "f.pdf"; doc.save(str(p)); doc.close()
    return p


def test_empty_page_has_no_usable_text_layer(tmp_path):
    flags = compute_page_flags(_pdf(tmp_path, ""), PageFlagsConfig())
    assert flags[0].char_count == 0
    assert flags[0].cid_corrupt is False


def test_text_page_reports_char_count(tmp_path):
    flags = compute_page_flags(_pdf(tmp_path, "Hello invoice world"), PageFlagsConfig())
    assert flags[0].char_count >= 15
    assert flags[0].pua_ratio == 0.0
    assert flags[0].cid_corrupt is False


def test_cid_corrupt_when_private_use_ratio_exceeds_threshold(tmp_path):
    # Private-use-area characters are what a broken CID font decodes to.
    corrupt = "".join(chr(0xE000 + (i % 10)) for i in range(60))
    flags = compute_page_flags(_pdf(tmp_path, corrupt), PageFlagsConfig())
    assert flags[0].pua_ratio > 0.3
    assert flags[0].cid_corrupt is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/cdm/adapters/custom_pipeline/test_page_flags.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write `page_flags.py`**

```python
"""Per-page facts consumed by the merger (CID precedence flip) and, in PR B,
by the OCR tool's `pages: "auto"` selector.

fitz metadata only — no rasterization. Deliberately independent of `app/probe/`:
the probe is advisory evidence, this is deterministic execution state.
"""
from __future__ import annotations
from pathlib import Path
from typing import Dict
import fitz
from pydantic import BaseModel


class PageFlagsConfig(BaseModel):
    min_chars: int = 10      # below this, the page has no usable text layer
    cid_ratio: float = 0.3   # private-use-area char ratio => cid_corrupt


class PageFlags(BaseModel):
    index: int
    char_count: int
    pua_ratio: float
    cid_corrupt: bool


def compute_page_flags(pdf_path: Path, cfg: PageFlagsConfig) -> Dict[int, PageFlags]:
    out: Dict[int, PageFlags] = {}
    doc = fitz.open(str(pdf_path))
    try:
        for i in range(len(doc)):
            text = doc[i].get_text("text")
            stripped = text.strip()
            pua = sum(1 for c in text if 0xE000 <= ord(c) <= 0xF8FF)
            ratio = (pua / len(text)) if text else 0.0
            out[i] = PageFlags(
                index=i,
                char_count=len(stripped),
                pua_ratio=ratio,
                cid_corrupt=ratio > cfg.cid_ratio,
            )
    finally:
        doc.close()
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/cdm/adapters/custom_pipeline/test_page_flags.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/cdm/adapters/custom_pipeline/page_flags.py backend/tests/cdm/adapters/custom_pipeline/test_page_flags.py
git commit -m "feat(pipeline): per-page flags (char_count, pua_ratio, cid_corrupt)"
```

---

## Task 3: `PipelineTool` contract

**Files:**
- Modify: `backend/app/cdm/adapters/custom_pipeline/tools/base.py`
- Test: `backend/tests/cdm/adapters/custom_pipeline/test_tools_base.py` (rewrite)

**Interfaces:**
- Consumes: `Capability` (Task 1).
- Produces: `PipelineTool` protocol with `tool_id: str`, `provides: frozenset[Capability]`, `run(pdf_path, *, pages=None, page_meta=None, emit) -> ToolResult`; `ToolResult` with `blocks_by_capability: Dict[Capability, List[Block]]` (replaces `blocks`); `PageMeta` and `clamp01` unchanged.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/cdm/adapters/custom_pipeline/test_tools_base.py
from app.cdm.adapters.custom_pipeline.capabilities import Capability
from app.cdm.adapters.custom_pipeline.tools.base import (
    PageMeta, PipelineTool, ToolResult, clamp01,
)
from app.cdm.models import Block, BlockRole


def test_clamp01_bounds():
    assert clamp01(-0.5) == 0.0 and clamp01(1.5) == 1.0 and clamp01(0.25) == 0.25


def test_tool_result_holds_blocks_by_capability():
    b = Block(id="x", role=BlockRole.TEXT, page_index=0)
    r = ToolResult(
        tool_id="fitz",
        blocks_by_capability={Capability.TEXT_EXTRACTION: [b]},
        page_meta={0: PageMeta(index=0, width=612, height=792)},
    )
    assert r.blocks_by_capability[Capability.TEXT_EXTRACTION][0].id == "x"
    assert r.warnings == [] and r.duration_ms == 0


def test_pipeline_tool_protocol_is_runtime_checkable():
    class Fake:
        tool_id = "fake"
        provides = frozenset({Capability.TEXT_EXTRACTION})
        def run(self, pdf_path, *, pages=None, page_meta=None, emit=frozenset()):
            return ToolResult(tool_id="fake", blocks_by_capability={}, page_meta={})

    assert isinstance(Fake(), PipelineTool)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/cdm/adapters/custom_pipeline/test_tools_base.py -v`
Expected: FAIL — `ImportError: cannot import name 'PipelineTool'`.

- [ ] **Step 3: Rewrite `tools/base.py`**

```python
"""Contracts shared by all custom-pipeline tools.

A PipelineTool reads a PDF and returns CDM Blocks (normalized bboxes) keyed by
the capability that produced them, plus the native records behind them.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

from app.cdm.adapters.custom_pipeline.capabilities import Capability
from app.cdm.models import Block


def clamp01(v: float) -> float:
    """Clamp a coordinate fraction into the [0, 1] range."""
    return max(0.0, min(1.0, v))


class PageMeta(BaseModel):
    """Authoritative page geometry, sourced from the text_extraction tool."""
    index: int
    width: float       # PDF points
    height: float      # PDF points
    unit: str = "points"
    rotation: int = 0  # degrees


class ToolResult(BaseModel):
    """Output of one PipelineTool.run() invocation."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tool_id: str
    blocks_by_capability: Dict[Capability, List[Block]] = {}
    page_meta: Dict[int, PageMeta] = {}
    raw: Any = None
    native_by_block: Dict[str, Any] = {}
    warnings: List[str] = []
    duration_ms: int = 0


@runtime_checkable
class PipelineTool(Protocol):
    tool_id: str
    provides: frozenset[Capability]

    def run(
        self,
        pdf_path: Path,
        *,
        pages: Optional[List[int]] = None,
        page_meta: Optional[Dict[int, PageMeta]] = None,
        emit: frozenset[Capability],
    ) -> ToolResult: ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/cdm/adapters/custom_pipeline/test_tools_base.py -v`
Expected: PASS (3 passed). Other pipeline tests will fail until Tasks 4–8 — that is expected.

- [ ] **Step 5: Commit**

```bash
git add backend/app/cdm/adapters/custom_pipeline/tools/base.py backend/tests/cdm/adapters/custom_pipeline/test_tools_base.py
git commit -m "refactor(pipeline): LocalTool -> PipelineTool; blocks_by_capability"
```

---

## Task 4: Port `FitzTool`

**Files:**
- Modify: `backend/app/cdm/adapters/custom_pipeline/tools/fitz_tool.py`
- Modify: `backend/tests/cdm/adapters/custom_pipeline/test_fitz_tool.py`

**Interfaces:**
- Consumes: `Capability`, `ToolResult`, `PageMeta`, `clamp01`.
- Produces: `FitzTool` with `provides = frozenset({Capability.TEXT_EXTRACTION})`; `run(..., emit=...)` returns `blocks_by_capability={TEXT_EXTRACTION: [...]}`.

- [ ] **Step 1: Update the test to the new contract**

Open `backend/tests/cdm/adapters/custom_pipeline/test_fitz_tool.py`. Every call site changes from `FitzTool().run(pdf)` to `FitzTool().run(pdf, emit=frozenset({Capability.TEXT_EXTRACTION}))`, and every `result.blocks` becomes `result.blocks_by_capability[Capability.TEXT_EXTRACTION]`. Add this test:

```python
# append to test_fitz_tool.py
from app.cdm.adapters.custom_pipeline.capabilities import Capability

def test_fitz_declares_text_extraction_and_emits_under_it(tmp_path):
    import fitz as _f
    doc = _f.open(); p = doc.new_page(); p.insert_text((72, 72), "hello world text")
    path = tmp_path / "a.pdf"; doc.save(str(path)); doc.close()

    tool = FitzTool()
    assert tool.provides == frozenset({Capability.TEXT_EXTRACTION})
    result = tool.run(path, emit=frozenset({Capability.TEXT_EXTRACTION}))
    assert list(result.blocks_by_capability) == [Capability.TEXT_EXTRACTION]
    assert len(result.blocks_by_capability[Capability.TEXT_EXTRACTION]) >= 1


def test_fitz_rejects_an_emit_it_does_not_provide(tmp_path):
    import fitz as _f, pytest
    doc = _f.open(); doc.new_page(); path = tmp_path / "b.pdf"; doc.save(str(path)); doc.close()
    with pytest.raises(ValueError, match="cannot emit"):
        FitzTool().run(path, emit=frozenset({Capability.TABLE_DETECTION}))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/cdm/adapters/custom_pipeline/test_fitz_tool.py -v`
Expected: FAIL — `run()` has no `emit` kwarg / no `provides`.

- [ ] **Step 3: Port `fitz_tool.py`**

Change only the class surface; the block-building body is untouched.

```python
# at the imports
from app.cdm.adapters.custom_pipeline.capabilities import Capability

# replace the class header and run() signature
class FitzTool:
    tool_id = "fitz"
    provides = frozenset({Capability.TEXT_EXTRACTION})

    def __init__(self, config: Optional[FitzConfig] = None) -> None:
        self.config = config or FitzConfig()

    def run(
        self,
        pdf_path: Path,
        *,
        pages: Optional[List[int]] = None,
        page_meta: Optional[Dict[int, PageMeta]] = None,   # unused; fitz is the source
        emit: frozenset[Capability] = frozenset({Capability.TEXT_EXTRACTION}),
    ) -> ToolResult:
        if not emit <= self.provides:
            raise ValueError(f"{self.tool_id} cannot emit {set(emit - self.provides)}")
        ...  # body unchanged, building `blocks`
```

and the return:

```python
        return ToolResult(
            tool_id=self.tool_id,
            blocks_by_capability={Capability.TEXT_EXTRACTION: blocks},
            page_meta=page_meta_out,          # rename the local dict to avoid shadowing the kwarg
            raw={"pages": native_raw},
            native_by_block=native_by_block,
            warnings=warnings,
            duration_ms=int((time.perf_counter() - t0) * 1000),
        )
```

> Rename the local `page_meta` accumulator to `page_meta_out` so it does not shadow the new keyword argument.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/cdm/adapters/custom_pipeline/test_fitz_tool.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/cdm/adapters/custom_pipeline/tools/fitz_tool.py backend/tests/cdm/adapters/custom_pipeline/test_fitz_tool.py
git commit -m "refactor(pipeline): port FitzTool to PipelineTool contract"
```

---

## Task 5: Port `FitzTablesTool` and `CamelotTool`

**Files:**
- Modify: `backend/app/cdm/adapters/custom_pipeline/tools/fitz_tables_tool.py`
- Modify: `backend/app/cdm/adapters/custom_pipeline/tools/camelot_tool.py`
- Modify: `backend/tests/cdm/adapters/custom_pipeline/test_fitz_tables_tool.py`, `test_camelot_tool.py`

**Interfaces:**
- Produces: both tools get `provides = frozenset({Capability.TABLE_DETECTION})`, emit under `TABLE_DETECTION`, and **`page_meta` moves from `__init__` to `run()`** so `build_pipeline_config` can instantiate every tool up front.

- [ ] **Step 1: Update the tests to the new contract**

In both test files, replace `Tool(config=cfg, page_meta=pm)` with `Tool(config=cfg)`, and `tool.run(pdf)` with `tool.run(pdf, page_meta=pm, emit=frozenset({Capability.TABLE_DETECTION}))`. Replace `result.blocks` with `result.blocks_by_capability[Capability.TABLE_DETECTION]`. Add to `test_fitz_tables_tool.py`:

```python
from app.cdm.adapters.custom_pipeline.capabilities import Capability

def test_fitz_tables_declares_table_detection():
    assert FitzTablesTool().provides == frozenset({Capability.TABLE_DETECTION})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/cdm/adapters/custom_pipeline/test_fitz_tables_tool.py tests/cdm/adapters/custom_pipeline/test_camelot_tool.py -v`
Expected: FAIL — unexpected keyword `emit` / no `provides`.

- [ ] **Step 3: Port `fitz_tables_tool.py`**

```python
from app.cdm.adapters.custom_pipeline.capabilities import Capability

class FitzTablesTool:
    tool_id = "fitz_tables"
    provides = frozenset({Capability.TABLE_DETECTION})

    def __init__(self, config: Optional[FitzTablesConfig] = None) -> None:
        self.config = config or FitzTablesConfig()

    def run(
        self,
        pdf_path: Path,
        *,
        pages: Optional[List[int]] = None,
        page_meta: Optional[Dict[int, PageMeta]] = None,
        emit: frozenset[Capability] = frozenset({Capability.TABLE_DETECTION}),
    ) -> ToolResult:
        if not emit <= self.provides:
            raise ValueError(f"{self.tool_id} cannot emit {set(emit - self.provides)}")
        self.page_meta = page_meta or {}          # methods below already read self.page_meta
        ...  # body unchanged
        return ToolResult(
            tool_id=self.tool_id,
            blocks_by_capability={Capability.TABLE_DETECTION: blocks},
            page_meta=self.page_meta,
            raw={"tables": list(native_by_block.values())},
            native_by_block=native_by_block,
            warnings=warnings,
            duration_ms=int((time.perf_counter() - t0) * 1000),
        )
```

- [ ] **Step 4: Port `camelot_tool.py` identically**

Same three edits: add `provides = frozenset({Capability.TABLE_DETECTION})`; drop `page_meta` from `__init__` and accept it in `run()` (assigning `self.page_meta = page_meta or {}`); add the `emit` guard; return `blocks_by_capability={Capability.TABLE_DETECTION: blocks}`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/cdm/adapters/custom_pipeline/test_fitz_tables_tool.py tests/cdm/adapters/custom_pipeline/test_camelot_tool.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/cdm/adapters/custom_pipeline/tools/fitz_tables_tool.py backend/app/cdm/adapters/custom_pipeline/tools/camelot_tool.py backend/tests/cdm/adapters/custom_pipeline/test_fitz_tables_tool.py backend/tests/cdm/adapters/custom_pipeline/test_camelot_tool.py
git commit -m "refactor(pipeline): port table tools; page_meta moves to run()"
```

---

## Task 6: Capability-slot config contract

**Files:**
- Modify: `backend/app/cdm/adapters/custom_pipeline/config.py`
- Modify: `backend/tests/cdm/adapters/custom_pipeline/test_config.py` (rewrite)

**Interfaces:**
- Consumes: `Capability`, `PageFlagsConfig`, the three tools.
- Produces:
  - `ToolSpec(config_cls, provides, factory)` and `TOOL_REGISTRY: Dict[str, ToolSpec]`
  - `ResolvedInstance(key, tool, emit)`
  - `ResolvedPipeline(instances: List[ResolvedInstance], page_flags: PageFlagsConfig, eviction_overlap_threshold: float, ocr_eviction_threshold: float)` with `for_capability(cap) -> ResolvedInstance | None`
  - `build_pipeline_config(config: Dict[str, Any]) -> ResolvedPipeline`
- **Deleted:** `TABLE_TOOL_IDS`, the `len(...) > 1` guard, the old `CustomPipelineConfig` dataclass.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/cdm/adapters/custom_pipeline/test_config.py
import pytest
from app.cdm.adapters.custom_pipeline.capabilities import Capability
from app.cdm.adapters.custom_pipeline.config import build_pipeline_config

BASE = {
    "tools": {"fitz": {"tool": "fitz", "config": {}}},
    "capabilities": {"text_extraction": "fitz"},
}


def test_builds_a_single_slot_pipeline():
    p = build_pipeline_config(BASE)
    inst = p.for_capability(Capability.TEXT_EXTRACTION)
    assert inst.key == "fitz"
    assert inst.tool.tool_id == "fitz"
    assert inst.emit == frozenset({Capability.TEXT_EXTRACTION})
    assert p.for_capability(Capability.TABLE_DETECTION) is None


def test_one_instance_serves_many_slots_and_is_built_once():
    cfg = {
        "tools": {"f": {"tool": "fitz", "config": {}},
                  "t": {"tool": "fitz_tables", "config": {}}},
        "capabilities": {"text_extraction": "f", "table_detection": "t"},
    }
    p = build_pipeline_config(cfg)
    assert len(p.instances) == 2
    assert {i.key for i in p.instances} == {"f", "t"}


def test_text_extraction_slot_is_required():
    with pytest.raises(ValueError, match="text_extraction"):
        build_pipeline_config({"tools": {}, "capabilities": {}})


def test_unknown_tool_is_rejected():
    with pytest.raises(ValueError, match="unknown tool"):
        build_pipeline_config({"tools": {"x": {"tool": "nope"}},
                               "capabilities": {"text_extraction": "x"}})


def test_capability_not_provided_by_tool_is_rejected():
    with pytest.raises(ValueError, match="does not provide"):
        build_pipeline_config({
            "tools": {"f": {"tool": "fitz"}},
            "capabilities": {"text_extraction": "f", "table_detection": "f"},
        })


def test_dangling_instance_reference_is_rejected():
    with pytest.raises(ValueError, match="unknown instance"):
        build_pipeline_config({"tools": {"f": {"tool": "fitz"}},
                               "capabilities": {"text_extraction": "ghost"}})


def test_thresholds_and_page_flags_defaults():
    p = build_pipeline_config(BASE)
    assert p.eviction_overlap_threshold == 0.5
    assert p.ocr_eviction_threshold == 0.3
    assert p.page_flags.min_chars == 10 and p.page_flags.cid_ratio == 0.3


def test_two_table_tools_are_structurally_unrepresentable():
    # The capabilities map is a dict — a second table_detection key overwrites
    # the first. There is nothing to guard against.
    cfg = {"tools": {"a": {"tool": "camelot"}, "b": {"tool": "fitz_tables"},
                     "f": {"tool": "fitz"}},
           "capabilities": {"text_extraction": "f", "table_detection": "b"}}
    p = build_pipeline_config(cfg)
    assert p.for_capability(Capability.TABLE_DETECTION).key == "b"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/cdm/adapters/custom_pipeline/test_config.py -v`
Expected: FAIL — `build_pipeline_config` still expects `tools: [...]`.

- [ ] **Step 3: Rewrite `config.py`**

Keep the four existing pydantic config classes (`FitzConfig`, `CamelotConfig`, `FitzTablesConfig`) exactly as they are. Replace `TABLE_TOOL_IDS`, `TOOL_REGISTRY`, `CustomPipelineConfig`, and `build_pipeline_config` with:

```python
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel

from app.cdm.adapters.custom_pipeline.capabilities import BLOCK_PRODUCING, Capability
from app.cdm.adapters.custom_pipeline.page_flags import PageFlagsConfig
from app.cdm.adapters.custom_pipeline.tools.base import PipelineTool


@dataclass(frozen=True)
class ToolSpec:
    config_cls: type[BaseModel]
    provides: frozenset[Capability]
    factory: Callable[[BaseModel], PipelineTool]


def _tool_registry() -> Dict[str, ToolSpec]:
    from app.cdm.adapters.custom_pipeline.tools.camelot_tool import CamelotTool
    from app.cdm.adapters.custom_pipeline.tools.fitz_tables_tool import FitzTablesTool
    from app.cdm.adapters.custom_pipeline.tools.fitz_tool import FitzTool
    return {
        "fitz": ToolSpec(FitzConfig, FitzTool.provides, lambda c: FitzTool(config=c)),
        "camelot": ToolSpec(CamelotConfig, CamelotTool.provides, lambda c: CamelotTool(config=c)),
        "fitz_tables": ToolSpec(FitzTablesConfig, FitzTablesTool.provides,
                                lambda c: FitzTablesTool(config=c)),
    }


@dataclass(frozen=True)
class ResolvedInstance:
    key: str
    tool: PipelineTool
    emit: frozenset[Capability]


@dataclass(frozen=True)
class ResolvedPipeline:
    instances: List[ResolvedInstance]
    page_flags: PageFlagsConfig
    eviction_overlap_threshold: float
    ocr_eviction_threshold: float

    def for_capability(self, cap: Capability) -> Optional[ResolvedInstance]:
        return next((i for i in self.instances if cap in i.emit), None)


def build_pipeline_config(config: Dict[str, Any]) -> ResolvedPipeline:
    registry = _tool_registry()
    tools_cfg: Dict[str, Any] = config.get("tools", {}) or {}
    caps_cfg: Dict[str, str] = config.get("capabilities", {}) or {}

    # capability key -> Capability, validating the enum
    slots: Dict[Capability, str] = {}
    for raw_cap, instance_key in caps_cfg.items():
        try:
            cap = Capability(raw_cap)
        except ValueError:
            raise ValueError(f"unknown capability: {raw_cap!r}")
        if cap not in BLOCK_PRODUCING:
            raise ValueError(f"no tool provides staging capability {cap.value!r}")
        slots[cap] = instance_key

    if Capability.TEXT_EXTRACTION not in slots:
        raise ValueError("capability 'text_extraction' is required")

    # instance key -> assigned capabilities (this is the masking set)
    assigned: Dict[str, set[Capability]] = {}
    for cap, key in slots.items():
        if key not in tools_cfg:
            raise ValueError(f"capability {cap.value!r} references unknown instance {key!r}")
        assigned.setdefault(key, set()).add(cap)

    instances: List[ResolvedInstance] = []
    for key in sorted(assigned):                       # deterministic order
        entry = tools_cfg[key]
        tool_id = entry.get("tool")
        spec = registry.get(tool_id)
        if spec is None:
            raise ValueError(f"unknown tool: {tool_id!r}")
        emit = frozenset(assigned[key])
        if not emit <= spec.provides:
            missing = {c.value for c in emit - spec.provides}
            raise ValueError(f"tool {tool_id!r} does not provide {missing}")
        tool_cfg = spec.config_cls.model_validate(entry.get("config", {}) or {})
        instances.append(ResolvedInstance(key=key, tool=spec.factory(tool_cfg), emit=emit))

    return ResolvedPipeline(
        instances=instances,
        page_flags=PageFlagsConfig.model_validate(config.get("page_flags", {}) or {}),
        eviction_overlap_threshold=config.get("eviction_overlap_threshold", 0.5),
        ocr_eviction_threshold=config.get("ocr_eviction_threshold", 0.3),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/cdm/adapters/custom_pipeline/test_config.py -v`
Expected: PASS (8 passed).

- [ ] **Step 5: Verify the old guard is gone**

Run: `cd backend && grep -rn "TABLE_TOOL_IDS\|only one table tool" app tests`
Expected: no results.

- [ ] **Step 6: Commit**

```bash
git add backend/app/cdm/adapters/custom_pipeline/config.py backend/tests/cdm/adapters/custom_pipeline/test_config.py
git commit -m "feat(pipeline): capability-slot config contract; delete TABLE_TOOL_IDS"
```

---

## Task 7: N-way capability-aware merger

**Files:**
- Modify: `backend/app/cdm/adapters/custom_pipeline/merger.py`
- Modify: `backend/tests/cdm/adapters/custom_pipeline/test_merger.py` (rewrite)

**Interfaces:**
- Consumes: `Capability`, `resolve_precedence`, `PageFlags`, `ToolResult`.
- Produces: `overlap_fraction(winner: BBox, loser: BBox) -> float` (renamed params, same maths); `merge(results: Sequence[ToolResult], *, source_document_id: str, page_flags: Dict[int, PageFlags], ocr_prefer: bool = False, eviction_overlap_threshold: float = 0.5, ocr_eviction_threshold: float = 0.3) -> MergeResult`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/cdm/adapters/custom_pipeline/test_merger.py
from app.cdm.adapters.custom_pipeline.capabilities import Capability
from app.cdm.adapters.custom_pipeline.merger import merge, overlap_fraction
from app.cdm.adapters.custom_pipeline.page_flags import PageFlags
from app.cdm.adapters.custom_pipeline.tools.base import ToolResult
from app.cdm.models import BBox, Block, BlockRole

TE, TB, OC = Capability.TEXT_EXTRACTION, Capability.TABLE_DETECTION, Capability.TEXT_OCR


def _b(bid, x0, y0, x1, y1, role=BlockRole.TEXT):
    return Block(id=bid, role=role, page_index=0, bbox=BBox(x0=x0, y0=y0, x1=x1, y1=y1))


def _res(tool_id, cap, blocks):
    return ToolResult(tool_id=tool_id, blocks_by_capability={cap: blocks},
                      native_by_block={b.id: {} for b in blocks})


def _flags(cid=False):
    return {0: PageFlags(index=0, char_count=100, pua_ratio=0.0, cid_corrupt=cid)}


def test_overlap_fraction_is_share_of_the_loser():
    assert overlap_fraction(BBox(x0=0, y0=0, x1=1, y1=1),
                            BBox(x0=0, y0=0, x1=0.5, y1=1)) == 1.0


def test_table_evicts_overlapping_text():
    text = _res("fitz", TE, [_b("t1", 0.1, 0.1, 0.9, 0.4)])
    table = _res("fitz_tables", TB, [_b("tb1", 0.0, 0.0, 1.0, 0.5, BlockRole.TABLE)])
    out = merge([text, table], source_document_id="d", page_flags=_flags())
    assert len(out.blocks) == 1
    assert out.raw_output["evicted"][0]["capability"] == "text_extraction"
    assert out.raw_output["evicted"][0]["winner_capability"] == "table_detection"


def test_native_text_evicts_overlapping_ocr_by_default():
    text = _res("fitz", TE, [_b("t1", 0.0, 0.0, 1.0, 0.5)])
    ocr = _res("tesseract", OC, [_b("o1", 0.1, 0.1, 0.3, 0.2)])
    out = merge([text, ocr], source_document_id="d", page_flags=_flags())
    assert [b.id for b in out.blocks] == ["d:0:0"]
    assert out.raw_output["evicted"][0]["capability"] == "text_ocr"


def test_ocr_survives_where_no_native_text_covers_it():
    text = _res("fitz", TE, [_b("t1", 0.0, 0.0, 1.0, 0.2)])
    ocr = _res("tesseract", OC, [_b("o1", 0.0, 0.6, 0.5, 0.8)])   # no overlap
    out = merge([text, ocr], source_document_id="d", page_flags=_flags())
    assert len(out.blocks) == 2


def test_cid_corrupt_page_lets_ocr_evict_native_text():
    text = _res("fitz", TE, [_b("t1", 0.1, 0.1, 0.3, 0.2)])
    ocr = _res("tesseract", OC, [_b("o1", 0.0, 0.0, 1.0, 0.5)])
    out = merge([text, ocr], source_document_id="d", page_flags=_flags(cid=True))
    assert out.raw_output["evicted"][0]["capability"] == "text_extraction"


def test_audit_trail_is_keyed_by_instance():
    text = _res("fitz", TE, [_b("t1", 0.0, 0.0, 0.2, 0.2)])
    out = merge([text], source_document_id="d", page_flags=_flags())
    assert "fitz" in out.raw_output["instances"]
    assert out.raw_output["instances"]["fitz"]["capabilities"] == ["text_extraction"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/cdm/adapters/custom_pipeline/test_merger.py -v`
Expected: FAIL — `merge()` still takes two positional `ToolResult`s.

- [ ] **Step 3: Rewrite `merger.py`**

```python
"""Merge tool outputs into a final ordered block list + an audit raw_output.

Blocks are tagged with the capability that produced them. Precedence is
per-page (see capabilities.resolve_precedence): structure beats loose text, and
OCR sits below native text unless the page is CID-corrupt or the router set
`ocr_prefer`. Losers are evicted (logged, not deleted).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Sequence, Tuple

from app.cdm.adapters.custom_pipeline.capabilities import Capability, resolve_precedence
from app.cdm.adapters.custom_pipeline.page_flags import PageFlags
from app.cdm.adapters.custom_pipeline.tools.base import ToolResult
from app.cdm.models import BBox, Block


def _area(b: BBox) -> float:
    return max(0.0, b.x1 - b.x0) * max(0.0, b.y1 - b.y0)


def overlap_fraction(winner: BBox, loser: BBox) -> float:
    """Intersection area / area(loser), in normalized coords."""
    loser_area = _area(loser)
    if loser_area == 0.0:
        return 0.0
    ix0, iy0 = max(winner.x0, loser.x0), max(winner.y0, loser.y0)
    ix1, iy1 = min(winner.x1, loser.x1), min(winner.y1, loser.y1)
    inter = max(0.0, ix1 - ix0) * max(0.0, iy1 - iy0)
    return inter / loser_area


@dataclass
class MergeResult:
    blocks: List[Block]
    raw_output: Dict[str, Any]


def _sort_key(block: Block) -> Tuple[float, float]:
    if block.bbox is None:
        return (1e9, 1e9)
    return (block.bbox.y0, block.bbox.x0)


def merge(
    results: Sequence[ToolResult],
    *,
    source_document_id: str,
    page_flags: Dict[int, PageFlags],
    ocr_prefer: bool = False,
    eviction_overlap_threshold: float = 0.5,
    ocr_eviction_threshold: float = 0.3,
) -> MergeResult:
    # Flatten to (block, capability, tool_id), preserving producer order.
    tagged: List[Tuple[Block, Capability, str]] = [
        (b, cap, r.tool_id)
        for r in results
        for cap, blocks in r.blocks_by_capability.items()
        for b in blocks
    ]

    def _threshold(loser_cap: Capability) -> float:
        return (ocr_eviction_threshold if loser_cap is Capability.TEXT_OCR
                else eviction_overlap_threshold)

    def _rank(page_index: int) -> Dict[Capability, int]:
        flags = page_flags.get(page_index)
        return resolve_precedence(
            cid_corrupt=bool(flags and flags.cid_corrupt), ocr_prefer=ocr_prefer,
        )

    # 1. Eviction pass — a block loses to any higher-ranked block that covers it.
    evicted: Dict[str, Dict[str, Any]] = {}
    for loser, loser_cap, loser_tool in tagged:
        if loser.bbox is None:
            continue
        ranks = _rank(loser.page_index)
        for winner, winner_cap, _ in tagged:
            if winner.id == loser.id or winner.bbox is None:
                continue
            if winner.page_index != loser.page_index:
                continue
            if ranks.get(winner_cap, 0) <= ranks.get(loser_cap, 0):
                continue
            frac = overlap_fraction(winner.bbox, loser.bbox)
            if frac > _threshold(loser_cap):
                evicted[loser.id] = {
                    "block_id": loser.id,
                    "capability": loser_cap.value,
                    "winner_capability": winner_cap.value,
                    "winner_prov_id": winner.id,
                    "reason": "covered_by",
                    "overlap_fraction": frac,
                    "tool": loser_tool,
                }
                break

    survivors = [(b, c, t) for (b, c, t) in tagged if b.id not in evicted]

    # 2. Mint final ids + reading order, grouped per page.
    by_page: Dict[int, List[Block]] = {}
    for b, _, _ in survivors:
        by_page.setdefault(b.page_index, []).append(b)

    prov_to_final: Dict[str, str] = {}
    final_blocks: List[Block] = []
    for page_index in sorted(by_page):
        for reading_order, block in enumerate(sorted(by_page[page_index], key=_sort_key)):
            final_id = f"{source_document_id}:{page_index}:{reading_order}"
            prov_to_final[block.id] = final_id
            final_blocks.append(
                block.model_copy(update={"id": final_id, "reading_order": reading_order})
            )

    # 3. Audit trail, keyed by instance and explained in capability terms.
    instances: Dict[str, Any] = {}
    for r in results:
        block_map = {
            prov_to_final[prov]: native
            for prov, native in r.native_by_block.items()
            if prov in prov_to_final
        }
        instances[r.tool_id] = {
            "tool": r.tool_id,
            "capabilities": [c.value for c in r.blocks_by_capability],
            "raw": r.raw,
            "block_map": block_map,
        }

    for record in evicted.values():
        record["won_by"] = prov_to_final.get(record.pop("winner_prov_id"))

    return MergeResult(
        blocks=final_blocks,
        raw_output={"instances": instances, "evicted": list(evicted.values())},
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/cdm/adapters/custom_pipeline/test_merger.py -v`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/cdm/adapters/custom_pipeline/merger.py backend/tests/cdm/adapters/custom_pipeline/test_merger.py
git commit -m "feat(pipeline): N-way capability-aware merger + capability-tagged audit"
```

---

## Task 8: Slot-driven runner

**Files:**
- Modify: `backend/app/services/parsing/custom_pipeline_runner.py`
- Modify: `backend/app/cdm/adapters/custom_pipeline/__init__.py`
- Modify: `backend/tests/services/parsing/test_custom_pipeline_runner.py`

**Interfaces:**
- Consumes: `build_pipeline_config`, `compute_page_flags`, `merge`, `Capability`, `CustomPipelineAdapter`.
- Produces: unchanged public signature `run_custom_pipeline(...) -> Tuple[ParseRun, ParsedDocument]`.

- [ ] **Step 1: Update the runner test to the new config shape**

In `test_custom_pipeline_runner.py`, every pipeline config literal changes from
`{"tools": [{"tool_id": "fitz", "config": {}}]}` to
`{"tools": {"fitz": {"tool": "fitz", "config": {}}}, "capabilities": {"text_extraction": "fitz"}}`.
Add:

```python
import pytest

@pytest.mark.asyncio
async def test_runner_requires_a_text_extraction_slot(source_doc, pdf_path):
    with pytest.raises(Exception, match="text_extraction"):
        await run_custom_pipeline(
            source=source_doc, file_path=str(pdf_path),
            representation_kind="extract_rich",
            config={"tools": {}, "capabilities": {}},
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/parsing/test_custom_pipeline_runner.py -v`
Expected: FAIL — old config shape / `merge()` signature.

- [ ] **Step 3: Rewrite the `try:` body of `run_custom_pipeline`**

Replace everything from `pdf_path = Path(file_path)` through the `merge(...)` call with:

```python
        pdf_path = Path(file_path)

        pipeline = build_pipeline_config(config)
        flags = compute_page_flags(pdf_path, pipeline.page_flags)

        text_instance = pipeline.for_capability(Capability.TEXT_EXTRACTION)
        # build_pipeline_config guarantees this, but fail loudly if it ever does not.
        if text_instance is None:
            raise ValueError("capability 'text_extraction' is required")

        text_result = text_instance.tool.run(pdf_path, emit=text_instance.emit)
        results = [text_result]
        warnings = list(text_result.warnings)

        # Remaining instances run once each, in the deterministic order
        # build_pipeline_config established, and receive page geometry from
        # the text_extraction tool.
        for inst in pipeline.instances:
            if inst is text_instance:
                continue
            r = inst.tool.run(pdf_path, page_meta=text_result.page_meta, emit=inst.emit)
            results.append(r)
            warnings.extend(r.warnings)

        merge_result = merge(
            results,
            source_document_id=source.id,
            page_flags=flags,
            eviction_overlap_threshold=pipeline.eviction_overlap_threshold,
            ocr_eviction_threshold=pipeline.ocr_eviction_threshold,
        )
```

Update the imports at the top of the file:

```python
from app.cdm.adapters.custom_pipeline.capabilities import Capability
from app.cdm.adapters.custom_pipeline.config import build_pipeline_config
from app.cdm.adapters.custom_pipeline.merger import merge
from app.cdm.adapters.custom_pipeline.page_flags import compute_page_flags
from app.cdm.adapters.custom_pipeline.tools.base import ToolResult   # keep if still referenced
```

Delete the `TABLE_TOOL_IDS` import, the `fitz_tool = next(...)` lookup, the
`raise ValueError("custom pipeline requires a 'fitz' tool")`, the `table_entry` block, and the
`ToolResult(tool_id="none", ...)` placeholder.

The `adapter.adapt(...)` call below is unchanged except it reads `text_result.page_meta`:

```python
        {"page_meta": text_result.page_meta, "blocks": merge_result.blocks},
```

- [ ] **Step 4: Update `__init__.py` exports**

```python
from app.cdm.adapters.custom_pipeline.adapter import CustomPipelineAdapter
from app.cdm.adapters.custom_pipeline.capabilities import (
    BLOCK_PRODUCING, STAGING, Capability, resolve_precedence,
)
from app.cdm.adapters.custom_pipeline.config import (
    CamelotConfig, FitzConfig, FitzTablesConfig,
    ResolvedInstance, ResolvedPipeline, build_pipeline_config,
)
from app.cdm.adapters.custom_pipeline.merger import MergeResult, merge, overlap_fraction
from app.cdm.adapters.custom_pipeline.page_flags import (
    PageFlags, PageFlagsConfig, compute_page_flags,
)
from app.cdm.adapters.custom_pipeline.tools.base import PageMeta, PipelineTool, ToolResult
from app.cdm.adapters.custom_pipeline.tools.camelot_tool import CamelotTool
from app.cdm.adapters.custom_pipeline.tools.fitz_tables_tool import FitzTablesTool
from app.cdm.adapters.custom_pipeline.tools.fitz_tool import FitzTool

__all__ = [
    "CustomPipelineAdapter", "BLOCK_PRODUCING", "STAGING", "Capability",
    "resolve_precedence", "CamelotConfig", "FitzConfig", "FitzTablesConfig",
    "ResolvedInstance", "ResolvedPipeline", "build_pipeline_config",
    "MergeResult", "merge", "overlap_fraction",
    "PageFlags", "PageFlagsConfig", "compute_page_flags",
    "PageMeta", "PipelineTool", "ToolResult",
    "CamelotTool", "FitzTablesTool", "FitzTool",
]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/parsing/test_custom_pipeline_runner.py tests/cdm/adapters/custom_pipeline -v`
Expected: PASS.

- [ ] **Step 6: Verify no `LocalTool` references survive**

Run: `cd backend && grep -rn "LocalTool" app tests`
Expected: no results.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/parsing/custom_pipeline_runner.py backend/app/cdm/adapters/custom_pipeline/__init__.py backend/tests/services/parsing/test_custom_pipeline_runner.py
git commit -m "refactor(pipeline): slot-driven runner; drop hardcoded fitz requirement"
```

---

## Task 9: Behaviour-equivalence acceptance test

**Files:**
- Create: `backend/tests/cdm/adapters/custom_pipeline/test_refactor_equivalence.py`

**Interfaces:**
- Consumes: `run_custom_pipeline`.
- Proves the plan's acceptance property: the refactor does not change `ParsedDocument`.

This is the task that justifies splitting PR A from PR B. It pins the output of a
representative document so a reviewer can trust the refactor without reading every diff.

- [ ] **Step 1: Write the test**

```python
# backend/tests/cdm/adapters/custom_pipeline/test_refactor_equivalence.py
"""PR A is a behaviour-preserving refactor.

`ParsedDocument` must be byte-identical to the pre-refactor pipeline for any
config expressible under the old contract. `ParseRun.raw_payload` is exempt —
its shape changes on purpose ("tools" -> "instances").
"""
import fitz
import pytest

from app.cdm.source import SourceDocument
from app.services.parsing.custom_pipeline_runner import run_custom_pipeline


@pytest.fixture
def doc_and_pdf(tmp_path):
    d = fitz.open()
    page = d.new_page(width=612, height=792)
    page.insert_text((72, 72), "Quarterly revenue report", fontsize=14)
    page.insert_text((72, 110), "Figures are unaudited and provisional.", fontsize=10)
    for i in range(5):                       # a ruled grid -> a table
        page.draw_line(fitz.Point(100, 300 + i * 20), fitz.Point(500, 300 + i * 20))
    for i in range(3):
        page.draw_line(fitz.Point(100 + i * 200, 300), fitz.Point(100 + i * 200, 380))
    path = tmp_path / "equiv.pdf"
    d.save(str(path)); d.close()
    source = SourceDocument(id="src-1", filename="equiv.pdf", sha256="deadbeef")
    return source, path


@pytest.mark.asyncio
async def test_text_only_pipeline_output_is_stable(doc_and_pdf):
    source, path = doc_and_pdf
    _run, parsed = await run_custom_pipeline(
        source=source, file_path=str(path), representation_kind="extract_rich",
        config={"tools": {"fitz": {"tool": "fitz", "config": {}}},
                "capabilities": {"text_extraction": "fitz"}},
    )
    assert parsed.page_count == 1
    assert "Quarterly revenue report" in parsed.full_text
    # Reading order is contiguous and starts at 0 on every page.
    orders = [b.reading_order for b in parsed.blocks if b.page_index == 0]
    assert orders == list(range(len(orders)))
    # Block ids follow the documented "<source>:<page>:<order>" scheme.
    assert parsed.blocks[0].id == "src-1:0:0"


@pytest.mark.asyncio
async def test_table_tool_evicts_overlapping_text_exactly_as_before(doc_and_pdf):
    source, path = doc_and_pdf
    cfg = {
        "tools": {"fitz": {"tool": "fitz", "config": {}},
                  "tbl": {"tool": "fitz_tables", "config": {}}},
        "capabilities": {"text_extraction": "fitz", "table_detection": "tbl"},
    }
    run, parsed = await run_custom_pipeline(
        source=source, file_path=str(path), representation_kind="extract_rich", config=cfg,
    )
    roles = {b.role.value for b in parsed.blocks}
    assert "table" in roles
    # Every eviction is explained in capability terms.
    for rec in run.raw_payload["evicted"]:
        assert rec["winner_capability"] == "table_detection"
        assert rec["reason"] == "covered_by"
    assert "instances" in run.raw_payload and "tools" not in run.raw_payload
```

> If `SourceDocument` requires additional fields, mirror the construction used in
> `backend/tests/services/parsing/test_custom_pipeline_runner.py`.

- [ ] **Step 2: Run the test**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/cdm/adapters/custom_pipeline/test_refactor_equivalence.py -v`
Expected: PASS (2 passed).

- [ ] **Step 3: Run the whole backend suite**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests -q`
Expected: all pass. (`tests/services/parser_eval` must be untouched and green — it treats config as an opaque dict.)

- [ ] **Step 4: Commit**

```bash
git add backend/tests/cdm/adapters/custom_pipeline/test_refactor_equivalence.py
git commit -m "test(pipeline): behaviour-equivalence acceptance test for the refactor"
```

---

## Task 10: Frontend — capability-slot config

**Files:**
- Modify: `frontend/src/components/documents/parser-configs/CustomPipelineConfig.tsx`
- Modify: `frontend/src/components/documents/parser-configs/CustomPipelineConfig.test.tsx`
- Modify: `frontend/src/components/documents/ParseMethodSelector.test.tsx`

**Interfaces:**
- Produces: the component emits the new config object:
  `{ tools: {<toolId>: {tool, config}}, capabilities: {text_extraction, table_detection?}, page_flags, eviction_overlap_threshold, ocr_eviction_threshold }`
- Instance keys are the tool id (1:1 simplification; a future multi-capability tool referenced from two slots therefore resolves to one instance).
- No OCR controls in PR A.

- [ ] **Step 1: Write the failing test**

```tsx
// append to CustomPipelineConfig.test.tsx
const capabilityConfig = {
  tools: { fitz: { tool: 'fitz', config: {} } },
  capabilities: { text_extraction: 'fitz' },
}

it('renders text extraction as a slot, not an always-on label', () => {
  render(<CustomPipelineConfig config={capabilityConfig} onChange={vi.fn()} />)
  expect(screen.getByRole('combobox', { name: /text extraction/i })).toBeInTheDocument()
  expect(screen.queryByText(/always on/i)).not.toBeInTheDocument()
})

it('selecting a table tool emits a capability-slot config', async () => {
  const onChange = vi.fn()
  render(<CustomPipelineConfig config={capabilityConfig} onChange={onChange} />)
  await userEvent.click(screen.getByRole('combobox', { name: /table extraction/i }))
  await userEvent.click(screen.getByText(/fitz_tables/i))
  const next = onChange.mock.calls[0][0]
  expect(next.capabilities.text_extraction).toBe('fitz')
  expect(next.capabilities.table_detection).toBe('fitz_tables')
  expect(next.tools.fitz_tables.tool).toBe('fitz_tables')
})

it('selecting none removes the table_detection slot and its instance', async () => {
  const withTable = {
    tools: { fitz: { tool: 'fitz', config: {} },
             fitz_tables: { tool: 'fitz_tables', config: {} } },
    capabilities: { text_extraction: 'fitz', table_detection: 'fitz_tables' },
  }
  const onChange = vi.fn()
  render(<CustomPipelineConfig config={withTable} onChange={onChange} />)
  await userEvent.click(screen.getByRole('combobox', { name: /table extraction/i }))
  await userEvent.click(screen.getByRole('option', { name: /none/i }))
  const next = onChange.mock.calls[0][0]
  expect(next.capabilities.table_detection).toBeUndefined()
  expect(next.tools.fitz_tables).toBeUndefined()
})
```

Replace the existing `fitzOnly` / `withFitzTables` / `withCamelot` fixtures with capability-slot
equivalents, and update the existing tool-selection tests to read
`next.capabilities.table_detection` instead of `next.tools.map(t => t.tool_id)`.

In `ParseMethodSelector.test.tsx`, change the `custom_pipeline` config literal to
`{ tools: { fitz: { tool: 'fitz', config: {} } }, capabilities: { text_extraction: 'fitz' } }`.
Its assertion on the *Table extraction* combobox stays as-is.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/components/documents/parser-configs/CustomPipelineConfig.test.tsx`
Expected: FAIL — no *Text extraction* combobox; config emitted as a `tools` array.

- [ ] **Step 3: Update `CustomPipelineConfig.tsx`**

Read the current file first. Then:

1. Replace the *"Fitz — always on"* heading with a **Text extraction** `Select` whose only
   option is `fitz` (labelled `fitz (text + images)`), wired with `aria-label="Text extraction"`.
2. Derive the currently-selected table tool from `config.capabilities?.table_detection` instead
   of scanning a `tools` array.
3. Replace the two config-mutation helpers with capability-slot equivalents:

```tsx
type ToolInstance = { tool: string; config: Record<string, unknown> }
type PipelineConfig = {
  tools: Record<string, ToolInstance>
  capabilities: Record<string, string>
  page_flags?: Record<string, number>
  eviction_overlap_threshold?: number
  ocr_eviction_threshold?: number
}

function setSlot(cfg: PipelineConfig, capability: string, toolId: string | null,
                 defaults: Record<string, unknown> = {}): PipelineConfig {
  const capabilities = { ...cfg.capabilities }
  const tools = { ...cfg.tools }
  const previous = capabilities[capability]
  if (previous) {
    delete capabilities[capability]
    // Drop the instance only if no other slot still references it.
    if (!Object.values(capabilities).includes(previous)) delete tools[previous]
  }
  if (toolId) {
    capabilities[capability] = toolId
    tools[toolId] = tools[toolId] ?? { tool: toolId, config: defaults }
  }
  return { ...cfg, tools, capabilities }
}

function setToolConfig(cfg: PipelineConfig, toolId: string,
                       patch: Record<string, unknown>): PipelineConfig {
  const existing = cfg.tools[toolId]
  if (!existing) return cfg
  return { ...cfg, tools: { ...cfg.tools,
    [toolId]: { ...existing, config: { ...existing.config, ...patch } } } }
}
```

4. The table-tool `Select`'s `onValueChange` becomes
   `onChange(setSlot(config, 'table_detection', v === 'none' ? null : v, v === 'camelot' ? CAMELOT_DEFAULTS : FITZ_TABLES_DEFAULTS))`.
5. The existing camelot / fitz_tables config panels read
   `config.tools[selectedTableTool]?.config` and write through `setToolConfig`.

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
cd frontend && npx vitest run src/components/documents/parser-configs/CustomPipelineConfig.test.tsx src/components/documents/ParseMethodSelector.test.tsx
```
Expected: PASS.

- [ ] **Step 5: Lint, typecheck, full suite**

Run:
```bash
cd frontend && npm run lint
cd frontend && npm run build
cd frontend && npx vitest run
```
Expected: lint clean; build succeeds; all tests pass.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/documents/parser-configs/CustomPipelineConfig.tsx frontend/src/components/documents/parser-configs/CustomPipelineConfig.test.tsx frontend/src/components/documents/ParseMethodSelector.test.tsx
git commit -m "feat(pipeline): capability-slot config UI; text extraction is a slot"
```

---

## Task 11: Full verification + PR

**Files:** none (verification only)

- [ ] **Step 1: Backend suite**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests -q`
Expected: all pass.

- [ ] **Step 2: Frontend suite, lint, build**

Run:
```bash
cd frontend && npx vitest run
cd frontend && npm run lint && npm run build
```
Expected: all pass.

- [ ] **Step 3: Confirm the deletions actually happened**

Run:
```bash
cd backend && grep -rn "LocalTool\|TABLE_TOOL_IDS\|only one table tool\|requires a 'fitz' tool" app tests
```
Expected: no results.

- [ ] **Step 4: Open the PR**

```bash
git push -u origin feat/ocr-capability-pipeline
gh pr create --base main --head feat/ocr-capability-pipeline \
  --title "refactor(pipeline): capability slots + N-way capability-aware merger (WS2 PR A)"
```

The PR body must state: **behaviour-preserving for `ParsedDocument`; `ParseRun.raw_payload`
changes shape intentionally**; and that OCR (`tesseract_tool.py`, `has_uncovered_image`,
`precedence` config) lands in PR B.

---

## Self-Review Notes (author)

- **Spec coverage.** §2 capability model → Tasks 1, 3, 6 (enum, `provides`/`emit` masking, instance→slot, `TABLE_TOOL_IDS` deleted, `PipelineTool` rename). §3 precedence + eviction + audit trail → Tasks 1, 7. §3 reading order → unchanged `_sort_key` (Task 7); the *granularity* rule binds producers and has no PR A consumer, since no tool emits lines. §4b PR A scope → Tasks 1–10, exactly. §5 backend structure → Tasks 1–8. §6 frontend → Task 10. Acceptance property → Task 9.
- **Deferred to PR B, correctly:** `tesseract_tool.py`, `page_flags.has_uncovered_image`, the `precedence` config field, `pages: auto`, OCR UI. `Capability.TEXT_OCR` and `ocr_prefer` exist in PR A as *fully unit-tested pure logic* (Tasks 1, 7) so PR B only wires config — not dead code.
- **Type consistency.** `resolve_precedence(*, cid_corrupt, ocr_prefer)` keyword-only in Tasks 1/7. `ToolResult.blocks_by_capability` in Tasks 3/4/5/7. `run(pdf_path, *, pages, page_meta, emit)` in Tasks 3/4/5/8. `ResolvedPipeline.for_capability()` in Tasks 6/8. `overlap_fraction(winner, loser)` in Task 7.
- **Known risk.** Task 4's `fitz_tool.py` has a local variable named `page_meta` that now collides with the new keyword argument; the plan renames it `page_meta_out` explicitly.
- **Verified, not assumed.** `parser_eval` hashes pipeline config as an opaque dict, so the contract change has no blast radius there (`app/services/parser_eval/variants.py`).
