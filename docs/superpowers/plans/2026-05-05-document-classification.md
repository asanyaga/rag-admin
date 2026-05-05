# Document Classification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add LLM-based document classification that identifies which pages/blocks of a `ParsedDocument` match user-defined labels, stores results for re-use, and exposes a top-level `/classify` UI.

**Architecture:** Classification is a new first-class workload. The service page-batches a serialized `ParsedDocument`, calls an LLM (Ollama-first via `LLMPort`), assembles batch results into `ClassifiedRegion` objects, and persists them via a new repository. The backend follows the `router → service → repository → database` pattern; the frontend adds a `/classify` route with list, wizard, and detail pages.

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy 2.0 / Alembic / Pydantic v2 (backend); React 18 / TypeScript / shadcn-ui / Tailwind (frontend); OpenAI-compatible API for Ollama and Groq.

---

## File Map

| Layer | File | Action |
|---|---|---|
| CDM | `backend/app/cdm/classification.py` | Create |
| CDM util | `backend/app/cdm/workloads.py` | Create |
| LLM adapters | `backend/app/services/llm/openai_adapter.py` | Modify (add `base_url`) |
| LLM adapters | `backend/app/services/llm/ollama_adapter.py` | Create |
| LLM adapters | `backend/app/services/llm/groq_adapter.py` | Create |
| Serializer | `backend/app/services/classification/serializer.py` | Create |
| Assembler | `backend/app/services/classification/assembler.py` | Create |
| ORM models | `backend/app/models/classification_run.py` | Create |
| ORM models | `backend/app/models/classification_region.py` | Create |
| ORM models | `backend/app/models/__init__.py` | Modify (add exports) |
| Migration | `backend/alembic/versions/<rev>_add_classification_tables.py` | Create |
| Repository | `backend/app/repositories/classification_run_repository.py` | Create |
| Config | `backend/app/config.py` | Modify (add classifier settings) |
| LLM dependency | `backend/app/dependencies/llm.py` | Create |
| Service | `backend/app/services/classification/service.py` | Create |
| Schemas | `backend/app/schemas/classification.py` | Create |
| Router | `backend/app/routers/classification.py` | Create |
| Wire-up | `backend/app/main.py` | Modify (include routers) |
| Frontend types | `frontend/src/types/classification.ts` | Create |
| Frontend API | `frontend/src/api/classification.ts` | Create |
| Frontend hook | `frontend/src/hooks/useClassificationRuns.ts` | Create |
| Components | `frontend/src/components/classification/ClassificationRunStatusBadge.tsx` | Create |
| Components | `frontend/src/components/classification/ClassificationRegionCard.tsx` | Create |
| Components | `frontend/src/components/classification/ClassificationRegionList.tsx` | Create |
| Components | `frontend/src/components/classification/ClassificationRunForm.tsx` | Create |
| Pages | `frontend/src/pages/ClassificationPage.tsx` | Create |
| Pages | `frontend/src/pages/NewClassificationRunPage.tsx` | Create |
| Pages | `frontend/src/pages/ClassificationRunDetailPage.tsx` | Create |
| Routing | `frontend/src/config/navigation.ts` | Modify (add Classify nav item) |
| Routing | `frontend/src/App.tsx` | Modify (add routes) |

---

## Task 1: CDM types and slice_doc

**Files:**
- Create: `backend/app/cdm/classification.py`
- Create: `backend/app/cdm/workloads.py`
- Test: `backend/tests/cdm/test_classification.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/cdm/test_classification.py
import pytest
from pydantic import ValidationError
from app.cdm.classification import ClassifiedRegion, ClassificationRunStatus


def test_classified_region_required_fields():
    region = ClassifiedRegion(
        label="balance_sheet",
        page_start=5,
        page_end=8,
        block_ids=["b-001", "b-002"],
    )
    assert region.label == "balance_sheet"
    assert region.page_start == 5
    assert region.page_end == 8
    assert region.block_ids == ["b-001", "b-002"]
    assert region.confidence is None
    assert region.reasoning is None
    assert region.source == "llm"


def test_classified_region_frozen():
    region = ClassifiedRegion(label="x", page_start=0, page_end=1, block_ids=[])
    with pytest.raises(ValidationError):
        region.label = "y"  # type: ignore


def test_classified_region_rejects_extra_fields():
    with pytest.raises(ValidationError):
        ClassifiedRegion(label="x", page_start=0, page_end=1, block_ids=[], unknown="bad")


def test_classification_run_status_values():
    assert ClassificationRunStatus.PENDING == "pending"
    assert ClassificationRunStatus.RUNNING == "running"
    assert ClassificationRunStatus.COMPLETED == "completed"
    assert ClassificationRunStatus.FAILED == "failed"
```

- [ ] **Step 2: Run tests to confirm they fail**

```
uv run --directory backend python -m pytest tests/cdm/test_classification.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.cdm.classification'`

- [ ] **Step 3: Create `cdm/classification.py`**

```python
# backend/app/cdm/classification.py
from __future__ import annotations
from enum import Enum
from typing import List, Literal, Optional

from app.cdm.models import _Frozen


class ClassifiedRegion(_Frozen):
    label: str
    page_start: int
    page_end: int
    block_ids: List[str]
    confidence: Optional[float] = None
    reasoning: Optional[str] = None
    source: Literal["llm", "human"] = "llm"


class ClassificationRunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
```

- [ ] **Step 4: Run classification tests — expect PASS**

```
uv run --directory backend python -m pytest tests/cdm/test_classification.py -v
```

- [ ] **Step 5: Write failing tests for slice_doc**

```python
# backend/tests/cdm/test_workloads.py
import pytest
from app.cdm.models import Block, BlockRole, Page, ParsedDocument
from app.cdm.classification import ClassifiedRegion
from app.cdm.workloads import slice_doc


def _make_doc() -> ParsedDocument:
    pages = [Page(index=i, block_ids=[f"b{i}"]) for i in range(5)]
    blocks = [
        Block(
            id=f"b{i}",
            role=BlockRole.PARAGRAPH,
            native_type="paragraph",
            text=f"text on page {i}",
            page_index=i,
            reading_order=0,
        )
        for i in range(5)
    ]
    return ParsedDocument(
        id="doc-1",
        source_document_id="src-1",
        parse_run_id="run-1",
        page_count=5,
        pages=pages,
        blocks=blocks,
    )


def test_slice_doc_returns_only_region_pages():
    doc = _make_doc()
    region = ClassifiedRegion(label="balance_sheet", page_start=1, page_end=3, block_ids=[])
    sliced = slice_doc(doc, region)
    assert sliced.page_count == 3
    assert [p.index for p in sliced.pages] == [1, 2, 3]
    assert [b.id for b in sliced.blocks] == ["b1", "b2", "b3"]


def test_slice_doc_sets_lineage():
    doc = _make_doc()
    region = ClassifiedRegion(label="income_statement", page_start=0, page_end=1, block_ids=[])
    sliced = slice_doc(doc, region)
    assert sliced.derived_from == "doc-1"
    assert "income_statement" in sliced.derivation
    assert "0" in sliced.derivation
    assert "1" in sliced.derivation


def test_slice_doc_original_unchanged():
    doc = _make_doc()
    region = ClassifiedRegion(label="x", page_start=0, page_end=0, block_ids=[])
    slice_doc(doc, region)
    assert doc.page_count == 5  # original not mutated
```

- [ ] **Step 6: Run tests to confirm they fail**

```
uv run --directory backend python -m pytest tests/cdm/test_workloads.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.cdm.workloads'`

- [ ] **Step 7: Create `cdm/workloads.py`**

```python
# backend/app/cdm/workloads.py
from app.cdm.classification import ClassifiedRegion
from app.cdm.models import ParsedDocument


def slice_doc(doc: ParsedDocument, region: ClassifiedRegion) -> ParsedDocument:
    """Return a derived sub-ParsedDocument containing only region pages."""
    page_set = set(range(region.page_start, region.page_end + 1))
    pages = [p for p in doc.pages if p.index in page_set]
    blocks = [b for b in doc.blocks if b.page_index in page_set]
    return doc.model_copy(update={
        "pages": pages,
        "blocks": blocks,
        "page_count": len(pages),
        "derived_from": doc.id,
        "derivation": f"slice:{region.label}:pages {region.page_start}-{region.page_end}",
    })
```

- [ ] **Step 8: Run workloads tests — expect PASS**

```
uv run --directory backend python -m pytest tests/cdm/ -v
```

- [ ] **Step 9: Commit**

```bash
git add backend/app/cdm/classification.py backend/app/cdm/workloads.py backend/tests/cdm/test_classification.py backend/tests/cdm/test_workloads.py
git commit -m "feat(cdm): add ClassifiedRegion type and slice_doc utility"
```

---

## Task 2: LLM adapters — Ollama and Groq

**Files:**
- Modify: `backend/app/services/llm/openai_adapter.py` (add `base_url` param)
- Create: `backend/app/services/llm/ollama_adapter.py`
- Create: `backend/app/services/llm/groq_adapter.py`
- Test: `backend/tests/services/llm/test_openai_compatible_adapters.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/services/llm/test_openai_compatible_adapters.py
from unittest.mock import AsyncMock, patch
import pytest
from app.services.llm.ollama_adapter import OllamaAdapter
from app.services.llm.groq_adapter import GroqAdapter
from app.services.llm.types import LLMConfig


def test_ollama_adapter_init():
    adapter = OllamaAdapter(base_url="http://localhost:11434/v1")
    assert adapter.client.base_url == "http://localhost:11434/v1"


def test_ollama_adapter_default_base_url():
    adapter = OllamaAdapter()
    assert "11434" in str(adapter.client.base_url)


def test_groq_adapter_init():
    adapter = GroqAdapter(api_key="test-key")
    assert "groq.com" in str(adapter.client.base_url)
```

- [ ] **Step 2: Run tests to confirm they fail**

```
uv run --directory backend python -m pytest tests/services/llm/test_openai_compatible_adapters.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.services.llm.ollama_adapter'`

- [ ] **Step 3: Add `base_url` to `OpenAIAdapter.__init__`**

Open `backend/app/services/llm/openai_adapter.py`. Change line 17–18 from:
```python
    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(api_key=api_key)
```
to:
```python
    def __init__(self, api_key: str, base_url: str | None = None):
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
```

- [ ] **Step 4: Create `ollama_adapter.py`**

```python
# backend/app/services/llm/ollama_adapter.py
from app.services.llm.openai_adapter import OpenAIAdapter


class OllamaAdapter(OpenAIAdapter):
    """OpenAI-compatible adapter pointing at a local Ollama instance."""

    def __init__(self, base_url: str = "http://localhost:11434/v1"):
        super().__init__(api_key="ollama", base_url=base_url)
```

- [ ] **Step 5: Create `groq_adapter.py`**

```python
# backend/app/services/llm/groq_adapter.py
from app.services.llm.openai_adapter import OpenAIAdapter


class GroqAdapter(OpenAIAdapter):
    """OpenAI-compatible adapter pointing at Groq's hosted inference."""

    def __init__(self, api_key: str):
        super().__init__(api_key=api_key, base_url="https://api.groq.com/openai/v1")
```

- [ ] **Step 6: Run adapter tests — expect PASS**

```
uv run --directory backend python -m pytest tests/services/llm/test_openai_compatible_adapters.py -v
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/llm/openai_adapter.py backend/app/services/llm/ollama_adapter.py backend/app/services/llm/groq_adapter.py backend/tests/services/llm/test_openai_compatible_adapters.py
git commit -m "feat(llm): add OllamaAdapter and GroqAdapter (OpenAI-compatible wrappers)"
```

---

## Task 3: Page serializer and batch builder

**Files:**
- Create: `backend/app/services/classification/__init__.py`
- Create: `backend/app/services/classification/serializer.py`
- Test: `backend/tests/services/classification/test_serializer.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/services/classification/test_serializer.py
from app.cdm.models import Block, BlockRole, Page, ParsedDocument
from app.services.classification.serializer import build_batches, serialize_pages


def _make_doc(page_count: int) -> ParsedDocument:
    pages = [Page(index=i, block_ids=[f"b{i}"]) for i in range(page_count)]
    blocks = [
        Block(
            id=f"b{i}",
            role=BlockRole.PARAGRAPH,
            native_type="paragraph",
            text=f"content on page {i}",
            page_index=i,
            reading_order=0,
        )
        for i in range(page_count)
    ]
    return ParsedDocument(
        id="doc-1",
        source_document_id="src-1",
        parse_run_id="run-1",
        page_count=page_count,
        pages=pages,
        blocks=blocks,
    )


def test_serialize_pages_format():
    doc = _make_doc(3)
    text = serialize_pages(doc, 0, 1)
    assert "[page 0, paragraph] content on page 0" in text
    assert "[page 1, paragraph] content on page 1" in text
    assert "page 2" not in text


def test_serialize_pages_prefers_markdown():
    from pydantic import ValidationError
    import pytest
    pages = [Page(index=0, block_ids=["b0"])]
    blocks = [
        Block(
            id="b0",
            role=BlockRole.TABLE,
            native_type="table",
            text="plain text",
            markdown="| col1 | col2 |",
            page_index=0,
            reading_order=0,
        )
    ]
    doc = ParsedDocument(
        id="d", source_document_id="s", parse_run_id="r",
        page_count=1, pages=pages, blocks=blocks,
    )
    text = serialize_pages(doc, 0, 0)
    assert "| col1 | col2 |" in text
    assert "plain text" not in text


def test_build_batches_25_pages():
    batches = build_batches(page_count=25, batch_size=10, overlap=3)
    assert batches[0] == (0, 9)
    assert batches[1] == (7, 16)
    assert batches[2] == (14, 23)
    assert batches[3] == (21, 24)


def test_build_batches_small_doc():
    batches = build_batches(page_count=5, batch_size=10, overlap=3)
    assert batches == [(0, 4)]


def test_build_batches_exact_fit():
    batches = build_batches(page_count=10, batch_size=10, overlap=3)
    assert batches == [(0, 9)]
```

- [ ] **Step 2: Run tests to confirm they fail**

```
uv run --directory backend python -m pytest tests/services/classification/test_serializer.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.services.classification'`

- [ ] **Step 3: Create the package and serializer**

First create `backend/app/services/classification/__init__.py` (empty file).

Then create `backend/app/services/classification/serializer.py`:

```python
# backend/app/services/classification/serializer.py
from app.cdm.models import ParsedDocument


def serialize_pages(doc: ParsedDocument, page_start: int, page_end: int) -> str:
    """Serialize blocks for pages [page_start, page_end] inclusive as compact text."""
    lines = []
    for block in doc.blocks:
        if block.page_index < page_start or block.page_index > page_end:
            continue
        content = block.markdown if block.markdown else block.text
        if not content.strip():
            continue
        lines.append(f"[page {block.page_index}, {block.role.value}] {content}")
    return "\n".join(lines)


def build_batches(page_count: int, batch_size: int, overlap: int) -> list[tuple[int, int]]:
    """Return (start, end) page ranges for each batch with given overlap.

    Example: page_count=25, batch_size=10, overlap=3 →
        [(0,9), (7,16), (14,23), (21,24)]
    """
    if page_count == 0:
        return []
    batches = []
    start = 0
    while True:
        end = min(start + batch_size - 1, page_count - 1)
        batches.append((start, end))
        if end >= page_count - 1:
            break
        start = end - overlap + 1
    return batches
```

Also create `backend/tests/services/__init__.py` and `backend/tests/services/classification/__init__.py` if they don't exist:

```
touch backend/tests/services/__init__.py backend/tests/services/classification/__init__.py
```

- [ ] **Step 4: Run serializer tests — expect PASS**

```
uv run --directory backend python -m pytest tests/services/classification/test_serializer.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/classification/ backend/tests/services/classification/test_serializer.py backend/tests/services/__init__.py backend/tests/services/classification/__init__.py
git commit -m "feat(classification): add page serializer and batch builder"
```

---

## Task 4: Assembler — overlap resolution and region assembly

**Files:**
- Create: `backend/app/services/classification/assembler.py`
- Test: `backend/tests/services/classification/test_assembler.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/services/classification/test_assembler.py
from app.cdm.models import Block, BlockRole, Page, ParsedDocument
from app.cdm.classification import ClassifiedRegion
from app.services.classification.assembler import (
    BatchPageResult,
    assemble_regions,
    resolve_page_statuses,
)


def _make_doc(page_count: int) -> ParsedDocument:
    pages = [Page(index=i, block_ids=[f"b{i}"]) for i in range(page_count)]
    blocks = [
        Block(
            id=f"b{i}",
            role=BlockRole.PARAGRAPH,
            native_type="paragraph",
            text=f"page {i}",
            page_index=i,
            reading_order=0,
        )
        for i in range(page_count)
    ]
    return ParsedDocument(
        id="d", source_document_id="s", parse_run_id="r",
        page_count=page_count, pages=pages, blocks=blocks,
    )


def test_resolve_prefers_middle_pages():
    """Page 7 appears in batch (0-9) at edge and batch (7-16) in the middle.
    The batch where it's in the middle should win."""
    batch_a = [
        BatchPageResult(page=7, label_statuses={"bs": "start"}, batch_start=0, batch_end=9),
    ]
    batch_b = [
        BatchPageResult(page=7, label_statuses={"bs": "none"}, batch_start=7, batch_end=16),
        BatchPageResult(page=10, label_statuses={"bs": "continue"}, batch_start=7, batch_end=16),
    ]
    resolved = resolve_page_statuses([batch_a, batch_b])
    # Page 7 at edge of batch_a (priority 1) vs middle of batch_b (priority 0)
    assert resolved[7]["bs"] == "none"
    assert resolved[10]["bs"] == "continue"


def test_assemble_simple_region():
    doc = _make_doc(5)
    resolved = {
        0: {"balance_sheet": "none"},
        1: {"balance_sheet": "start"},
        2: {"balance_sheet": "continue"},
        3: {"balance_sheet": "none"},
        4: {"balance_sheet": "none"},
    }
    regions = assemble_regions(resolved, ["balance_sheet"], doc)
    assert len(regions) == 1
    r = regions[0]
    assert r.label == "balance_sheet"
    assert r.page_start == 1
    assert r.page_end == 2
    assert "b1" in r.block_ids
    assert "b2" in r.block_ids
    assert "b0" not in r.block_ids


def test_assemble_no_region():
    doc = _make_doc(3)
    resolved = {i: {"x": "none"} for i in range(3)}
    regions = assemble_regions(resolved, ["x"], doc)
    assert regions == []


def test_assemble_region_open_at_end():
    doc = _make_doc(3)
    resolved = {
        0: {"x": "none"},
        1: {"x": "start"},
        2: {"x": "continue"},
    }
    regions = assemble_regions(resolved, ["x"], doc)
    assert len(regions) == 1
    assert regions[0].page_end == 2


def test_assemble_two_regions_same_label():
    doc = _make_doc(6)
    resolved = {
        0: {"x": "start"},
        1: {"x": "none"},
        2: {"x": "start"},
        3: {"x": "continue"},
        4: {"x": "none"},
        5: {"x": "none"},
    }
    regions = assemble_regions(resolved, ["x"], doc)
    assert len(regions) == 2
    assert regions[0].page_start == 0 and regions[0].page_end == 0
    assert regions[1].page_start == 2 and regions[1].page_end == 3
```

- [ ] **Step 2: Run tests to confirm they fail**

```
uv run --directory backend python -m pytest tests/services/classification/test_assembler.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.services.classification.assembler'`

- [ ] **Step 3: Create the assembler**

```python
# backend/app/services/classification/assembler.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional

from app.cdm.classification import ClassifiedRegion
from app.cdm.models import ParsedDocument


@dataclass
class BatchPageResult:
    page: int
    label_statuses: Dict[str, str]  # label -> "start"|"continue"|"none"
    batch_start: int
    batch_end: int


def resolve_page_statuses(
    batch_results: List[List[BatchPageResult]],
) -> Dict[int, Dict[str, str]]:
    """For overlapping pages, prefer results from the middle 50% of each batch window."""
    best: Dict[int, tuple[int, Dict[str, str]]] = {}

    for batch_pages in batch_results:
        if not batch_pages:
            continue
        batch_start = batch_pages[0].batch_start
        batch_end = batch_pages[0].batch_end
        batch_len = batch_end - batch_start + 1
        quarter = max(1, batch_len // 4)

        for page_result in batch_pages:
            page = page_result.page
            in_middle = (
                page >= batch_start + quarter
                and page <= batch_end - quarter
            )
            priority = 0 if in_middle else 1
            if page not in best or priority < best[page][0]:
                best[page] = (priority, page_result.label_statuses)

    return {page: statuses for page, (_, statuses) in best.items()}


def assemble_regions(
    resolved: Dict[int, Dict[str, str]],
    labels: List[str],
    doc: ParsedDocument,
) -> List[ClassifiedRegion]:
    """Walk sorted pages per label and build ClassifiedRegion objects."""
    regions: List[ClassifiedRegion] = []

    for label in labels:
        current_start: Optional[int] = None
        current_end: Optional[int] = None

        for page in sorted(resolved.keys()):
            status = resolved[page].get(label, "none")

            if status == "start":
                if current_start is not None:
                    regions.append(_make_region(label, current_start, current_end, doc))
                current_start = page
                current_end = page
            elif status == "continue" and current_start is not None:
                current_end = page
            elif status == "none" and current_start is not None:
                regions.append(_make_region(label, current_start, current_end, doc))
                current_start = None
                current_end = None

        if current_start is not None:
            regions.append(_make_region(label, current_start, current_end, doc))

    return regions


def _make_region(
    label: str,
    page_start: int,
    page_end: int,
    doc: ParsedDocument,
) -> ClassifiedRegion:
    block_ids = [
        b.id
        for b in sorted(
            (b for b in doc.blocks if page_start <= b.page_index <= page_end),
            key=lambda b: (b.page_index, b.reading_order or 0),
        )
    ]
    return ClassifiedRegion(
        label=label,
        page_start=page_start,
        page_end=page_end,
        block_ids=block_ids,
    )
```

- [ ] **Step 4: Run assembler tests — expect PASS**

```
uv run --directory backend python -m pytest tests/services/classification/test_assembler.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/classification/assembler.py backend/tests/services/classification/test_assembler.py
git commit -m "feat(classification): add batch result assembler with overlap resolution"
```

---

## Task 5: ORM models and Alembic migration

**Files:**
- Create: `backend/app/models/classification_run.py`
- Create: `backend/app/models/classification_region.py`
- Modify: `backend/app/models/__init__.py`
- Create: Alembic migration file

- [ ] **Step 1: Create `models/classification_run.py`**

```python
# backend/app/models/classification_run.py
from datetime import datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ClassificationRun(Base):
    __tablename__ = "classification_runs"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4,
        server_default=sa.text("gen_random_uuid()"),
    )
    parse_run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("parse_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    document_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    labels_requested: Mapped[list] = mapped_column(JSON, nullable=False)
    llm_provider: Mapped[str] = mapped_column(Text, nullable=False)
    llm_model: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    batch_size: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    batch_overlap: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=datetime.utcnow, server_default=sa.text("NOW()"),
    )

    __table_args__ = (
        sa.Index("ix_classification_runs_parse_run_id", "parse_run_id"),
        sa.Index("ix_classification_runs_document_id", "document_id"),
        sa.Index("ix_classification_runs_status", "status"),
    )
```

- [ ] **Step 2: Create `models/classification_region.py`**

```python
# backend/app/models/classification_region.py
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import Float, ForeignKey, Integer, JSON, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ClassificationRegion(Base):
    __tablename__ = "classification_regions"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4,
        server_default=sa.text("gen_random_uuid()"),
    )
    run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("classification_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    label: Mapped[str] = mapped_column(Text, nullable=False)
    page_start: Mapped[int] = mapped_column(Integer, nullable=False)
    page_end: Mapped[int] = mapped_column(Integer, nullable=False)
    block_ids: Mapped[list] = mapped_column(JSON, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(Text, nullable=False, default="llm")

    __table_args__ = (
        sa.Index("ix_classification_regions_run_id", "run_id"),
        sa.Index("ix_classification_regions_label", "label"),
    )
```

- [ ] **Step 3: Register models in `models/__init__.py`**

Add to the imports and `__all__` list in `backend/app/models/__init__.py`:

```python
from app.models.classification_run import ClassificationRun
from app.models.classification_region import ClassificationRegion
```

And add `"ClassificationRun"` and `"ClassificationRegion"` to `__all__`.

- [ ] **Step 4: Generate and write the Alembic migration**

Run `alembic heads` to confirm the current head, then create the migration file manually. Replace `<prev_rev>` with the output of `alembic heads`:

```bash
uv run --directory backend alembic heads
```

Create `backend/alembic/versions/<timestamp>_add_classification_tables.py` (pick a hex revision ID, e.g. `a1b2c3d4e5f6`):

```python
"""add classification tables

Revision ID: a1b2c3d4e5f6
Revises: f9b0c1d2e3a4
Create Date: 2026-05-05 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "f9b0c1d2e3a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "classification_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("parse_run_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("parse_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("labels_requested", postgresql.JSONB(), nullable=False),
        sa.Column("llm_provider", sa.Text(), nullable=False),
        sa.Column("llm_model", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("batch_size", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("batch_overlap", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
    )
    op.create_index("ix_classification_runs_parse_run_id", "classification_runs", ["parse_run_id"])
    op.create_index("ix_classification_runs_document_id", "classification_runs", ["document_id"])
    op.create_index("ix_classification_runs_status", "classification_runs", ["status"])

    op.create_table(
        "classification_regions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("run_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("classification_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("page_start", sa.Integer(), nullable=False),
        sa.Column("page_end", sa.Integer(), nullable=False),
        sa.Column("block_ids", postgresql.JSONB(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("reasoning", sa.Text(), nullable=True),
        sa.Column("source", sa.Text(), nullable=False, server_default="llm"),
    )
    op.create_index("ix_classification_regions_run_id", "classification_regions", ["run_id"])
    op.create_index("ix_classification_regions_label", "classification_regions", ["label"])


def downgrade() -> None:
    op.drop_index("ix_classification_regions_label", table_name="classification_regions")
    op.drop_index("ix_classification_regions_run_id", table_name="classification_regions")
    op.drop_table("classification_regions")

    op.drop_index("ix_classification_runs_status", table_name="classification_runs")
    op.drop_index("ix_classification_runs_document_id", table_name="classification_runs")
    op.drop_index("ix_classification_runs_parse_run_id", table_name="classification_runs")
    op.drop_table("classification_runs")
```

> **Note:** Verify `down_revision` matches the actual current head from `alembic heads`. The value `f9b0c1d2e3a4` is the revision of `f9b0c1d2e3a4_drop_parse_results_table.py` — confirm it's still the head before running.

- [ ] **Step 5: Apply migration**

```
uv run --directory backend alembic upgrade head
```

Expected: migration applies cleanly, two new tables created.

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/classification_run.py backend/app/models/classification_region.py backend/app/models/__init__.py backend/alembic/versions/
git commit -m "feat(classification): add ORM models and Alembic migration for classification tables"
```

---

## Task 6: Repository

**Files:**
- Create: `backend/app/repositories/classification_run_repository.py`
- Test: `backend/tests/repositories/test_classification_run_repository.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/repositories/test_classification_run_repository.py
import pytest
from uuid import uuid4
from app.cdm.classification import ClassifiedRegion
from app.repositories.classification_run_repository import (
    ClassificationRunCreate,
    ClassificationRunRepository,
)


@pytest.mark.asyncio
async def test_create_and_get_run(test_db):
    # test_db is the AsyncSession fixture from conftest.py
    # We need a document_id and parse_run_id that exist — skip FK enforcement
    # by using the sync_client fixture instead, OR just test the repo in isolation
    # with mock FKs (SQLite doesn't enforce FK by default)
    repo = ClassificationRunRepository(test_db)
    data = ClassificationRunCreate(
        parse_run_id=uuid4(),
        document_id=uuid4(),
        labels_requested=["balance_sheet"],
        llm_provider="ollama_local",
        llm_model="qwen2.5:7b",
        batch_size=10,
        batch_overlap=3,
    )
    run = await repo.create(data)
    assert run.id is not None
    assert run.status == "pending"
    assert run.labels_requested == ["balance_sheet"]

    fetched = await repo.get(run.id)
    assert fetched is not None
    assert fetched.llm_provider == "ollama"


@pytest.mark.asyncio
async def test_update_status(test_db):
    repo = ClassificationRunRepository(test_db)
    data = ClassificationRunCreate(
        parse_run_id=uuid4(),
        document_id=uuid4(),
        labels_requested=["x"],
        llm_provider="ollama_local",
        llm_model="qwen2.5:7b",
        batch_size=10,
        batch_overlap=3,
    )
    run = await repo.create(data)
    await repo.update_status(run.id, "running")
    fetched = await repo.get(run.id)
    assert fetched.status == "running"


@pytest.mark.asyncio
async def test_save_and_get_regions(test_db):
    repo = ClassificationRunRepository(test_db)
    data = ClassificationRunCreate(
        parse_run_id=uuid4(),
        document_id=uuid4(),
        labels_requested=["balance_sheet"],
        llm_provider="ollama_local",
        llm_model="qwen2.5:7b",
        batch_size=10,
        batch_overlap=3,
    )
    run = await repo.create(data)
    regions = [
        ClassifiedRegion(label="balance_sheet", page_start=5, page_end=8, block_ids=["b1", "b2"]),
    ]
    await repo.save_regions(run.id, regions)
    fetched = await repo.get_regions(run.id)
    assert len(fetched) == 1
    assert fetched[0].label == "balance_sheet"
    assert fetched[0].page_start == 5
    assert fetched[0].block_ids == ["b1", "b2"]
```

- [ ] **Step 2: Run tests to confirm they fail**

```
uv run --directory backend python -m pytest tests/repositories/test_classification_run_repository.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.repositories.classification_run_repository'`

- [ ] **Step 3: Create the repository**

```python
# backend/app/repositories/classification_run_repository.py
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cdm.classification import ClassifiedRegion
from app.models.classification_region import ClassificationRegion as ClassificationRegionORM
from app.models.classification_run import ClassificationRun as ClassificationRunORM


@dataclass
class ClassificationRunCreate:
    parse_run_id: UUID
    document_id: UUID
    labels_requested: list[str]
    llm_provider: str
    llm_model: str
    batch_size: int
    batch_overlap: int


class ClassificationRunRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, data: ClassificationRunCreate) -> ClassificationRunORM:
        run = ClassificationRunORM(
            parse_run_id=data.parse_run_id,
            document_id=data.document_id,
            labels_requested=data.labels_requested,
            llm_provider=data.llm_provider,
            llm_model=data.llm_model,
            batch_size=data.batch_size,
            batch_overlap=data.batch_overlap,
            status="pending",
        )
        self.session.add(run)
        await self.session.commit()
        await self.session.refresh(run)
        return run

    async def get(self, run_id: UUID) -> ClassificationRunORM | None:
        result = await self.session.execute(
            select(ClassificationRunORM).where(ClassificationRunORM.id == run_id)
        )
        return result.scalar_one_or_none()

    async def list_for_document(self, document_id: UUID) -> list[ClassificationRunORM]:
        result = await self.session.execute(
            select(ClassificationRunORM)
            .where(ClassificationRunORM.document_id == document_id)
            .order_by(ClassificationRunORM.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_for_project(self, project_id: UUID) -> list[ClassificationRunORM]:
        from app.models.document import Document as DocumentORM
        result = await self.session.execute(
            select(ClassificationRunORM)
            .join(DocumentORM, ClassificationRunORM.document_id == DocumentORM.id)
            .where(DocumentORM.project_id == project_id)
            .order_by(ClassificationRunORM.created_at.desc())
        )
        return list(result.scalars().all())

    async def update_status(
        self,
        run_id: UUID,
        status: str,
        error: str | None = None,
    ) -> None:
        run = await self.get(run_id)
        if run is None:
            return
        run.status = status
        if error is not None:
            run.error = error
        if status == "running":
            run.started_at = datetime.now(timezone.utc)
        await self.session.commit()

    async def update_completed(
        self,
        run_id: UUID,
        input_tokens: int,
        output_tokens: int,
        duration_ms: int,
    ) -> None:
        run = await self.get(run_id)
        if run is None:
            return
        run.status = "completed"
        run.input_tokens = input_tokens
        run.output_tokens = output_tokens
        run.duration_ms = duration_ms
        run.finished_at = datetime.now(timezone.utc)
        await self.session.commit()

    async def get_regions(self, run_id: UUID) -> list[ClassificationRegionORM]:
        result = await self.session.execute(
            select(ClassificationRegionORM)
            .where(ClassificationRegionORM.run_id == run_id)
            .order_by(ClassificationRegionORM.label, ClassificationRegionORM.page_start)
        )
        return list(result.scalars().all())

    async def save_regions(self, run_id: UUID, regions: list[ClassifiedRegion]) -> None:
        for region in regions:
            self.session.add(ClassificationRegionORM(
                run_id=run_id,
                label=region.label,
                page_start=region.page_start,
                page_end=region.page_end,
                block_ids=region.block_ids,
                confidence=region.confidence,
                reasoning=region.reasoning,
                source=region.source,
            ))
        await self.session.commit()

    async def delete(self, run_id: UUID) -> None:
        run = await self.get(run_id)
        if run is not None:
            await self.session.delete(run)
            await self.session.commit()
```

- [ ] **Step 4: Run repository tests — expect PASS**

```
uv run --directory backend python -m pytest tests/repositories/test_classification_run_repository.py -v
```

> If SQLite FK enforcement blocks tests, add `PRAGMA foreign_keys=OFF` in conftest or just verify the tests pass with SQLite's default FK-off behavior (which is what the test_db fixture uses).

- [ ] **Step 5: Commit**

```bash
git add backend/app/repositories/classification_run_repository.py backend/tests/repositories/test_classification_run_repository.py
git commit -m "feat(classification): add ClassificationRunRepository"
```

---

## Task 7: Config, LLM dependency, and classification service

**Files:**
- Modify: `backend/app/config.py`
- Create: `backend/app/dependencies/llm.py`
- Create: `backend/app/services/classification/service.py`

- [ ] **Step 1: Add classifier settings to `config.py`**

Add these fields to the `Settings` class in `backend/app/config.py`:

```python
    # Classification LLM defaults
    CLASSIFIER_LLM_PROVIDER: str = "ollama_local"
    CLASSIFIER_LLM_MODEL: str = "qwen2.5:7b"

    # Ollama — local instance
    OLLAMA_LOCAL_BASE_URL: str = "http://localhost:11434/v1"

    # Ollama — cloud instance (https://ollama.com)
    # Leave OLLAMA_CLOUD_API_KEY empty to disable the ollama_cloud provider.
    OLLAMA_CLOUD_BASE_URL: str = "https://ollama.com/v1"
    OLLAMA_CLOUD_API_KEY: str = ""

    # Groq hosted inference
    GROQ_API_KEY: str = ""
```

- [ ] **Step 2: Update `OllamaAdapter` to accept `api_key`**

Open `backend/app/services/llm/ollama_adapter.py` and update it:

```python
# backend/app/services/llm/ollama_adapter.py
from app.services.llm.openai_adapter import OpenAIAdapter


class OllamaAdapter(OpenAIAdapter):
    """OpenAI-compatible adapter for Ollama (local or cloud).

    Local:  base_url="http://localhost:11434/v1", api_key="ollama" (dummy)
    Cloud:  base_url="https://ollama.com/v1",    api_key=<real key>
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434/v1",
        api_key: str = "ollama",
    ):
        super().__init__(api_key=api_key, base_url=base_url)
```

- [ ] **Step 3: Create `dependencies/llm.py`**

The registry uses distinct provider names (`ollama_local`, `ollama_cloud`) so the client can
select either target explicitly by name. `ollama_cloud` is only registered when the API key
is set; requesting it without a key raises `ValueError` at call time.

```python
# backend/app/dependencies/llm.py
from functools import lru_cache

from app.config import settings
from app.services.llm.ollama_adapter import OllamaAdapter
from app.services.llm.groq_adapter import GroqAdapter
from app.services.llm.registry import LLMRegistry


@lru_cache(maxsize=1)
def get_llm_registry() -> LLMRegistry:
    """Build and cache the LLM adapter registry from env config.

    Provider names are the routing keys clients pass in requests:
      ollama_local  — local Ollama instance (always registered)
      ollama_cloud  — Ollama Cloud (registered only if OLLAMA_CLOUD_API_KEY is set)
      groq          — Groq hosted inference (registered only if GROQ_API_KEY is set)
    """
    registry = LLMRegistry()
    registry.register(
        "ollama_local",
        OllamaAdapter(base_url=settings.OLLAMA_LOCAL_BASE_URL, api_key="ollama"),
    )
    if settings.OLLAMA_CLOUD_API_KEY:
        registry.register(
            "ollama_cloud",
            OllamaAdapter(
                base_url=settings.OLLAMA_CLOUD_BASE_URL,
                api_key=settings.OLLAMA_CLOUD_API_KEY,
            ),
        )
    if settings.GROQ_API_KEY:
        registry.register("groq", GroqAdapter(api_key=settings.GROQ_API_KEY))
    return registry
```

- [ ] **Step 3: Write failing service test**

```python
# backend/tests/services/classification/test_service.py
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
import pytest
from app.cdm.models import Block, BlockRole, Page, ParsedDocument
from app.cdm.classification import ClassifiedRegion
from app.services.classification.service import ClassificationService
from app.services.llm.types import CompletionResult, TokenUsage


def _make_doc() -> ParsedDocument:
    pages = [Page(index=i, block_ids=[f"b{i}"]) for i in range(3)]
    blocks = [
        Block(id=f"b{i}", role=BlockRole.PARAGRAPH, native_type="p",
              text=f"page {i}", page_index=i, reading_order=0)
        for i in range(3)
    ]
    return ParsedDocument(
        id="doc-1", source_document_id="s", parse_run_id="r",
        page_count=3, pages=pages, blocks=blocks,
    )


@pytest.mark.asyncio
async def test_service_execute_saves_regions():
    repo = MagicMock()
    repo.update_status = AsyncMock()
    repo.update_completed = AsyncMock()
    repo.save_regions = AsyncMock()

    llm_adapter = MagicMock()
    llm_adapter.complete = AsyncMock(return_value=CompletionResult(
        content='{"pages": [{"page": 0, "labels": {"x": "none"}}, {"page": 1, "labels": {"x": "start"}}, {"page": 2, "labels": {"x": "continue"}}]}',
        usage=TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150),
        latency_ms=200.0,
        model="qwen2.5:7b",
        provider="ollama",
    ))

    registry = MagicMock()
    registry.get.return_value = llm_adapter

    service = ClassificationService(repo=repo, llm_registry=registry)
    doc = _make_doc()

    await service.execute(
        run_id=uuid4(),
        doc=doc,
        labels=["x"],
        llm_provider="ollama_local",
        llm_model="qwen2.5:7b",
        batch_size=10,
        batch_overlap=3,
    )

    repo.update_status.assert_any_call(run_id=pytest.ANY, status="running")
    repo.save_regions.assert_called_once()
    saved_regions = repo.save_regions.call_args[1]["regions"]
    assert len(saved_regions) == 1
    assert saved_regions[0].label == "x"
    assert saved_regions[0].page_start == 1
    assert saved_regions[0].page_end == 2
    repo.update_completed.assert_called_once()
```

- [ ] **Step 4: Run test to confirm it fails**

```
uv run --directory backend python -m pytest tests/services/classification/test_service.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.services.classification.service'`

- [ ] **Step 5: Create the service**

```python
# backend/app/services/classification/service.py
from __future__ import annotations
import json
import logging
import time
from uuid import UUID

from pydantic import BaseModel

from app.cdm.classification import ClassifiedRegion
from app.cdm.models import ParsedDocument
from app.services.classification.assembler import (
    BatchPageResult,
    assemble_regions,
    resolve_page_statuses,
)
from app.services.classification.serializer import build_batches, serialize_pages
from app.services.llm.registry import LLMRegistry
from app.services.llm.types import LLMConfig

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a document classifier. Analyze the document pages provided and determine which labels apply to each page.

For each label, classify each page as:
- "start": this page begins a section matching this label
- "continue": this page continues a section from a previous page
- "none": this page does not contain this label

Return ONLY valid JSON in this exact format:
{
  "pages": [
    {"page": <page_index>, "labels": {"<label>": "start"|"continue"|"none", ...}},
    ...
  ]
}

Include every page index present in the document content.\
"""


class _PageResult(BaseModel):
    page: int
    labels: dict[str, str]


class _BatchLLMResponse(BaseModel):
    pages: list[_PageResult]


class ClassificationService:
    def __init__(self, repo: object, llm_registry: LLMRegistry) -> None:
        self.repo = repo
        self.llm_registry = llm_registry

    async def execute(
        self,
        run_id: UUID,
        doc: ParsedDocument,
        labels: list[str],
        llm_provider: str,
        llm_model: str,
        batch_size: int,
        batch_overlap: int,
    ) -> None:
        await self.repo.update_status(run_id=run_id, status="running")
        start = time.monotonic()
        total_input = 0
        total_output = 0

        try:
            adapter = self.llm_registry.get(llm_provider)
            config = LLMConfig(
                provider=llm_provider,
                model=llm_model,
                temperature=0.0,
                max_tokens=4096,
                json_mode=True,
            )
            labels_str = ", ".join(labels)
            batches = build_batches(doc.page_count, batch_size, batch_overlap)
            all_batch_results: list[list[BatchPageResult]] = []

            for batch_start, batch_end in batches:
                serialized = serialize_pages(doc, batch_start, batch_end)
                messages = [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            f"Labels to identify: {labels_str}\n\n"
                            f"Document pages:\n{serialized}"
                        ),
                    },
                ]
                result = await adapter.complete(messages, config)
                total_input += result.usage.prompt_tokens
                total_output += result.usage.completion_tokens

                parsed = _BatchLLMResponse.model_validate_json(result.content)
                batch_page_results = [
                    BatchPageResult(
                        page=p.page,
                        label_statuses=p.labels,
                        batch_start=batch_start,
                        batch_end=batch_end,
                    )
                    for p in parsed.pages
                ]
                all_batch_results.append(batch_page_results)

            resolved = resolve_page_statuses(all_batch_results)
            regions = assemble_regions(resolved, labels, doc)

            await self.repo.save_regions(run_id=run_id, regions=regions)
            duration_ms = int((time.monotonic() - start) * 1000)
            await self.repo.update_completed(
                run_id=run_id,
                input_tokens=total_input,
                output_tokens=total_output,
                duration_ms=duration_ms,
            )
        except Exception as exc:
            logger.exception("Classification run %s failed", run_id)
            await self.repo.update_status(run_id=run_id, status="failed", error=str(exc))
            raise
```

- [ ] **Step 6: Run service tests — expect PASS**

```
uv run --directory backend python -m pytest tests/services/classification/test_service.py -v
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/config.py backend/app/dependencies/llm.py backend/app/services/classification/service.py backend/tests/services/classification/test_service.py
git commit -m "feat(classification): add ClassificationService, LLM dependency, and config settings"
```

---

## Task 8: Schemas and router

**Files:**
- Create: `backend/app/schemas/classification.py`
- Create: `backend/app/routers/classification.py`

- [ ] **Step 1: Create `schemas/classification.py`**

```python
# backend/app/schemas/classification.py
from __future__ import annotations
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ClassificationRunCreateRequest(BaseModel):
    parse_run_id: UUID
    labels: list[str]
    llm_provider: str | None = None
    llm_model: str | None = None
    batch_size: int | None = None
    batch_overlap: int | None = None


class ClassificationRegionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    label: str
    page_start: int = Field(..., alias="pageStart")
    page_end: int = Field(..., alias="pageEnd")
    block_ids: list[str] = Field(..., alias="blockIds")
    confidence: float | None = None
    reasoning: str | None = None
    source: str


class ClassificationRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    parse_run_id: UUID = Field(..., alias="parseRunId")
    document_id: UUID = Field(..., alias="documentId")
    labels_requested: list[str] = Field(..., alias="labelsRequested")
    llm_provider: str = Field(..., alias="llmProvider")
    llm_model: str = Field(..., alias="llmModel")
    status: str
    error: str | None = None
    batch_size: int = Field(..., alias="batchSize")
    batch_overlap: int = Field(..., alias="batchOverlap")
    input_tokens: int | None = Field(None, alias="inputTokens")
    output_tokens: int | None = Field(None, alias="outputTokens")
    duration_ms: int | None = Field(None, alias="durationMs")
    created_at: datetime = Field(..., alias="createdAt")
    regions: list[ClassificationRegionResponse] = []
```

- [ ] **Step 2: Create `routers/classification.py`**

```python
# backend/app/routers/classification.py
"""Classification API — two routers mounted at different prefixes in main.py."""
import logging
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal, get_db
from app.dependencies.auth import get_current_active_user
from app.dependencies.llm import get_llm_registry
from app.models import User
from app.repositories.classification_run_repository import (
    ClassificationRunCreate,
    ClassificationRunRepository,
)
from app.repositories.parsed_document_repository import ParsedDocumentRepository
from app.repositories.document_repository import DocumentRepository
from app.schemas.classification import (
    ClassificationRegionResponse,
    ClassificationRunCreateRequest,
    ClassificationRunResponse,
)
from app.services.classification.service import ClassificationService
from app.services.llm.registry import LLMRegistry

logger = logging.getLogger(__name__)

# Mounted at /api/v1/documents
documents_router = APIRouter(prefix="/documents", tags=["classification"])

# Mounted at /api/v1/classification-runs
runs_router = APIRouter(prefix="/classification-runs", tags=["classification"])


async def _run_classification_background(
    run_id: UUID,
    parse_run_id: UUID,
    labels: list[str],
    llm_provider: str,
    llm_model: str,
    batch_size: int,
    batch_overlap: int,
) -> None:
    from app.cdm.models import ParsedDocument as CDMParsedDocument

    async with AsyncSessionLocal() as session:
        repo = ClassificationRunRepository(session)
        pd_repo = ParsedDocumentRepository(session)

        pd_orm = await pd_repo.get_by_run(parse_run_id)
        if pd_orm is None:
            await repo.update_status(run_id=run_id, status="failed", error="ParsedDocument not found")
            return

        doc = CDMParsedDocument.model_validate(pd_orm.content)
        registry = get_llm_registry()
        service = ClassificationService(repo=repo, llm_registry=registry)

        await service.execute(
            run_id=run_id,
            doc=doc,
            labels=labels,
            llm_provider=llm_provider,
            llm_model=llm_model,
            batch_size=batch_size,
            batch_overlap=batch_overlap,
        )


def _to_run_response(run, regions=None) -> ClassificationRunResponse:
    return ClassificationRunResponse(
        id=run.id,
        parseRunId=run.parse_run_id,
        documentId=run.document_id,
        labelsRequested=run.labels_requested,
        llmProvider=run.llm_provider,
        llmModel=run.llm_model,
        status=run.status,
        error=run.error,
        batchSize=run.batch_size,
        batchOverlap=run.batch_overlap,
        inputTokens=run.input_tokens,
        outputTokens=run.output_tokens,
        durationMs=run.duration_ms,
        createdAt=run.created_at,
        regions=[
            ClassificationRegionResponse(
                id=r.id,
                label=r.label,
                pageStart=r.page_start,
                pageEnd=r.page_end,
                blockIds=r.block_ids,
                confidence=r.confidence,
                reasoning=r.reasoning,
                source=r.source,
            )
            for r in (regions or [])
        ],
    )


@documents_router.post(
    "/{document_id}/classification-runs",
    response_model=ClassificationRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_classification_run(
    document_id: UUID,
    body: ClassificationRunCreateRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    doc_repo = DocumentRepository(db)
    document = await doc_repo.get_by_id(document_id, current_user.id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    llm_provider = body.llm_provider or settings.CLASSIFIER_LLM_PROVIDER
    llm_model = body.llm_model or settings.CLASSIFIER_LLM_MODEL
    batch_size = body.batch_size or 10
    batch_overlap = body.batch_overlap or 3

    repo = ClassificationRunRepository(db)
    run = await repo.create(ClassificationRunCreate(
        parse_run_id=body.parse_run_id,
        document_id=document_id,
        labels_requested=body.labels,
        llm_provider=llm_provider,
        llm_model=llm_model,
        batch_size=batch_size,
        batch_overlap=batch_overlap,
    ))

    background_tasks.add_task(
        _run_classification_background,
        run_id=run.id,
        parse_run_id=body.parse_run_id,
        labels=body.labels,
        llm_provider=llm_provider,
        llm_model=llm_model,
        batch_size=batch_size,
        batch_overlap=batch_overlap,
    )

    return _to_run_response(run)


@documents_router.get(
    "/{document_id}/classification-runs",
    response_model=list[ClassificationRunResponse],
)
async def list_document_classification_runs(
    document_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    doc_repo = DocumentRepository(db)
    document = await doc_repo.get_by_id(document_id, current_user.id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    repo = ClassificationRunRepository(db)
    runs = await repo.list_for_document(document_id)
    return [_to_run_response(r) for r in runs]


@runs_router.get("", response_model=list[ClassificationRunResponse])
async def list_all_classification_runs(
    project_id: UUID = Query(...),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    repo = ClassificationRunRepository(db)
    runs = await repo.list_for_project(project_id)
    return [_to_run_response(r) for r in runs]


@runs_router.get("/{run_id}", response_model=ClassificationRunResponse)
async def get_classification_run(
    run_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    repo = ClassificationRunRepository(db)
    run = await repo.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Classification run not found")
    regions = await repo.get_regions(run_id)
    return _to_run_response(run, regions)


@runs_router.delete("/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_classification_run(
    run_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    repo = ClassificationRunRepository(db)
    run = await repo.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Classification run not found")
    await repo.delete(run_id)
```

- [ ] **Step 3: Wire up in `main.py`**

Add to the imports in `backend/app/main.py`:
```python
from app.routers import classification
```

Add after the last `app.include_router(...)` call:
```python
app.include_router(classification.documents_router, prefix="/api/v1")
app.include_router(classification.runs_router, prefix="/api/v1")
```

- [ ] **Step 4: Verify the server starts cleanly**

```
uv run --directory backend uvicorn app.main:app --reload --port 8000
```

Expected: server starts, no import errors. Hit `http://localhost:8000/docs` and verify the classification endpoints appear.

Stop the server with Ctrl+C.

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/classification.py backend/app/routers/classification.py backend/app/main.py
git commit -m "feat(classification): add schemas, router, and wire up endpoints"
```

---

## Task 9: Frontend types and API client

**Files:**
- Create: `frontend/src/types/classification.ts`
- Create: `frontend/src/api/classification.ts`

- [ ] **Step 1: Create `types/classification.ts`**

```typescript
// frontend/src/types/classification.ts

export type ClassificationRunStatus = 'pending' | 'running' | 'completed' | 'failed'

export interface ClassificationRegion {
  id: string
  label: string
  pageStart: number
  pageEnd: number
  blockIds: string[]
  confidence: number | null
  reasoning: string | null
  source: 'llm' | 'human'
}

export interface ClassificationRun {
  id: string
  parseRunId: string
  documentId: string
  labelsRequested: string[]
  llmProvider: string
  llmModel: string
  status: ClassificationRunStatus
  error: string | null
  batchSize: number
  batchOverlap: number
  inputTokens: number | null
  outputTokens: number | null
  durationMs: number | null
  createdAt: string
  regions: ClassificationRegion[]
}

export interface ClassificationRunCreateRequest {
  parseRunId: string
  labels: string[]
  llmProvider?: string
  llmModel?: string
  batchSize?: number
  batchOverlap?: number
}
```

- [ ] **Step 2: Create `api/classification.ts`**

```typescript
// frontend/src/api/classification.ts
import apiClient from './client'
import type { ClassificationRun, ClassificationRunCreateRequest } from '@/types/classification'

export async function createClassificationRun(
  documentId: string,
  data: ClassificationRunCreateRequest,
): Promise<ClassificationRun> {
  const response = await apiClient.post<ClassificationRun>(
    `/documents/${documentId}/classification-runs`,
    {
      parse_run_id: data.parseRunId,
      labels: data.labels,
      llm_provider: data.llmProvider,
      llm_model: data.llmModel,
      batch_size: data.batchSize,
      batch_overlap: data.batchOverlap,
    },
  )
  return response.data
}

export async function listDocumentClassificationRuns(
  documentId: string,
): Promise<ClassificationRun[]> {
  const response = await apiClient.get<ClassificationRun[]>(
    `/documents/${documentId}/classification-runs`,
  )
  return response.data
}

export async function listAllClassificationRuns(
  projectId: string,
): Promise<ClassificationRun[]> {
  const response = await apiClient.get<ClassificationRun[]>(
    `/classification-runs?project_id=${projectId}`,
  )
  return response.data
}

export async function getClassificationRun(runId: string): Promise<ClassificationRun> {
  const response = await apiClient.get<ClassificationRun>(`/classification-runs/${runId}`)
  return response.data
}

export async function deleteClassificationRun(runId: string): Promise<void> {
  await apiClient.delete(`/classification-runs/${runId}`)
}
```

- [ ] **Step 3: Confirm TypeScript compiles**

```
npm --prefix frontend run build 2>&1 | tail -20
```

Expected: build succeeds (no type errors in these files — they're not imported yet).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/classification.ts frontend/src/api/classification.ts
git commit -m "feat(classification): add frontend types and API client"
```

---

## Task 10: Frontend hook

**Files:**
- Create: `frontend/src/hooks/useClassificationRuns.ts`

- [ ] **Step 1: Create the hook**

```typescript
// frontend/src/hooks/useClassificationRuns.ts
import { useCallback, useEffect, useRef, useState } from 'react'
import * as classificationApi from '@/api/classification'
import type { ClassificationRun, ClassificationRunStatus } from '@/types/classification'

const POLL_MS = 5000
const TERMINAL: ReadonlyArray<ClassificationRunStatus> = ['completed', 'failed']

function isTerminal(status: ClassificationRunStatus): boolean {
  return TERMINAL.includes(status)
}

interface UseClassificationRunsReturn {
  runs: ClassificationRun[]
  isLoading: boolean
  error: string | null
  refresh: () => void
  deleteRun: (runId: string) => Promise<void>
}

export function useClassificationRuns(projectId: string | null): UseClassificationRunsReturn {
  const [runs, setRuns] = useState<ClassificationRun[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [forcePolling, setForcePolling] = useState(false)
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const forceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const stopPolling = useCallback(() => {
    if (pollingRef.current !== null) {
      clearInterval(pollingRef.current)
      pollingRef.current = null
    }
  }, [])

  const fetchList = useCallback(
    async (id: string, silent = false) => {
      if (!silent) { setIsLoading(true); setError(null) }
      try {
        const data = await classificationApi.listAllClassificationRuns(id)
        setRuns(data)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch classification runs')
      } finally {
        if (!silent) setIsLoading(false)
      }
    },
    [],
  )

  useEffect(() => {
    if (!projectId) { setRuns([]); stopPolling(); return }
    void fetchList(projectId)
  }, [projectId, fetchList, stopPolling])

  useEffect(() => {
    if (!projectId) return
    const hasActive = runs.some((r) => !isTerminal(r.status))
    if (!hasActive && !forcePolling) { stopPolling(); return }
    if (pollingRef.current !== null) return
    pollingRef.current = setInterval(() => void fetchList(projectId, true), POLL_MS)
    return () => stopPolling()
  }, [projectId, runs, fetchList, stopPolling, forcePolling])

  useEffect(() => () => stopPolling(), [stopPolling])

  const refresh = useCallback(() => {
    if (!projectId) return
    void fetchList(projectId, true)
    setForcePolling(true)
    if (forceTimerRef.current !== null) clearTimeout(forceTimerRef.current)
    forceTimerRef.current = setTimeout(() => {
      setForcePolling(false)
      forceTimerRef.current = null
    }, 30_000)
  }, [projectId, fetchList])

  const deleteRun = useCallback(
    async (runId: string) => {
      await classificationApi.deleteClassificationRun(runId)
      if (projectId) void fetchList(projectId, true)
    },
    [projectId, fetchList],
  )

  return { runs, isLoading, error, refresh, deleteRun }
}

interface UseClassificationRunDetailReturn {
  run: ClassificationRun | null
  isLoading: boolean
  error: string | null
  refresh: () => void
}

export function useClassificationRunDetail(runId: string | null): UseClassificationRunDetailReturn {
  const [run, setRun] = useState<ClassificationRun | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const stopPolling = useCallback(() => {
    if (pollingRef.current !== null) { clearInterval(pollingRef.current); pollingRef.current = null }
  }, [])

  const fetchRun = useCallback(async (id: string, silent = false) => {
    if (!silent) { setIsLoading(true); setError(null) }
    try {
      const data = await classificationApi.getClassificationRun(id)
      setRun(data)
      return data
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch run')
      return null
    } finally {
      if (!silent) setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!runId) { setRun(null); stopPolling(); return }
    void fetchRun(runId)
  }, [runId, fetchRun, stopPolling])

  useEffect(() => {
    if (!runId) return
    if (run && isTerminal(run.status)) { stopPolling(); return }
    if (pollingRef.current !== null) return
    pollingRef.current = setInterval(() => void fetchRun(runId, true), POLL_MS)
    return () => stopPolling()
  }, [runId, run, fetchRun, stopPolling])

  useEffect(() => () => stopPolling(), [stopPolling])

  const refresh = useCallback(() => {
    if (runId) void fetchRun(runId, true)
  }, [runId, fetchRun])

  return { run, isLoading, error, refresh }
}
```

- [ ] **Step 2: Confirm TypeScript compiles**

```
npm --prefix frontend run build 2>&1 | tail -20
```

Expected: builds cleanly.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/hooks/useClassificationRuns.ts
git commit -m "feat(classification): add useClassificationRuns and useClassificationRunDetail hooks"
```

---

## Task 11: Reusable components

**Files:**
- Create: `frontend/src/components/classification/ClassificationRunStatusBadge.tsx`
- Create: `frontend/src/components/classification/ClassificationRegionCard.tsx`
- Create: `frontend/src/components/classification/ClassificationRegionList.tsx`
- Create: `frontend/src/components/classification/ClassificationRunForm.tsx`

- [ ] **Step 1: Create `ClassificationRunStatusBadge.tsx`**

```tsx
// frontend/src/components/classification/ClassificationRunStatusBadge.tsx
import { Badge } from '@/components/ui/badge'
import type { ClassificationRunStatus } from '@/types/classification'

const STATUS_STYLES: Record<ClassificationRunStatus, string> = {
  pending: 'bg-gray-100 text-gray-700',
  running: 'bg-blue-100 text-blue-700',
  completed: 'bg-green-100 text-green-700',
  failed: 'bg-red-100 text-red-700',
}

interface Props {
  status: ClassificationRunStatus
}

export function ClassificationRunStatusBadge({ status }: Props) {
  return (
    <Badge className={STATUS_STYLES[status]}>
      {status}
    </Badge>
  )
}
```

- [ ] **Step 2: Create `ClassificationRegionCard.tsx`**

```tsx
// frontend/src/components/classification/ClassificationRegionCard.tsx
import { useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import type { ClassificationRegion } from '@/types/classification'

interface Props {
  region: ClassificationRegion
}

export function ClassificationRegionCard({ region }: Props) {
  const [reasoningOpen, setReasoningOpen] = useState(false)

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base font-medium">{region.label}</CardTitle>
          <div className="flex items-center gap-2">
            {region.confidence !== null && (
              <Badge variant="outline">
                {(region.confidence * 100).toFixed(0)}% confidence
              </Badge>
            )}
            <span className="text-sm text-muted-foreground">
              Pages {region.pageStart + 1}–{region.pageEnd + 1}
            </span>
          </div>
        </div>
      </CardHeader>
      <CardContent className="text-sm text-muted-foreground space-y-2">
        <p>{region.blockIds.length} blocks</p>
        {region.reasoning && (
          <div>
            <button
              className="flex items-center gap-1 text-xs font-medium hover:text-foreground"
              onClick={() => setReasoningOpen((v) => !v)}
            >
              {reasoningOpen ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
              Reasoning
            </button>
            {reasoningOpen && (
              <p className="mt-1 text-xs leading-relaxed">{region.reasoning}</p>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
```

- [ ] **Step 3: Create `ClassificationRegionList.tsx`**

```tsx
// frontend/src/components/classification/ClassificationRegionList.tsx
import { ClassificationRegionCard } from './ClassificationRegionCard'
import type { ClassificationRegion } from '@/types/classification'

interface Props {
  regions: ClassificationRegion[]
}

export function ClassificationRegionList({ regions }: Props) {
  if (regions.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">No regions identified.</p>
    )
  }
  return (
    <div className="space-y-3">
      {regions.map((region) => (
        <ClassificationRegionCard key={region.id} region={region} />
      ))}
    </div>
  )
}
```

- [ ] **Step 4: Create `ClassificationRunForm.tsx`**

```tsx
// frontend/src/components/classification/ClassificationRunForm.tsx
import { useState } from 'react'
import { X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import { ChevronDown } from 'lucide-react'

const PROVIDER_OPTIONS = [
  { value: 'ollama_local', label: 'Ollama — local' },
  { value: 'ollama_cloud', label: 'Ollama — cloud' },
  { value: 'groq', label: 'Groq (hosted)' },
  { value: 'anthropic', label: 'Anthropic' },
]

const DEFAULT_MODELS: Record<string, string> = {
  ollama_local: 'qwen2.5:7b',
  ollama_cloud: 'qwen3:32b',
  groq: 'llama-3.3-70b-versatile',
  anthropic: 'claude-haiku-4-5-20251001',
}

export interface ClassificationRunFormValues {
  labels: string[]
  llmProvider: string
  llmModel: string
  batchSize: number
  batchOverlap: number
}

interface Props {
  defaultValues?: Partial<ClassificationRunFormValues>
  onSubmit: (values: ClassificationRunFormValues) => void
  isSubmitting?: boolean
  submitLabel?: string
}

export function ClassificationRunForm({
  defaultValues,
  onSubmit,
  isSubmitting,
  submitLabel = 'Start classification',
}: Props) {
  const [labels, setLabels] = useState<string[]>(defaultValues?.labels ?? [])
  const [labelInput, setLabelInput] = useState('')
  const [provider, setProvider] = useState(defaultValues?.llmProvider ?? 'ollama')
  const [model, setModel] = useState(defaultValues?.llmModel ?? DEFAULT_MODELS['ollama'])
  const [batchSize, setBatchSize] = useState(defaultValues?.batchSize ?? 10)
  const [batchOverlap, setBatchOverlap] = useState(defaultValues?.batchOverlap ?? 3)

  const addLabel = () => {
    const trimmed = labelInput.trim()
    if (trimmed && !labels.includes(trimmed)) {
      setLabels((prev) => [...prev, trimmed])
    }
    setLabelInput('')
  }

  const removeLabel = (l: string) => setLabels((prev) => prev.filter((x) => x !== l))

  const handleProviderChange = (p: string) => {
    setProvider(p)
    setModel(DEFAULT_MODELS[p] ?? '')
  }

  const handleSubmit = () => {
    if (labels.length === 0) return
    onSubmit({ labels, llmProvider: provider, llmModel: model, batchSize, batchOverlap })
  }

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <Label>Labels to classify</Label>
        <div className="flex gap-2">
          <Input
            placeholder="e.g. balance_sheet"
            value={labelInput}
            onChange={(e) => setLabelInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addLabel() } }}
          />
          <Button type="button" variant="outline" onClick={addLabel}>Add</Button>
        </div>
        {labels.length > 0 && (
          <div className="flex flex-wrap gap-2 mt-2">
            {labels.map((l) => (
              <Badge key={l} variant="secondary" className="flex items-center gap-1">
                {l}
                <button onClick={() => removeLabel(l)} className="ml-1 hover:text-destructive">
                  <X className="h-3 w-3" />
                </button>
              </Badge>
            ))}
          </div>
        )}
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label>LLM provider</Label>
          <Select value={provider} onValueChange={handleProviderChange}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {PROVIDER_OPTIONS.map((o) => (
                <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-2">
          <Label>Model</Label>
          <Input value={model} onChange={(e) => setModel(e.target.value)} />
        </div>
      </div>

      <Collapsible>
        <CollapsibleTrigger className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground">
          <ChevronDown className="h-4 w-4" />
          Advanced
        </CollapsibleTrigger>
        <CollapsibleContent className="mt-3 grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label>Batch size (pages)</Label>
            <Input
              type="number"
              min={1}
              value={batchSize}
              onChange={(e) => setBatchSize(Number(e.target.value))}
            />
          </div>
          <div className="space-y-2">
            <Label>Batch overlap (pages)</Label>
            <Input
              type="number"
              min={0}
              value={batchOverlap}
              onChange={(e) => setBatchOverlap(Number(e.target.value))}
            />
          </div>
        </CollapsibleContent>
      </Collapsible>

      <Button onClick={handleSubmit} disabled={labels.length === 0 || isSubmitting}>
        {isSubmitting ? 'Starting…' : submitLabel}
      </Button>
    </div>
  )
}
```

- [ ] **Step 5: Confirm TypeScript compiles**

```
npm --prefix frontend run build 2>&1 | tail -20
```

Expected: builds cleanly.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/classification/
git commit -m "feat(classification): add reusable classification components"
```

---

## Task 12: Pages, navigation, and routing

**Files:**
- Create: `frontend/src/pages/ClassificationPage.tsx`
- Create: `frontend/src/pages/NewClassificationRunPage.tsx`
- Create: `frontend/src/pages/ClassificationRunDetailPage.tsx`
- Modify: `frontend/src/config/navigation.ts`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Create `ClassificationPage.tsx`**

```tsx
// frontend/src/pages/ClassificationPage.tsx
import { useNavigate } from 'react-router-dom'
import { Plus, Trash2 } from 'lucide-react'
import { useProject } from '@/contexts/ProjectContext'
import { useClassificationRuns } from '@/hooks/useClassificationRuns'
import { ClassificationRunStatusBadge } from '@/components/classification/ClassificationRunStatusBadge'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { toast } from 'sonner'
import { formatDistanceToNow } from 'date-fns'

export default function ClassificationPage(): JSX.Element {
  const navigate = useNavigate()
  const { currentProject } = useProject()
  const { runs, isLoading, error, deleteRun } = useClassificationRuns(currentProject?.id ?? null)

  const handleDelete = async (runId: string) => {
    try {
      await deleteRun(runId)
      toast.success('Classification run deleted')
    } catch {
      toast.error('Failed to delete run')
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Classify</h1>
          <p className="text-muted-foreground mt-1">{currentProject?.name}</p>
        </div>
        <Button onClick={() => navigate('/classify/new')}>
          <Plus className="h-4 w-4 mr-2" />
          New classification run
        </Button>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {isLoading ? (
        <div className="space-y-3">
          {[0, 1, 2].map((i) => <Skeleton key={i} className="h-12 w-full" />)}
        </div>
      ) : runs.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">
          <p>No classification runs yet.</p>
          <Button className="mt-4" onClick={() => navigate('/classify/new')}>
            Start your first run
          </Button>
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Labels</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Provider / Model</TableHead>
              <TableHead>Duration</TableHead>
              <TableHead>Created</TableHead>
              <TableHead />
            </TableRow>
          </TableHeader>
          <TableBody>
            {runs.map((run) => (
              <TableRow
                key={run.id}
                className="cursor-pointer hover:bg-muted/50"
                onClick={() => navigate(`/classify/${run.id}`)}
              >
                <TableCell>
                  <span className="text-sm">{run.labelsRequested.join(', ')}</span>
                </TableCell>
                <TableCell>
                  <ClassificationRunStatusBadge status={run.status} />
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  {run.llmProvider} / {run.llmModel}
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  {run.durationMs !== null ? `${(run.durationMs / 1000).toFixed(1)}s` : '—'}
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  {formatDistanceToNow(new Date(run.createdAt), { addSuffix: true })}
                </TableCell>
                <TableCell onClick={(e) => e.stopPropagation()}>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => handleDelete(run.id)}
                  >
                    <Trash2 className="h-4 w-4 text-muted-foreground hover:text-destructive" />
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Create `NewClassificationRunPage.tsx`**

```tsx
// frontend/src/pages/NewClassificationRunPage.tsx
import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useProject } from '@/contexts/ProjectContext'
import { useDocuments } from '@/hooks/useDocuments'
import { useParseRuns } from '@/hooks/useParseRuns'
import { ClassificationRunForm } from '@/components/classification/ClassificationRunForm'
import type { ClassificationRunFormValues } from '@/components/classification/ClassificationRunForm'
import { createClassificationRun } from '@/api/classification'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { toast } from 'sonner'
import { formatDistanceToNow } from 'date-fns'
import { ChevronLeft } from 'lucide-react'

type Step = 'document' | 'parse-run' | 'configure'

export default function NewClassificationRunPage(): JSX.Element {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { currentProject } = useProject()

  const [step, setStep] = useState<Step>('document')
  const [documentSearch, setDocumentSearch] = useState('')
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(
    searchParams.get('documentId'),
  )
  const [selectedParseRunId, setSelectedParseRunId] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const { documents } = useDocuments(currentProject?.id ?? null)
  const { parseRuns } = useParseRuns(selectedDocumentId)

  const filteredDocuments = documents.filter((d) =>
    d.title.toLowerCase().includes(documentSearch.toLowerCase()),
  )

  const handleDocumentSelect = (id: string) => {
    setSelectedDocumentId(id)
    setSelectedParseRunId(null)
    setStep('parse-run')
  }

  const handleParseRunSelect = (id: string) => {
    setSelectedParseRunId(id)
    setStep('configure')
  }

  const handleSubmit = async (values: ClassificationRunFormValues) => {
    if (!selectedDocumentId || !selectedParseRunId) return
    setIsSubmitting(true)
    try {
      const run = await createClassificationRun(selectedDocumentId, {
        parseRunId: selectedParseRunId,
        labels: values.labels,
        llmProvider: values.llmProvider,
        llmModel: values.llmModel,
        batchSize: values.batchSize,
        batchOverlap: values.batchOverlap,
      })
      toast.success('Classification started')
      navigate(`/classify/${run.id}`)
    } catch (err) {
      toast.error('Failed to start classification', {
        description: err instanceof Error ? err.message : 'An error occurred',
      })
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => navigate('/classify')}>
          <ChevronLeft className="h-4 w-4" />
        </Button>
        <h1 className="text-2xl font-bold">New classification run</h1>
      </div>

      {/* Step 1: Select document */}
      <div className={step !== 'document' ? 'opacity-50 pointer-events-none' : ''}>
        <h2 className="text-lg font-medium mb-3">
          {step !== 'document' && selectedDocumentId
            ? `Document: ${documents.find((d) => d.id === selectedDocumentId)?.title}`
            : '1. Select document'}
        </h2>
        {step === 'document' && (
          <div className="space-y-3">
            <Input
              placeholder="Search documents…"
              value={documentSearch}
              onChange={(e) => setDocumentSearch(e.target.value)}
            />
            <div className="border rounded-md divide-y max-h-64 overflow-y-auto">
              {filteredDocuments.map((doc) => (
                <button
                  key={doc.id}
                  className="w-full text-left px-4 py-3 hover:bg-muted/50 text-sm"
                  onClick={() => handleDocumentSelect(doc.id)}
                >
                  {doc.title}
                </button>
              ))}
              {filteredDocuments.length === 0 && (
                <p className="px-4 py-3 text-sm text-muted-foreground">No documents found.</p>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Step 2: Select parse run */}
      {(step === 'parse-run' || step === 'configure') && (
        <div className={step !== 'parse-run' ? 'opacity-50 pointer-events-none' : ''}>
          <h2 className="text-lg font-medium mb-3">
            {step !== 'parse-run' && selectedParseRunId
              ? `Parse run: ${parseRuns.find((r) => r.id === selectedParseRunId)?.parser}`
              : '2. Select parse run'}
          </h2>
          {step === 'parse-run' && (
            <RadioGroup
              value={selectedParseRunId ?? ''}
              onValueChange={handleParseRunSelect}
              className="space-y-2"
            >
              {parseRuns
                .filter((r) => r.status === 'succeeded' || r.status === 'partial')
                .map((run) => (
                  <div key={run.id} className="flex items-center gap-3 border rounded-md px-4 py-3">
                    <RadioGroupItem value={run.id} id={run.id} />
                    <Label htmlFor={run.id} className="flex-1 cursor-pointer">
                      <span className="font-medium">{run.parser}</span>
                      <span className="text-sm text-muted-foreground ml-2">
                        {run.finishedAt
                          ? formatDistanceToNow(new Date(run.finishedAt), { addSuffix: true })
                          : ''}
                      </span>
                    </Label>
                  </div>
                ))}
              {parseRuns.filter((r) => r.status === 'succeeded' || r.status === 'partial').length === 0 && (
                <Alert>
                  <AlertDescription>No completed parse runs for this document.</AlertDescription>
                </Alert>
              )}
            </RadioGroup>
          )}
        </div>
      )}

      {/* Step 3: Configure */}
      {step === 'configure' && (
        <div>
          <h2 className="text-lg font-medium mb-3">3. Configure labels and model</h2>
          <ClassificationRunForm onSubmit={handleSubmit} isSubmitting={isSubmitting} />
        </div>
      )}
    </div>
  )
}
```

> **Note:** `useParseRuns` returns `ParseRunListItem` which has `parser`, `status`, `finishedAt` (camelCase from the schema alias). Check `types/cdm.ts` for the exact field names and adjust the JSX if needed.

- [ ] **Step 3: Create `ClassificationRunDetailPage.tsx`**

```tsx
// frontend/src/pages/ClassificationRunDetailPage.tsx
import { useNavigate, useParams } from 'react-router-dom'
import { useClassificationRunDetail } from '@/hooks/useClassificationRuns'
import { ClassificationRunStatusBadge } from '@/components/classification/ClassificationRunStatusBadge'
import { ClassificationRegionList } from '@/components/classification/ClassificationRegionList'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { ChevronLeft, RotateCw } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'

export default function ClassificationRunDetailPage(): JSX.Element {
  const { runId } = useParams<{ runId: string }>()
  const navigate = useNavigate()
  const { run, isLoading, error } = useClassificationRunDetail(runId ?? null)

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-4 w-48" />
        <Skeleton className="h-32 w-full" />
      </div>
    )
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    )
  }

  if (!run) return <></>

  const handleRerun = () => {
    navigate(`/classify/new?documentId=${run.documentId}`)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => navigate('/classify')}>
          <ChevronLeft className="h-4 w-4" />
        </Button>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold">Classification run</h1>
            <ClassificationRunStatusBadge status={run.status} />
          </div>
          <p className="text-muted-foreground text-sm mt-1">
            {run.llmProvider} / {run.llmModel} ·{' '}
            {formatDistanceToNow(new Date(run.createdAt), { addSuffix: true })}
          </p>
        </div>
        <Button variant="outline" onClick={handleRerun}>
          <RotateCw className="h-4 w-4 mr-2" />
          Re-run
        </Button>
      </div>

      <div className="grid grid-cols-4 gap-4 text-sm">
        <div>
          <p className="text-muted-foreground">Labels</p>
          <p className="font-medium">{run.labelsRequested.join(', ')}</p>
        </div>
        <div>
          <p className="text-muted-foreground">Regions found</p>
          <p className="font-medium">{run.regions.length}</p>
        </div>
        <div>
          <p className="text-muted-foreground">Tokens</p>
          <p className="font-medium">
            {run.inputTokens !== null ? `${run.inputTokens} in / ${run.outputTokens} out` : '—'}
          </p>
        </div>
        <div>
          <p className="text-muted-foreground">Duration</p>
          <p className="font-medium">
            {run.durationMs !== null ? `${(run.durationMs / 1000).toFixed(1)}s` : '—'}
          </p>
        </div>
      </div>

      {run.error && (
        <Alert variant="destructive">
          <AlertDescription>{run.error}</AlertDescription>
        </Alert>
      )}

      {run.status === 'running' && (
        <p className="text-sm text-muted-foreground animate-pulse">
          Classification in progress…
        </p>
      )}

      {run.status === 'completed' && (
        <section>
          <h2 className="text-lg font-medium mb-3">Identified regions</h2>
          <ClassificationRegionList regions={run.regions} />
        </section>
      )}
    </div>
  )
}
```

- [ ] **Step 4: Add navigation item to `navigation.ts`**

Open `frontend/src/config/navigation.ts`. Add after the `Extraction` entry:

```typescript
  { label: 'Classify', href: '/classify', icon: Tags, activeColor: 'border-l-pink-500' },
```

And add `Tags` to the import from lucide-react at line 1:

```typescript
import { LayoutDashboard, FolderKanban, FileText, Database, BarChart3, Settings, FileSearch, Bot, HardDrive, ArrowUpFromLine, Tags } from 'lucide-react'
```

- [ ] **Step 5: Add routes to `App.tsx`**

Add imports at the top of `frontend/src/App.tsx`:

```typescript
import ClassificationPage from './pages/ClassificationPage'
import NewClassificationRunPage from './pages/NewClassificationRunPage'
import ClassificationRunDetailPage from './pages/ClassificationRunDetailPage'
```

Add inside the `children` array (after the `extraction` route):

```typescript
          {
            path: 'classify',
            element: <ClassificationPage />,
            handle: { breadcrumb: 'Classify' },
          },
          {
            path: 'classify/new',
            element: <NewClassificationRunPage />,
            handle: { breadcrumb: 'New Classification Run' },
          },
          {
            path: 'classify/:runId',
            element: <ClassificationRunDetailPage />,
            handle: { breadcrumb: 'Classification Run' },
          },
```

- [ ] **Step 6: Build and confirm no TypeScript errors**

```
npm --prefix frontend run build 2>&1 | tail -30
```

Expected: build succeeds with no errors.

- [ ] **Step 7: Start dev server and manually verify**

```
npm --prefix frontend run dev
```

Open http://localhost:5173 and verify:
1. "Classify" appears in the left navigation sidebar
2. Clicking it shows the classification list page (empty state with "Start your first run")
3. Clicking "New classification run" opens the wizard — step 1 shows the document list
4. Selecting a document advances to parse run selection
5. Selecting a parse run advances to the config form with label input, provider/model selects, and advanced batch settings
6. Submitting navigates to the detail page showing `status: pending` then `running`
7. Detail page auto-polls and updates when the run completes

- [ ] **Step 8: Commit**

```bash
git add frontend/src/pages/ClassificationPage.tsx frontend/src/pages/NewClassificationRunPage.tsx frontend/src/pages/ClassificationRunDetailPage.tsx frontend/src/config/navigation.ts frontend/src/App.tsx
git commit -m "feat(classification): add classification pages, navigation, and routing"
```

---

## Final integration check

- [ ] Run all backend tests to catch any regressions

```
uv run --directory backend python -m pytest -o "addopts=" -v 2>&1 | tail -30
```

- [ ] Run frontend lint

```
npm --prefix frontend run lint
```

- [ ] Create a GitHub issue and link it to this plan before beginning implementation. The issue title should be: **"feat: document classification workload"** with acceptance criteria derived from the spec at `docs/superpowers/specs/2026-05-04-document-classification-design.md`.
