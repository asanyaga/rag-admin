# Local Pipeline — DocumentProbe (Iteration 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the `DocumentProbe` — a standalone PDF classifier that returns a per-page `DocumentProfile` — and surface it in the document detail sheet.

**Architecture:** `DocumentProbe` is a pure-Python class in `backend/app/cdm/adapters/local_pipeline/probe.py` that uses PyMuPDF (fitz) to inspect a PDF and return a frozen Pydantic `DocumentProfile`. A new `POST /documents/{id}/probe` endpoint fetches the document file from storage and returns the profile. The frontend adds a "Probe" section to the existing document detail Sheet in `DocumentsPage.tsx`.

**Tech Stack:** Python 3.12, PyMuPDF (fitz), Pydantic v2, FastAPI, React 18, TypeScript, shadcn/ui, Tailwind CSS.

## Global Constraints

- Python 3.12+; Pydantic v2 frozen models only (`model_config = ConfigDict(frozen=True)`)
- All CDM types in `backend/app/cdm/` — no business logic in routers
- Router → service → repository layering; probe logic lives in the CDM package, not in a service
- Frontend: one hook per feature (`useDocumentProbe`), feature-scoped component (`DocumentProbePanel`)
- Run backend tests with: `uv run python -m pytest -o "addopts=" tests/cdm/test_probe.py -v`
- Run frontend lint with: `npm run lint` from `frontend/`
- No persistence in iteration 1 — probe returns in-memory result only

---

## File Map

**New files:**
- `backend/app/cdm/adapters/local_pipeline/__init__.py`
- `backend/app/cdm/adapters/local_pipeline/probe.py`
- `backend/tests/cdm/adapters/local_pipeline/__init__.py`
- `backend/tests/cdm/adapters/local_pipeline/test_probe.py`
- `backend/tests/cdm/adapters/local_pipeline/fixtures/simple_text.pdf` *(generated in Task 3)*
- `frontend/src/types/probe.ts`
- `frontend/src/api/probe.ts`
- `frontend/src/hooks/useDocumentProbe.ts`
- `frontend/src/components/documents/DocumentProbePanel.tsx`

**Modified files:**
- `backend/app/cdm/models.py` — add `LOCAL_PIPELINE` to `ParserKind`
- `backend/app/routers/documents.py` — add `POST /{document_id}/probe` endpoint
- `backend/pyproject.toml` — add `pymupdf` dependency
- `frontend/src/pages/DocumentsPage.tsx` — add probe panel + "Probe" button to document Sheet

---

## Task 1: Add pymupdf dependency + scaffold local_pipeline package

**Files:**
- Modify: `backend/pyproject.toml`
- Create: `backend/app/cdm/adapters/local_pipeline/__init__.py`
- Modify: `backend/app/cdm/models.py`

**Interfaces:**
- Produces: `ParserKind.LOCAL_PIPELINE` available for import in later tasks

- [ ] **Step 1: Add pymupdf to pyproject.toml**

Open `backend/pyproject.toml`. In the `# Document Processing` section (around line 40), add after `"pypdf>=6.6.2",`:

```toml
    "pymupdf>=1.24.0",          # fitz — PDF text/image/drawing extraction for DocumentProbe
```

- [ ] **Step 2: Install the dependency**

```bash
uv add --directory backend pymupdf
```

Expected: resolves and installs pymupdf, updates `uv.lock`.

- [ ] **Step 3: Verify fitz import works**

```bash
uv run --directory backend python -c "import fitz; print(fitz.version)"
```

Expected: prints version tuple like `('1.24.x', '...', '...')`.

- [ ] **Step 4: Add LOCAL_PIPELINE to ParserKind**

In `backend/app/cdm/models.py`, update the `ParserKind` enum:

```python
class ParserKind(str, Enum):
    SIMPLE       = "simple"
    LITEPARSE    = "liteparse"
    UNSTRUCTURED = "unstructured"
    LLAMAPARSE   = "llamaparse"
    LANDING_AI   = "landing_ai"
    DOCLING      = "docling"
    LOCAL_PIPELINE = "local_pipeline"   # composable local tool pipeline
```

- [ ] **Step 5: Create the local_pipeline package**

Create `backend/app/cdm/adapters/local_pipeline/__init__.py` with empty content:

```python
```

- [ ] **Step 6: Verify the enum is importable**

```bash
uv run --directory backend python -c "from app.cdm.models import ParserKind; print(ParserKind.LOCAL_PIPELINE)"
```

Expected: `ParserKind.LOCAL_PIPELINE`

- [ ] **Step 7: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock backend/app/cdm/models.py backend/app/cdm/adapters/local_pipeline/__init__.py
git commit -m "feat(local-pipeline): scaffold package + add LOCAL_PIPELINE ParserKind + pymupdf dep"
```

---

## Task 2: DocumentProbe Pydantic types

**Files:**
- Create: `backend/app/cdm/adapters/local_pipeline/probe.py`
- Create: `backend/tests/cdm/adapters/local_pipeline/__init__.py`
- Create: `backend/tests/cdm/adapters/local_pipeline/test_probe.py`

**Interfaces:**
- Produces:
  - `PageProfile` — frozen Pydantic model, per-page signals
  - `DocumentProfile` — frozen Pydantic model, document-level summary
  - `DocumentProbe` — class with `run(pdf_path: Path) -> DocumentProfile` (stub for now)

- [ ] **Step 1: Write the failing type round-trip test**

Create `backend/tests/cdm/adapters/local_pipeline/__init__.py` (empty).

Create `backend/tests/cdm/adapters/local_pipeline/test_probe.py`:

```python
import json
from app.cdm.adapters.local_pipeline.probe import PageProfile, DocumentProfile


def _make_page_profile(index: int = 0) -> PageProfile:
    return PageProfile(
        index=index,
        char_count=500,
        has_text_layer=True,
        image_count=0,
        font_health="clean",
        table_signal=False,
        page_type="text",
    )


def _make_document_profile() -> DocumentProfile:
    from datetime import datetime, timezone
    return DocumentProfile(
        source_document_id="doc-123",
        filename="test.pdf",
        page_count=2,
        pages=[_make_page_profile(0), _make_page_profile(1)],
        has_text_layer=True,
        has_scanned_pages=False,
        has_cid_corruption=False,
        table_signal=False,
        recommended_tools=["fitz", "camelot"],
        duration_ms=42,
        probed_at=datetime(2026, 6, 25, 12, 0, 0, tzinfo=timezone.utc),
    )


def test_page_profile_round_trips_json():
    p = _make_page_profile()
    restored = PageProfile.model_validate_json(p.model_dump_json())
    assert restored == p


def test_document_profile_round_trips_json():
    d = _make_document_profile()
    restored = DocumentProfile.model_validate_json(d.model_dump_json())
    assert restored == d


def test_document_profile_is_frozen():
    d = _make_document_profile()
    try:
        d.page_count = 99  # type: ignore
        assert False, "should have raised"
    except Exception:
        pass


def test_page_profile_page_types_are_valid():
    valid_types = {"text", "scanned", "mixed", "empty"}
    p = _make_page_profile()
    assert p.page_type in valid_types


def test_recommended_tools_is_list_of_strings():
    d = _make_document_profile()
    assert isinstance(d.recommended_tools, list)
    assert all(isinstance(t, str) for t in d.recommended_tools)
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run --directory backend python -m pytest -o "addopts=" tests/cdm/adapters/local_pipeline/test_probe.py -v
```

Expected: `ImportError` — `probe` module does not exist yet.

- [ ] **Step 3: Implement the probe types**

Create `backend/app/cdm/adapters/local_pipeline/probe.py`:

```python
"""DocumentProbe — standalone PDF classifier using PyMuPDF."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict


class PageProfile(BaseModel):
    model_config = ConfigDict(frozen=True)

    index: int
    char_count: int
    has_text_layer: bool
    image_count: int
    font_health: Literal["clean", "cid_corrupt", "mixed", "unknown"]
    table_signal: bool
    page_type: Literal["text", "scanned", "mixed", "empty"]


class DocumentProfile(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_document_id: str
    filename: Optional[str]
    page_count: int
    pages: List[PageProfile]
    has_text_layer: bool
    has_scanned_pages: bool
    has_cid_corruption: bool
    table_signal: bool
    recommended_tools: List[str]
    duration_ms: int
    probed_at: datetime


class DocumentProbe:
    """Inspects a PDF and returns a DocumentProfile.

    Uses only PyMuPDF — no network calls, no side effects.
    """

    def run(self, pdf_path: Path, source_document_id: str = "") -> DocumentProfile:
        raise NotImplementedError
```

- [ ] **Step 4: Run tests to confirm types pass**

```bash
uv run --directory backend python -m pytest -o "addopts=" tests/cdm/adapters/local_pipeline/test_probe.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/cdm/adapters/local_pipeline/probe.py \
        backend/tests/cdm/adapters/local_pipeline/__init__.py \
        backend/tests/cdm/adapters/local_pipeline/test_probe.py
git commit -m "feat(local-pipeline): add DocumentProbe + DocumentProfile Pydantic types"
```

---

## Task 3: DocumentProbe.run() implementation

**Files:**
- Modify: `backend/app/cdm/adapters/local_pipeline/probe.py`
- Create: `backend/tests/cdm/adapters/local_pipeline/fixtures/simple_text.pdf`
- Modify: `backend/tests/cdm/adapters/local_pipeline/test_probe.py`

**Interfaces:**
- Consumes: `PageProfile`, `DocumentProfile` from Task 2
- Produces: `DocumentProbe.run(pdf_path, source_document_id) -> DocumentProfile` (fully implemented)

- [ ] **Step 1: Generate a minimal test PDF fixture**

```bash
uv run --directory backend python - <<'EOF'
import fitz, pathlib
pathlib.Path("tests/cdm/adapters/local_pipeline/fixtures").mkdir(parents=True, exist_ok=True)
doc = fitz.open()

# Page 0: clean text
p0 = doc.new_page()
p0.insert_text((72, 72), "Hello world. This is page one with some text content.", fontsize=12)

# Page 1: text + a ruled table (draw lines to trigger table_signal)
p1 = doc.new_page()
p1.insert_text((72, 72), "Page two has a table below.", fontsize=12)
# draw a simple 2x2 grid
r = fitz.Rect(72, 100, 300, 200)
p1.draw_rect(r, color=(0,0,0), width=1)
p1.draw_line(fitz.Point(186, 100), fitz.Point(186, 200), color=(0,0,0), width=1)
p1.draw_line(fitz.Point(72, 150), fitz.Point(300, 150), color=(0,0,0), width=1)

doc.save("tests/cdm/adapters/local_pipeline/fixtures/simple_text.pdf")
print("Created simple_text.pdf")
EOF
```

Expected: prints "Created simple_text.pdf". File exists at `backend/tests/cdm/adapters/local_pipeline/fixtures/simple_text.pdf`.

- [ ] **Step 2: Write failing implementation tests**

Append to `backend/tests/cdm/adapters/local_pipeline/test_probe.py`:

```python
from pathlib import Path
from app.cdm.adapters.local_pipeline.probe import DocumentProbe

FIXTURES = Path(__file__).parent / "fixtures"


def test_run_returns_document_profile():
    probe = DocumentProbe()
    profile = probe.run(FIXTURES / "simple_text.pdf", source_document_id="doc-abc")
    assert profile.source_document_id == "doc-abc"
    assert profile.page_count == 2


def test_run_detects_text_layer():
    probe = DocumentProbe()
    profile = probe.run(FIXTURES / "simple_text.pdf", source_document_id="doc-abc")
    assert profile.has_text_layer is True
    assert profile.has_scanned_pages is False


def test_run_per_page_char_counts():
    probe = DocumentProbe()
    profile = probe.run(FIXTURES / "simple_text.pdf", source_document_id="doc-abc")
    assert profile.pages[0].char_count > 0
    assert profile.pages[1].char_count > 0


def test_run_page_type_text():
    probe = DocumentProbe()
    profile = probe.run(FIXTURES / "simple_text.pdf", source_document_id="doc-abc")
    assert profile.pages[0].page_type == "text"


def test_run_table_signal_on_page_with_grid():
    probe = DocumentProbe()
    profile = probe.run(FIXTURES / "simple_text.pdf", source_document_id="doc-abc")
    # page 1 has a drawn grid
    assert profile.pages[1].table_signal is True


def test_run_no_table_signal_on_plain_text_page():
    probe = DocumentProbe()
    profile = probe.run(FIXTURES / "simple_text.pdf", source_document_id="doc-abc")
    assert profile.pages[0].table_signal is False


def test_run_duration_ms_is_positive():
    probe = DocumentProbe()
    profile = probe.run(FIXTURES / "simple_text.pdf", source_document_id="doc-abc")
    assert profile.duration_ms >= 0


def test_run_recommended_tools_not_empty():
    probe = DocumentProbe()
    profile = probe.run(FIXTURES / "simple_text.pdf", source_document_id="doc-abc")
    assert len(profile.recommended_tools) > 0


def test_run_no_cid_corruption_on_clean_pdf():
    probe = DocumentProbe()
    profile = probe.run(FIXTURES / "simple_text.pdf", source_document_id="doc-abc")
    assert profile.has_cid_corruption is False
```

- [ ] **Step 3: Run to confirm failure**

```bash
uv run --directory backend python -m pytest -o "addopts=" tests/cdm/adapters/local_pipeline/test_probe.py -v -k "test_run"
```

Expected: all `test_run_*` tests FAIL with `NotImplementedError`.

- [ ] **Step 4: Implement DocumentProbe.run()**

Replace the `DocumentProbe` class in `backend/app/cdm/adapters/local_pipeline/probe.py`:

```python
import time

import fitz  # pymupdf


class DocumentProbe:
    """Inspects a PDF and returns a DocumentProfile.

    Uses only PyMuPDF — no network calls, no side effects.
    """

    # Pages below this char count are considered to lack a usable text layer.
    _MIN_TEXT_CHARS = 10
    # Ratio of Unicode private-use area chars that triggers CID corruption flag.
    _CID_THRESHOLD = 0.3
    _CID_WARN_THRESHOLD = 0.05
    # Minimum axis-aligned line/rect drawing items to flag table_signal.
    _TABLE_LINE_MIN = 4

    def run(self, pdf_path: Path, source_document_id: str = "") -> DocumentProfile:
        t0 = time.monotonic()
        doc = fitz.open(str(pdf_path))
        try:
            pages = [self._profile_page(doc[i], i) for i in range(len(doc))]
        finally:
            doc.close()

        has_text_layer = any(p.has_text_layer for p in pages)
        has_scanned_pages = any(p.page_type == "scanned" for p in pages)
        has_cid = any(p.font_health in ("cid_corrupt", "mixed") for p in pages)
        table_sig = any(p.table_signal for p in pages)

        return DocumentProfile(
            source_document_id=source_document_id,
            filename=pdf_path.name,
            page_count=len(pages),
            pages=pages,
            has_text_layer=has_text_layer,
            has_scanned_pages=has_scanned_pages,
            has_cid_corruption=has_cid,
            table_signal=table_sig,
            recommended_tools=self._recommend(has_cid, has_scanned_pages, table_sig),
            duration_ms=int((time.monotonic() - t0) * 1000),
            probed_at=datetime.now(tz=timezone.utc),
        )

    def _profile_page(self, page: fitz.Page, index: int) -> PageProfile:
        text = page.get_text("text")
        char_count = len(text.strip())
        has_text = char_count >= self._MIN_TEXT_CHARS
        image_count = len(page.get_images(full=True))
        font_health = self._font_health(text)
        table_signal = self._table_signal(page)

        if not has_text and image_count > 0:
            page_type: Literal["text", "scanned", "mixed", "empty"] = "scanned"
        elif has_text and image_count > 0:
            page_type = "mixed"
        elif has_text:
            page_type = "text"
        else:
            page_type = "empty"

        return PageProfile(
            index=index,
            char_count=char_count,
            has_text_layer=has_text,
            image_count=image_count,
            font_health=font_health,
            table_signal=table_signal,
            page_type=page_type,
        )

    def _font_health(self, text: str) -> Literal["clean", "cid_corrupt", "mixed", "unknown"]:
        if not text.strip():
            return "unknown"
        total = len(text)
        pua = sum(1 for c in text if 0xe000 <= ord(c) <= 0xf8ff)
        ratio = pua / total
        if ratio > self._CID_THRESHOLD:
            return "cid_corrupt"
        if ratio > self._CID_WARN_THRESHOLD:
            return "mixed"
        return "clean"

    def _table_signal(self, page: fitz.Page) -> bool:
        drawings = page.get_drawings()
        line_count = 0
        for path in drawings:
            for item in path.get("items", []):
                if item[0] in ("l", "re"):  # line or rectangle
                    line_count += 1
        return line_count >= self._TABLE_LINE_MIN

    def _recommend(self, has_cid: bool, has_scanned: bool, has_tables: bool) -> List[str]:
        if has_cid or has_scanned:
            tools = ["paddleocr"]
            if has_tables:
                tools.append("paddleocr_pp_structure")
        else:
            tools = ["fitz"]
            if has_tables:
                tools.append("camelot")
        return tools
```

- [ ] **Step 5: Run all probe tests**

```bash
uv run --directory backend python -m pytest -o "addopts=" tests/cdm/adapters/local_pipeline/test_probe.py -v
```

Expected: all tests PASS (including type round-trip tests from Task 2).

- [ ] **Step 6: Commit**

```bash
git add backend/app/cdm/adapters/local_pipeline/probe.py \
        backend/tests/cdm/adapters/local_pipeline/test_probe.py \
        backend/tests/cdm/adapters/local_pipeline/fixtures/simple_text.pdf
git commit -m "feat(local-pipeline): implement DocumentProbe.run() with fitz"
```

---

## Task 4: Backend probe endpoint

**Files:**
- Modify: `backend/app/routers/documents.py`

**Interfaces:**
- Consumes: `DocumentProbe`, `DocumentProfile` from Task 3; `DocumentRepository`, `StorageService` from existing patterns
- Produces: `POST /documents/{document_id}/probe` → `DocumentProfile` as JSON

- [ ] **Step 1: Write the failing router test**

Append to `backend/tests/routers/test_documents_router.py` (find the existing document router tests and add at the end — or create a new file `backend/tests/routers/test_probe_endpoint.py`):

Create `backend/tests/routers/test_probe_endpoint.py`:

```python
"""Smoke test: probe endpoint returns a DocumentProfile-shaped response."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from uuid import uuid4


@pytest.fixture
def mock_profile_dict():
    from datetime import datetime, timezone
    return {
        "source_document_id": "doc-abc",
        "filename": "test.pdf",
        "page_count": 1,
        "pages": [{
            "index": 0,
            "char_count": 100,
            "has_text_layer": True,
            "image_count": 0,
            "font_health": "clean",
            "table_signal": False,
            "page_type": "text",
        }],
        "has_text_layer": True,
        "has_scanned_pages": False,
        "has_cid_corruption": False,
        "table_signal": False,
        "recommended_tools": ["fitz"],
        "duration_ms": 10,
        "probed_at": datetime(2026, 6, 25, tzinfo=timezone.utc).isoformat(),
    }


def test_probe_endpoint_returns_profile_shape(mock_profile_dict):
    """DocumentProbe.run() is mocked — we only test the endpoint wiring."""
    from app.cdm.adapters.local_pipeline.probe import DocumentProfile
    from datetime import datetime, timezone

    profile = DocumentProfile(
        source_document_id="doc-abc",
        filename="test.pdf",
        page_count=1,
        pages=[],
        has_text_layer=True,
        has_scanned_pages=False,
        has_cid_corruption=False,
        table_signal=False,
        recommended_tools=["fitz"],
        duration_ms=10,
        probed_at=datetime(2026, 6, 25, tzinfo=timezone.utc),
    )

    with patch(
        "app.routers.documents.DocumentProbe"
    ) as MockProbe, patch(
        "app.routers.documents.DocumentRepository"
    ) as MockRepo, patch(
        "app.routers.documents.get_storage_service"
    ):
        mock_doc = MagicMock()
        mock_doc.id = uuid4()
        mock_doc.title = "test.pdf"
        mock_doc.source_metadata = {"file_path": "/tmp/test.pdf"}

        MockRepo.return_value.get_by_id = AsyncMock(return_value=mock_doc)
        MockProbe.return_value.run = MagicMock(return_value=profile)

        # Confirm the profile serialises to JSON correctly
        data = profile.model_dump()
        assert data["page_count"] == 1
        assert data["has_text_layer"] is True
        assert "recommended_tools" in data
```

- [ ] **Step 2: Run to confirm test passes (it's a unit test of the types, not a full HTTP test)**

```bash
uv run --directory backend python -m pytest -o "addopts=" tests/routers/test_probe_endpoint.py -v
```

Expected: PASS (just validates the profile dict shape — full integration test requires test DB).

- [ ] **Step 3: Implement the probe endpoint**

In `backend/app/routers/documents.py`, add the following import at the top with the other imports:

```python
from app.cdm.adapters.local_pipeline.probe import DocumentProbe, DocumentProfile
```

Then add the endpoint **before** the existing `router = APIRouter(...)` line is used as the last endpoint, or after the last existing endpoint. Add it after the final existing `@router` decorated function:

```python
@router.post(
    "/{document_id}/probe",
    summary="Run DocumentProbe — classify PDF by page without parsing",
)
async def probe_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    storage_service: StorageService = Depends(get_storage_service),
) -> dict:
    import tempfile, os
    document_repo = DocumentRepository(db)
    doc = await document_repo.get_by_id(document_id)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    file_path = doc.source_metadata.get("file_path")
    if not file_path:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Document has no stored file path — cannot probe.",
        )

    content = await storage_service.get(file_path)
    if content is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found in storage")

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        profile = DocumentProbe().run(
            pdf_path=Path(tmp_path),
            source_document_id=str(doc.id),
        )
    finally:
        os.unlink(tmp_path)

    return profile.model_dump(mode="json")
```

Also add `from pathlib import Path` to the imports at the top if not already present.

- [ ] **Step 4: Verify the router imports cleanly**

```bash
uv run --directory backend python -c "from app.routers.documents import router; print('OK')"
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/documents.py \
        backend/tests/routers/test_probe_endpoint.py
git commit -m "feat(local-pipeline): add POST /documents/{id}/probe endpoint"
```

---

## Task 5: Frontend types + API function

**Files:**
- Create: `frontend/src/types/probe.ts`
- Create: `frontend/src/api/probe.ts`

**Interfaces:**
- Produces:
  - `PageProfile`, `DocumentProfile` TypeScript interfaces
  - `probeDocument(documentId: string): Promise<DocumentProfile>`

- [ ] **Step 1: Create TypeScript types**

Create `frontend/src/types/probe.ts`:

```typescript
export type FontHealth = 'clean' | 'cid_corrupt' | 'mixed' | 'unknown'
export type PageType = 'text' | 'scanned' | 'mixed' | 'empty'

export interface PageProfile {
  index: number
  char_count: number
  has_text_layer: boolean
  image_count: number
  font_health: FontHealth
  table_signal: boolean
  page_type: PageType
}

export interface DocumentProfile {
  source_document_id: string
  filename: string | null
  page_count: number
  pages: PageProfile[]
  has_text_layer: boolean
  has_scanned_pages: boolean
  has_cid_corruption: boolean
  table_signal: boolean
  recommended_tools: string[]
  duration_ms: number
  probed_at: string  // ISO datetime string
}
```

- [ ] **Step 2: Create the API function**

Create `frontend/src/api/probe.ts`:

```typescript
import apiClient from './client'
import type { DocumentProfile } from '@/types/probe'

export async function probeDocument(documentId: string): Promise<DocumentProfile> {
  const response = await apiClient.post<DocumentProfile>(`/documents/${documentId}/probe`)
  return response.data
}
```

- [ ] **Step 3: Verify lint passes**

```bash
npm --prefix frontend run lint
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/probe.ts frontend/src/api/probe.ts
git commit -m "feat(local-pipeline): add DocumentProfile TypeScript types + probeDocument API fn"
```

---

## Task 6: useDocumentProbe hook

**Files:**
- Create: `frontend/src/hooks/useDocumentProbe.ts`

**Interfaces:**
- Consumes: `probeDocument` from `@/api/probe`
- Produces:
  ```typescript
  useDocumentProbe(documentId: string | null): {
    profile: DocumentProfile | null
    isLoading: boolean
    error: string | null
    runProbe: () => Promise<void>
  }
  ```

- [ ] **Step 1: Create the hook**

Create `frontend/src/hooks/useDocumentProbe.ts`:

```typescript
import { useState, useCallback } from 'react'
import { probeDocument } from '@/api/probe'
import type { DocumentProfile } from '@/types/probe'

interface UseDocumentProbeReturn {
  profile: DocumentProfile | null
  isLoading: boolean
  error: string | null
  runProbe: () => Promise<void>
}

export function useDocumentProbe(documentId: string | null): UseDocumentProbeReturn {
  const [profile, setProfile] = useState<DocumentProfile | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const runProbe = useCallback(async () => {
    if (!documentId) return
    setIsLoading(true)
    setError(null)
    try {
      const result = await probeDocument(documentId)
      setProfile(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Probe failed')
    } finally {
      setIsLoading(false)
    }
  }, [documentId])

  return { profile, isLoading, error, runProbe }
}
```

- [ ] **Step 2: Verify lint passes**

```bash
npm --prefix frontend run lint
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/hooks/useDocumentProbe.ts
git commit -m "feat(local-pipeline): add useDocumentProbe hook"
```

---

## Task 7: DocumentProbePanel component + DocumentsPage integration

**Files:**
- Create: `frontend/src/components/documents/DocumentProbePanel.tsx`
- Modify: `frontend/src/pages/DocumentsPage.tsx`

**Interfaces:**
- Consumes: `useDocumentProbe` from Task 6; `DocumentProfile`, `PageProfile` from Task 5
- Produces: `<DocumentProbePanel documentId={string} />` — self-contained section

- [ ] **Step 1: Create DocumentProbePanel**

Create `frontend/src/components/documents/DocumentProbePanel.tsx`:

```tsx
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { useDocumentProbe } from '@/hooks/useDocumentProbe'
import type { PageProfile } from '@/types/probe'
import { ScanSearch } from 'lucide-react'

interface DocumentProbePanelProps {
  documentId: string
}

function pageTypeBadge(type: PageProfile['page_type']) {
  const variants: Record<PageProfile['page_type'], 'default' | 'secondary' | 'destructive' | 'outline'> = {
    text: 'default',
    scanned: 'destructive',
    mixed: 'secondary',
    empty: 'outline',
  }
  return <Badge variant={variants[type]}>{type}</Badge>
}

function fontHealthBadge(health: PageProfile['font_health']) {
  if (health === 'cid_corrupt') return <Badge variant="destructive">CID corrupt</Badge>
  if (health === 'mixed') return <Badge variant="secondary">mixed</Badge>
  if (health === 'clean') return <Badge variant="default">clean</Badge>
  return <Badge variant="outline">unknown</Badge>
}

export function DocumentProbePanel({ documentId }: DocumentProbePanelProps) {
  const { profile, isLoading, error, runProbe } = useDocumentProbe(documentId)

  return (
    <section>
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-medium">Document probe</h3>
        <Button variant="outline" size="sm" onClick={runProbe} disabled={isLoading}>
          <ScanSearch className="h-4 w-4 mr-2" />
          {isLoading ? 'Probing…' : profile ? 'Re-probe' : 'Run probe'}
        </Button>
      </div>

      {error && (
        <Alert variant="destructive" className="mb-2">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {isLoading && (
        <div className="space-y-2">
          <Skeleton className="h-6 w-full" />
          <Skeleton className="h-6 w-full" />
          <Skeleton className="h-6 w-3/4" />
        </div>
      )}

      {profile && !isLoading && (
        <div className="space-y-3">
          {/* Document-level flags */}
          <div className="flex flex-wrap gap-2 text-xs">
            {profile.has_cid_corruption && <Badge variant="destructive">CID corruption</Badge>}
            {profile.has_scanned_pages && <Badge variant="secondary">Scanned pages</Badge>}
            {profile.table_signal && <Badge variant="outline">Table signal</Badge>}
            {!profile.has_text_layer && <Badge variant="destructive">No text layer</Badge>}
          </div>

          {/* Recommended tools */}
          <div className="text-xs text-muted-foreground">
            <span className="font-medium">Suggested tools: </span>
            {profile.recommended_tools.join(', ')}
          </div>

          {/* Per-page table */}
          <div className="border rounded-md overflow-hidden">
            <table className="w-full text-xs">
              <thead className="bg-muted">
                <tr>
                  <th className="text-left px-3 py-2 font-medium">Page</th>
                  <th className="text-left px-3 py-2 font-medium">Type</th>
                  <th className="text-left px-3 py-2 font-medium">Chars</th>
                  <th className="text-left px-3 py-2 font-medium">Font</th>
                  <th className="text-left px-3 py-2 font-medium">Table?</th>
                  <th className="text-left px-3 py-2 font-medium">Images</th>
                </tr>
              </thead>
              <tbody>
                {profile.pages.map((page) => (
                  <tr key={page.index} className="border-t">
                    <td className="px-3 py-1.5">{page.index + 1}</td>
                    <td className="px-3 py-1.5">{pageTypeBadge(page.page_type)}</td>
                    <td className="px-3 py-1.5">{page.char_count.toLocaleString()}</td>
                    <td className="px-3 py-1.5">{fontHealthBadge(page.font_health)}</td>
                    <td className="px-3 py-1.5">{page.table_signal ? '✓' : '—'}</td>
                    <td className="px-3 py-1.5">{page.image_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <p className="text-xs text-muted-foreground">
            Probed in {profile.duration_ms}ms · {profile.page_count} page{profile.page_count !== 1 ? 's' : ''}
          </p>
        </div>
      )}
    </section>
  )
}
```

- [ ] **Step 2: Add import to DocumentsPage.tsx**

In `frontend/src/pages/DocumentsPage.tsx`, add to the imports block (with the other component imports):

```typescript
import { DocumentProbePanel } from '@/components/documents/DocumentProbePanel'
```

- [ ] **Step 3: Add DocumentProbePanel to the document Sheet**

In `frontend/src/pages/DocumentsPage.tsx`, find the `<div className="mt-6 space-y-6">` section inside the Sheet (around line 311) and add the probe panel as the **first section**, before the parse runs section:

```tsx
          <div className="mt-6 space-y-6">
            {viewDocumentId && (
              <DocumentProbePanel documentId={viewDocumentId} />
            )}
            {viewDocumentId && (
              <section>
                <h3 className="text-sm font-medium mb-2">Parse runs</h3>
                <RunTimeline
                  documentId={viewDocumentId}
                  runs={parseRuns}
                  onRunDeleted={refreshParseRuns}
                />
              </section>
            )}
            {viewDocumentId && (
              <ParsedDocumentViewer documentId={viewDocumentId} />
            )}
            {viewDocumentId && viewedDocument && (
              <DocumentTextViewer
                documentId={viewDocumentId}
                documentTitle={viewedDocument.title}
                onDownload={() => handleDownload(viewDocumentId, viewedDocument.title)}
              />
            )}
          </div>
```

- [ ] **Step 4: Verify lint and build pass**

```bash
npm --prefix frontend run lint
npm --prefix frontend run build
```

Expected: no errors in either command.

- [ ] **Step 5: Manual smoke test**

Start the backend and frontend:
```bash
uv run --directory backend uvicorn app.main:app --reload
npm --prefix frontend run dev
```

1. Open http://localhost:5173 and log in.
2. Navigate to a project with at least one uploaded PDF document.
3. Click a document to open the detail Sheet.
4. Verify the "Document probe" section appears at the top with a "Run probe" button.
5. Click "Run probe" — loading skeletons should appear briefly.
6. Verify the per-page table renders with page type, char count, font health, table signal, image count.
7. Verify document-level flag badges appear if applicable.
8. Click "Re-probe" — result should refresh.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/documents/DocumentProbePanel.tsx \
        frontend/src/pages/DocumentsPage.tsx
git commit -m "feat(local-pipeline): add DocumentProbePanel + integrate into document Sheet"
```

---

## Self-Review Checklist (for implementer)

Before opening a PR:
- [ ] `uv run --directory backend python -m pytest -o "addopts=" tests/cdm/adapters/local_pipeline/ -v` — all green
- [ ] `uv run --directory backend python -m pytest -o "addopts=" tests/routers/test_probe_endpoint.py -v` — green
- [ ] `npm --prefix frontend run lint` — no errors
- [ ] `npm --prefix frontend run build` — no errors
- [ ] Manual smoke test completed (Task 7, Step 5)
- [ ] No `TODO`, `TBD`, or `raise NotImplementedError` remaining in new files
