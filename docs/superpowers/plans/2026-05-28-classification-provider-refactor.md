# Classification Provider Refactor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor classification to be provider-agnostic via a `ClassificationPort` protocol, replacing LLM-specific DB columns with `classifier_type`/`classifier_config` and replacing custom LLM UI with the shared `PromptConfigEditor`.

**Architecture:** A `ClassificationPort` protocol defines `classify(doc, labels) -> ClassificationResult`. `LLMClassifier` implements it and delegates to the existing `LLMRegistry`/adapters. `ClassificationService` becomes lifecycle-only. A `classifier_factory.py` module builds the right classifier from `classifier_type` + `classifier_config`. The DB drops `llm_provider`/`llm_model`/`batch_size`/`batch_overlap` in favour of two columns.

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy 2.0 / Alembic / Pydantic v2 — React 18 / TypeScript / shadcn/ui

**Spec:** `docs/superpowers/specs/2026-05-28-classification-provider-refactor-design.md`

---

## File Map

**New backend files:**
- `backend/app/services/classification/port.py` — `ClassificationPort` protocol + `ClassificationResult`
- `backend/app/services/classification/llm_classifier.py` — `LLMClassifier` (batching loop from service.py)
- `backend/app/services/classification/llamaindex_split_classifier.py` — skeleton
- `backend/app/services/classification/classifier_factory.py` — `build_classifier()` + `_resolve_byok_provider()`
- `backend/alembic/versions/<rev>_classification_provider_refactor.py` — data migration

**New test files:**
- `backend/tests/services/classification/test_llm_classifier.py`
- `backend/tests/services/classification/test_classifier_factory.py`

**Modified backend files:**
- `backend/app/services/classification/service.py`
- `backend/app/models/classification_run.py`
- `backend/app/repositories/classification_run_repository.py`
- `backend/app/schemas/classification.py`
- `backend/app/routers/classification.py`

**Deleted test file:**
- `backend/tests/routers/test_classification_key_resolution.py` — replaced by `test_classifier_factory.py`

**Updated test files:**
- `backend/tests/services/classification/test_service.py`
- `backend/tests/repositories/test_classification_run_repository.py`
- `backend/tests/routers/test_classification_router.py`

**Modified frontend files:**
- `frontend/src/types/classification.ts`
- `frontend/src/api/classification.ts`
- `frontend/src/components/classification/ClassificationRunForm.tsx`
- `frontend/src/pages/NewClassificationRunPage.tsx`
- `frontend/src/pages/ClassificationRunDetailPage.tsx`

---

## Task 1: ClassificationPort protocol

**Files:**
- Create: `backend/app/services/classification/port.py`

- [ ] **Step 1: Write the file**

```python
# backend/app/services/classification/port.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol

from app.cdm.classification import ClassifiedRegion
from app.cdm.models import ParsedDocument


@dataclass
class ClassificationResult:
    regions: list[ClassifiedRegion]
    input_tokens: int = 0
    output_tokens: int = 0


class ClassificationPort(Protocol):
    async def classify(
        self,
        doc: ParsedDocument,
        labels: list[str],
    ) -> ClassificationResult: ...
```

- [ ] **Step 2: Verify the import**

```
uv run --directory backend python -c "from app.services.classification.port import ClassificationPort, ClassificationResult; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/classification/port.py
git commit -m "feat(classification): add ClassificationPort protocol and ClassificationResult"
```

---

## Task 2: LLMClassifier

**Files:**
- Create: `backend/app/services/classification/llm_classifier.py`
- Create: `backend/tests/services/classification/test_llm_classifier.py`

The batching loop, system prompt constant, `_PageResult`, and `_BatchLLMResponse` move verbatim from `service.py`. `service.py` is not touched in this task.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/services/classification/test_llm_classifier.py
from unittest.mock import AsyncMock, MagicMock
import pytest
from app.cdm.models import Block, BlockRole, Page, ParsedDocument
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


def _make_adapter(content: str) -> MagicMock:
    adapter = MagicMock()
    adapter.complete = AsyncMock(return_value=CompletionResult(
        content=content,
        usage=TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150),
        latency_ms=200.0, model="qwen2.5:7b", provider="ollama",
    ))
    return adapter


@pytest.mark.asyncio
async def test_llm_classifier_returns_regions_and_tokens():
    from app.services.classification.llm_classifier import LLMClassifier
    adapter = _make_adapter(
        '{"pages":['
        '{"page":0,"labels":{"x":"none"}},'
        '{"page":1,"labels":{"x":"start"}},'
        '{"page":2,"labels":{"x":"continue"}}'
        ']}'
    )
    registry = MagicMock()
    registry.get.return_value = adapter
    classifier = LLMClassifier(
        llm_registry=registry, provider="ollama_local", model="qwen2.5:7b",
        batch_size=10, batch_overlap=3,
    )
    result = await classifier.classify(_make_doc(), ["x"])
    assert len(result.regions) == 1
    assert result.regions[0].label == "x"
    assert result.regions[0].page_start == 1
    assert result.regions[0].page_end == 2
    assert result.input_tokens == 100
    assert result.output_tokens == 50


@pytest.mark.asyncio
async def test_llm_classifier_uses_custom_system_prompt():
    from app.services.classification.llm_classifier import LLMClassifier
    adapter = _make_adapter(
        '{"pages":[{"page":0,"labels":{"x":"none"}},{"page":1,"labels":{"x":"none"}},{"page":2,"labels":{"x":"none"}}]}'
    )
    registry = MagicMock()
    registry.get.return_value = adapter
    classifier = LLMClassifier(
        llm_registry=registry, provider="ollama_local", model="qwen2.5:7b",
        batch_size=10, batch_overlap=3, system_prompt="Custom prompt",
    )
    await classifier.classify(_make_doc(), ["x"])
    messages = adapter.complete.call_args[0][0]
    assert messages[0]["content"] == "Custom prompt"


@pytest.mark.asyncio
async def test_llm_classifier_threads_temperature_and_max_tokens():
    from app.services.classification.llm_classifier import LLMClassifier
    adapter = _make_adapter(
        '{"pages":[{"page":0,"labels":{"x":"none"}},{"page":1,"labels":{"x":"none"}},{"page":2,"labels":{"x":"none"}}]}'
    )
    registry = MagicMock()
    registry.get.return_value = adapter
    classifier = LLMClassifier(
        llm_registry=registry, provider="ollama_local", model="qwen2.5:7b",
        batch_size=10, batch_overlap=3, temperature=0.7, max_tokens=2048,
    )
    await classifier.classify(_make_doc(), ["x"])
    config = adapter.complete.call_args[0][1]
    assert config.temperature == 0.7
    assert config.max_tokens == 2048
```

- [ ] **Step 2: Run tests to confirm they fail**

```
uv run --directory backend python -m pytest tests/services/classification/test_llm_classifier.py -v
```

Expected: `ImportError` — `llm_classifier` does not exist yet.

- [ ] **Step 3: Write the implementation**

```python
# backend/app/services/classification/llm_classifier.py
from __future__ import annotations
import logging

from pydantic import BaseModel

from app.cdm.models import ParsedDocument
from app.services.classification.assembler import (
    BatchPageResult, assemble_regions, resolve_page_statuses,
)
from app.services.classification.port import ClassificationPort, ClassificationResult
from app.services.classification.serializer import build_batches, serialize_pages
from app.services.llm.registry import LLMRegistry
from app.services.llm.types import LLMConfig

logger = logging.getLogger(__name__)

_DEFAULT_SYSTEM_PROMPT = """\
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


class LLMClassifier:
    def __init__(
        self,
        llm_registry: LLMRegistry,
        provider: str,
        model: str,
        batch_size: int = 10,
        batch_overlap: int = 3,
        system_prompt: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> None:
        self.llm_registry = llm_registry
        self.provider = provider
        self.model = model
        self.batch_size = batch_size
        self.batch_overlap = batch_overlap
        self.system_prompt = system_prompt or _DEFAULT_SYSTEM_PROMPT
        self.temperature = temperature
        self.max_tokens = max_tokens

    async def classify(
        self, doc: ParsedDocument, labels: list[str]
    ) -> ClassificationResult:
        adapter = self.llm_registry.get(self.provider)
        config = LLMConfig(
            provider=self.provider,
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            json_mode=True,
        )
        labels_str = ", ".join(labels)
        batches = build_batches(doc.page_count, self.batch_size, self.batch_overlap)
        all_batch_results: list[list[BatchPageResult]] = []
        total_input = 0
        total_output = 0

        for batch_start, batch_end in batches:
            serialized = serialize_pages(doc, batch_start, batch_end)
            messages = [
                {"role": "system", "content": self.system_prompt},
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
        return ClassificationResult(
            regions=regions, input_tokens=total_input, output_tokens=total_output,
        )
```

- [ ] **Step 4: Run tests to confirm they pass**

```
uv run --directory backend python -m pytest tests/services/classification/test_llm_classifier.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/classification/llm_classifier.py backend/tests/services/classification/test_llm_classifier.py
git commit -m "feat(classification): add LLMClassifier implementing ClassificationPort"
```

---

## Task 3: LlamaIndexSplitClassifier skeleton

**Files:**
- Create: `backend/app/services/classification/llamaindex_split_classifier.py`

- [ ] **Step 1: Write the skeleton**

```python
# backend/app/services/classification/llamaindex_split_classifier.py
from app.cdm.models import ParsedDocument
from app.services.classification.port import ClassificationResult


class LlamaIndexSplitClassifier:
    def __init__(self, classifier_config: dict) -> None:
        self.classifier_config = classifier_config

    async def classify(
        self, doc: ParsedDocument, labels: list[str]
    ) -> ClassificationResult:
        raise NotImplementedError(
            "LlamaIndexSplitClassifier is not yet implemented. "
            "Select classifier_type='llm' to use the LLM-based classifier."
        )
```

- [ ] **Step 2: Verify import**

```
uv run --directory backend python -c "from app.services.classification.llamaindex_split_classifier import LlamaIndexSplitClassifier; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/classification/llamaindex_split_classifier.py
git commit -m "feat(classification): add LlamaIndexSplitClassifier skeleton"
```

---

## Task 4: Thin ClassificationService + update service test

**Files:**
- Modify: `backend/app/services/classification/service.py`
- Modify: `backend/tests/services/classification/test_service.py`

- [ ] **Step 1: Update the test**

Replace the entire contents of `backend/tests/services/classification/test_service.py`:

```python
# backend/tests/services/classification/test_service.py
from unittest.mock import ANY, AsyncMock, MagicMock
from uuid import uuid4
import pytest
from app.cdm.classification import ClassifiedRegion
from app.cdm.models import Block, BlockRole, Page, ParsedDocument
from app.services.classification.port import ClassificationResult


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
    from app.services.classification.service import ClassificationService

    repo = MagicMock()
    repo.update_status = AsyncMock()
    repo.update_completed = AsyncMock()
    repo.save_regions = AsyncMock()

    regions = [ClassifiedRegion(label="x", page_start=1, page_end=2, block_ids=["b1"])]
    classifier = MagicMock()
    classifier.classify = AsyncMock(return_value=ClassificationResult(
        regions=regions, input_tokens=100, output_tokens=50,
    ))

    service = ClassificationService(repo=repo, classifier=classifier)
    await service.execute(run_id=uuid4(), doc=_make_doc(), labels=["x"])

    repo.update_status.assert_any_call(run_id=ANY, status="running")
    repo.save_regions.assert_called_once()
    assert repo.save_regions.call_args[1]["regions"][0].label == "x"
    call_kwargs = repo.update_completed.call_args[1]
    assert call_kwargs["input_tokens"] == 100
    assert call_kwargs["output_tokens"] == 50


@pytest.mark.asyncio
async def test_service_execute_marks_failed_on_error():
    from app.services.classification.service import ClassificationService

    repo = MagicMock()
    repo.update_status = AsyncMock()
    repo.update_completed = AsyncMock()
    repo.save_regions = AsyncMock()

    classifier = MagicMock()
    classifier.classify = AsyncMock(side_effect=RuntimeError("boom"))

    service = ClassificationService(repo=repo, classifier=classifier)
    with pytest.raises(RuntimeError):
        await service.execute(run_id=uuid4(), doc=_make_doc(), labels=["x"])

    repo.update_status.assert_any_call(run_id=ANY, status="failed", error="boom")
```

- [ ] **Step 2: Run test to confirm it fails**

```
uv run --directory backend python -m pytest tests/services/classification/test_service.py -v
```

Expected: FAIL — `ClassificationService` still takes `llm_registry`.

- [ ] **Step 3: Rewrite service.py**

Replace the entire contents of `backend/app/services/classification/service.py`:

```python
# backend/app/services/classification/service.py
from __future__ import annotations
import logging
import time
from uuid import UUID

from app.cdm.models import ParsedDocument
from app.services.classification.port import ClassificationPort

logger = logging.getLogger(__name__)


class ClassificationService:
    def __init__(self, repo: object, classifier: ClassificationPort) -> None:
        self.repo = repo
        self.classifier = classifier

    async def execute(
        self,
        run_id: UUID,
        doc: ParsedDocument,
        labels: list[str],
    ) -> None:
        await self.repo.update_status(run_id=run_id, status="running")
        start = time.monotonic()

        try:
            result = await self.classifier.classify(doc, labels)
            await self.repo.save_regions(run_id=run_id, regions=result.regions)
            duration_ms = int((time.monotonic() - start) * 1000)
            await self.repo.update_completed(
                run_id=run_id,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                duration_ms=duration_ms,
            )
        except Exception as exc:
            logger.exception("Classification run %s failed", run_id)
            await self.repo.update_status(run_id=run_id, status="failed", error=str(exc))
            raise
```

- [ ] **Step 4: Run tests**

```
uv run --directory backend python -m pytest tests/services/classification/test_service.py -v
```

Expected: 2 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/classification/service.py backend/tests/services/classification/test_service.py
git commit -m "feat(classification): thin ClassificationService to delegate via ClassificationPort"
```

---

## Task 5: classifier_factory + replace key resolution tests

**Files:**
- Create: `backend/app/services/classification/classifier_factory.py`
- Create: `backend/tests/services/classification/test_classifier_factory.py`
- Delete: `backend/tests/routers/test_classification_key_resolution.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/services/classification/test_classifier_factory.py
from unittest.mock import patch
import pytest
from app.services.classification.classifier_factory import (
    _resolve_byok_provider,
    build_classifier,
)
from app.services.classification.llm_classifier import LLMClassifier
from app.services.classification.llamaindex_split_classifier import LlamaIndexSplitClassifier


def test_resolve_byok_groq():
    assert _resolve_byok_provider("llm", {"provider": "groq"}) == "groq"


def test_resolve_byok_ollama_cloud():
    assert _resolve_byok_provider("llm", {"provider": "ollama_cloud"}) == "ollama_cloud"


def test_resolve_byok_anthropic():
    assert _resolve_byok_provider("llm", {"provider": "anthropic"}) == "anthropic"


def test_resolve_byok_openai():
    assert _resolve_byok_provider("llm", {"provider": "openai"}) == "openai"


def test_resolve_byok_ollama_local_returns_none():
    assert _resolve_byok_provider("llm", {"provider": "ollama_local"}) is None


def test_resolve_byok_non_llm_returns_none():
    assert _resolve_byok_provider("llamaindex_split", {}) is None


def test_build_classifier_llm_returns_llm_classifier():
    with patch("app.services.classification.classifier_factory.settings") as mock:
        mock.OLLAMA_LOCAL_BASE_URL = "http://localhost:11434/v1"
        mock.OLLAMA_CLOUD_BASE_URL = "https://ollama.com/v1"
        classifier = build_classifier(
            "llm",
            {"provider": "ollama_local", "model": "qwen2.5:7b",
             "batch_size": 10, "batch_overlap": 3},
            api_key=None,
        )
    assert isinstance(classifier, LLMClassifier)
    assert classifier.provider == "ollama_local"
    assert classifier.model == "qwen2.5:7b"
    assert classifier.batch_size == 10
    assert classifier.batch_overlap == 3


def test_build_classifier_llm_threads_llm_config():
    with patch("app.services.classification.classifier_factory.settings") as mock:
        mock.OLLAMA_LOCAL_BASE_URL = "http://localhost:11434/v1"
        mock.OLLAMA_CLOUD_BASE_URL = "https://ollama.com/v1"
        classifier = build_classifier(
            "llm",
            {
                "provider": "ollama_local",
                "model": "qwen2.5:7b",
                "llm_config": {"system_prompt": "Custom", "temperature": 0.5, "max_tokens": 2048},
            },
            api_key=None,
        )
    assert isinstance(classifier, LLMClassifier)
    assert classifier.system_prompt == "Custom"
    assert classifier.temperature == 0.5
    assert classifier.max_tokens == 2048


def test_build_classifier_llamaindex_split():
    classifier = build_classifier("llamaindex_split", {"chunk_size": 512}, api_key=None)
    assert isinstance(classifier, LlamaIndexSplitClassifier)


def test_build_classifier_unknown_raises():
    with pytest.raises(ValueError, match="Unknown classifier type"):
        build_classifier("nonexistent", {}, api_key=None)
```

- [ ] **Step 2: Run tests to confirm they fail**

```
uv run --directory backend python -m pytest tests/services/classification/test_classifier_factory.py -v
```

Expected: `ImportError` — `classifier_factory` does not exist yet.

- [ ] **Step 3: Write classifier_factory.py**

```python
# backend/app/services/classification/classifier_factory.py
from app.config import settings
from app.services.classification.llm_classifier import LLMClassifier
from app.services.classification.llamaindex_split_classifier import LlamaIndexSplitClassifier
from app.services.classification.port import ClassificationPort
from app.services.llm.factory import create_adapter
from app.services.llm.registry import LLMRegistry

_LLM_BYOK_PROVIDERS = {"groq", "ollama_cloud", "anthropic", "openai"}


def _resolve_byok_provider(classifier_type: str, classifier_config: dict) -> str | None:
    """Return the BYOK provider ID if an API key is required, else None."""
    if classifier_type == "llm":
        provider = classifier_config.get("provider", "")
        return provider if provider in _LLM_BYOK_PROVIDERS else None
    return None


def _build_llm_registry(provider: str, api_key: str | None) -> LLMRegistry:
    from app.services.llm.groq_adapter import GroqAdapter

    registry = LLMRegistry()
    if provider == "groq":
        if api_key:
            registry.register("groq", GroqAdapter(api_key=api_key))
    else:
        effective_key = api_key if api_key is not None else "ollama"
        try:
            adapter = create_adapter(provider, effective_key)
            registry.register(provider, adapter)
        except ValueError:
            pass
    return registry


def build_classifier(
    classifier_type: str,
    classifier_config: dict,
    api_key: str | None,
) -> ClassificationPort:
    if classifier_type == "llm":
        provider = classifier_config.get("provider", settings.CLASSIFIER_LLM_PROVIDER)
        model = classifier_config.get("model", settings.CLASSIFIER_LLM_MODEL)
        batch_size = int(classifier_config.get("batch_size", 10))
        batch_overlap = int(classifier_config.get("batch_overlap", 3))
        llm_config = classifier_config.get("llm_config") or {}
        system_prompt: str | None = llm_config.get("system_prompt")
        temperature: float = float(llm_config.get("temperature", 0.0))
        max_tokens: int = int(llm_config.get("max_tokens", 4096))
        registry = _build_llm_registry(provider, api_key)
        return LLMClassifier(
            llm_registry=registry,
            provider=provider,
            model=model,
            batch_size=batch_size,
            batch_overlap=batch_overlap,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    elif classifier_type == "llamaindex_split":
        return LlamaIndexSplitClassifier(classifier_config)
    else:
        raise ValueError(
            f"Unknown classifier type: {classifier_type!r}. "
            "Supported: 'llm', 'llamaindex_split'"
        )
```

- [ ] **Step 4: Run tests**

```
uv run --directory backend python -m pytest tests/services/classification/test_classifier_factory.py -v
```

Expected: all PASS.

- [ ] **Step 5: Delete old key resolution tests**

```bash
git rm backend/tests/routers/test_classification_key_resolution.py
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/classification/classifier_factory.py backend/tests/services/classification/test_classifier_factory.py
git commit -m "feat(classification): add classifier_factory replacing _build_llm_registry in router"
```

---

## Task 6: DB model + Alembic migration

**Files:**
- Modify: `backend/app/models/classification_run.py`
- Create: Alembic migration

- [ ] **Step 1: Update the ORM model**

Replace the entire contents of `backend/app/models/classification_run.py`:

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
    classifier_type: Mapped[str] = mapped_column(Text, nullable=False)
    classifier_config: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
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

- [ ] **Step 2: Generate a blank migration**

```
uv run --directory backend alembic revision -m "classification_provider_refactor"
```

Open the generated file in `backend/alembic/versions/`. Replace the `upgrade()` and `downgrade()` bodies:

```python
def upgrade() -> None:
    # Add new columns as nullable first
    op.add_column('classification_runs', sa.Column('classifier_type', sa.Text(), nullable=True))
    op.add_column('classification_runs', sa.Column('classifier_config', sa.JSON(), nullable=True))

    # Migrate existing rows — all previous runs used the LLM classifier
    op.execute("""
        UPDATE classification_runs
        SET
            classifier_type = 'llm',
            classifier_config = json_build_object(
                'provider', llm_provider,
                'model', llm_model,
                'batch_size', batch_size,
                'batch_overlap', batch_overlap,
                'llm_config', '{}'::json
            )
    """)

    # Make non-nullable
    op.alter_column('classification_runs', 'classifier_type', nullable=False)
    op.alter_column('classification_runs', 'classifier_config', nullable=False)

    # Drop replaced columns
    op.drop_column('classification_runs', 'llm_provider')
    op.drop_column('classification_runs', 'llm_model')
    op.drop_column('classification_runs', 'batch_size')
    op.drop_column('classification_runs', 'batch_overlap')


def downgrade() -> None:
    op.add_column('classification_runs', sa.Column('llm_provider', sa.Text(), nullable=True))
    op.add_column('classification_runs', sa.Column('llm_model', sa.Text(), nullable=True))
    op.add_column('classification_runs', sa.Column('batch_size', sa.Integer(), nullable=True))
    op.add_column('classification_runs', sa.Column('batch_overlap', sa.Integer(), nullable=True))

    op.execute("""
        UPDATE classification_runs
        SET
            llm_provider = classifier_config->>'provider',
            llm_model = classifier_config->>'model',
            batch_size = (classifier_config->>'batch_size')::int,
            batch_overlap = (classifier_config->>'batch_overlap')::int
        WHERE classifier_type = 'llm'
    """)

    op.drop_column('classification_runs', 'classifier_type')
    op.drop_column('classification_runs', 'classifier_config')
```

- [ ] **Step 3: Apply the migration**

```
uv run --directory backend alembic upgrade head
```

Expected: `Running upgrade <prev> -> <new>, classification_provider_refactor`

- [ ] **Step 4: Verify**

```
uv run --directory backend alembic current
```

Expected: shows the new revision as current head.

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/classification_run.py backend/alembic/versions/
git commit -m "feat(classification): replace llm columns with classifier_type/classifier_config"
```

---

## Task 7: Repository + schemas

**Files:**
- Modify: `backend/app/repositories/classification_run_repository.py`
- Modify: `backend/app/schemas/classification.py`
- Modify: `backend/tests/repositories/test_classification_run_repository.py`

- [ ] **Step 1: Update the repository test**

Replace the entire contents of `backend/tests/repositories/test_classification_run_repository.py`:

```python
# backend/tests/repositories/test_classification_run_repository.py
import pytest
from uuid import uuid4
from app.cdm.classification import ClassifiedRegion
from app.repositories.classification_run_repository import (
    ClassificationRunCreate,
    ClassificationRunRepository,
)

_LLM_CONFIG = {
    "provider": "ollama_local",
    "model": "qwen2.5:7b",
    "batch_size": 10,
    "batch_overlap": 3,
    "llm_config": {},
}


@pytest.mark.asyncio
async def test_create_and_get_run(test_db):
    repo = ClassificationRunRepository(test_db)
    run = await repo.create(ClassificationRunCreate(
        parse_run_id=uuid4(), document_id=uuid4(),
        labels_requested=["balance_sheet"],
        classifier_type="llm", classifier_config=_LLM_CONFIG,
    ))
    assert run.id is not None
    assert run.status == "pending"
    fetched = await repo.get(run.id)
    assert fetched.classifier_type == "llm"
    assert fetched.classifier_config["provider"] == "ollama_local"


@pytest.mark.asyncio
async def test_update_status(test_db):
    repo = ClassificationRunRepository(test_db)
    run = await repo.create(ClassificationRunCreate(
        parse_run_id=uuid4(), document_id=uuid4(), labels_requested=["x"],
        classifier_type="llm", classifier_config=_LLM_CONFIG,
    ))
    await repo.update_status(run.id, "running")
    assert (await repo.get(run.id)).status == "running"


@pytest.mark.asyncio
async def test_save_and_get_regions(test_db):
    repo = ClassificationRunRepository(test_db)
    run = await repo.create(ClassificationRunCreate(
        parse_run_id=uuid4(), document_id=uuid4(), labels_requested=["balance_sheet"],
        classifier_type="llm", classifier_config=_LLM_CONFIG,
    ))
    await repo.save_regions(run.id, [
        ClassifiedRegion(label="balance_sheet", page_start=5, page_end=8, block_ids=["b1", "b2"]),
    ])
    fetched = await repo.get_regions(run.id)
    assert len(fetched) == 1
    assert fetched[0].label == "balance_sheet"
    assert fetched[0].page_start == 5
    assert fetched[0].block_ids == ["b1", "b2"]


@pytest.mark.asyncio
async def test_get_annotated_blocks(test_db):
    from app.models.parsed_document import ParsedDocument as ParsedDocumentORM

    parse_run_id = uuid4()
    source_doc_id = uuid4()
    pd = ParsedDocumentORM(
        parse_run_id=parse_run_id, source_document_id=source_doc_id,
        full_text=None, full_markdown=None, page_count=2, block_count=3,
        content={
            "id": "doc-1", "source_document_id": str(source_doc_id),
            "parse_run_id": str(parse_run_id), "page_count": 2,
            "pages": [{"index": 0}, {"index": 1}],
            "blocks": [
                {"id": "b-1", "role": "heading", "native_type": "heading",
                 "text": "Balance Sheet", "page_index": 0},
                {"id": "b-2", "role": "paragraph", "native_type": "paragraph",
                 "text": "Assets data", "page_index": 0},
                {"id": "b-3", "role": "paragraph", "native_type": "paragraph",
                 "text": "Notes", "page_index": 1},
            ],
        },
    )
    test_db.add(pd)
    await test_db.commit()

    repo = ClassificationRunRepository(test_db)
    run = await repo.create(ClassificationRunCreate(
        parse_run_id=parse_run_id, document_id=uuid4(), labels_requested=["balance_sheet"],
        classifier_type="llm", classifier_config=_LLM_CONFIG,
    ))
    await repo.save_regions(run.id, [
        ClassifiedRegion(label="balance_sheet", page_start=0, page_end=0, block_ids=["b-1", "b-2"]),
    ])
    blocks = await repo.get_annotated_blocks(run.id)
    assert len(blocks) == 3
    assert blocks[0].block_id == "b-1"
    assert blocks[0].label == "balance_sheet"
    assert blocks[2].label is None


@pytest.mark.asyncio
async def test_get_annotated_blocks_no_parsed_doc(test_db):
    repo = ClassificationRunRepository(test_db)
    run = await repo.create(ClassificationRunCreate(
        parse_run_id=uuid4(), document_id=uuid4(), labels_requested=["x"],
        classifier_type="llm", classifier_config=_LLM_CONFIG,
    ))
    assert await repo.get_annotated_blocks(run.id) == []
```

- [ ] **Step 2: Run test to confirm it fails**

```
uv run --directory backend python -m pytest tests/repositories/test_classification_run_repository.py -v
```

Expected: FAIL — `ClassificationRunCreate` still has old fields.

- [ ] **Step 3: Update ClassificationRunCreate and create() in the repository**

In `backend/app/repositories/classification_run_repository.py`, replace the `ClassificationRunCreate` dataclass and `create()` method (leave all other methods unchanged):

```python
@dataclass
class ClassificationRunCreate:
    parse_run_id: UUID
    document_id: UUID
    labels_requested: list[str]
    classifier_type: str
    classifier_config: dict
```

```python
    async def create(self, data: ClassificationRunCreate) -> ClassificationRunORM:
        run = ClassificationRunORM(
            parse_run_id=data.parse_run_id,
            document_id=data.document_id,
            labels_requested=data.labels_requested,
            classifier_type=data.classifier_type,
            classifier_config=data.classifier_config,
            status="pending",
        )
        self.session.add(run)
        await self.session.commit()
        await self.session.refresh(run)
        return run
```

- [ ] **Step 4: Update schemas**

Replace the entire contents of `backend/app/schemas/classification.py`:

```python
from __future__ import annotations
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ClassificationRunCreateRequest(BaseModel):
    parse_run_id: UUID
    labels: list[str]
    classifier_type: str | None = None
    classifier_config: dict | None = None


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
    classifier_type: str = Field(..., alias="classifierType")
    classifier_config: dict = Field(..., alias="classifierConfig")
    status: str
    error: str | None = None
    input_tokens: int | None = Field(None, alias="inputTokens")
    output_tokens: int | None = Field(None, alias="outputTokens")
    duration_ms: int | None = Field(None, alias="durationMs")
    created_at: datetime = Field(..., alias="createdAt")
    regions: list[ClassificationRegionResponse] = []


class AnnotatedBlockResponse(BaseModel):
    blockId: str
    pageIndex: int
    role: str
    text: str
    markdown: str | None
    label: str | None
```

- [ ] **Step 5: Run repository + service tests**

```
uv run --directory backend python -m pytest tests/repositories/test_classification_run_repository.py tests/services/classification/ -v
```

Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/repositories/classification_run_repository.py backend/app/schemas/classification.py backend/tests/repositories/test_classification_run_repository.py
git commit -m "feat(classification): update repository dataclass and schemas for provider refactor"
```

---

## Task 8: Router update

**Files:**
- Modify: `backend/app/routers/classification.py`
- Modify: `backend/tests/routers/test_classification_router.py`

- [ ] **Step 1: Update the router test**

In `backend/tests/routers/test_classification_router.py`, replace the `ClassificationRunORM(...)` constructor — swap out the four LLM kwargs for the two new ones:

```python
run = ClassificationRunORM(
    parse_run_id=parse_run_id,
    document_id=uuid4(),
    labels_requested=["section_a"],
    classifier_type="llm",
    classifier_config={
        "provider": "ollama_local",
        "model": "qwen2.5:7b",
        "batch_size": 10,
        "batch_overlap": 3,
        "llm_config": {},
    },
    status="completed",
)
```

- [ ] **Step 2: Run router test to confirm it fails**

```
uv run --directory backend python -m pytest tests/routers/test_classification_router.py -v
```

Expected: FAIL — router still references old fields.

- [ ] **Step 3: Rewrite the router**

Replace the entire contents of `backend/app/routers/classification.py`:

```python
"""Classification API — two routers mounted at different prefixes in main.py."""
import logging
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal, get_db
from app.dependencies.auth import get_current_active_user
from app.models import User
from app.repositories.classification_run_repository import (
    ClassificationRunCreate,
    ClassificationRunRepository,
)
from app.repositories.parsed_document_repository import ParsedDocumentRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.provider_key_repository import ProviderKeyRepository
from app.schemas.classification import (
    AnnotatedBlockResponse,
    ClassificationRegionResponse,
    ClassificationRunCreateRequest,
    ClassificationRunResponse,
)
from app.services.classification.classifier_factory import (
    _resolve_byok_provider,
    build_classifier,
)
from app.services.classification.service import ClassificationService
from app.services.provider_key_service import resolve_api_key

logger = logging.getLogger(__name__)

documents_router = APIRouter(prefix="/documents", tags=["classification"])
runs_router = APIRouter(prefix="/classification-runs", tags=["classification"])

_DEFAULT_CLASSIFIER_TYPE = "llm"


def _default_classifier_config() -> dict:
    return {
        "provider": settings.CLASSIFIER_LLM_PROVIDER,
        "model": settings.CLASSIFIER_LLM_MODEL,
        "batch_size": 10,
        "batch_overlap": 3,
        "llm_config": {},
    }


async def _run_classification_background(
    run_id: UUID,
    parse_run_id: UUID,
    labels: list[str],
    classifier_type: str,
    classifier_config: dict,
    api_key: str | None,
) -> None:
    from app.cdm.models import ParsedDocument as CDMParsedDocument

    try:
        async with AsyncSessionLocal() as session:
            repo = ClassificationRunRepository(session)
            pd_repo = ParsedDocumentRepository(session)

            pd_orm = await pd_repo.get_by_run(parse_run_id)
            if pd_orm is None:
                await repo.update_status(run_id=run_id, status="failed", error="ParsedDocument not found")
                return

            doc = CDMParsedDocument.model_validate(pd_orm.content)
            classifier = build_classifier(classifier_type, classifier_config, api_key)
            service = ClassificationService(repo=repo, classifier=classifier)
            await service.execute(run_id=run_id, doc=doc, labels=labels)
    except Exception:
        logger.exception("Classification background task failed for run %s", run_id)
        async with AsyncSessionLocal() as recovery_session:
            recovery_repo = ClassificationRunRepository(recovery_session)
            run = await recovery_repo.get(run_id)
            if run and run.status == "running":
                await recovery_repo.update_status(
                    run_id=run_id, status="failed",
                    error="Internal error — check server logs",
                )


def _to_run_response(run, regions=None) -> ClassificationRunResponse:
    return ClassificationRunResponse(
        id=run.id,
        parseRunId=run.parse_run_id,
        documentId=run.document_id,
        labelsRequested=run.labels_requested,
        classifierType=run.classifier_type,
        classifierConfig=run.classifier_config,
        status=run.status,
        error=run.error,
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

    classifier_type = body.classifier_type or _DEFAULT_CLASSIFIER_TYPE
    classifier_config = body.classifier_config or _default_classifier_config()

    repo = ClassificationRunRepository(db)
    run = await repo.create(ClassificationRunCreate(
        parse_run_id=body.parse_run_id,
        document_id=document_id,
        labels_requested=body.labels,
        classifier_type=classifier_type,
        classifier_config=classifier_config,
    ))

    byok_provider = _resolve_byok_provider(classifier_type, classifier_config)
    api_key: str | None = None
    if byok_provider:
        provider_key_repo = ProviderKeyRepository(db)
        api_key = await resolve_api_key(provider_key_repo, current_user.id, byok_provider)
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"No API key configured for provider '{byok_provider}'. "
                    "Add one in Settings → API Keys."
                ),
            )

    background_tasks.add_task(
        _run_classification_background,
        run_id=run.id,
        parse_run_id=body.parse_run_id,
        labels=body.labels,
        classifier_type=classifier_type,
        classifier_config=classifier_config,
        api_key=api_key,
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


@runs_router.get("/{run_id}/blocks", response_model=list[AnnotatedBlockResponse])
async def get_classification_run_blocks(
    run_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    repo = ClassificationRunRepository(db)
    run = await repo.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Classification run not found")
    blocks = await repo.get_annotated_blocks(run_id)
    return [
        AnnotatedBlockResponse(
            blockId=b.block_id,
            pageIndex=b.page_index,
            role=b.role,
            text=b.text,
            markdown=b.markdown,
            label=b.label,
        )
        for b in blocks
    ]
```

- [ ] **Step 4: Run all backend classification tests**

```
uv run --directory backend python -m pytest tests/services/classification/ tests/repositories/test_classification_run_repository.py tests/routers/test_classification_router.py -v
```

Expected: all PASS.

- [ ] **Step 5: Start the backend to confirm no startup errors**

```
uv run --directory backend uvicorn app.main:app --reload
```

Expected: server starts cleanly. Stop with Ctrl+C.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/classification.py backend/tests/routers/test_classification_router.py
git commit -m "feat(classification): wire classifier_factory through router, drop LLM-specific params"
```

---

## Task 9: Frontend types + API client

**Files:**
- Modify: `frontend/src/types/classification.ts`
- Modify: `frontend/src/api/classification.ts`

- [ ] **Step 1: Replace classification.ts**

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
  classifierType: string
  classifierConfig: Record<string, unknown>
  status: ClassificationRunStatus
  error: string | null
  inputTokens: number | null
  outputTokens: number | null
  durationMs: number | null
  createdAt: string
  regions: ClassificationRegion[]
}

export interface ClassificationRunCreateRequest {
  parseRunId: string
  labels: string[]
  classifierType?: string
  classifierConfig?: Record<string, unknown>
}

export interface AnnotatedBlock {
  blockId: string
  pageIndex: number
  role: string
  text: string
  markdown: string | null
  label: string | null
}
```

- [ ] **Step 2: Replace api/classification.ts**

```typescript
// frontend/src/api/classification.ts
import apiClient from './client'
import type { AnnotatedBlock, ClassificationRun, ClassificationRunCreateRequest } from '@/types/classification'

export async function createClassificationRun(
  documentId: string,
  data: ClassificationRunCreateRequest,
): Promise<ClassificationRun> {
  const response = await apiClient.post<ClassificationRun>(
    `/documents/${documentId}/classification-runs`,
    {
      parse_run_id: data.parseRunId,
      labels: data.labels,
      classifier_type: data.classifierType,
      classifier_config: data.classifierConfig,
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

export async function getClassificationRunBlocks(runId: string): Promise<AnnotatedBlock[]> {
  const response = await apiClient.get<AnnotatedBlock[]>(`/classification-runs/${runId}/blocks`)
  return response.data
}
```

- [ ] **Step 3: Check for TypeScript errors**

```
npm --prefix frontend run build 2>&1 | head -40
```

Fix any errors before continuing.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/classification.ts frontend/src/api/classification.ts
git commit -m "feat(classification): update frontend types and API client for classifier_type/classifier_config"
```

---

## Task 10: ClassificationRunForm refactor

**Files:**
- Modify: `frontend/src/components/classification/ClassificationRunForm.tsx`

- [ ] **Step 1: Rewrite the form**

Replace the entire contents of `frontend/src/components/classification/ClassificationRunForm.tsx`:

```tsx
// frontend/src/components/classification/ClassificationRunForm.tsx
import { useState } from 'react'
import { X, ChevronDown } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import {
  Collapsible, CollapsibleContent, CollapsibleTrigger,
} from '@/components/ui/collapsible'
import { PromptConfigEditor } from '@/components/shared/PromptConfigEditor'
import type { PromptConfig } from '@/types/prompt-config'

const CLASSIFIER_TYPES = [
  { value: 'llm', label: 'LLM classifier' },
  { value: 'llamaindex_split', label: 'LlamaIndex split (not yet implemented)' },
]

const DEFAULT_LLM_PROMPT_CONFIG: PromptConfig = {
  provider: 'ollama_local',
  model: 'qwen2.5:7b',
  temperature: 0.0,
  maxTokens: 4096,
}

export interface ClassificationRunFormValues {
  labels: string[]
  classifierType: string
  classifierConfig: Record<string, unknown>
}

interface Props {
  defaultValues?: Partial<ClassificationRunFormValues>
  onSubmit: (values: ClassificationRunFormValues) => void
  isSubmitting?: boolean
  submitLabel?: string
}

function _configToPromptConfig(config: Record<string, unknown>): PromptConfig {
  const llmConfig = (config.llm_config as Record<string, unknown> | undefined) ?? {}
  return {
    provider: (config.provider as string | undefined) ?? DEFAULT_LLM_PROMPT_CONFIG.provider,
    model: (config.model as string | undefined) ?? DEFAULT_LLM_PROMPT_CONFIG.model,
    temperature: (llmConfig.temperature as number | undefined) ?? DEFAULT_LLM_PROMPT_CONFIG.temperature,
    maxTokens: (llmConfig.max_tokens as number | undefined) ?? DEFAULT_LLM_PROMPT_CONFIG.maxTokens,
    systemPrompt: (llmConfig.system_prompt as string | undefined),
  }
}

export function ClassificationRunForm({
  defaultValues,
  onSubmit,
  isSubmitting,
  submitLabel = 'Start classification',
}: Props) {
  const [labels, setLabels] = useState<string[]>(defaultValues?.labels ?? [])
  const [labelInput, setLabelInput] = useState('')
  const [classifierType, setClassifierType] = useState(defaultValues?.classifierType ?? 'llm')
  const [promptConfig, setPromptConfig] = useState<PromptConfig>(
    defaultValues?.classifierConfig
      ? _configToPromptConfig(defaultValues.classifierConfig)
      : DEFAULT_LLM_PROMPT_CONFIG,
  )
  const [batchSize, setBatchSize] = useState(
    (defaultValues?.classifierConfig?.batch_size as number | undefined) ?? 10,
  )
  const [batchOverlap, setBatchOverlap] = useState(
    (defaultValues?.classifierConfig?.batch_overlap as number | undefined) ?? 3,
  )

  const addLabel = () => {
    const trimmed = labelInput.trim()
    if (trimmed && !labels.includes(trimmed)) setLabels((prev) => [...prev, trimmed])
    setLabelInput('')
  }

  const removeLabel = (l: string) => setLabels((prev) => prev.filter((x) => x !== l))

  const handleSubmit = () => {
    if (labels.length === 0) return
    const classifierConfig: Record<string, unknown> =
      classifierType === 'llm'
        ? {
            provider: promptConfig.provider,
            model: promptConfig.model,
            batch_size: batchSize,
            batch_overlap: batchOverlap,
            llm_config: {
              system_prompt: promptConfig.systemPrompt ?? null,
              temperature: promptConfig.temperature ?? 0.0,
              max_tokens: promptConfig.maxTokens ?? 4096,
            },
          }
        : {}
    onSubmit({ labels, classifierType, classifierConfig })
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

      <div className="space-y-2">
        <Label>Classifier</Label>
        <Select value={classifierType} onValueChange={setClassifierType}>
          <SelectTrigger><SelectValue /></SelectTrigger>
          <SelectContent>
            {CLASSIFIER_TYPES.map((t) => (
              <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {classifierType === 'llm' && (
        <>
          <PromptConfigEditor value={promptConfig} onChange={setPromptConfig} />
          <Collapsible>
            <CollapsibleTrigger className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground">
              <ChevronDown className="h-4 w-4" />
              Batch settings
            </CollapsibleTrigger>
            <CollapsibleContent className="mt-3 grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Batch size (pages)</Label>
                <Input type="number" min={1} value={batchSize}
                  onChange={(e) => setBatchSize(Number(e.target.value))} />
              </div>
              <div className="space-y-2">
                <Label>Batch overlap (pages)</Label>
                <Input type="number" min={0} value={batchOverlap}
                  onChange={(e) => setBatchOverlap(Number(e.target.value))} />
              </div>
            </CollapsibleContent>
          </Collapsible>
        </>
      )}

      {classifierType === 'llamaindex_split' && (
        <p className="text-sm text-muted-foreground">
          LlamaIndex split classifier is not yet implemented. Select LLM classifier to proceed.
        </p>
      )}

      <Button
        onClick={handleSubmit}
        disabled={labels.length === 0 || isSubmitting || classifierType === 'llamaindex_split'}
      >
        {isSubmitting ? 'Starting…' : submitLabel}
      </Button>
    </div>
  )
}
```

- [ ] **Step 2: Build to verify no TypeScript errors**

```
npm --prefix frontend run build 2>&1 | head -50
```

Expected: no errors. Fix any before continuing.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/classification/ClassificationRunForm.tsx
git commit -m "feat(classification): replace LLM-specific form UI with PromptConfigEditor"
```

---

## Task 11: Update pages

**Files:**
- Modify: `frontend/src/pages/NewClassificationRunPage.tsx`
- Modify: `frontend/src/pages/ClassificationRunDetailPage.tsx`

- [ ] **Step 1: Update handleSubmit in NewClassificationRunPage**

In `frontend/src/pages/NewClassificationRunPage.tsx`, replace the `handleSubmit` function:

```typescript
const handleSubmit = async (values: ClassificationRunFormValues) => {
  if (!selectedDocumentId || !selectedParseRunId) return
  setIsSubmitting(true)
  try {
    const run = await createClassificationRun(selectedDocumentId, {
      parseRunId: selectedParseRunId,
      labels: values.labels,
      classifierType: values.classifierType,
      classifierConfig: values.classifierConfig,
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
```

- [ ] **Step 2: Update the metadata line in ClassificationRunDetailPage**

In `frontend/src/pages/ClassificationRunDetailPage.tsx`, replace the `<p className="text-muted-foreground text-sm mt-1">` line:

```tsx
<p className="text-muted-foreground text-sm mt-1">
  {run.classifierType === 'llm'
    ? `${run.classifierConfig.provider as string} / ${run.classifierConfig.model as string}`
    : run.classifierType}{' '}
  · {formatDistanceToNow(new Date(run.createdAt), { addSuffix: true })}
</p>
```

- [ ] **Step 3: Full frontend build**

```
npm --prefix frontend run build
```

Expected: 0 TypeScript errors, build succeeds.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/NewClassificationRunPage.tsx frontend/src/pages/ClassificationRunDetailPage.tsx
git commit -m "feat(classification): update pages for classifier_type/classifier_config"
```

---

## Task 12: Full test suite + smoke test

- [ ] **Step 1: Run all backend classification tests**

```
uv run --directory backend python -m pytest tests/services/classification/ tests/repositories/test_classification_run_repository.py tests/routers/test_classification_router.py -v
```

Expected: all PASS.

- [ ] **Step 2: Run the broader backend test suite**

```
uv run --directory backend python -m pytest tests/ -v --ignore=tests/cdm/eval -x
```

Fix any failures caused by this refactor before proceeding.

- [ ] **Step 3: Start backend and frontend**

```
uv run --directory backend uvicorn app.main:app --reload
npm --prefix frontend run dev
```

Expected: backend on port 8000, frontend on port 5173, no startup errors.

- [ ] **Step 4: Manual smoke test**

1. Navigate to `/classify/new`
2. Select a document and a parse run
3. Confirm the configure step shows a **Classifier** dropdown (LLM classifier selected by default) and `PromptConfigEditor` below it — no old "LLM provider" / "Model" dropdowns
4. Change provider to Groq — confirm model dropdown updates
5. Enter a system prompt — confirm it is visible
6. Expand **Batch settings** — confirm batch size / batch overlap inputs
7. Add a label, submit — confirm run is created and redirects to detail page
8. On the detail page, confirm metadata shows e.g. `ollama_local / qwen2.5:7b · just now`
9. Confirm tokens, duration, and regions all display as before

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "feat(classification): complete classification provider refactor"
```
