# Standalone Probe Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone Probe feature that inspects a stored PDF and returns a structured `ProbeReport` of per-page and per-image-region evidence (signals + confidence) to inform downstream parser configuration — consumed by a new `/probe` UI and by AI agents.

**Architecture:** New top-level `backend/app/probe/` package (evidence provider, not a CDM producer). A pluggable `InspectionBackend` (fitz only in slice 1) extracts primitives; independent, configurable signal analyzers turn primitives into `Signal`s; an `observe()` step derives a per-region observation label + confidence; a thin, non-authoritative `recommend()` produces an advisory parser suggestion. Exposed as `POST /probe`. Frontend reuses `DocumentPickerPanel` and the already-decoupled `DocumentPdfViewer` (via a `RegionFinding`→synthetic-block adapter). No persistence.

**Tech Stack:** Python 3.12, FastAPI (async), pydantic v2, PyMuPDF (`fitz`), numpy (Sobel). React 18, TypeScript, Vite, shadcn/ui, Tailwind, react-router, vitest.

**Spec:** [docs/superpowers/specs/2026-07-09-probe-standalone-design.md](../specs/2026-07-09-probe-standalone-design.md)

## Global Constraints

- **Pre-implementation gate:** a GitHub issue with acceptance criteria must exist and be confirmed with the user BEFORE Task 1. Work on branch `feat/standalone-probe` (already created).
- **Two PRs, one branch:** Tasks 1–18 = PR 1 (new probe, legacy untouched). Tasks 19–20 = PR 2 (legacy removal), only after PR 1 is reviewed.
- **No persistence** — probe is request/response; no models, migrations, or repositories.
- **Backend tests run on SQLite** via the `test_db` fixture. Run backend tests with: `cd backend && uv run python -m pytest -o "addopts=" <path> -v`.
- **numpy only** for edge density — do NOT add OpenCV/scikit-image.
- **All bboxes normalized to `[0,1]`** (matches `DocumentPdfViewer`).
- **Data flow:** router → service → (probe package). Services raise exceptions; routers catch and map to HTTP.
- **Frontend:** one hook per feature (`useProbe`); shadcn/ui + Tailwind for all UI.
- **Confidence is a calibrated score, not a probability** — always surface the contributing inputs.

---

## Task 1: Report contract + config

**Files:**
- Create: `backend/app/probe/__init__.py` (empty)
- Create: `backend/app/probe/report.py`
- Create: `backend/app/probe/config.py`
- Test: `backend/tests/probe/__init__.py` (empty), `backend/tests/probe/test_report_contract.py`

**Interfaces:**
- Produces: `BBox`, `Signal`, `Observation`, `RegionFinding`, `PageProfile`, `ParserSuggestion`, `ProbeReport` (pydantic models); `ProbeConfig`, `Thresholds`, `DEFAULT_CONFIG`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/probe/test_report_contract.py
from app.probe.report import (
    BBox, Signal, Observation, RegionFinding, PageProfile, ProbeReport,
)
from app.probe.config import ProbeConfig, DEFAULT_CONFIG


def test_probe_report_roundtrips_json():
    region = RegionFinding(
        id="p0:img0", page_index=0, kind="image",
        bbox=BBox(x0=0.1, y0=0.1, x1=0.9, y1=0.5),
        signals=[Signal(name="edge_density", value=0.21, unit=None, strength=0.85, detail="sobel")],
        observation=Observation(label="text_image", confidence=0.88),
    )
    page = PageProfile(index=0, page_type="scanned", signals=[], regions=[region])
    report = ProbeReport(
        document_id="doc-1", filename="a.pdf", page_count=1,
        inspection={"backend": "fitz", "backend_version": "1.27", "config_used": DEFAULT_CONFIG.model_dump()},
        pages=[page], suggestion=None, duration_ms=5, probed_at="2026-07-09T00:00:00Z",
    )
    dumped = report.model_dump(mode="json")
    assert dumped["pages"][0]["regions"][0]["observation"]["label"] == "text_image"
    assert ProbeReport.model_validate(dumped).pages[0].regions[0].observation.confidence == 0.88


def test_default_config_has_all_signals_and_thresholds():
    cfg = ProbeConfig()
    assert set(cfg.enabled_signals) == {
        "text_layer", "font_health", "copy_restricted",
        "coverage", "dpi", "text_overlap", "table_grid", "edge_density",
    }
    assert cfg.thresholds.edge_density_min == 0.15
    assert cfg.backend == "fitz"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/probe/test_report_contract.py -v`
Expected: FAIL — `ModuleNotFoundError: app.probe.report`.

- [ ] **Step 3: Write `config.py`**

```python
# backend/app/probe/config.py
from __future__ import annotations
from typing import List, Literal
from pydantic import BaseModel, Field

ALL_SIGNALS = [
    "text_layer", "font_health", "copy_restricted",
    "coverage", "dpi", "text_overlap", "table_grid", "edge_density",
]


class Thresholds(BaseModel):
    min_text_chars: int = 10
    cid_ratio: float = 0.3
    edge_density_min: float = 0.15   # >= is text-like
    coverage_min: float = 0.10       # image must cover >= 10% of page to matter
    table_line_min: int = 3
    overlap_covered: float = 0.6     # >= means text already sits over the image


class ProbeConfig(BaseModel):
    enabled_signals: List[str] = Field(default_factory=lambda: list(ALL_SIGNALS))
    thresholds: Thresholds = Field(default_factory=Thresholds)
    backend: Literal["fitz"] = "fitz"


DEFAULT_CONFIG = ProbeConfig()
```

- [ ] **Step 4: Write `report.py`**

```python
# backend/app/probe/report.py
from __future__ import annotations
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel

ObservationLabel = Literal[
    "text_image", "decorative_image", "text_covered_image", "uncertain", "table_grid",
]
PageType = Literal["text", "scanned", "mixed", "empty"]


class BBox(BaseModel):
    x0: float
    y0: float
    x1: float
    y1: float


class Signal(BaseModel):
    name: str
    value: Union[float, str]
    unit: Optional[str] = None
    strength: Optional[float] = None   # normalized 0..1
    detail: Optional[str] = None


class Observation(BaseModel):
    label: ObservationLabel
    confidence: float


class RegionFinding(BaseModel):
    id: str
    page_index: int
    kind: Literal["image", "table"]
    bbox: BBox
    signals: List[Signal] = []
    observation: Observation


class PageProfile(BaseModel):
    index: int
    page_type: PageType
    signals: List[Signal] = []
    regions: List[RegionFinding] = []


class ParserSuggestion(BaseModel):
    authoritative: bool = False
    tools: List[str] = []
    ocr_pages: List[int] = []
    overall_confidence: float = 0.0
    rationale: List[str] = []


class ProbeReport(BaseModel):
    document_id: str
    filename: Optional[str]
    page_count: int
    inspection: Dict[str, Any]
    pages: List[PageProfile]
    suggestion: Optional[ParserSuggestion]
    duration_ms: int
    probed_at: str
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/probe/test_report_contract.py -v`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add backend/app/probe/__init__.py backend/app/probe/report.py backend/app/probe/config.py backend/tests/probe/
git commit -m "feat(probe): report contract + config models"
```

---

## Task 2: Inspection backend seam + fitz backend

**Files:**
- Create: `backend/app/probe/backends/__init__.py` (empty)
- Create: `backend/app/probe/backends/base.py`
- Create: `backend/app/probe/backends/fitz_backend.py`
- Test: `backend/tests/probe/test_fitz_backend.py`, `backend/tests/probe/fixtures/` (generated in-test)

**Interfaces:**
- Consumes: `BBox` (Task 1).
- Produces: `TextSpan`, `ImagePrimitive`, `DrawingPrimitive`, `PagePrimitives`, `DocumentPrimitives`, `InspectionBackend` (Protocol), `FitzBackend` with `inspect(pdf_path) -> DocumentPrimitives` and `render_gray(pdf_path, page_index, bbox, target_px=256) -> numpy.ndarray`.

- [ ] **Step 1: Write the failing test** (builds a 1-page PDF with text + a rectangle via fitz, then inspects it)

```python
# backend/tests/probe/test_fitz_backend.py
import fitz
import numpy as np
from app.probe.backends.fitz_backend import FitzBackend
from app.probe.report import BBox


def _make_pdf(tmp_path):
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((72, 72), "Hello invoice world", fontsize=12)
    page.draw_rect(fitz.Rect(100, 300, 500, 500))  # a box -> a drawing
    path = tmp_path / "sample.pdf"
    doc.save(str(path)); doc.close()
    return path


def test_inspect_extracts_text_size_and_drawings(tmp_path):
    path = _make_pdf(tmp_path)
    prims = FitzBackend().inspect(path)
    assert prims.page_count == 1
    p = prims.pages[0]
    assert p.width_pt == 612 and p.height_pt == 792
    assert "invoice" in p.text
    assert len(p.text_spans) >= 1
    assert all(0.0 <= s.bbox.x0 <= 1.0 for s in p.text_spans)  # normalized
    assert len(p.drawings) >= 1


def test_render_gray_returns_2d_array(tmp_path):
    path = _make_pdf(tmp_path)
    gray = FitzBackend().render_gray(path, 0, BBox(x0=0.1, y0=0.3, x1=0.9, y1=0.7), target_px=64)
    assert gray.ndim == 2
    assert gray.dtype == np.uint8
    assert max(gray.shape) <= 64
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/probe/test_fitz_backend.py -v`
Expected: FAIL — `ModuleNotFoundError: app.probe.backends.fitz_backend`.

- [ ] **Step 3: Write `base.py`**

```python
# backend/app/probe/backends/base.py
from __future__ import annotations
from pathlib import Path
from typing import List, Protocol, runtime_checkable
import numpy as np
from pydantic import BaseModel
from app.probe.report import BBox


class TextSpan(BaseModel):
    text: str
    bbox: BBox            # normalized


class ImagePrimitive(BaseModel):
    xref: int
    bbox: BBox            # normalized position on the page
    width_px: int         # native pixel dimensions of the embedded image
    height_px: int


class DrawingPrimitive(BaseModel):
    kind: str             # 'l' (line) or 're' (rect)
    bbox: BBox


class PagePrimitives(BaseModel):
    index: int
    width_pt: float
    height_pt: float
    text: str
    text_spans: List[TextSpan]
    images: List[ImagePrimitive]
    drawings: List[DrawingPrimitive]


class DocumentPrimitives(BaseModel):
    page_count: int
    copy_restricted: bool
    pages: List[PagePrimitives]


@runtime_checkable
class InspectionBackend(Protocol):
    name: str
    version: str
    def inspect(self, pdf_path: Path) -> DocumentPrimitives: ...
    def render_gray(self, pdf_path: Path, page_index: int, bbox: BBox, target_px: int = 256) -> np.ndarray: ...
```

- [ ] **Step 4: Write `fitz_backend.py`**

```python
# backend/app/probe/backends/fitz_backend.py
from __future__ import annotations
from pathlib import Path
import fitz
import numpy as np
from app.probe.backends.base import (
    DocumentPrimitives, DrawingPrimitive, ImagePrimitive, PagePrimitives, TextSpan,
)
from app.probe.report import BBox


def _norm(x0, y0, x1, y1, w, h) -> BBox:
    return BBox(x0=max(0.0, x0 / w), y0=max(0.0, y0 / h),
                x1=min(1.0, x1 / w), y1=min(1.0, y1 / h))


class FitzBackend:
    name = "fitz"
    version = fitz.VersionBind

    def inspect(self, pdf_path: Path) -> DocumentPrimitives:
        doc = fitz.open(str(pdf_path))
        try:
            copy_restricted = (doc.permissions & fitz.PDF_PERM_COPY) == 0
            pages = [self._page(doc, i) for i in range(len(doc))]
            return DocumentPrimitives(
                page_count=len(pages), copy_restricted=copy_restricted, pages=pages,
            )
        finally:
            doc.close()

    def _page(self, doc, i) -> PagePrimitives:
        page = doc[i]
        w, h = page.rect.width, page.rect.height
        text = page.get_text("text")
        spans = []
        for blk in page.get_text("dict")["blocks"]:
            for line in blk.get("lines", []):
                for span in line.get("spans", []):
                    x0, y0, x1, y1 = span["bbox"]
                    spans.append(TextSpan(text=span["text"], bbox=_norm(x0, y0, x1, y1, w, h)))
        images = []
        for img in page.get_images(full=True):
            xref = img[0]
            rects = page.get_image_rects(xref)
            if not rects:
                continue
            r = rects[0]
            images.append(ImagePrimitive(
                xref=xref, bbox=_norm(r.x0, r.y0, r.x1, r.y1, w, h),
                width_px=int(img[2]), height_px=int(img[3]),
            ))
        drawings = []
        for path in page.get_drawings():
            for item in path.get("items", []):
                if item[0] in ("l", "re"):
                    rect = path.get("rect")
                    if rect:
                        drawings.append(DrawingPrimitive(
                            kind=item[0], bbox=_norm(rect.x0, rect.y0, rect.x1, rect.y1, w, h)))
        return PagePrimitives(
            index=i, width_pt=w, height_pt=h, text=text,
            text_spans=spans, images=images, drawings=drawings,
        )

    def render_gray(self, pdf_path: Path, page_index: int, bbox: BBox, target_px: int = 256) -> np.ndarray:
        doc = fitz.open(str(pdf_path))
        try:
            page = doc[page_index]
            w, h = page.rect.width, page.rect.height
            clip = fitz.Rect(bbox.x0 * w, bbox.y0 * h, bbox.x1 * w, bbox.y1 * h)
            longest = max(clip.width, clip.height) or 1.0
            scale = min(target_px / longest, 4.0)
            pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), clip=clip, colorspace=fitz.csGRAY)
            arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
            return arr
        finally:
            doc.close()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/probe/test_fitz_backend.py -v`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add backend/app/probe/backends/ backend/tests/probe/test_fitz_backend.py
git commit -m "feat(probe): fitz inspection backend + primitives"
```

---

## Task 3: Page-level signal analyzers

**Files:**
- Create: `backend/app/probe/signals/__init__.py` (empty)
- Create: `backend/app/probe/signals/page_signals.py`
- Test: `backend/tests/probe/test_page_signals.py`

**Interfaces:**
- Consumes: `PagePrimitives`, `DocumentPrimitives` (Task 2), `ProbeConfig`, `Signal` (Task 1).
- Produces: `text_layer(page, cfg) -> list[Signal]`, `font_health(page, cfg) -> list[Signal]`, `copy_restricted(doc, cfg) -> list[Signal]`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/probe/test_page_signals.py
from app.probe.backends.base import DocumentPrimitives, PagePrimitives
from app.probe.config import ProbeConfig
from app.probe.signals.page_signals import text_layer, font_health, copy_restricted


def _page(text="", spans=None):
    return PagePrimitives(index=0, width_pt=612, height_pt=792, text=text,
                          text_spans=spans or [], images=[], drawings=[])


def test_text_layer_reports_char_count_and_presence():
    sigs = {s.name: s for s in text_layer(_page("Hello world " * 5), ProbeConfig())}
    assert sigs["has_text_layer"].value == "true"
    assert float(sigs["char_count"].value) >= 60


def test_font_health_flags_cid_corruption():
    corrupt = "".join(chr(0xE000 + i % 10) for i in range(100))
    sigs = {s.name: s for s in font_health(_page(corrupt), ProbeConfig())}
    assert sigs["font_health"].value == "cid_corrupt"


def test_copy_restricted_signal():
    doc = DocumentPrimitives(page_count=1, copy_restricted=True, pages=[_page("x")])
    sigs = {s.name: s for s in copy_restricted(doc, ProbeConfig())}
    assert sigs["copy_restricted"].value == "true"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/probe/test_page_signals.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write `page_signals.py`**

```python
# backend/app/probe/signals/page_signals.py
from __future__ import annotations
from typing import List
from app.probe.backends.base import DocumentPrimitives, PagePrimitives
from app.probe.config import ProbeConfig
from app.probe.report import Signal


def text_layer(page: PagePrimitives, cfg: ProbeConfig) -> List[Signal]:
    chars = len(page.text.strip())
    has = chars >= cfg.thresholds.min_text_chars
    return [
        Signal(name="char_count", value=float(chars), unit="chars"),
        Signal(name="has_text_layer", value="true" if has else "false",
               strength=1.0 if has else 0.0, detail=f"{chars} chars (min {cfg.thresholds.min_text_chars})"),
    ]


def font_health(page: PagePrimitives, cfg: ProbeConfig) -> List[Signal]:
    text = page.text
    if not text.strip():
        return [Signal(name="font_health", value="unknown")]
    pua = sum(1 for c in text if 0xE000 <= ord(c) <= 0xF8FF)
    ratio = pua / len(text)
    if ratio > cfg.thresholds.cid_ratio:
        health = "cid_corrupt"
    elif ratio > 0.05:
        health = "mixed"
    else:
        health = "clean"
    return [Signal(name="font_health", value=health, strength=1.0 - min(ratio, 1.0),
                   detail=f"{ratio:.0%} private-use chars")]


def copy_restricted(doc: DocumentPrimitives, cfg: ProbeConfig) -> List[Signal]:
    return [Signal(name="copy_restricted", value="true" if doc.copy_restricted else "false",
                   detail="PDF_PERM_COPY bit clear" if doc.copy_restricted else "copy allowed")]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/probe/test_page_signals.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/probe/signals/__init__.py backend/app/probe/signals/page_signals.py backend/tests/probe/test_page_signals.py
git commit -m "feat(probe): page-level signal analyzers (text_layer, font_health, copy_restricted)"
```

---

## Task 4: Region metadata signals (coverage, dpi, text_overlap)

**Files:**
- Create: `backend/app/probe/signals/region_signals.py`
- Test: `backend/tests/probe/test_region_signals.py`

**Interfaces:**
- Consumes: `PagePrimitives`, `ImagePrimitive` (Task 2), `ProbeConfig`, `Signal`, `BBox` (Task 1).
- Produces: `coverage(page, image, cfg) -> Signal`, `dpi(page, image, cfg) -> Signal`, `text_overlap(page, image, cfg) -> Signal`, and helper `bbox_area(b) -> float`, `intersect_area(a, b) -> float`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/probe/test_region_signals.py
from app.probe.backends.base import ImagePrimitive, PagePrimitives, TextSpan
from app.probe.config import ProbeConfig
from app.probe.report import BBox
from app.probe.signals.region_signals import coverage, dpi, text_overlap


def _img(x0, y0, x1, y1, wpx=900, hpx=600):
    return ImagePrimitive(xref=1, bbox=BBox(x0=x0, y0=y0, x1=x1, y1=y1), width_px=wpx, height_px=hpx)


def _page(spans=None):
    return PagePrimitives(index=0, width_pt=612, height_pt=792, text="", text_spans=spans or [],
                          images=[], drawings=[])


def test_coverage_is_fraction_of_page():
    s = coverage(_page(), _img(0.0, 0.0, 0.5, 0.5), ProbeConfig())
    assert abs(float(s.value) - 0.25) < 1e-6


def test_dpi_from_pixels_over_rendered_inches():
    # image spans full 612pt width (8.5in) with 900 px -> ~105 dpi
    s = dpi(_page(), _img(0.0, 0.0, 1.0, 0.5, wpx=900), ProbeConfig())
    assert 100 <= float(s.value) <= 110


def test_text_overlap_high_when_text_sits_over_image():
    spans = [TextSpan(text="hi", bbox=BBox(x0=0.1, y0=0.1, x1=0.9, y1=0.9))]
    s = text_overlap(_page(spans), _img(0.0, 0.0, 1.0, 1.0), ProbeConfig())
    assert float(s.value) > 0.5


def test_text_overlap_zero_when_no_text():
    s = text_overlap(_page([]), _img(0.0, 0.0, 1.0, 1.0), ProbeConfig())
    assert float(s.value) == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/probe/test_region_signals.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write `region_signals.py`**

```python
# backend/app/probe/signals/region_signals.py
from __future__ import annotations
from app.probe.backends.base import ImagePrimitive, PagePrimitives
from app.probe.config import ProbeConfig
from app.probe.report import BBox, Signal


def bbox_area(b: BBox) -> float:
    return max(0.0, b.x1 - b.x0) * max(0.0, b.y1 - b.y0)


def intersect_area(a: BBox, b: BBox) -> float:
    ix0, iy0 = max(a.x0, b.x0), max(a.y0, b.y0)
    ix1, iy1 = min(a.x1, b.x1), min(a.y1, b.y1)
    return max(0.0, ix1 - ix0) * max(0.0, iy1 - iy0)


def coverage(page: PagePrimitives, image: ImagePrimitive, cfg: ProbeConfig) -> Signal:
    frac = bbox_area(image.bbox)   # page is the unit square in normalized coords
    return Signal(name="coverage", value=round(frac, 4), unit="fraction",
                  strength=min(frac, 1.0), detail=f"{frac:.0%} of page")


def dpi(page: PagePrimitives, image: ImagePrimitive, cfg: ProbeConfig) -> Signal:
    rendered_in = ((image.bbox.x1 - image.bbox.x0) * page.width_pt) / 72.0
    value = (image.width_px / rendered_in) if rendered_in > 0 else 0.0
    return Signal(name="dpi", value=round(value, 1), unit="dpi",
                  strength=min(value / 300.0, 1.0), detail=f"{image.width_px}px over {rendered_in:.1f}in")


def text_overlap(page: PagePrimitives, image: ImagePrimitive, cfg: ProbeConfig) -> Signal:
    img_area = bbox_area(image.bbox)
    if img_area == 0.0:
        return Signal(name="text_overlap", value=0.0, unit="fraction", strength=0.0)
    covered = sum(intersect_area(image.bbox, s.bbox) for s in page.text_spans)
    frac = min(covered / img_area, 1.0)
    return Signal(name="text_overlap", value=round(frac, 4), unit="fraction",
                  strength=frac, detail=f"{frac:.0%} of image covered by text spans")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/probe/test_region_signals.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/probe/signals/region_signals.py backend/tests/probe/test_region_signals.py
git commit -m "feat(probe): region metadata signals (coverage, dpi, text_overlap)"
```

---

## Task 5: Table-grid signal

**Files:**
- Modify: `backend/app/probe/signals/region_signals.py` (append `table_grid`)
- Test: `backend/tests/probe/test_table_grid.py`

**Interfaces:**
- Consumes: `PagePrimitives.drawings` (Task 2), `ProbeConfig`, `Signal`, `BBox`.
- Produces: `table_grid(page, cfg) -> list[RegionFinding-less tuple]` — returns `list[tuple[BBox, Signal]]` (bbox of the detected grid + a `table_grid` signal). The prober turns each into a `RegionFinding` with `kind="table"`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/probe/test_table_grid.py
from app.probe.backends.base import DrawingPrimitive, PagePrimitives
from app.probe.config import ProbeConfig
from app.probe.report import BBox
from app.probe.signals.region_signals import table_grid


def _page(drawings):
    return PagePrimitives(index=0, width_pt=612, height_pt=792, text="",
                          text_spans=[], images=[], drawings=drawings)


def test_table_grid_detected_when_enough_lines_cluster():
    lines = [DrawingPrimitive(kind="l", bbox=BBox(x0=0.1, y0=0.1 + i * 0.05, x1=0.9, y1=0.1 + i * 0.05))
             for i in range(5)]
    results = table_grid(_page(lines), ProbeConfig())
    assert len(results) == 1
    bbox, sig = results[0]
    assert sig.name == "table_grid"
    assert float(sig.value) >= 5


def test_no_table_when_too_few_lines():
    lines = [DrawingPrimitive(kind="l", bbox=BBox(x0=0.1, y0=0.2, x1=0.9, y1=0.2))]
    assert table_grid(_page(lines), ProbeConfig()) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/probe/test_table_grid.py -v`
Expected: FAIL — `ImportError: cannot import name 'table_grid'`.

- [ ] **Step 3: Append `table_grid` to `region_signals.py`**

```python
# backend/app/probe/signals/region_signals.py  (append)
from typing import List, Tuple
from app.probe.backends.base import PagePrimitives  # already imported above


def table_grid(page: PagePrimitives, cfg: ProbeConfig) -> List[Tuple[BBox, Signal]]:
    lines = [d.bbox for d in page.drawings if d.kind in ("l", "re")]
    if len(lines) < cfg.thresholds.table_line_min:
        return []
    x0 = min(b.x0 for b in lines); y0 = min(b.y0 for b in lines)
    x1 = max(b.x1 for b in lines); y1 = max(b.y1 for b in lines)
    grid = BBox(x0=x0, y0=y0, x1=x1, y1=y1)
    regularity = min(len(lines) / 12.0, 1.0)
    sig = Signal(name="table_grid", value=float(len(lines)), unit="lines",
                 strength=regularity, detail=f"{len(lines)} ruling lines")
    return [(grid, sig)]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/probe/test_table_grid.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/probe/signals/region_signals.py backend/tests/probe/test_table_grid.py
git commit -m "feat(probe): table_grid region signal"
```

---

## Task 6: Edge-density signal (numpy-Sobel)

**Files:**
- Create: `backend/app/probe/signals/edge_density.py`
- Test: `backend/tests/probe/test_edge_density.py`

**Interfaces:**
- Consumes: `ProbeConfig`, `Signal`; a grayscale `numpy.ndarray` (produced by `FitzBackend.render_gray`).
- Produces: `edge_density(gray, cfg) -> Signal` (name `"edge_density"`, `value` = ratio, `strength` = ratio normalized against `edge_density_min`).

- [ ] **Step 1: Write the failing test** (synthetic arrays — no PDF needed)

```python
# backend/tests/probe/test_edge_density.py
import numpy as np
from app.probe.config import ProbeConfig
from app.probe.signals.edge_density import edge_density


def test_text_like_pattern_has_higher_density_than_smooth():
    stripes = np.zeros((64, 64), dtype=np.uint8)
    stripes[:, ::2] = 255                       # high-frequency edges, like text strokes
    smooth = np.tile(np.linspace(0, 255, 64, dtype=np.uint8), (64, 1))  # gradient
    d_text = float(edge_density(stripes, ProbeConfig()).value)
    d_smooth = float(edge_density(smooth, ProbeConfig()).value)
    assert d_text > d_smooth


def test_strength_crosses_threshold_for_text_like():
    stripes = np.zeros((64, 64), dtype=np.uint8)
    stripes[:, ::2] = 255
    sig = edge_density(stripes, ProbeConfig())
    assert sig.name == "edge_density"
    assert sig.strength >= 0.5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/probe/test_edge_density.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write `edge_density.py`**

```python
# backend/app/probe/signals/edge_density.py
from __future__ import annotations
import numpy as np
from app.probe.config import ProbeConfig
from app.probe.report import Signal

_KX = np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], dtype=np.float32)
_KY = _KX.T


def _convolve2d(a: np.ndarray, k: np.ndarray) -> np.ndarray:
    padded = np.pad(a, 1, mode="edge")
    out = np.zeros_like(a, dtype=np.float32)
    for dy in range(3):
        for dx in range(3):
            out += k[dy, dx] * padded[dy:dy + a.shape[0], dx:dx + a.shape[1]]
    return out


def edge_density(gray: np.ndarray, cfg: ProbeConfig) -> Signal:
    g = gray.astype(np.float32) / 255.0
    gx = _convolve2d(g, _KX)
    gy = _convolve2d(g, _KY)
    mag = np.sqrt(gx * gx + gy * gy)
    ratio = float((mag > 0.5).mean())   # fraction of strong-gradient pixels
    strength = min(ratio / (cfg.thresholds.edge_density_min * 2), 1.0)
    return Signal(name="edge_density", value=round(ratio, 4), unit="fraction",
                  strength=round(strength, 4), detail="sobel gradient-magnitude ratio")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/probe/test_edge_density.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/probe/signals/edge_density.py backend/tests/probe/test_edge_density.py
git commit -m "feat(probe): numpy-Sobel edge_density signal"
```

---

## Task 7: Observation derivation

**Files:**
- Create: `backend/app/probe/observe.py`
- Test: `backend/tests/probe/test_observe.py`

**Interfaces:**
- Consumes: `Signal` (Task 1), `ProbeConfig`.
- Produces: `observe_image(signals: list[Signal], cfg) -> Observation`, `observe_table(signals: list[Signal], cfg) -> Observation`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/probe/test_observe.py
from app.probe.config import ProbeConfig
from app.probe.observe import observe_image, observe_table
from app.probe.report import Signal


def _sig(name, value, strength=None):
    return Signal(name=name, value=value, strength=strength)


def test_text_covered_when_overlap_high():
    sigs = [_sig("text_overlap", 0.9, 0.9), _sig("edge_density", 0.2, 0.9), _sig("coverage", 0.5, 0.5)]
    obs = observe_image(sigs, ProbeConfig())
    assert obs.label == "text_covered_image"


def test_text_image_when_edgey_and_no_overlap():
    sigs = [_sig("text_overlap", 0.0, 0.0), _sig("edge_density", 0.22, 0.9), _sig("coverage", 0.9, 0.9)]
    obs = observe_image(sigs, ProbeConfig())
    assert obs.label == "text_image"
    assert obs.confidence > 0.6


def test_decorative_when_smooth_and_no_overlap():
    sigs = [_sig("text_overlap", 0.0, 0.0), _sig("edge_density", 0.02, 0.05), _sig("coverage", 0.95, 0.95)]
    obs = observe_image(sigs, ProbeConfig())
    assert obs.label == "decorative_image"


def test_uncertain_when_signals_disagree():
    sigs = [_sig("text_overlap", 0.0, 0.0), _sig("edge_density", 0.12, 0.4), _sig("coverage", 0.05, 0.05)]
    obs = observe_image(sigs, ProbeConfig())
    assert obs.label == "uncertain"


def test_observe_table():
    obs = observe_table([_sig("table_grid", 14.0, 0.8)], ProbeConfig())
    assert obs.label == "table_grid" and obs.confidence == 0.8
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/probe/test_observe.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write `observe.py`**

```python
# backend/app/probe/observe.py
from __future__ import annotations
from typing import Dict, List
from app.probe.config import ProbeConfig
from app.probe.report import Observation, Signal


def _by_name(signals: List[Signal]) -> Dict[str, Signal]:
    return {s.name: s for s in signals}


def _f(sig: Signal | None, default: float = 0.0) -> float:
    if sig is None or not isinstance(sig.value, (int, float)):
        return default
    return float(sig.value)


def observe_image(signals: List[Signal], cfg: ProbeConfig) -> Observation:
    s = _by_name(signals)
    overlap = _f(s.get("text_overlap"))
    edge = _f(s.get("edge_density"))
    edge_strength = s.get("edge_density").strength if s.get("edge_density") else 0.0
    coverage = _f(s.get("coverage"))
    t = cfg.thresholds

    if overlap >= t.overlap_covered:
        return Observation(label="text_covered_image", confidence=round(overlap, 3))

    matters = coverage >= t.coverage_min
    if edge >= t.edge_density_min and matters:
        conf = round(0.6 * (edge_strength or 0.0) + 0.4 * min(coverage, 1.0), 3)
        return Observation(label="text_image", confidence=conf)
    if edge < t.edge_density_min / 2 and matters:
        return Observation(label="decorative_image", confidence=round(1.0 - (edge_strength or 0.0), 3))
    return Observation(label="uncertain", confidence=0.4)


def observe_table(signals: List[Signal], cfg: ProbeConfig) -> Observation:
    s = _by_name(signals)
    grid = s.get("table_grid")
    return Observation(label="table_grid", confidence=round(grid.strength if grid else 0.5, 3))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/probe/test_observe.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/probe/observe.py backend/tests/probe/test_observe.py
git commit -m "feat(probe): region observation derivation"
```

---

## Task 8: Prober orchestrator

**Files:**
- Create: `backend/app/probe/prober.py`
- Test: `backend/tests/probe/test_prober.py`

**Interfaces:**
- Consumes: everything from Tasks 1–7.
- Produces: `Prober(backend: InspectionBackend)` with `run(pdf_path, document_id, filename, config) -> ProbeReport`. `page_type` derived: text+images→`mixed`, images only→`scanned`, text only→`text`, else `empty`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/probe/test_prober.py
import fitz
from app.probe.backends.fitz_backend import FitzBackend
from app.probe.config import ProbeConfig
from app.probe.prober import Prober


def _pdf(tmp_path):
    doc = fitz.open(); page = doc.new_page(width=612, height=792)
    page.insert_text((72, 72), "Quarterly revenue table follows " * 3, fontsize=11)
    for i in range(5):
        page.draw_line(fitz.Point(100, 300 + i * 20), fitz.Point(500, 300 + i * 20))
    p = tmp_path / "r.pdf"; doc.save(str(p)); doc.close()
    return p


def test_prober_produces_report_with_pages_and_table_region(tmp_path):
    report = Prober(FitzBackend()).run(_pdf(tmp_path), document_id="doc-1",
                                       filename="r.pdf", config=ProbeConfig())
    assert report.page_count == 1
    page = report.pages[0]
    assert page.page_type in ("text", "mixed")
    assert any(r.kind == "table" for r in page.regions)
    assert report.inspection["backend"] == "fitz"


def test_disabled_signal_is_skipped(tmp_path):
    cfg = ProbeConfig(enabled_signals=["text_layer"])
    report = Prober(FitzBackend()).run(_pdf(tmp_path), document_id="d", filename="r.pdf", config=cfg)
    names = {s.name for s in report.pages[0].signals}
    assert "font_health" not in names
    assert "char_count" in names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/probe/test_prober.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write `prober.py`**

```python
# backend/app/probe/prober.py
from __future__ import annotations
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List
from app.probe.backends.base import DocumentPrimitives, InspectionBackend, PagePrimitives
from app.probe.config import ProbeConfig
from app.probe.observe import observe_image, observe_table
from app.probe.report import PageProfile, ProbeReport, RegionFinding, Signal
from app.probe.signals import page_signals, region_signals
from app.probe.signals.edge_density import edge_density


class Prober:
    def __init__(self, backend: InspectionBackend):
        self.backend = backend

    def run(self, pdf_path: Path, document_id: str, filename: str, config: ProbeConfig) -> ProbeReport:
        t0 = time.monotonic()
        prims = self.backend.inspect(pdf_path)
        enabled = set(config.enabled_signals)
        pages = [self._page(pdf_path, prims, page, enabled, config) for page in prims.pages]
        return ProbeReport(
            document_id=document_id, filename=filename, page_count=prims.page_count,
            inspection={"backend": self.backend.name, "backend_version": self.backend.version,
                        "config_used": config.model_dump()},
            pages=pages, suggestion=None,
            duration_ms=int((time.monotonic() - t0) * 1000),
            probed_at=datetime.now(tz=timezone.utc).isoformat(),
        )

    def _page(self, pdf_path, doc: DocumentPrimitives, page: PagePrimitives, enabled, cfg) -> PageProfile:
        signals: List[Signal] = []
        if "text_layer" in enabled:
            signals += page_signals.text_layer(page, cfg)
        if "font_health" in enabled:
            signals += page_signals.font_health(page, cfg)
        if "copy_restricted" in enabled:
            signals += page_signals.copy_restricted(doc, cfg)

        regions: List[RegionFinding] = []
        for idx, image in enumerate(page.images):
            rsigs: List[Signal] = []
            if "coverage" in enabled:
                rsigs.append(region_signals.coverage(page, image, cfg))
            if "dpi" in enabled:
                rsigs.append(region_signals.dpi(page, image, cfg))
            if "text_overlap" in enabled:
                rsigs.append(region_signals.text_overlap(page, image, cfg))
            if "edge_density" in enabled:
                gray = self.backend.render_gray(pdf_path, page.index, image.bbox)
                rsigs.append(edge_density(gray, cfg))
            regions.append(RegionFinding(
                id=f"p{page.index}:img{idx}", page_index=page.index, kind="image",
                bbox=image.bbox, signals=rsigs, observation=observe_image(rsigs, cfg)))

        if "table_grid" in enabled:
            for tidx, (bbox, sig) in enumerate(region_signals.table_grid(page, cfg)):
                regions.append(RegionFinding(
                    id=f"p{page.index}:tbl{tidx}", page_index=page.index, kind="table",
                    bbox=bbox, signals=[sig], observation=observe_table([sig], cfg)))

        return PageProfile(index=page.index, page_type=self._page_type(page), signals=signals, regions=regions)

    @staticmethod
    def _page_type(page: PagePrimitives) -> str:
        has_text = len(page.text.strip()) >= 10
        has_img = len(page.images) > 0
        if has_text and has_img:
            return "mixed"
        if has_img:
            return "scanned"
        if has_text:
            return "text"
        return "empty"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/probe/test_prober.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/app/probe/prober.py backend/tests/probe/test_prober.py
git commit -m "feat(probe): prober orchestrator assembles ProbeReport"
```

---

## Task 9: Advisory recommender

**Files:**
- Create: `backend/app/probe/recommend.py`
- Modify: `backend/app/probe/prober.py` (call `recommend()` and set `suggestion`)
- Test: `backend/tests/probe/test_recommend.py`

**Interfaces:**
- Consumes: `ProbeReport` (with `suggestion=None`), `Signal`, `ParserSuggestion`.
- Produces: `recommend(report) -> ParserSuggestion` (advisory, `authoritative=False`).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/probe/test_recommend.py
from app.probe.recommend import recommend
from app.probe.report import (
    Observation, PageProfile, ProbeReport, RegionFinding, Signal, BBox,
)


def _report(pages):
    return ProbeReport(document_id="d", filename="f.pdf", page_count=len(pages),
                       inspection={}, pages=pages, suggestion=None, duration_ms=1, probed_at="t")


def test_recommends_ocr_for_text_image_page():
    region = RegionFinding(id="p0:img0", page_index=0, kind="image",
                           bbox=BBox(x0=0, y0=0, x1=1, y1=1), signals=[],
                           observation=Observation(label="text_image", confidence=0.9))
    page = PageProfile(index=0, page_type="scanned", signals=[], regions=[region])
    sug = recommend(_report([page]))
    assert sug.authoritative is False
    assert 0 in sug.ocr_pages
    assert any("OCR" in r for r in sug.rationale)


def test_recommends_fitz_tables_when_table_present():
    region = RegionFinding(id="p0:tbl0", page_index=0, kind="table",
                           bbox=BBox(x0=0, y0=0, x1=1, y1=1),
                           signals=[Signal(name="table_grid", value=9.0, strength=0.7)],
                           observation=Observation(label="table_grid", confidence=0.7))
    page = PageProfile(index=0, page_type="text",
                       signals=[Signal(name="has_text_layer", value="true", strength=1.0)],
                       regions=[region])
    sug = recommend(_report([page]))
    assert "fitz" in sug.tools and "fitz_tables" in sug.tools
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/probe/test_recommend.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write `recommend.py`**

```python
# backend/app/probe/recommend.py
from __future__ import annotations
from app.probe.report import ParserSuggestion, ProbeReport


def recommend(report: ProbeReport) -> ParserSuggestion:
    tools = ["fitz"]
    rationale = ["Base extractor fitz for the text layer."]
    ocr_pages = []
    has_table = False

    for page in report.pages:
        for region in page.regions:
            label = region.observation.label
            if label == "table_grid":
                has_table = True
            if label == "text_image" and page.index not in ocr_pages:
                ocr_pages.append(page.index)

    if has_table:
        tools.append("fitz_tables")
        rationale.append("Table grids detected -> add fitz_tables.")
    if ocr_pages:
        rationale.append(f"Text-like images on pages {ocr_pages} -> OCR suggested.")

    confidences = [r.observation.confidence for p in report.pages for r in p.regions]
    overall = round(sum(confidences) / len(confidences), 3) if confidences else 0.5

    return ParserSuggestion(authoritative=False, tools=tools, ocr_pages=sorted(ocr_pages),
                            overall_confidence=overall, rationale=rationale)
```

- [ ] **Step 4: Wire it into the prober**

In `backend/app/probe/prober.py`, replace `suggestion=None,` in `run()` with a post-assembly call:

```python
# add import at top
from app.probe.recommend import recommend
# ...in run(), build the report first as `report` with suggestion=None, then:
report.suggestion = recommend(report)
return report
```

(Restructure `run()` to assign the `ProbeReport(...)` to `report`, set `report.suggestion = recommend(report)`, then `return report`.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/probe/test_recommend.py tests/probe/test_prober.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/probe/recommend.py backend/app/probe/prober.py backend/tests/probe/test_recommend.py
git commit -m "feat(probe): advisory (non-authoritative) parser suggestion"
```

---

## Task 10: Probe service

**Files:**
- Create: `backend/app/services/probe_service.py`
- Test: `backend/tests/probe/test_probe_service.py`

**Interfaces:**
- Consumes: `DocumentService.get_file_content(document_id, user_id) -> (bytes, filename, mime)`; `Prober`, `FitzBackend`, `ProbeConfig`, `ProbeReport`.
- Produces: `ProbeService(document_service)` with `async def probe(document_id: UUID, user_id: UUID, config: ProbeConfig) -> ProbeReport`. Raises `NotFoundError`/`ValidationError` from the document layer.

- [ ] **Step 1: Write the failing test** (fakes the document service; real prober on a generated PDF)

```python
# backend/tests/probe/test_probe_service.py
import uuid
import fitz
import pytest
from app.probe.config import ProbeConfig
from app.services.probe_service import ProbeService


class _FakeDocService:
    def __init__(self, content, filename="f.pdf"):
        self._content = content; self._filename = filename
    async def get_file_content(self, document_id, user_id):
        return self._content, self._filename, "application/pdf"


def _pdf_bytes():
    doc = fitz.open(); page = doc.new_page(); page.insert_text((72, 72), "hello world text")
    data = doc.tobytes(); doc.close(); return data


@pytest.mark.asyncio
async def test_probe_service_returns_report():
    svc = ProbeService(_FakeDocService(_pdf_bytes()))
    report = await svc.probe(uuid.uuid4(), uuid.uuid4(), ProbeConfig())
    assert report.page_count == 1
    assert report.filename == "f.pdf"
    assert report.suggestion is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/probe/test_probe_service.py -v`
Expected: FAIL — `ModuleNotFoundError: app.services.probe_service`.

- [ ] **Step 3: Write `probe_service.py`**

```python
# backend/app/services/probe_service.py
from __future__ import annotations
import os
import tempfile
from pathlib import Path
from uuid import UUID
from app.probe.backends.fitz_backend import FitzBackend
from app.probe.config import ProbeConfig
from app.probe.prober import Prober
from app.probe.report import ProbeReport


class ProbeService:
    def __init__(self, document_service):
        self._documents = document_service

    async def probe(self, document_id: UUID, user_id: UUID, config: ProbeConfig) -> ProbeReport:
        content, filename, _mime = await self._documents.get_file_content(
            document_id=document_id, user_id=user_id)
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        try:
            return Prober(FitzBackend()).run(
                pdf_path=Path(tmp_path), document_id=str(document_id),
                filename=filename, config=config)
        finally:
            os.unlink(tmp_path)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/probe/test_probe_service.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/probe_service.py backend/tests/probe/test_probe_service.py
git commit -m "feat(probe): probe service (fetch file + run prober)"
```

---

## Task 11: Probe router + registration

**Files:**
- Create: `backend/app/routers/probe.py`
- Modify: `backend/app/main.py` (include the router)
- Test: `backend/tests/routers/test_probe_router.py`

**Interfaces:**
- Consumes: `ProbeService`, `ProbeConfig`, existing `get_document_service`, `get_current_active_user` dependencies.
- Produces: `POST /probe` with body `{ "document_id": str, "config": ProbeConfig | null }` -> `ProbeReport` JSON.

- [ ] **Step 1: Write the failing test** (mirror existing router tests; find how `test_probe_endpoint.py` builds an authed client + a document, and reuse that setup)

```python
# backend/tests/routers/test_probe_router.py
# NOTE: reuse the authenticated-client + uploaded-document fixtures from
# tests/routers/test_probe_endpoint.py (same auth + upload helpers).
import pytest


@pytest.mark.asyncio
async def test_probe_endpoint_returns_report(authed_client, uploaded_pdf_document):
    resp = await authed_client.post("/api/v1/probe", json={"document_id": str(uploaded_pdf_document.id)})
    assert resp.status_code == 200
    body = resp.json()
    assert body["document_id"] == str(uploaded_pdf_document.id)
    assert "pages" in body and "suggestion" in body


@pytest.mark.asyncio
async def test_probe_endpoint_404_for_unknown_document(authed_client):
    import uuid
    resp = await authed_client.post("/api/v1/probe", json={"document_id": str(uuid.uuid4())})
    assert resp.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/routers/test_probe_router.py -v`
Expected: FAIL — 404 route not found / import error.

- [ ] **Step 3: Write `probe.py` router**

```python
# backend/app/routers/probe.py
from __future__ import annotations
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from app.models.user import User
from app.probe.config import ProbeConfig
from app.probe.report import ProbeReport
from app.routers.dependencies import get_current_active_user, get_document_service
from app.services.document_service import DocumentService
from app.services.exceptions import NotFoundError, ValidationError
from app.services.probe_service import ProbeService

router = APIRouter(prefix="/probe", tags=["probe"])


class ProbeRequest(BaseModel):
    document_id: UUID
    config: Optional[ProbeConfig] = None


@router.post("", response_model=ProbeReport, summary="Probe a document for parser-config evidence")
async def probe_document(
    body: ProbeRequest,
    current_user: User = Depends(get_current_active_user),
    document_service: DocumentService = Depends(get_document_service),
) -> ProbeReport:
    service = ProbeService(document_service)
    try:
        return await service.probe(
            document_id=body.document_id, user_id=current_user.id,
            config=body.config or ProbeConfig())
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
```

> Confirm the exact import paths for `get_current_active_user` / `get_document_service` by matching `backend/app/routers/documents.py` (they may live in `app.routers.dependencies` or be defined locally). Use whatever that file imports.

- [ ] **Step 4: Register the router in `main.py`**

Find where existing routers are included (e.g. `app.include_router(documents.router, prefix="/api/v1")`) and add:

```python
from app.routers import probe
app.include_router(probe.router, prefix="/api/v1")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/routers/test_probe_router.py -v`
Expected: PASS.

- [ ] **Step 6: Full backend probe suite + commit**

```bash
cd backend && uv run python -m pytest -o "addopts=" tests/probe tests/routers/test_probe_router.py -v
git add backend/app/routers/probe.py backend/app/main.py backend/tests/routers/test_probe_router.py
git commit -m "feat(probe): POST /probe endpoint"
```

---

## Task 12: Frontend types + API client

**Files:**
- Create: `frontend/src/types/probeReport.ts`
- Create: `frontend/src/api/probeReport.ts`
- Test: `frontend/src/api/probeReport.test.ts`

**Interfaces:**
- Produces: TS types mirroring the backend contract (`ProbeReport`, `PageProfile`, `RegionFinding`, `Observation`, `Signal`, `BBox`, `ParserSuggestion`, `ProbeConfig`, `Thresholds`, `ObservationLabel`); `probeDocument(documentId, config?) -> Promise<ProbeReport>`.

- [ ] **Step 1: Write the failing test**

```ts
// frontend/src/api/probeReport.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { probeDocument } from './probeReport'
import { apiClient } from './client'

vi.mock('./client', () => ({ apiClient: { post: vi.fn() } }))

describe('probeDocument', () => {
  beforeEach(() => vi.clearAllMocks())
  it('posts document_id + config and returns the report', async () => {
    const report = { document_id: 'd1', pages: [], suggestion: null }
    ;(apiClient.post as any).mockResolvedValue({ data: report })
    const result = await probeDocument('d1')
    expect(apiClient.post).toHaveBeenCalledWith('/probe', { document_id: 'd1', config: null })
    expect(result.document_id).toBe('d1')
  })
})
```

> Match the real HTTP helper in `frontend/src/api/client.ts` (it may export `apiClient`, `api`, or named `post`). Mirror what `frontend/src/api/probe.ts` (legacy) does.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/api/probeReport.test.ts`
Expected: FAIL — cannot find `./probeReport`.

- [ ] **Step 3: Write `types/probeReport.ts`**

```ts
// frontend/src/types/probeReport.ts
export type ObservationLabel =
  | 'text_image' | 'decorative_image' | 'text_covered_image' | 'uncertain' | 'table_grid'
export type PageType = 'text' | 'scanned' | 'mixed' | 'empty'

export interface BBox { x0: number; y0: number; x1: number; y1: number }
export interface Signal {
  name: string; value: number | string; unit: string | null
  strength: number | null; detail: string | null
}
export interface Observation { label: ObservationLabel; confidence: number }
export interface RegionFinding {
  id: string; page_index: number; kind: 'image' | 'table'
  bbox: BBox; signals: Signal[]; observation: Observation
}
export interface PageProfile {
  index: number; page_type: PageType; signals: Signal[]; regions: RegionFinding[]
}
export interface ParserSuggestion {
  authoritative: boolean; tools: string[]; ocr_pages: number[]
  overall_confidence: number; rationale: string[]
}
export interface ProbeReport {
  document_id: string; filename: string | null; page_count: number
  inspection: Record<string, unknown>; pages: PageProfile[]
  suggestion: ParserSuggestion | null; duration_ms: number; probed_at: string
}
export interface Thresholds {
  min_text_chars: number; cid_ratio: number; edge_density_min: number
  coverage_min: number; table_line_min: number; overlap_covered: number
}
export interface ProbeConfig {
  enabled_signals: string[]; thresholds: Thresholds; backend: 'fitz'
}
```

- [ ] **Step 4: Write `api/probeReport.ts`**

```ts
// frontend/src/api/probeReport.ts
import { apiClient } from './client'
import type { ProbeConfig, ProbeReport } from '@/types/probeReport'

export async function probeDocument(
  documentId: string, config: ProbeConfig | null = null,
): Promise<ProbeReport> {
  const { data } = await apiClient.post('/probe', { document_id: documentId, config })
  return data as ProbeReport
}
```

- [ ] **Step 5: Run test + commit**

Run: `cd frontend && npx vitest run src/api/probeReport.test.ts` → PASS.

```bash
git add frontend/src/types/probeReport.ts frontend/src/api/probeReport.ts frontend/src/api/probeReport.test.ts
git commit -m "feat(probe): frontend types + api client"
```

---

## Task 13: useProbe hook

**Files:**
- Create: `frontend/src/hooks/useProbe.ts`
- Test: `frontend/src/hooks/useProbe.test.tsx`

**Interfaces:**
- Consumes: `probeDocument` (Task 12), `ProbeReport`, `ProbeConfig`.
- Produces: `useProbe()` returning `{ report, isLoading, error, run(documentId, config?) }`.

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/hooks/useProbe.test.tsx
import { renderHook, act, waitFor } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { useProbe } from './useProbe'
import * as api from '@/api/probeReport'

describe('useProbe', () => {
  it('runs a probe and exposes the report', async () => {
    vi.spyOn(api, 'probeDocument').mockResolvedValue({
      document_id: 'd1', filename: 'f.pdf', page_count: 1, inspection: {},
      pages: [], suggestion: null, duration_ms: 1, probed_at: 't',
    } as any)
    const { result } = renderHook(() => useProbe())
    await act(async () => { await result.current.run('d1') })
    await waitFor(() => expect(result.current.report?.document_id).toBe('d1'))
    expect(result.current.isLoading).toBe(false)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/hooks/useProbe.test.tsx`
Expected: FAIL — cannot find `./useProbe`.

- [ ] **Step 3: Write `useProbe.ts`**

```ts
// frontend/src/hooks/useProbe.ts
import { useCallback, useState } from 'react'
import { probeDocument } from '@/api/probeReport'
import type { ProbeConfig, ProbeReport } from '@/types/probeReport'

export function useProbe() {
  const [report, setReport] = useState<ProbeReport | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const run = useCallback(async (documentId: string, config: ProbeConfig | null = null) => {
    setIsLoading(true); setError(null)
    try {
      setReport(await probeDocument(documentId, config))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Probe failed')
    } finally {
      setIsLoading(false)
    }
  }, [])

  return { report, isLoading, error, run }
}
```

- [ ] **Step 4: Run test + commit**

Run: `cd frontend && npx vitest run src/hooks/useProbe.test.tsx` → PASS.

```bash
git add frontend/src/hooks/useProbe.ts frontend/src/hooks/useProbe.test.tsx
git commit -m "feat(probe): useProbe hook"
```

---

## Task 14: Region→overlay adapter + colors

**Files:**
- Create: `frontend/src/lib/probeOverlay.ts`
- Test: `frontend/src/lib/probeOverlay.test.ts`

**Interfaces:**
- Consumes: `RegionFinding`, `ObservationLabel`, and the `Block` type from `@/types/cdm` (fields used by `DocumentPdfViewer`: `id`, `page_index`, `bbox`, `role`).
- Produces: `OBSERVATION_COLORS: Record<ObservationLabel, string>`; `regionsToBlocks(regions) -> Block[]`; `regionColors(regions) -> Map<string,string>`.

- [ ] **Step 1: Write the failing test**

```ts
// frontend/src/lib/probeOverlay.test.ts
import { describe, it, expect } from 'vitest'
import { regionsToBlocks, regionColors, OBSERVATION_COLORS } from './probeOverlay'
import type { RegionFinding } from '@/types/probeReport'

const region: RegionFinding = {
  id: 'p0:img0', page_index: 0, kind: 'image',
  bbox: { x0: 0.1, y0: 0.1, x1: 0.9, y1: 0.5 }, signals: [],
  observation: { label: 'text_image', confidence: 0.88 },
}

describe('probeOverlay', () => {
  it('maps a region to a synthetic block preserving id/page/bbox', () => {
    const [b] = regionsToBlocks([region])
    expect(b.id).toBe('p0:img0'); expect(b.page_index).toBe(0)
    expect(b.bbox).toEqual(region.bbox)
  })
  it('colors regions by observation label', () => {
    const colors = regionColors([region])
    expect(colors.get('p0:img0')).toBe(OBSERVATION_COLORS.text_image)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/lib/probeOverlay.test.ts`
Expected: FAIL — cannot find `./probeOverlay`.

- [ ] **Step 3: Write `probeOverlay.ts`**

```ts
// frontend/src/lib/probeOverlay.ts
import type { Block } from '@/types/cdm'
import type { ObservationLabel, RegionFinding } from '@/types/probeReport'

export const OBSERVATION_COLORS: Record<ObservationLabel, string> = {
  text_image: 'rgb(37,99,235)',        // blue — OCR candidate
  decorative_image: 'rgb(148,163,184)', // gray — skip
  text_covered_image: 'rgb(100,116,139)', // slate — skip (text already there)
  uncertain: 'rgb(245,158,11)',        // amber
  table_grid: 'rgb(16,185,129)',       // green
}

export function regionsToBlocks(regions: RegionFinding[]): Block[] {
  return regions.map((r) => ({
    id: r.id, page_index: r.page_index, bbox: r.bbox, role: 'figure',
  } as unknown as Block))
}

export function regionColors(regions: RegionFinding[]): Map<string, string> {
  return new Map(regions.map((r) => [r.id, OBSERVATION_COLORS[r.observation.label]]))
}
```

> If TypeScript complains that `Block` requires more fields, add the minimal required ones with neutral defaults (e.g. `role: 'figure'`, `text: ''`) to satisfy the type — check `@/types/cdm`.

- [ ] **Step 4: Run test + commit**

Run: `cd frontend && npx vitest run src/lib/probeOverlay.test.ts` → PASS.

```bash
git add frontend/src/lib/probeOverlay.ts frontend/src/lib/probeOverlay.test.ts
git commit -m "feat(probe): region->overlay adapter + observation colors"
```

---

## Task 15: Region receipt + page card components

**Files:**
- Create: `frontend/src/components/probe/SignalReceipt.tsx`
- Create: `frontend/src/components/probe/RegionCard.tsx`
- Create: `frontend/src/components/probe/PageCard.tsx`
- Test: `frontend/src/components/probe/PageCard.test.tsx`

**Interfaces:**
- Consumes: `PageProfile`, `RegionFinding`, `Signal`, `OBSERVATION_COLORS`.
- Produces: `<SignalReceipt signal>`, `<RegionCard region>`, `<PageCard page selected onSelect>` (React components). `PageCard` renders `page_type`, page signal chips, and expandable region receipts.

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/components/probe/PageCard.test.tsx
import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { PageCard } from './PageCard'
import type { PageProfile } from '@/types/probeReport'

const page: PageProfile = {
  index: 3, page_type: 'scanned',
  signals: [{ name: 'font_health', value: 'clean', unit: null, strength: 1, detail: null }],
  regions: [{
    id: 'p3:img0', page_index: 3, kind: 'image',
    bbox: { x0: 0, y0: 0, x1: 1, y1: 1 },
    signals: [{ name: 'edge_density', value: 0.21, unit: 'fraction', strength: 0.85, detail: 'sobel' }],
    observation: { label: 'text_image', confidence: 0.88 },
  }],
}

describe('PageCard', () => {
  it('shows page number, type, and region observation with confidence', () => {
    render(<PageCard page={page} selected={false} onSelect={() => {}} />)
    expect(screen.getByText(/Page 4/)).toBeInTheDocument()   // index 3 -> "Page 4"
    expect(screen.getByText(/scanned/)).toBeInTheDocument()
    expect(screen.getByText(/text_image/)).toBeInTheDocument()
    expect(screen.getByText(/0\.88/)).toBeInTheDocument()
    expect(screen.getByText(/edge_density/)).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/probe/PageCard.test.tsx`
Expected: FAIL — cannot find `./PageCard`.

- [ ] **Step 3: Write `SignalReceipt.tsx`**

```tsx
// frontend/src/components/probe/SignalReceipt.tsx
import type { Signal } from '@/types/probeReport'

export function SignalReceipt({ signal }: { signal: Signal }) {
  const pct = signal.strength == null ? null : Math.round(signal.strength * 100)
  return (
    <div className="grid grid-cols-[110px_60px_1fr] items-center gap-2 text-xs py-0.5">
      <span className="text-muted-foreground">{signal.name}</span>
      <span className="font-mono tabular-nums">{String(signal.value)}{signal.unit === '%' ? '%' : ''}</span>
      <div className="h-1.5 rounded bg-muted overflow-hidden">
        {pct != null && <div className="h-full bg-blue-500" style={{ width: `${pct}%` }} />}
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Write `RegionCard.tsx`**

```tsx
// frontend/src/components/probe/RegionCard.tsx
import type { RegionFinding } from '@/types/probeReport'
import { OBSERVATION_COLORS } from '@/lib/probeOverlay'
import { SignalReceipt } from './SignalReceipt'

export function RegionCard({ region }: { region: RegionFinding }) {
  const color = OBSERVATION_COLORS[region.observation.label]
  return (
    <div className="rounded border p-2 mb-1.5">
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs font-medium">{region.id}</span>
        <span className="text-[10px] px-2 py-0.5 rounded-full text-white" style={{ background: color }}>
          {region.observation.label} · {region.observation.confidence.toFixed(2)}
        </span>
      </div>
      {region.signals.map((s) => <SignalReceipt key={s.name} signal={s} />)}
    </div>
  )
}
```

- [ ] **Step 5: Write `PageCard.tsx`**

```tsx
// frontend/src/components/probe/PageCard.tsx
import type { PageProfile } from '@/types/probeReport'
import { cn } from '@/lib/utils'
import { RegionCard } from './RegionCard'

interface Props { page: PageProfile; selected: boolean; onSelect: (index: number) => void }

export function PageCard({ page, selected, onSelect }: Props) {
  return (
    <button
      onClick={() => onSelect(page.index)}
      className={cn('w-full text-left rounded-md border p-3 mb-2 hover:bg-muted/40',
        selected && 'ring-2 ring-primary')}
    >
      <div className="flex items-center gap-2 mb-1">
        <span className="text-sm font-semibold">Page {page.index + 1}</span>
        <span className="text-xs text-muted-foreground">{page.page_type}</span>
      </div>
      <div className="flex flex-wrap gap-1 mb-2">
        {page.signals.map((s) => (
          <span key={s.name} className="text-[10px] px-1.5 rounded-full bg-muted">
            {s.name}: {String(s.value)}
          </span>
        ))}
      </div>
      {page.regions.map((r) => <RegionCard key={r.id} region={r} />)}
    </button>
  )
}
```

- [ ] **Step 6: Run test + commit**

Run: `cd frontend && npx vitest run src/components/probe/PageCard.test.tsx` → PASS.

```bash
git add frontend/src/components/probe/SignalReceipt.tsx frontend/src/components/probe/RegionCard.tsx frontend/src/components/probe/PageCard.tsx frontend/src/components/probe/PageCard.test.tsx
git commit -m "feat(probe): page card + region receipt components"
```

---

## Task 16: Suggestion panel + report container

**Files:**
- Create: `frontend/src/components/probe/SuggestionPanel.tsx`
- Create: `frontend/src/components/probe/ProbeReportView.tsx`
- Test: `frontend/src/components/probe/SuggestionPanel.test.tsx`

**Interfaces:**
- Consumes: `ProbeReport`, `ParserSuggestion`, `PageCard` (Task 15).
- Produces: `<SuggestionPanel suggestion>` (advisory, labeled "Suggested — not authoritative"), `<ProbeReportView report selectedPage onSelectPage>`.

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/components/probe/SuggestionPanel.test.tsx
import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { SuggestionPanel } from './SuggestionPanel'

describe('SuggestionPanel', () => {
  it('renders tools, rationale, and the advisory disclaimer', () => {
    render(<SuggestionPanel suggestion={{
      authoritative: false, tools: ['fitz', 'fitz_tables'], ocr_pages: [3],
      overall_confidence: 0.81, rationale: ['Base extractor fitz.', 'Text-like images on pages [3] -> OCR suggested.'],
    }} />)
    expect(screen.getByText(/Suggested/i)).toBeInTheDocument()
    expect(screen.getByText(/not authoritative/i)).toBeInTheDocument()
    expect(screen.getByText('fitz_tables')).toBeInTheDocument()
    expect(screen.getByText(/OCR suggested/)).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/probe/SuggestionPanel.test.tsx`
Expected: FAIL — cannot find `./SuggestionPanel`.

- [ ] **Step 3: Write `SuggestionPanel.tsx`**

```tsx
// frontend/src/components/probe/SuggestionPanel.tsx
import type { ParserSuggestion } from '@/types/probeReport'

export function SuggestionPanel({ suggestion }: { suggestion: ParserSuggestion }) {
  return (
    <div className="rounded-md border bg-indigo-50/60 dark:bg-indigo-950/20 p-3 mb-4">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">Suggested parse configuration</span>
        <span className="text-[10px] uppercase text-muted-foreground">Suggested — not authoritative</span>
      </div>
      <div className="flex flex-wrap gap-1 my-2">
        {suggestion.tools.map((t) => (
          <span key={t} className="text-[11px] px-2 py-0.5 rounded-full bg-indigo-600 text-white">{t}</span>
        ))}
        {suggestion.ocr_pages.length > 0 && (
          <span className="text-[11px] px-2 py-0.5 rounded-full bg-blue-600 text-white">
            OCR · pages [{suggestion.ocr_pages.join(', ')}]
          </span>
        )}
      </div>
      <ul className="text-xs text-muted-foreground space-y-0.5">
        {suggestion.rationale.map((r, i) => <li key={i}>• {r}</li>)}
      </ul>
    </div>
  )
}
```

- [ ] **Step 4: Write `ProbeReportView.tsx`**

```tsx
// frontend/src/components/probe/ProbeReportView.tsx
import type { ProbeReport } from '@/types/probeReport'
import { PageCard } from './PageCard'
import { SuggestionPanel } from './SuggestionPanel'

interface Props {
  report: ProbeReport
  selectedPage: number | null
  onSelectPage: (index: number) => void
}

export function ProbeReportView({ report, selectedPage, onSelectPage }: Props) {
  return (
    <div className="p-4 overflow-y-auto h-full">
      {report.suggestion && <SuggestionPanel suggestion={report.suggestion} />}
      {report.pages.map((page) => (
        <PageCard key={page.index} page={page}
          selected={selectedPage === page.index} onSelect={onSelectPage} />
      ))}
    </div>
  )
}
```

- [ ] **Step 5: Run test + commit**

Run: `cd frontend && npx vitest run src/components/probe/SuggestionPanel.test.tsx` → PASS.

```bash
git add frontend/src/components/probe/SuggestionPanel.tsx frontend/src/components/probe/ProbeReportView.tsx frontend/src/components/probe/SuggestionPanel.test.tsx
git commit -m "feat(probe): advisory suggestion panel + report view"
```

---

## Task 17: Signals popover (config)

**Files:**
- Create: `frontend/src/components/probe/SignalsPopover.tsx`
- Test: `frontend/src/components/probe/SignalsPopover.test.tsx`

**Interfaces:**
- Consumes: `ProbeConfig`, `Thresholds`, shadcn `Popover`, `Switch`, `Slider`/`Input`, `Button`.
- Produces: `<SignalsPopover config onChange onRerun>` — toggles signals, tunes `edge_density_min` / `coverage_min` / `min_text_chars`, emits an updated `ProbeConfig`, and triggers a re-probe.

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/components/probe/SignalsPopover.test.tsx
import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { SignalsPopover } from './SignalsPopover'
import { DEFAULT_PROBE_CONFIG } from './SignalsPopover'

describe('SignalsPopover', () => {
  it('toggling a signal emits an updated config', () => {
    const onChange = vi.fn()
    render(<SignalsPopover config={DEFAULT_PROBE_CONFIG} onChange={onChange} onRerun={() => {}} />)
    fireEvent.click(screen.getByText('Signals'))            // open popover
    fireEvent.click(screen.getByLabelText('edge_density'))  // toggle off
    expect(onChange).toHaveBeenCalled()
    const cfg = onChange.mock.calls.at(-1)![0]
    expect(cfg.enabled_signals).not.toContain('edge_density')
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/probe/SignalsPopover.test.tsx`
Expected: FAIL — cannot find `./SignalsPopover`.

- [ ] **Step 3: Write `SignalsPopover.tsx`** (uses shadcn `popover`, `switch`, `label`, `button`; add any missing shadcn primitive with `npx shadcn@latest add switch` etc.)

```tsx
// frontend/src/components/probe/SignalsPopover.tsx
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import type { ProbeConfig } from '@/types/probeReport'
import { SlidersHorizontal } from 'lucide-react'

const ALL_SIGNALS = [
  'text_layer', 'font_health', 'copy_restricted',
  'coverage', 'dpi', 'text_overlap', 'table_grid', 'edge_density',
]

export const DEFAULT_PROBE_CONFIG: ProbeConfig = {
  enabled_signals: [...ALL_SIGNALS],
  thresholds: { min_text_chars: 10, cid_ratio: 0.3, edge_density_min: 0.15,
    coverage_min: 0.10, table_line_min: 3, overlap_covered: 0.6 },
  backend: 'fitz',
}

interface Props { config: ProbeConfig; onChange: (c: ProbeConfig) => void; onRerun: () => void }

export function SignalsPopover({ config, onChange, onRerun }: Props) {
  const toggle = (name: string) => {
    const on = config.enabled_signals.includes(name)
    onChange({ ...config,
      enabled_signals: on ? config.enabled_signals.filter((s) => s !== name)
                          : [...config.enabled_signals, name] })
  }
  const setThreshold = (key: keyof ProbeConfig['thresholds'], value: number) =>
    onChange({ ...config, thresholds: { ...config.thresholds, [key]: value } })

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="outline" size="sm"><SlidersHorizontal className="h-4 w-4 mr-1.5" />Signals</Button>
      </PopoverTrigger>
      <PopoverContent className="w-72 space-y-3">
        <div className="space-y-1.5">
          {ALL_SIGNALS.map((name) => (
            <div key={name} className="flex items-center justify-between">
              <Label htmlFor={name} className="text-xs">{name}</Label>
              <Switch id={name} aria-label={name}
                checked={config.enabled_signals.includes(name)} onCheckedChange={() => toggle(name)} />
            </div>
          ))}
        </div>
        <div className="space-y-2 border-t pt-2">
          <label className="text-xs flex items-center justify-between">edge_density_min
            <Input type="number" step="0.01" className="h-7 w-20"
              value={config.thresholds.edge_density_min}
              onChange={(e) => setThreshold('edge_density_min', parseFloat(e.target.value))} /></label>
          <label className="text-xs flex items-center justify-between">coverage_min
            <Input type="number" step="0.05" className="h-7 w-20"
              value={config.thresholds.coverage_min}
              onChange={(e) => setThreshold('coverage_min', parseFloat(e.target.value))} /></label>
          <label className="text-xs flex items-center justify-between">min_text_chars
            <Input type="number" className="h-7 w-20"
              value={config.thresholds.min_text_chars}
              onChange={(e) => setThreshold('min_text_chars', parseInt(e.target.value, 10))} /></label>
        </div>
        <Button size="sm" className="w-full" onClick={onRerun}>Re-probe</Button>
      </PopoverContent>
    </Popover>
  )
}
```

- [ ] **Step 4: Run test + commit**

Run: `cd frontend && npx vitest run src/components/probe/SignalsPopover.test.tsx` → PASS.

```bash
git add frontend/src/components/probe/SignalsPopover.tsx frontend/src/components/probe/SignalsPopover.test.tsx
git commit -m "feat(probe): signals config popover"
```

---

## Task 18: Probe page + route + nav

**Files:**
- Create: `frontend/src/pages/ProbePage.tsx`
- Modify: `frontend/src/App.tsx` (add `probe` route + lazy/eager import)
- Modify: `frontend/src/config/navigation.ts` (add Probe nav item)
- Test: `frontend/src/pages/ProbePage.test.tsx`

**Interfaces:**
- Consumes: `DocumentPickerPanel`, `DocumentPdfViewer`, `useProbe`, `useDocuments`, `useFolders`, `useProject`, `ProbeReportView`, `SignalsPopover` + `DEFAULT_PROBE_CONFIG`, `regionsToBlocks`, `regionColors`, `DocumentUploadDialog`.
- Produces: `ProbePage` (Layout 1: header with picker toggle + `SignalsPopover`; two panes — `DocumentPdfViewer` left, `ProbeReportView` right). Route `path: 'probe'`.

- [ ] **Step 1: Write the failing test** (smoke: renders picker empty-state before a document is chosen)

```tsx
// frontend/src/pages/ProbePage.test.tsx
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi } from 'vitest'
import ProbePage from './ProbePage'

vi.mock('@/contexts/ProjectContext', () => ({ useProject: () => ({ currentProject: { id: 'p1', name: 'Proj' } }) }))
vi.mock('@/hooks/useDocuments', () => ({ useDocuments: () => ({ documents: [], isLoading: false, uploadDocument: vi.fn() }) }))
vi.mock('@/hooks/useFolders', () => ({ useFolders: () => ({ folders: [] }) }))

describe('ProbePage', () => {
  it('shows the empty state prompting document selection', () => {
    render(<MemoryRouter><ProbePage /></MemoryRouter>)
    expect(screen.getByText(/Select a document/i)).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/pages/ProbePage.test.tsx`
Expected: FAIL — cannot find `./ProbePage`.

- [ ] **Step 3: Write `ProbePage.tsx`** (model on `ExtractionPage.tsx`: header + `w-72` picker rail + `flex-1` content; here the content is two panes)

```tsx
// frontend/src/pages/ProbePage.tsx
import { useState } from 'react'
import { useProject } from '@/contexts/ProjectContext'
import { useDocuments } from '@/hooks/useDocuments'
import { useFolders } from '@/hooks/useFolders'
import { useProbe } from '@/hooks/useProbe'
import { DocumentPickerPanel } from '@/components/shared/DocumentPickerPanel'
import { DocumentPdfViewer } from '@/components/parse-runs/DocumentPdfViewer'
import { ProbeReportView } from '@/components/probe/ProbeReportView'
import { SignalsPopover, DEFAULT_PROBE_CONFIG } from '@/components/probe/SignalsPopover'
import { regionsToBlocks, regionColors } from '@/lib/probeOverlay'
import type { ProbeConfig } from '@/types/probeReport'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { FileSearch } from 'lucide-react'

export default function ProbePage(): JSX.Element {
  const { currentProject } = useProject()
  const projectId = currentProject?.id ?? null
  const { documents, isLoading } = useDocuments(projectId)
  const { folders } = useFolders(projectId)
  const { report, isLoading: probing, error, run } = useProbe()

  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(null)
  const [selectedPage, setSelectedPage] = useState<number | null>(null)
  const [config, setConfig] = useState<ProbeConfig>(DEFAULT_PROBE_CONFIG)

  const selectDoc = (id: string) => { setSelectedDocumentId(id); run(id, config) }

  if (!currentProject) {
    return <div className="p-6"><Alert><AlertDescription>Loading project...</AlertDescription></Alert></div>
  }

  const regions = report?.pages.flatMap((p) => p.regions) ?? []
  const blocks = regionsToBlocks(regions)
  const colors = regionColors(regions)

  return (
    <div className="-m-6 flex flex-col h-[calc(100vh-3.5rem)]">
      <div className="flex items-center justify-between px-6 py-3 border-b shrink-0">
        <div>
          <h1 className="text-lg font-semibold">Probe</h1>
          <p className="text-xs text-muted-foreground">{currentProject.name}</p>
        </div>
        {selectedDocumentId && (
          <SignalsPopover config={config} onChange={setConfig}
            onRerun={() => selectedDocumentId && run(selectedDocumentId, config)} />
        )}
      </div>

      <div className="flex flex-1 min-h-0">
        <div className="w-64 border-r shrink-0 flex flex-col">
          <DocumentPickerPanel documents={documents} folders={folders} isLoading={isLoading}
            selectedDocumentId={selectedDocumentId} onSelect={selectDoc} onUploadClick={() => {}} />
        </div>

        {!selectedDocumentId ? (
          <div className="flex-1 flex flex-col items-center justify-center text-center">
            <FileSearch className="h-12 w-12 text-muted-foreground/40 mb-4" />
            <h2 className="text-lg font-medium text-muted-foreground">Select a document to probe</h2>
          </div>
        ) : (
          <div className="flex flex-1 min-h-0">
            <div className="flex-1 min-w-0 border-r">
              <DocumentPdfViewer documentId={selectedDocumentId} blocks={blocks}
                selectedBlockId={null} onBlockSelect={() => {}} blockColors={colors}
                selectedPageIndex={selectedPage} />
            </div>
            <div className="w-[420px] shrink-0 overflow-hidden">
              {error && <div className="p-4 text-sm text-destructive">{error}</div>}
              {probing && <div className="p-4 text-sm text-muted-foreground">Probing…</div>}
              {report && <ProbeReportView report={report} selectedPage={selectedPage} onSelectPage={setSelectedPage} />}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Add the route in `App.tsx`**

Add the import near the other page imports:
```tsx
import ProbePage from './pages/ProbePage'
```
Add the route object next to the `extract` route (around line 109):
```tsx
{
  path: 'probe',
  element: <ProbePage />,
  handle: { breadcrumb: 'Probe' },
},
```

- [ ] **Step 5: Add the nav item in `config/navigation.ts`**

Import `ScanSearch` from `lucide-react` and add after the `Parse` entry:
```ts
{ label: 'Probe', href: '/probe', icon: ScanSearch, activeColor: 'border-l-sky-500' },
```

- [ ] **Step 6: Run test, lint, build**

Run:
```bash
cd frontend && npx vitest run src/pages/ProbePage.test.tsx
cd frontend && npm run lint
cd frontend && npm run build
```
Expected: test PASS; lint clean; build succeeds.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/ProbePage.tsx frontend/src/pages/ProbePage.test.tsx frontend/src/App.tsx frontend/src/config/navigation.ts
git commit -m "feat(probe): standalone Probe page + route + nav item"
```

---

## Task 19 (PR 2): Remove legacy backend probe

> **Do not start until PR 1 is reviewed/merged.** Open PR 2 from the same branch (or a follow-up branch off it).

**Files:**
- Delete: `backend/app/cdm/adapters/custom_pipeline/probe.py`
- Delete: `backend/tests/cdm/adapters/custom_pipeline/test_probe.py`, `backend/tests/routers/test_probe_endpoint.py`
- Modify: `backend/app/routers/documents.py` (remove the `probe_document` endpoint + `DocumentProbe` import + now-unused `tempfile`/`os`/`Path` imports if unused elsewhere)

- [ ] **Step 1: Delete legacy files**

```bash
git rm backend/app/cdm/adapters/custom_pipeline/probe.py \
       backend/tests/cdm/adapters/custom_pipeline/test_probe.py \
       backend/tests/routers/test_probe_endpoint.py
```

- [ ] **Step 2: Remove the endpoint from `documents.py`**

Delete the `@router.post("/{document_id}/probe" ...)` block (lines ~623–655) and the `from app.cdm.adapters.custom_pipeline.probe import DocumentProbe` import. Remove `tempfile`/`os` imports only if no longer referenced in the file.

- [ ] **Step 3: Verify nothing else imports the legacy probe**

Run: `cd backend && grep -rn "custom_pipeline.probe\|DocumentProbe" app tests`
Expected: no results.

- [ ] **Step 4: Run the backend suite**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/probe tests/routers -v`
Expected: PASS (no references to the removed endpoint).

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore(probe): remove legacy custom_pipeline probe + endpoint"
```

---

## Task 20 (PR 2): Remove legacy frontend probe panel

**Files:**
- Delete: `frontend/src/components/documents/DocumentProbePanel.tsx`, `frontend/src/hooks/useDocumentProbe.ts`, `frontend/src/api/probe.ts`, `frontend/src/types/probe.ts`
- Modify: whichever page/component mounts `DocumentProbePanel` (find with grep) to remove its usage.

- [ ] **Step 1: Find usages**

Run: `cd frontend && grep -rn "DocumentProbePanel\|useDocumentProbe\|api/probe'\|types/probe'" src`
Record every file that references them.

- [ ] **Step 2: Remove the mount(s)**

In each referencing file, delete the `<DocumentProbePanel ... />` usage and its import. (These are display-only; no replacement needed — the standalone `/probe` page supersedes it.)

- [ ] **Step 3: Delete the legacy files**

```bash
git rm frontend/src/components/documents/DocumentProbePanel.tsx \
       frontend/src/hooks/useDocumentProbe.ts \
       frontend/src/api/probe.ts \
       frontend/src/types/probe.ts
# also remove DocumentProbePanel.test.tsx / useDocumentProbe.test if present
```

- [ ] **Step 4: Verify, lint, build**

Run:
```bash
cd frontend && grep -rn "DocumentProbePanel\|useDocumentProbe" src   # expect no results
cd frontend && npm run lint && npm run build
```
Expected: no dangling references; lint clean; build succeeds.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore(probe): remove legacy DocumentProbePanel + api/types/hook"
```

---

## Self-Review Notes (author)

- **Spec coverage:** §4 contract → Task 1; §5 signals → Tasks 3–6; §6 confidence → Tasks 4/6/7 (strength + observation); §7 backend/package/endpoint → Tasks 2/8/10/11; advisory recommend (§2) → Task 9; §8 frontend (nav, Layout 1, picker, PdfViewer adapter, page cards, receipts, popover) → Tasks 12–18; §9 legacy two-PR → Tasks 19–20; `copy_restricted` (kept in) → Task 3. Pluggable-method seam (P4) present via `InspectionBackend` (Task 2). No-persistence honored (no models/migrations).
- **Deferred correctly (non-goals):** OCR execution (WS2), auto-routing, pdfplumber/VLM backends, persistence.
- **Known integration points to confirm during execution (flagged inline):** exact HTTP client export in `api/client.ts`; exact `Block` required fields in `@/types/cdm`; dependency-injection import paths for `get_document_service`/`get_current_active_user`; the authed-client/upload fixtures in `tests/routers/test_probe_endpoint.py`.
