# Tesseract OCR Tool (WS2 slice 1, PR B) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add OCR to the custom pipeline as a `tesseract` tool filling the `text_ocr` capability slot — OCR runs wholesale on the selected pages and its output is reconciled spatially against native text.

**Architecture:** A `TesseractTool` (one concrete engine — the engine *is* the tool) rasterizes each selected page, runs `pytesseract.image_to_data`, and aggregates the word hierarchy into **paragraph-level** blocks (never lines — this preserves reading order). Page selection (`pages: auto|all|[…]`) and the CID/precedence flip are driven by `PageFlags` computed once in the runner. Native text beats OCR on overlap, except on CID-corrupt pages or when the router sets `precedence.text_ocr: "prefer"` — all of which PR A already built into the merger.

**Tech Stack:** Python 3.12, PyMuPDF (`fitz`), `pytesseract` + `Pillow` (already installed; tesseract 5.5 in the image and on the dev box). React 18, TypeScript, vitest.

**Spec:** [docs/superpowers/specs/2026-07-10-ocr-capability-pipeline-design.md](../specs/2026-07-10-ocr-capability-pipeline-design.md) (§3, §4, §4b PR B)

## Global Constraints

- **Pre-implementation gate:** a GitHub issue with acceptance criteria must exist and be confirmed with the user BEFORE Task 1. Branch `feat/ocr-tesseract-tool` already exists (off the merged PR A).
- **No new dependencies.** `pytesseract`, `Pillow` are in `pyproject.toml`; the `tesseract-ocr` binary is in the Dockerfile. Do NOT add paddleocr/easyocr. There is NO `execution` config field — execution location is parked.
- **The engine is the tool.** `tesseract` is a `tool_id` filling `text_ocr`. No `OcrEngine`/`OcrExecutor` abstraction in this slice.
- **Reading-order rule (load-bearing):** the OCR tool emits **paragraph-level** blocks with intra-paragraph order preserved. It must NEVER emit line-level or word-level blocks. The merger's `(y0, x0)` cross-block sort is unchanged.
- **`min_confidence` defaults to 0.0** — an evaluation tool must not silently discard low-confidence OCR.
- **`page_flags` thresholds live at the pipeline level**, not in the tesseract config, because the merger consumes `cid_corrupt` even when no OCR tool is configured.
- **Per-page OCR failure degrades to a warning + `failed_pages`**, never a failed run.
- Backend tests: `cd backend && uv run python -m pytest -o "addopts=" <path> -v` (SQLite). Integration tests that invoke tesseract are guarded `@pytest.mark.skipif(not _tesseract_available(), ...)`.
- Frontend: `cd frontend && npx vitest run <path>`, `npm run lint`, `npm run build`.
- `parser_eval` treats pipeline config as an opaque dict — do NOT touch `app/services/parser_eval/`.

---

## File Structure

**Create**
- `backend/app/cdm/adapters/custom_pipeline/tools/tesseract_tool.py` — `TesseractTool`, `aggregate_paragraphs`, `OcrParagraph`

**Modify**
- `backend/app/cdm/adapters/custom_pipeline/page_flags.py` — add `has_text_layer`, `has_uncovered_image`, the two thresholds, and the pure `image_is_uncovered` helper
- `backend/app/cdm/adapters/custom_pipeline/config.py` — `TesseractConfig`, register in `_tool_registry`, `ResolvedPipeline.ocr_prefer` + `precedence` parsing
- `backend/app/cdm/adapters/custom_pipeline/__init__.py` — export `TesseractConfig`, `TesseractTool`
- `backend/app/services/parsing/custom_pipeline_runner.py` — resolve OCR page selection; pass `ocr_prefer` to `merge`
- `frontend/src/components/documents/parser-configs/CustomPipelineConfig.tsx` (+ test) — OCR slot, precedence control, OCR thresholds

---

## Task 1: Page flags — `has_text_layer` + `has_uncovered_image`

**Files:**
- Modify: `backend/app/cdm/adapters/custom_pipeline/page_flags.py`
- Modify: `backend/tests/cdm/adapters/custom_pipeline/test_page_flags.py`

**Interfaces:**
- Consumes: `fitz`.
- Produces: `PageFlagsConfig` gains `min_uncovered_coverage: float = 0.10`, `covered_overlap: float = 0.6`. `PageFlags` gains `has_text_layer: bool`, `has_uncovered_image: bool`. New pure helper `image_is_uncovered(image, words, page_w, page_h, cfg) -> bool` where `image`/`words` are `(x0,y0,x1,y1)` point tuples.

- [ ] **Step 1: Write the failing test**

```python
# append to backend/tests/cdm/adapters/custom_pipeline/test_page_flags.py
import fitz
from app.cdm.adapters.custom_pipeline.page_flags import image_is_uncovered


CFG = PageFlagsConfig()  # min_uncovered_coverage=0.10, covered_overlap=0.6


def test_image_is_uncovered_true_for_large_untexted_image():
    # image covers 25% of a 100x100 page, no words over it
    assert image_is_uncovered((0, 0, 50, 50), [], 100.0, 100.0, CFG) is True


def test_image_is_uncovered_false_when_text_covers_it():
    # a word box spanning the whole image -> covered
    assert image_is_uncovered((0, 0, 50, 50), [(0, 0, 50, 50)], 100.0, 100.0, CFG) is False


def test_image_is_uncovered_false_for_tiny_image_below_coverage_floor():
    # image covers 1% of page -> below min_uncovered_coverage -> ignored
    assert image_is_uncovered((0, 0, 10, 10), [], 100.0, 100.0, CFG) is False


def test_flags_expose_has_text_layer(tmp_path):
    doc = fitz.open(); page = doc.new_page(width=612, height=792)
    page.insert_text((72, 72), "Plenty of real text here on the page", fontsize=11)
    p = tmp_path / "t.pdf"; doc.save(str(p)); doc.close()
    flags = compute_page_flags(p, PageFlagsConfig())
    assert flags[0].has_text_layer is True
    assert flags[0].has_uncovered_image is False


def test_flags_flag_a_full_bleed_untexted_image(tmp_path):
    doc = fitz.open(); page = doc.new_page(width=200, height=200)
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 180, 180))
    pix.set_rect(pix.irect, (10, 20, 30))
    page.insert_image(fitz.Rect(10, 10, 190, 190), pixmap=pix)
    p = tmp_path / "img.pdf"; doc.save(str(p)); doc.close()
    flags = compute_page_flags(p, PageFlagsConfig())
    assert flags[0].has_text_layer is False       # no text
    assert flags[0].has_uncovered_image is True    # big image, nothing over it
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/cdm/adapters/custom_pipeline/test_page_flags.py -v`
Expected: FAIL — `ImportError: cannot import name 'image_is_uncovered'`.

- [ ] **Step 3: Rewrite `page_flags.py`**

```python
"""Per-page facts consumed by the merger (CID precedence flip) and by the OCR
tool's `pages: "auto"` selector.

fitz metadata only — no rasterization. Deliberately independent of `app/probe/`:
the probe is advisory evidence, this is deterministic execution state.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import fitz
from pydantic import BaseModel

Rect = Tuple[float, float, float, float]  # (x0, y0, x1, y1) in page points


class PageFlagsConfig(BaseModel):
    min_chars: int = 10                 # below this, the page has no usable text layer
    cid_ratio: float = 0.3              # private-use-area char ratio => cid_corrupt
    min_uncovered_coverage: float = 0.10  # an image must cover >= this share of the page to matter
    covered_overlap: float = 0.6        # >= this share overlapped by text => "covered"


class PageFlags(BaseModel):
    index: int
    char_count: int
    pua_ratio: float
    cid_corrupt: bool
    has_text_layer: bool
    has_uncovered_image: bool


def pua_ratio(text: str) -> float:
    """Fraction of characters in the Unicode private-use area.

    A broken CID font decodes to private-use codepoints, so a high ratio means
    the page has a text layer that is present but unusable.
    """
    if not text:
        return 0.0
    pua = sum(1 for c in text if 0xE000 <= ord(c) <= 0xF8FF)
    return pua / len(text)


def _intersection_area(a: Rect, b: Rect) -> float:
    ix0, iy0 = max(a[0], b[0]), max(a[1], b[1])
    ix1, iy1 = min(a[2], b[2]), min(a[3], b[3])
    return max(0.0, ix1 - ix0) * max(0.0, iy1 - iy0)


def image_is_uncovered(
    image: Rect, words: Sequence[Rect], page_w: float, page_h: float,
    cfg: PageFlagsConfig,
) -> bool:
    """True if this image is large enough to matter and is NOT substantially
    covered by native text — i.e. it may hold text trapped in an image.

    This is the term that stops a full-bleed marketing image from triggering OCR
    on every page: a decorative image has near-zero text over it, yes, but so
    does a scanned figure. The caller's page-level policy decides what to do;
    here we only report the fact.
    """
    page_area = page_w * page_h
    img_area = max(0.0, image[2] - image[0]) * max(0.0, image[3] - image[1])
    if page_area <= 0 or img_area <= 0:
        return False
    if (img_area / page_area) < cfg.min_uncovered_coverage:
        return False
    covered = sum(_intersection_area(image, w) for w in words)
    return (covered / img_area) < cfg.covered_overlap


def compute_page_flags(pdf_path: Path, cfg: PageFlagsConfig) -> Dict[int, PageFlags]:
    out: Dict[int, PageFlags] = {}
    doc = fitz.open(str(pdf_path))
    try:
        for i in range(len(doc)):
            page = doc[i]
            w, h = page.rect.width, page.rect.height
            text = page.get_text("text")
            ratio = pua_ratio(text)
            char_count = len(text.strip())

            words: List[Rect] = [
                (word[0], word[1], word[2], word[3])
                for word in page.get_text("words")
            ]
            uncovered = False
            for img in page.get_images(full=True):
                for rect in page.get_image_rects(img[0]):
                    if image_is_uncovered(
                        (rect.x0, rect.y0, rect.x1, rect.y1), words, w, h, cfg
                    ):
                        uncovered = True
                        break
                if uncovered:
                    break

            out[i] = PageFlags(
                index=i,
                char_count=char_count,
                pua_ratio=ratio,
                cid_corrupt=ratio > cfg.cid_ratio,
                has_text_layer=char_count >= cfg.min_chars,
                has_uncovered_image=uncovered,
            )
    finally:
        doc.close()
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/cdm/adapters/custom_pipeline/test_page_flags.py -v`
Expected: PASS.

- [ ] **Step 5: Run the merger tests — `PageFlags` gained required fields**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/cdm/adapters/custom_pipeline/test_merger.py -v`
Expected: FAIL — the merger tests build `PageFlags(...)` without `has_text_layer`/`has_uncovered_image`. Update the `_flags` helper in `test_merger.py`:

```python
def _flags(cid=False):
    return {0: PageFlags(index=0, char_count=100, pua_ratio=0.0, cid_corrupt=cid,
                         has_text_layer=True, has_uncovered_image=False)}
```

Re-run: `cd backend && uv run python -m pytest -o "addopts=" tests/cdm/adapters/custom_pipeline/test_merger.py -v` → PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/cdm/adapters/custom_pipeline/page_flags.py backend/tests/cdm/adapters/custom_pipeline/test_page_flags.py backend/tests/cdm/adapters/custom_pipeline/test_merger.py
git commit -m "feat(pipeline): page flags gain has_text_layer + has_uncovered_image"
```

---

## Task 2: Tesseract config + precedence plumbing

**Files:**
- Modify: `backend/app/cdm/adapters/custom_pipeline/config.py`
- Modify: `backend/tests/cdm/adapters/custom_pipeline/test_config.py`

**Interfaces:**
- Consumes: `Capability`, `PageFlagsConfig`.
- Produces: `TesseractConfig(pages, lang, psm, dpi, min_confidence)`; `ResolvedPipeline` gains `ocr_prefer: bool`; `_tool_registry()` gains `"tesseract"`. `build_pipeline_config` parses `config["precedence"]["text_ocr"] == "prefer"`.
- **Note:** `TesseractConfig`'s factory does `TesseractTool(config=c)` — import lazily inside `_tool_registry` (same pattern as the others) to avoid importing `pytesseract` at module load.

- [ ] **Step 1: Write the failing test**

```python
# append to backend/tests/cdm/adapters/custom_pipeline/test_config.py
def test_tesseract_fills_the_text_ocr_slot():
    cfg = {
        "tools": {"fitz": {"tool": "fitz", "config": {}},
                  "ocr": {"tool": "tesseract", "config": {"pages": "auto", "lang": "eng"}}},
        "capabilities": {"text_extraction": "fitz", "text_ocr": "ocr"},
    }
    p = build_pipeline_config(cfg)
    inst = p.for_capability(Capability.TEXT_OCR)
    assert inst.key == "ocr"
    assert inst.tool.tool_id == "tesseract"
    assert inst.tool.config.pages == "auto"


def test_ocr_prefer_defaults_false_and_reads_precedence():
    base = {"tools": {"fitz": {"tool": "fitz", "config": {}}},
            "capabilities": {"text_extraction": "fitz"}}
    assert build_pipeline_config(base).ocr_prefer is False
    prefer = {**base, "precedence": {"text_ocr": "prefer"}}
    assert build_pipeline_config(prefer).ocr_prefer is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/cdm/adapters/custom_pipeline/test_config.py -v`
Expected: FAIL — `unknown tool: 'tesseract'` / `ResolvedPipeline` has no `ocr_prefer`.

- [ ] **Step 3: Edit `config.py`**

Add the config class after `FitzTablesConfig`:

```python
class TesseractConfig(BaseModel):
    pages: Union[Literal["auto", "all"], List[int]] = "auto"
    lang: str = "eng"
    psm: int = 3               # tesseract page-segmentation mode
    dpi: int = 300             # render resolution
    min_confidence: float = 0.0  # 0..1; default keeps everything
```

(`Union`, `Literal`, `List` are already imported.)

Register it in `_tool_registry()`:

```python
    from app.cdm.adapters.custom_pipeline.tools.tesseract_tool import TesseractTool
    # ...add to the returned dict:
        "tesseract": ToolSpec(TesseractConfig, TesseractTool.provides,
                              lambda c: TesseractTool(config=c)),
```

Add `ocr_prefer` to `ResolvedPipeline`:

```python
@dataclass(frozen=True)
class ResolvedPipeline:
    instances: List[ResolvedInstance]
    page_flags: PageFlagsConfig
    eviction_overlap_threshold: float
    ocr_eviction_threshold: float
    ocr_prefer: bool = False

    def for_capability(self, cap: Capability) -> Optional[ResolvedInstance]:
        return next((i for i in self.instances if cap in i.emit), None)
```

Parse it in `build_pipeline_config` (replace the `return ResolvedPipeline(...)`):

```python
    precedence = config.get("precedence", {}) or {}
    return ResolvedPipeline(
        instances=instances,
        page_flags=PageFlagsConfig.model_validate(config.get("page_flags", {}) or {}),
        eviction_overlap_threshold=config.get("eviction_overlap_threshold", 0.5),
        ocr_eviction_threshold=config.get("ocr_eviction_threshold", 0.3),
        ocr_prefer=precedence.get("text_ocr") == "prefer",
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/cdm/adapters/custom_pipeline/test_config.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/cdm/adapters/custom_pipeline/config.py backend/tests/cdm/adapters/custom_pipeline/test_config.py
git commit -m "feat(pipeline): TesseractConfig + ocr_prefer precedence plumbing"
```

---

## Task 3: Paragraph aggregation (the reading-order rule)

**Files:**
- Create: `backend/app/cdm/adapters/custom_pipeline/tools/tesseract_tool.py`
- Test: `backend/tests/cdm/adapters/custom_pipeline/test_tesseract_aggregation.py`

**Interfaces:**
- Produces: `OcrParagraph` dataclass (`text: str`, `bbox: Tuple[float,float,float,float]` normalized, `confidence: float`); `aggregate_paragraphs(data: Dict[str, list], img_w: int, img_h: int, min_confidence: float) -> List[OcrParagraph]`. `data` is a `pytesseract.image_to_data(output_type=DICT)` dict.
- This is the load-bearing rule: **words are grouped into paragraphs by `(block_num, par_num)`; lines are joined in order; NO line- or word-level output.**

- [ ] **Step 1: Write the failing test** (a fixture `image_to_data` dict — no tesseract needed)

```python
# backend/tests/cdm/adapters/custom_pipeline/test_tesseract_aggregation.py
from app.cdm.adapters.custom_pipeline.tools.tesseract_tool import (
    OcrParagraph, aggregate_paragraphs,
)


def _data(rows):
    """rows: list of (block, par, line, left, top, w, h, conf, text)."""
    keys = ["block_num", "par_num", "line_num", "left", "top", "width", "height",
            "conf", "text"]
    cols = {k: [] for k in keys}
    for r in rows:
        for k, v in zip(keys, r):
            cols[k].append(v)
    return cols


def test_words_group_into_a_single_paragraph_in_order():
    data = _data([
        (1, 1, 1, 10, 10, 40, 12, 95.0, "Hello"),
        (1, 1, 1, 55, 10, 40, 12, 90.0, "world"),
        (1, 1, 2, 10, 25, 90, 12, 80.0, "again"),
    ])
    paras = aggregate_paragraphs(data, img_w=200, img_h=100, min_confidence=0.0)
    assert len(paras) == 1
    assert paras[0].text == "Hello world\nagain"
    # bbox is the union, normalized to [0,1]
    assert paras[0].bbox[0] == 0.05 and paras[0].bbox[1] == 0.10
    assert abs(paras[0].bbox[2] - (95 / 200)) < 1e-9
    # mean of 95, 90, 80 -> 0.883...
    assert abs(paras[0].confidence - 0.8833) < 1e-3


def test_two_paragraphs_stay_separate():
    data = _data([
        (1, 1, 1, 10, 10, 40, 12, 90.0, "para"),
        (1, 1, 1, 55, 10, 40, 12, 90.0, "one"),
        (2, 1, 1, 10, 50, 40, 12, 70.0, "para"),
        (2, 1, 1, 55, 50, 40, 12, 70.0, "two"),
    ])
    paras = aggregate_paragraphs(data, img_w=200, img_h=100, min_confidence=0.0)
    assert [p.text for p in paras] == ["para one", "para two"]


def test_low_confidence_words_and_blanks_are_dropped():
    data = _data([
        (1, 1, 1, 10, 10, 40, 12, 95.0, "keep"),
        (1, 1, 1, 55, 10, 40, 12, -1.0, ""),      # tesseract's non-word rows
        (1, 1, 1, 90, 10, 40, 12, 5.0, "noise"),  # below min_confidence
    ])
    paras = aggregate_paragraphs(data, img_w=200, img_h=100, min_confidence=0.5)
    assert len(paras) == 1
    assert paras[0].text == "keep"
    assert isinstance(paras[0], OcrParagraph)


def test_paragraph_with_no_surviving_words_is_omitted():
    data = _data([(1, 1, 1, 10, 10, 40, 12, 1.0, "noise")])
    assert aggregate_paragraphs(data, img_w=200, img_h=100, min_confidence=0.5) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/cdm/adapters/custom_pipeline/test_tesseract_aggregation.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write the aggregation half of `tesseract_tool.py`**

```python
"""TesseractTool — OCR for the text_ocr capability slot.

Emits paragraph-level CDM TEXT blocks. It must never emit line- or word-level
blocks: the merger re-sorts blocks by (y0, x0), which would interleave the
lines of a multi-column page into gibberish. Paragraph granularity keeps each
block internally ordered and atomic.
"""
from __future__ import annotations

import io
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.cdm.adapters.custom_pipeline.capabilities import Capability
from app.cdm.adapters.custom_pipeline.config import TesseractConfig
from app.cdm.adapters.custom_pipeline.page_flags import PageFlags
from app.cdm.adapters.custom_pipeline.tools.base import PageMeta, ToolResult, clamp01
from app.cdm.models import BBox, Block, BlockRole, Quality


@dataclass
class OcrParagraph:
    text: str
    bbox: Tuple[float, float, float, float]  # normalized (x0, y0, x1, y1)
    confidence: float                         # 0..1


def aggregate_paragraphs(
    data: Dict[str, list], img_w: int, img_h: int, min_confidence: float,
) -> List[OcrParagraph]:
    """Group image_to_data word rows into ordered paragraph blocks.

    Rows are grouped by (block_num, par_num); within a paragraph, words are
    grouped by line_num and joined with spaces, lines joined with newlines. The
    dict preserves tesseract's reading order, so we do not re-sort.
    """
    n = len(data.get("text", []))
    # ordered paragraph keys; ordered line keys within each paragraph
    paragraphs: "List[Tuple[int, int]]" = []
    lines: Dict[Tuple[int, int], List[int]] = {}
    words: Dict[Tuple[int, int, int], List[int]] = {}

    for i in range(n):
        text = (data["text"][i] or "").strip()
        conf = float(data["conf"][i])
        if not text or conf < min_confidence * 100.0:
            continue
        pkey = (int(data["block_num"][i]), int(data["par_num"][i]))
        lkey = (*pkey, int(data["line_num"][i]))
        if pkey not in lines:
            paragraphs.append(pkey)
            lines[pkey] = []
        if lkey not in words:
            lines[pkey].append(lkey[2])
            words[lkey] = []
        words[lkey].append(i)

    out: List[OcrParagraph] = []
    for pkey in paragraphs:
        line_texts: List[str] = []
        confs: List[float] = []
        x0s, y0s, x1s, y1s = [], [], [], []
        for line_num in lines[pkey]:
            lkey = (*pkey, line_num)
            line_words = []
            for i in words[lkey]:
                line_words.append(data["text"][i].strip())
                confs.append(float(data["conf"][i]))
                left, top = float(data["left"][i]), float(data["top"][i])
                x0s.append(left); y0s.append(top)
                x1s.append(left + float(data["width"][i]))
                y1s.append(top + float(data["height"][i]))
            line_texts.append(" ".join(line_words))
        if not confs:
            continue
        out.append(OcrParagraph(
            text="\n".join(line_texts),
            bbox=(
                clamp01(min(x0s) / img_w), clamp01(min(y0s) / img_h),
                clamp01(max(x1s) / img_w), clamp01(max(y1s) / img_h),
            ),
            confidence=sum(confs) / len(confs) / 100.0,
        ))
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/cdm/adapters/custom_pipeline/test_tesseract_aggregation.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/cdm/adapters/custom_pipeline/tools/tesseract_tool.py backend/tests/cdm/adapters/custom_pipeline/test_tesseract_aggregation.py
git commit -m "feat(pipeline): tesseract paragraph aggregation (reading-order rule)"
```

---

## Task 4: `TesseractTool` — page selection + run

**Files:**
- Modify: `backend/app/cdm/adapters/custom_pipeline/tools/tesseract_tool.py`
- Modify: `backend/app/cdm/adapters/custom_pipeline/__init__.py`
- Test: `backend/tests/cdm/adapters/custom_pipeline/test_tesseract_tool.py`

**Interfaces:**
- Consumes: `aggregate_paragraphs`, `TesseractConfig`, `PageFlags`.
- Produces: `TesseractTool` with `tool_id="tesseract"`, `provides=frozenset({Capability.TEXT_OCR})`, `select_pages(flags) -> Optional[List[int]]`, and `run(pdf_path, *, pages=None, page_meta=None, emit) -> ToolResult`.
- `select_pages`: `"all" -> None` (run does every page), `[…] -> sorted list`, `"auto" -> pages where not has_text_layer OR cid_corrupt OR has_uncovered_image`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/cdm/adapters/custom_pipeline/test_tesseract_tool.py
import shutil
import fitz
import pytest

from app.cdm.adapters.custom_pipeline.capabilities import Capability
from app.cdm.adapters.custom_pipeline.config import TesseractConfig
from app.cdm.adapters.custom_pipeline.page_flags import PageFlags
from app.cdm.adapters.custom_pipeline.tools.tesseract_tool import TesseractTool


def _tesseract_available() -> bool:
    return shutil.which("tesseract") is not None


def _flags(**over):
    base = dict(index=0, char_count=0, pua_ratio=0.0, cid_corrupt=False,
                has_text_layer=False, has_uncovered_image=False)
    base.update(over)
    return PageFlags(**base)


def test_provides_text_ocr():
    assert TesseractTool().provides == frozenset({Capability.TEXT_OCR})


def test_select_pages_all_returns_none():
    tool = TesseractTool(config=TesseractConfig(pages="all"))
    assert tool.select_pages({0: _flags(), 1: _flags()}) is None


def test_select_pages_explicit_list_is_sorted():
    tool = TesseractTool(config=TesseractConfig(pages=[2, 0]))
    assert tool.select_pages({}) == [0, 2]


def test_select_pages_auto_picks_scanned_cid_and_uncovered():
    tool = TesseractTool(config=TesseractConfig(pages="auto"))
    flags = {
        0: _flags(has_text_layer=True),                       # clean text -> skip
        1: _flags(has_text_layer=False),                      # scanned -> ocr
        2: _flags(has_text_layer=True, cid_corrupt=True),     # cid -> ocr
        3: _flags(has_text_layer=True, has_uncovered_image=True),  # image text -> ocr
    }
    assert tool.select_pages(flags) == [1, 2, 3]


def test_run_rejects_an_emit_it_does_not_provide(tmp_path):
    doc = fitz.open(); doc.new_page(); p = tmp_path / "x.pdf"; doc.save(str(p)); doc.close()
    with pytest.raises(ValueError, match="cannot emit"):
        TesseractTool().run(p, emit=frozenset({Capability.TABLE_DETECTION}))


@pytest.mark.skipif(not _tesseract_available(), reason="tesseract binary not installed")
def test_run_recovers_text_from_a_rendered_page(tmp_path):
    # A page whose text is drawn large; OCR should recover it.
    doc = fitz.open(); page = doc.new_page(width=612, height=200)
    page.insert_text((40, 120), "INVOICE TOTAL", fontsize=48)
    p = tmp_path / "scan.pdf"; doc.save(str(p)); doc.close()

    result = TesseractTool(config=TesseractConfig(dpi=200)).run(
        p, pages=[0], emit=frozenset({Capability.TEXT_OCR}))
    blocks = result.blocks_by_capability[Capability.TEXT_OCR]
    assert blocks, "expected at least one OCR block"
    joined = " ".join(b.text for b in blocks).upper()
    assert "INVOICE" in joined
    b = blocks[0]
    assert b.native_type == "ocr_text"
    assert b.parser_extras["capability"] == "text_ocr"
    assert b.quality is not None and 0.0 <= b.quality.confidence <= 1.0
    for v in (b.bbox.x0, b.bbox.y0, b.bbox.x1, b.bbox.y1):
        assert 0.0 <= v <= 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/cdm/adapters/custom_pipeline/test_tesseract_tool.py -v`
Expected: FAIL — `TesseractTool` has no `select_pages`/`run`.

- [ ] **Step 3: Append the tool class to `tesseract_tool.py`**

```python
def _render_page_gray(page, dpi: int):
    """Render a fitz page to a PIL image at the given DPI."""
    from PIL import Image  # local import: Pillow is only needed when OCR runs
    pix = page.get_pixmap(matrix=fitz.Matrix(dpi / 72.0, dpi / 72.0))
    return Image.open(io.BytesIO(pix.tobytes("png"))), pix.width, pix.height


class TesseractTool:
    tool_id = "tesseract"
    provides = frozenset({Capability.TEXT_OCR})

    def __init__(self, config: Optional[TesseractConfig] = None) -> None:
        self.config = config or TesseractConfig()

    def select_pages(self, flags: Dict[int, PageFlags]) -> Optional[List[int]]:
        pages = self.config.pages
        if pages == "all":
            return None
        if isinstance(pages, list):
            return sorted(pages)
        # "auto"
        return sorted(
            i for i, f in flags.items()
            if (not f.has_text_layer) or f.cid_corrupt or f.has_uncovered_image
        )

    def run(
        self,
        pdf_path: Path,
        *,
        pages: Optional[List[int]] = None,
        page_meta: Optional[Dict[int, PageMeta]] = None,
        emit: frozenset = frozenset({Capability.TEXT_OCR}),
    ) -> ToolResult:
        if not emit <= self.provides:
            raise ValueError(f"{self.tool_id} cannot emit {set(emit - self.provides)}")

        import pytesseract
        from pytesseract import Output

        t0 = time.perf_counter()
        blocks: List[Block] = []
        native_by_block: Dict[str, object] = {}
        warnings: List[str] = []
        raw: Dict[int, object] = {}

        doc = fitz.open(str(pdf_path))
        try:
            for i in range(len(doc)):
                if pages is not None and i not in pages:
                    continue
                try:
                    image, img_w, img_h = _render_page_gray(doc[i], self.config.dpi)
                    data = pytesseract.image_to_data(
                        image, lang=self.config.lang,
                        config=f"--psm {self.config.psm}",
                        output_type=Output.DICT,
                    )
                except Exception as exc:  # noqa: BLE001
                    warnings.append(f"page {i}: OCR failed — {exc}")
                    continue

                paras = aggregate_paragraphs(
                    data, img_w, img_h, self.config.min_confidence)
                raw[i] = {"paragraphs": len(paras)}
                for seq, para in enumerate(paras):
                    prov_id = f"tesseract:{i}:{seq}"
                    blocks.append(Block(
                        id=prov_id, role=BlockRole.TEXT, native_type="ocr_text",
                        text=para.text, page_index=i,
                        bbox=BBox(x0=para.bbox[0], y0=para.bbox[1],
                                  x1=para.bbox[2], y1=para.bbox[3],
                                  source_space="pixels"),
                        quality=Quality(confidence=round(para.confidence, 4)),
                        parser_extras={"producer": "tesseract",
                                       "capability": "text_ocr", "engine": "tesseract"},
                    ))
                    native_by_block[prov_id] = {"page": i, "seq": seq,
                                                "confidence": para.confidence}
        finally:
            doc.close()

        return ToolResult(
            tool_id=self.tool_id,
            blocks_by_capability={Capability.TEXT_OCR: blocks},
            page_meta={},
            raw={"pages": raw},
            native_by_block=native_by_block,
            warnings=warnings,
            duration_ms=int((time.perf_counter() - t0) * 1000),
        )
```

- [ ] **Step 4: Export from `__init__.py`**

Add to the imports and `__all__` in `backend/app/cdm/adapters/custom_pipeline/__init__.py`:

```python
from app.cdm.adapters.custom_pipeline.config import (
    CamelotConfig, FitzConfig, FitzTablesConfig, TesseractConfig,
    ResolvedInstance, ResolvedPipeline, build_pipeline_config,
)
from app.cdm.adapters.custom_pipeline.tools.tesseract_tool import TesseractTool
```

Add `"TesseractConfig"` and `"TesseractTool"` to `__all__`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/cdm/adapters/custom_pipeline/test_tesseract_tool.py -v`
Expected: PASS (the integration test runs — tesseract is installed here).

- [ ] **Step 6: Commit**

```bash
git add backend/app/cdm/adapters/custom_pipeline/tools/tesseract_tool.py backend/app/cdm/adapters/custom_pipeline/__init__.py backend/tests/cdm/adapters/custom_pipeline/test_tesseract_tool.py
git commit -m "feat(pipeline): TesseractTool — page selection + OCR run"
```

---

## Task 5: Wire OCR into the runner

**Files:**
- Modify: `backend/app/services/parsing/custom_pipeline_runner.py`
- Modify: `backend/tests/services/parsing/test_custom_pipeline_runner.py`

**Interfaces:**
- Consumes: `ResolvedPipeline.for_capability`, `TesseractTool.select_pages`, `merge(..., ocr_prefer=...)`.
- The generic instance loop resolves a `pages` argument per instance: only the `text_ocr` instance gets a resolved page list (via `select_pages`); all others get `pages=None`.

- [ ] **Step 1: Write the failing test** (fitz-only PDF; a fake OCR tool proves wiring without needing tesseract)

```python
# append to backend/tests/services/parsing/test_custom_pipeline_runner.py
@pytest.mark.asyncio
async def test_runner_passes_selected_pages_and_ocr_prefer(monkeypatch):
    """The runner must resolve the OCR page selection via select_pages and pass
    ocr_prefer through to the merger."""
    captured = {}

    import app.cdm.adapters.custom_pipeline.config as cfgmod
    from app.cdm.adapters.custom_pipeline.capabilities import Capability
    from app.cdm.adapters.custom_pipeline.tools.base import ToolResult

    class FakeOcr:
        tool_id = "tesseract"
        provides = frozenset({Capability.TEXT_OCR})
        def __init__(self, config=None): pass
        def select_pages(self, flags):
            captured["select_pages_called"] = True
            return [0]
        def run(self, pdf_path, *, pages=None, page_meta=None, emit=frozenset()):
            captured["ocr_pages"] = pages
            return ToolResult(tool_id="tesseract",
                              blocks_by_capability={Capability.TEXT_OCR: []})

    # register the fake engine
    real_registry = cfgmod._tool_registry
    def fake_registry():
        reg = real_registry()
        reg["tesseract"] = cfgmod.ToolSpec(cfgmod.TesseractConfig,
                                           FakeOcr.provides, lambda c: FakeOcr())
        return reg
    monkeypatch.setattr(cfgmod, "_tool_registry", fake_registry)

    import app.cdm.adapters.custom_pipeline.merger as mergemod
    real_merge = mergemod.merge
    def spy_merge(*a, **k):
        captured["ocr_prefer"] = k.get("ocr_prefer")
        return real_merge(*a, **k)
    monkeypatch.setattr("app.services.parsing.custom_pipeline_runner.merge", spy_merge)

    config = {
        "tools": {"fitz": {"tool": "fitz", "config": {}},
                  "ocr": {"tool": "tesseract", "config": {"pages": "auto"}}},
        "capabilities": {"text_extraction": "fitz", "text_ocr": "ocr"},
        "precedence": {"text_ocr": "prefer"},
    }
    run, _ = await run_custom_pipeline(
        source=_source(), file_path=str(FIXTURES / "simple_text.pdf"),
        representation_kind="extract_rich", config=config, client=None)
    assert run.status == ParseRunStatus.SUCCEEDED
    assert captured["select_pages_called"] is True
    assert captured["ocr_pages"] == [0]
    assert captured["ocr_prefer"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/parsing/test_custom_pipeline_runner.py::test_runner_passes_selected_pages_and_ocr_prefer -v`
Expected: FAIL — runner ignores `select_pages` and never passes `ocr_prefer`.

- [ ] **Step 3: Edit the runner's instance loop and merge call**

Replace the `for inst in pipeline.instances:` loop and the `merge(...)` call:

```python
        for inst in pipeline.instances:
            if inst is text_instance:
                continue
            pages = None
            if Capability.TEXT_OCR in inst.emit:
                # OCR is the one capability whose page selection depends on
                # per-page facts; every other tool runs over the whole document.
                pages = inst.tool.select_pages(flags)
            r = inst.tool.run(
                pdf_path, pages=pages, page_meta=text_result.page_meta, emit=inst.emit)
            results.append(r)
            warnings.extend(r.warnings)

        merge_result = merge(
            results,
            source_document_id=source.id,
            page_flags=flags,
            ocr_prefer=pipeline.ocr_prefer,
            eviction_overlap_threshold=pipeline.eviction_overlap_threshold,
            ocr_eviction_threshold=pipeline.ocr_eviction_threshold,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/parsing/test_custom_pipeline_runner.py -v`
Expected: PASS (existing runner tests still green; new one passes).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/parsing/custom_pipeline_runner.py backend/tests/services/parsing/test_custom_pipeline_runner.py
git commit -m "feat(pipeline): runner resolves OCR page selection + ocr_prefer"
```

---

## Task 6: Mixed-page acceptance test

**Files:**
- Create: `backend/tests/cdm/adapters/custom_pipeline/test_ocr_reconciliation.py`

**Interfaces:**
- Consumes: `run_custom_pipeline`.
- Proves the whole reconciliation model end to end: on a page with native text AND an image containing text, native survives, OCR over native is evicted, OCR over the image survives.

- [ ] **Step 1: Write the test**

```python
# backend/tests/cdm/adapters/custom_pipeline/test_ocr_reconciliation.py
"""Acceptance test for OCR reconciliation.

On a page with a native text layer plus an image containing text, OCR runs
wholesale; the merger keeps native text and OCR-over-image, and drops OCR that
duplicates native text.
"""
import shutil
from datetime import datetime, timezone

import fitz
import pytest

from app.cdm.models import BlockRole
from app.cdm.source import ParseRunStatus, SourceDocument
from app.services.parsing.custom_pipeline_runner import run_custom_pipeline


def _tesseract_available() -> bool:
    return shutil.which("tesseract") is not None


def _source() -> SourceDocument:
    return SourceDocument(id="src-ocr", sha256="c" * 64, filename="mixed.pdf",
                          mime_type="application/pdf", byte_size=1,
                          created_at=datetime.now(timezone.utc))


def _mixed_pdf(tmp_path):
    """Native text at the top; an image of text (rendered separately) at the
    bottom with no native text under it."""
    # Build an image that itself contains the word LOGO.
    label = fitz.open(); lp = label.new_page(width=300, height=100)
    lp.insert_text((20, 70), "LOGO", fontsize=64)
    img_bytes = lp.get_pixmap(matrix=fitz.Matrix(2, 2)).tobytes("png")
    label.close()

    doc = fitz.open(); page = doc.new_page(width=612, height=400)
    page.insert_text((40, 60), "Native invoice heading", fontsize=18)
    page.insert_image(fitz.Rect(40, 200, 340, 300), stream=img_bytes)
    p = tmp_path / "mixed.pdf"; doc.save(str(p)); doc.close()
    return p


@pytest.mark.skipif(not _tesseract_available(), reason="tesseract binary not installed")
@pytest.mark.asyncio
async def test_ocr_keeps_image_text_and_drops_ocr_over_native(tmp_path):
    config = {
        "tools": {"fitz": {"tool": "fitz", "config": {}},
                  "ocr": {"tool": "tesseract", "config": {"pages": "all", "dpi": 200}}},
        "capabilities": {"text_extraction": "fitz", "text_ocr": "ocr"},
    }
    run, parsed = await run_custom_pipeline(
        source=_source(), file_path=str(_mixed_pdf(tmp_path)),
        representation_kind="extract_rich", config=config, client=None)

    assert run.status == ParseRunStatus.SUCCEEDED
    all_text = " ".join(b.text for b in parsed.blocks if b.text)
    # Native heading survives (exact), and the image's text is recovered by OCR.
    assert "Native invoice heading" in all_text
    assert "LOGO" in all_text.upper()

    # The surviving native heading is a native block, not an OCR block.
    heading = next(b for b in parsed.blocks if "Native invoice heading" in (b.text or ""))
    assert heading.native_type != "ocr_text"

    # Any OCR block that duplicated the native heading was evicted.
    for rec in run.raw_payload["evicted"]:
        assert rec["reason"] == "covered_by"
```

- [ ] **Step 2: Run the test**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/cdm/adapters/custom_pipeline/test_ocr_reconciliation.py -v`
Expected: PASS.

- [ ] **Step 3: Run the whole custom_pipeline suite + runner**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/cdm/adapters/custom_pipeline tests/services/parsing/test_custom_pipeline_runner.py -q`
Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/cdm/adapters/custom_pipeline/test_ocr_reconciliation.py
git commit -m "test(pipeline): mixed-page OCR reconciliation acceptance test"
```

---

## Task 7: Frontend — OCR slot + precedence control

**Files:**
- Modify: `frontend/src/components/documents/parser-configs/CustomPipelineConfig.tsx`
- Modify: `frontend/src/components/documents/parser-configs/CustomPipelineConfig.test.tsx`

**Interfaces:**
- Consumes: the existing `setSlot` / `setToolConfig` / `normalizeCustomPipelineConfig` helpers.
- Produces: a **Text OCR** slot (`none | tesseract`) with a config panel (`pages`, `lang`, `psm`, `dpi`, `min_confidence`) and a **precedence** control shown only when OCR is on, writing `config.precedence.text_ocr`.

- [ ] **Step 1: Write the failing test**

```tsx
// append to CustomPipelineConfig.test.tsx
const TESSERACT_DEFAULTS_KEYS = ['pages', 'lang', 'psm', 'dpi', 'min_confidence']

describe('OCR slot', () => {
  const base = {
    tools: { fitz: { tool: 'fitz', config: {} } },
    capabilities: { text_extraction: 'fitz' },
  }

  it('selecting tesseract adds a text_ocr slot with defaults', async () => {
    const onChange = vi.fn()
    render(<CustomPipelineConfig config={base} onChange={onChange} />)
    await userEvent.click(screen.getByRole('combobox', { name: /text ocr/i }))
    await userEvent.click(screen.getByText(/tesseract/i))
    const next = onChange.mock.calls[onChange.mock.calls.length - 1][0]
    expect(next.capabilities.text_ocr).toBe('tesseract')
    expect(next.tools.tesseract.tool).toBe('tesseract')
    for (const k of TESSERACT_DEFAULTS_KEYS) {
      expect(next.tools.tesseract.config[k]).toBeDefined()
    }
  })

  it('shows the precedence control only when OCR is on', () => {
    const withOcr = {
      tools: { fitz: { tool: 'fitz', config: {} },
               tesseract: { tool: 'tesseract', config: { pages: 'auto' } } },
      capabilities: { text_extraction: 'fitz', text_ocr: 'tesseract' },
    }
    const { rerender } = render(<CustomPipelineConfig config={base} onChange={vi.fn()} />)
    expect(screen.queryByText(/native text wins/i)).not.toBeInTheDocument()
    rerender(<CustomPipelineConfig config={withOcr} onChange={vi.fn()} />)
    expect(screen.getByText(/native text wins/i)).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/documents/parser-configs/CustomPipelineConfig.test.tsx`
Expected: FAIL — no Text OCR combobox / no precedence control.

- [ ] **Step 3: Add the OCR defaults + slot UI**

In `CustomPipelineConfig.tsx`, add near `CAMELOT_DEFAULTS`:

```tsx
const TESSERACT_DEFAULTS = {
  pages: 'auto', lang: 'eng', psm: 3, dpi: 300, min_confidence: 0,
}
```

Inside the component (after the table-slot block), derive the OCR state:

```tsx
  const ocrKey = capabilities.text_ocr
  const ocrTool = ocrKey ? tools[ocrKey] : undefined
  const ocrOn = !!ocrTool
  const precedencePrefer =
    ((cfg as unknown as { precedence?: Record<string, string> }).precedence
      ?.text_ocr) === 'prefer'

  const handleOcrToolChange = (value: 'none' | 'tesseract') => {
    onChange(setSlot(cfg, 'text_ocr', value === 'none' ? null : value,
      { ...TESSERACT_DEFAULTS }) as unknown as ParseConfig)
  }

  const setPrecedence = (prefer: boolean) => {
    const next = { ...cfg, precedence: { ...(cfg as any).precedence, text_ocr: prefer ? 'prefer' : 'fallback' } }
    onChange(next as unknown as ParseConfig)
  }
```

Render, after the Table extraction block:

```tsx
      {/* Text OCR — a capability slot */}
      <div className="space-y-2 rounded-md border p-3">
        <div className="space-y-1">
          <Label htmlFor="ocr-tool-select">Text OCR</Label>
          <p className="text-xs text-muted-foreground">
            Optional. Recovers text from scanned pages and text-in-images.
          </p>
          <Select value={ocrOn ? 'tesseract' : 'none'}
            onValueChange={(v) => handleOcrToolChange(v as 'none' | 'tesseract')}
            disabled={disabled}>
            <SelectTrigger id="ocr-tool-select" aria-label="Text OCR">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="none">none</SelectItem>
              <SelectItem value="tesseract">tesseract — local OCR</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {ocrOn && ocrKey && (
          <div className="space-y-3 pl-6">
            <div className="space-y-1">
              <Label htmlFor="ocr-pages">Pages</Label>
              <Select value={String(ocrTool!.config.pages ?? 'auto')}
                onValueChange={(v) => updateTool(ocrKey, { pages: v })}
                disabled={disabled}>
                <SelectTrigger id="ocr-pages"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="auto">auto (scanned / CID / text-in-image)</SelectItem>
                  <SelectItem value="all">all pages</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <NumField id="ocr-dpi" label="dpi" value={(ocrTool!.config.dpi as number) ?? 300}
              onChange={(v) => updateTool(ocrKey, { dpi: Math.round(v) })} disabled={disabled} />
            <NumField id="ocr-min-conf" label="min_confidence"
              description="0..1; 0 keeps every result"
              value={(ocrTool!.config.min_confidence as number) ?? 0}
              onChange={(v) => updateTool(ocrKey, { min_confidence: v })} disabled={disabled} />

            <div className="space-y-1">
              <Label htmlFor="ocr-precedence">When OCR overlaps native text</Label>
              <Select id="ocr-precedence" value={precedencePrefer ? 'prefer' : 'fallback'}
                onValueChange={(v) => setPrecedence(v === 'prefer')} disabled={disabled}>
                <SelectTrigger aria-label="Precedence"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="fallback">Native text wins (default)</SelectItem>
                  <SelectItem value="prefer">OCR wins — for scans with a poor text layer</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        )}
      </div>
```

Extend the `PipelineConfig` interface with `precedence?: Record<string, string>` so the new field type-checks.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/documents/parser-configs/CustomPipelineConfig.test.tsx`
Expected: PASS.

- [ ] **Step 5: Lint, build, full frontend suite**

Run:
```bash
cd frontend && npm run lint
cd frontend && npm run build
cd frontend && npx vitest run
```
Expected: lint clean; build succeeds; all pass.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/documents/parser-configs/CustomPipelineConfig.tsx frontend/src/components/documents/parser-configs/CustomPipelineConfig.test.tsx
git commit -m "feat(pipeline): OCR slot + precedence control in the config UI"
```

---

## Task 8: Full verification + PR

**Files:** none (verification only)

- [ ] **Step 1: Backend suite**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests -q`
Expected: all pass (except the known-pre-existing `test_project_repository.py::test_list_all_sorted_by_created_at`, which is unrelated to this work — confirm it is the only failure).

- [ ] **Step 2: Frontend suite, lint, build**

Run:
```bash
cd frontend && npx vitest run
cd frontend && npm run lint && npm run build
```
Expected: all pass.

- [ ] **Step 3: Rebuild the container so the running app picks up OCR**

Run:
```bash
cd /c/Repos/rag-admin && sed -i 's/\r//' backend/entrypoint.sh
docker compose -f docker-compose.local.yml -p rag-admin up --build -d
```
Expected: containers healthy. (`tesseract-ocr` is already in the image; no Dockerfile change.)

- [ ] **Step 4: Open the PR**

```bash
git push -u origin feat/ocr-tesseract-tool
gh pr create --base main --head feat/ocr-tesseract-tool \
  --title "feat(pipeline): tesseract OCR tool (WS2 PR B)"
```

The PR body must note: OCR fills the `text_ocr` slot; reconciliation keeps native text and OCR-over-image and drops OCR-over-native; `precedence.text_ocr: "prefer"` flips it; execution location remains parked (no `execution` field, tesseract in-process); no new dependencies.

---

## Self-Review Notes (author)

- **Spec coverage.** §3 reconciliation → Tasks 3 (paragraph rule), 5 (wiring), 6 (acceptance). §3 precedence/`ocr_prefer` → Tasks 2, 5 (PR A already built the merger logic). §4 tool identity/`OcrEngine`-is-the-tool → Task 4. §4 config → Task 2. §4 `pages: auto` + `has_uncovered_image` → Tasks 1, 4. §4 execution order → Task 5. §4 errors (warning + continue) → Task 4 (`try/except` per page). §6 UI → Task 7. `min_confidence` default 0.0 → Task 2. Reading-order rule → Task 3.
- **Deferred, correctly:** execution location (no `execution` field); paddleocr/easyocr; layout analysis.
- **Type consistency.** `PageFlags(index, char_count, pua_ratio, cid_corrupt, has_text_layer, has_uncovered_image)` — every constructor updated (Tasks 1, 5 test helper, Task 4 test helper). `select_pages(flags) -> Optional[List[int]]` (Tasks 4, 5). `aggregate_paragraphs(data, img_w, img_h, min_confidence) -> List[OcrParagraph]` (Tasks 3, 4). `merge(..., ocr_prefer=...)` already exists from PR A (Task 5 passes it). `ResolvedPipeline.ocr_prefer` (Tasks 2, 5).
- **Known integration point to confirm during execution:** `page.get_text("words")` returns tuples `(x0, y0, x1, y1, word, block_no, line_no, word_no)` — Task 1 uses only the first four; confirm the arity on the installed PyMuPDF.
- **Migration safety:** an existing pipeline config without `text_ocr` or `precedence` is unaffected — `for_capability(TEXT_OCR)` returns `None`, `ocr_prefer` defaults `False`. The PR A frontend normalizer already guarantees `text_extraction`, so no config-shape regression.
