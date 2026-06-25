# LlamaExtractAdapter Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the `LlamaExtractAdapter` stub with a full implementation that receives a `ParsedDocument`, resolves file bytes via `SourceDocumentRepository` + `StorageService`, uploads to LlamaCloud, runs extraction, and returns a typed `ExtractionOutput`.

**Architecture:** The adapter implements the `DataExtractor` port and pulls file bytes through the storage abstraction layer, keeping file-system details out of the service layer. The registry factory is updated to inject `SourceDocumentRepository` and `StorageService` as explicit dependencies, following the existing `credentials: dict` pattern. The router wires these from the DI context.

**Tech Stack:** Python 3.12, FastAPI, `llama-cloud` SDK (`AsyncLlamaCloud`, `files.create`, `extraction.extract`), SQLAlchemy async, pytest + `unittest.mock.AsyncMock`

---

## File Map

| Action | File |
|--------|------|
| **Modify** | `backend/app/adapters/extraction/llamaextract.py` — full implementation replacing stub |
| **Modify** | `backend/app/adapters/extraction/registry.py` — add `dependencies` param to `get_extractor`, update config schema |
| **Modify** | `backend/app/routers/extraction.py` — pass `SourceDocumentRepository` + `StorageService` to `get_extractor` |
| **Create** | `backend/tests/adapters/extraction/test_llamaextract.py` — unit tests for adapter |
| **Modify** | `backend/tests/adapters/extraction/test_registry.py` — update factory tests to pass mock dependencies |

---

## Task 1: Update registry config schema

Add `extraction_target` and `confidence_scores` to the `llamaextract` config schema in the registry. These are currently missing but required by the spec.

**Files:**
- Modify: `backend/app/adapters/extraction/registry.py`
- Modify: `backend/tests/adapters/extraction/test_registry.py`

- [ ] **Step 1: Write failing test for config schema completeness**

Add this test class to `backend/tests/adapters/extraction/test_registry.py`:

```python
class TestLlamaExtractConfigSchema:
    def test_config_schema_has_extraction_target(self):
        extractor = next(
            e for e in get_known_extractors()
            if e["extraction_method"] == "llamaextract"
        )
        props = extractor["config_schema"]["properties"]
        assert "extraction_target" in props
        assert props["extraction_target"]["enum"] == ["PER_DOC", "PER_PAGE"]

    def test_config_schema_has_confidence_scores(self):
        extractor = next(
            e for e in get_known_extractors()
            if e["extraction_method"] == "llamaextract"
        )
        props = extractor["config_schema"]["properties"]
        assert "confidence_scores" in props
        assert props["confidence_scores"]["type"] == "boolean"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run --directory backend python -m pytest tests/adapters/extraction/test_registry.py::TestLlamaExtractConfigSchema -v -o "addopts="
```

Expected: FAIL — `AssertionError: assert 'extraction_target' in {...}`

- [ ] **Step 3: Add missing fields to config schema**

In `backend/app/adapters/extraction/registry.py`, inside the `llamaextract` entry's `config_schema.properties`, add after the `extraction_mode` entry:

```python
"extraction_target": {
    "type": "string",
    "enum": ["PER_DOC", "PER_PAGE"],
    "default": "PER_DOC",
},
```

And after `use_reasoning`:

```python
"confidence_scores": {"type": "boolean", "default": False},
```

The complete updated `config_schema` block in `get_known_extractors()`:

```python
"config_schema": {
    "type": "object",
    "properties": {
        "system_prompt": {
            "type": "string",
            "description": "Custom extraction prompt (maps to LlamaExtract prompt_override)",
        },
        "extraction_mode": {
            "type": "string",
            "enum": ["FAST", "BALANCED", "MULTIMODAL", "PREMIUM"],
            "default": "MULTIMODAL",
        },
        "extraction_target": {
            "type": "string",
            "enum": ["PER_DOC", "PER_PAGE"],
            "default": "PER_DOC",
        },
        "cite_sources": {"type": "boolean", "default": False},
        "use_reasoning": {"type": "boolean", "default": False},
        "confidence_scores": {"type": "boolean", "default": False},
        "page_range": {"type": "string"},
    },
},
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run --directory backend python -m pytest tests/adapters/extraction/test_registry.py -v -o "addopts="
```

Expected: all 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/adapters/extraction/registry.py backend/tests/adapters/extraction/test_registry.py
git commit -m "feat(extraction): add extraction_target and confidence_scores to llamaextract config schema"
```

---

## Task 2: New constructor + `_get_file_bytes` + registry factory update

Change `LlamaExtractAdapter.__init__` to accept `source_document_repo` and `storage_service`, implement `_get_file_bytes`, and update `registry.get_extractor` to pass these dependencies. All three changes must ship together because the constructor signature change would break the registry factory tests if done piecemeal.

**Files:**
- Create: `backend/tests/adapters/extraction/test_llamaextract.py`
- Modify: `backend/app/adapters/extraction/llamaextract.py`
- Modify: `backend/app/adapters/extraction/registry.py`
- Modify: `backend/tests/adapters/extraction/test_registry.py`

- [ ] **Step 1: Create test file with failing tests for `_get_file_bytes`**

Create `backend/tests/adapters/extraction/test_llamaextract.py`:

```python
"""Unit tests for LlamaExtractAdapter."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

from app.adapters.extraction.llamaextract import LlamaExtractAdapter


SOURCE_DOC_ID = "12345678-1234-5678-1234-567812345678"
PARSE_RUN_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


@pytest.fixture
def source_doc_repo():
    return AsyncMock()


@pytest.fixture
def storage_service():
    return AsyncMock()


@pytest.fixture
def adapter(source_doc_repo, storage_service):
    a = LlamaExtractAdapter(
        api_key="test-key",
        source_document_repo=source_doc_repo,
        storage_service=storage_service,
    )
    a._client = AsyncMock()  # replace real HTTP client
    return a


@pytest.fixture
def parsed_doc():
    doc = MagicMock()
    doc.source_document_id = SOURCE_DOC_ID
    doc.parse_run_id = PARSE_RUN_ID
    return doc


class TestGetFileBytes:
    async def test_fetches_bytes_from_storage(
        self, adapter, source_doc_repo, storage_service
    ):
        source_doc = MagicMock()
        source_doc.storage_uri = "uploads/test.pdf"
        source_doc_repo.get.return_value = source_doc
        storage_service.get.return_value = b"pdf bytes"

        result = await adapter._get_file_bytes(SOURCE_DOC_ID)

        source_doc_repo.get.assert_called_once_with(UUID(SOURCE_DOC_ID))
        storage_service.get.assert_called_once_with("uploads/test.pdf")
        assert result == b"pdf bytes"

    async def test_raises_when_source_doc_not_found(
        self, adapter, source_doc_repo
    ):
        source_doc_repo.get.return_value = None

        with pytest.raises(ValueError, match="SourceDocument .* not found"):
            await adapter._get_file_bytes(SOURCE_DOC_ID)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run --directory backend python -m pytest tests/adapters/extraction/test_llamaextract.py -v -o "addopts="
```

Expected: FAIL — `TypeError: LlamaExtractAdapter.__init__() got unexpected keyword arguments` (or similar, since current constructor only takes `api_key`)

- [ ] **Step 3: Update `LlamaExtractAdapter` constructor and add `_get_file_bytes`**

Replace entire `backend/app/adapters/extraction/llamaextract.py`:

```python
"""LlamaExtract adapter — CDM-based DataExtractor port implementation."""
import time
from typing import Any
from uuid import UUID

from llama_cloud import AsyncLlamaCloud

from app.ports.data_extraction import DataExtractor, ExtractionOutput
from app.ports.storage import StorageService
from app.repositories.source_document_repository import SourceDocumentRepository


class LlamaExtractAdapter(DataExtractor):
    """Structured extraction via LlamaCloud using a CDM ParsedDocument as input."""

    def __init__(
        self,
        api_key: str | None,
        source_document_repo: SourceDocumentRepository,
        storage_service: StorageService,
    ):
        self._client = AsyncLlamaCloud(api_key=api_key) if api_key else AsyncLlamaCloud()
        self._source_doc_repo = source_document_repo
        self._storage_service = storage_service

    @property
    def extractor_type(self) -> str:
        return "llamaextract"

    @property
    def display_name(self) -> str:
        return "LlamaExtract"

    async def _get_file_bytes(self, source_document_id: str) -> bytes:
        source_doc = await self._source_doc_repo.get(UUID(source_document_id))
        if not source_doc:
            raise ValueError(f"SourceDocument {source_document_id} not found")
        return await self._storage_service.get(source_doc.storage_uri)

    async def extract(
        self,
        parsed_document: Any,
        schema: dict[str, Any],
        config: dict[str, Any] | None = None,
    ) -> ExtractionOutput:
        raise NotImplementedError("extract() — see Task 3 of the implementation plan")
```

- [ ] **Step 4: Update `registry.get_extractor` to accept and pass dependencies**

In `backend/app/adapters/extraction/registry.py`, update the `get_extractor` function:

```python
def get_extractor(
    method: str,
    credentials: dict,
    dependencies: dict | None = None,
) -> DataExtractor:
    """Construct an adapter with caller-supplied credentials and dependencies.

    Credentials and dependencies are resolved by the call site. Raises ValueError
    for unknown methods.
    """
    if method == "llamaextract":
        from app.adapters.extraction.llamaextract import LlamaExtractAdapter
        deps = dependencies or {}
        return LlamaExtractAdapter(
            api_key=credentials.get("api_key"),
            source_document_repo=deps["source_document_repo"],
            storage_service=deps["storage_service"],
        )

    raise ValueError(f"Unknown extraction method: {method!r}")
```

- [ ] **Step 5: Update registry tests to pass mock dependencies**

In `backend/tests/adapters/extraction/test_registry.py`, add `from unittest.mock import AsyncMock` at the top, then update `TestGetExtractor`:

```python
from unittest.mock import AsyncMock

# ...

class TestGetExtractor:
    def test_unknown_method_raises(self):
        with pytest.raises(ValueError, match="Unknown extraction method"):
            get_extractor("nonexistent_method", {})

    def test_llamaextract_uses_credentials_api_key(self):
        extractor = get_extractor(
            "llamaextract",
            {"api_key": "test-key-123"},
            {"source_document_repo": AsyncMock(), "storage_service": AsyncMock()},
        )
        assert extractor.extractor_type == "llamaextract"

    def test_llamaextract_works_with_empty_credentials(self):
        extractor = get_extractor(
            "llamaextract",
            {},
            {"source_document_repo": AsyncMock(), "storage_service": AsyncMock()},
        )
        assert extractor is not None

    def test_no_settings_read_in_factory(self):
        import app.adapters.extraction.registry as registry_module
        assert not hasattr(registry_module, "settings")
        extractor = get_extractor(
            "llamaextract",
            {"api_key": "k"},
            {"source_document_repo": AsyncMock(), "storage_service": AsyncMock()},
        )
        assert extractor.extractor_type == "llamaextract"
```

- [ ] **Step 6: Run all extraction adapter tests to verify they pass**

```bash
uv run --directory backend python -m pytest tests/adapters/extraction/ -v -o "addopts="
```

Expected: all tests PASS including the 2 new `TestGetFileBytes` tests

- [ ] **Step 7: Commit**

```bash
git add backend/app/adapters/extraction/llamaextract.py \
        backend/app/adapters/extraction/registry.py \
        backend/tests/adapters/extraction/test_llamaextract.py \
        backend/tests/adapters/extraction/test_registry.py
git commit -m "feat(extraction): LlamaExtractAdapter constructor + _get_file_bytes; update registry factory to accept dependencies"
```

---

## Task 3: Implement `extract()` method

Implement the full `extract()` method: build the LlamaCloud `extraction_config`, upload file bytes, run extraction, and map the result to `ExtractionOutput`.

**Files:**
- Modify: `backend/tests/adapters/extraction/test_llamaextract.py` — add output mapping and config tests
- Modify: `backend/app/adapters/extraction/llamaextract.py` — implement `extract()`

- [ ] **Step 1: Add failing tests for output mapping and config passthrough**

Append these two test classes to `backend/tests/adapters/extraction/test_llamaextract.py`:

```python
class TestExtractOutputMapping:
    async def _setup_mocks(self, adapter, source_doc_repo, storage_service, file_id="file-abc"):
        source_doc = MagicMock()
        source_doc.storage_uri = "uploads/doc.pdf"
        source_doc_repo.get.return_value = source_doc
        storage_service.get.return_value = b"bytes"
        file_obj = MagicMock()
        file_obj.id = file_id
        adapter._client.files.create = AsyncMock(return_value=file_obj)

    async def test_structured_data_from_result(
        self, adapter, source_doc_repo, storage_service, parsed_doc
    ):
        await self._setup_mocks(adapter, source_doc_repo, storage_service)
        result_obj = MagicMock()
        result_obj.data = {"name": "Alice", "age": 30}
        result_obj.model_dump.return_value = {"data": {"name": "Alice"}, "run_id": "r1"}
        adapter._client.extraction.extract = AsyncMock(return_value=result_obj)

        output = await adapter.extract(parsed_doc, {"type": "object"}, {})

        assert output.structured_data == {"name": "Alice", "age": 30}
        assert output.source_parse_run_id == UUID(PARSE_RUN_ID)
        assert output.citations is None
        assert output.provider_response_raw == {"data": {"name": "Alice"}, "run_id": "r1"}
        assert output.extraction_metadata["file_id"] == "file-abc"
        assert "latency_ms" in output.extraction_metadata

    async def test_structured_data_defaults_to_empty_dict_when_none(
        self, adapter, source_doc_repo, storage_service, parsed_doc
    ):
        await self._setup_mocks(adapter, source_doc_repo, storage_service)
        result_obj = MagicMock()
        result_obj.data = None
        result_obj.model_dump.return_value = {"data": None}
        adapter._client.extraction.extract = AsyncMock(return_value=result_obj)

        output = await adapter.extract(parsed_doc, {"type": "object"}, {})

        assert output.structured_data == {}

    async def test_file_upload_uses_correct_purpose(
        self, adapter, source_doc_repo, storage_service, parsed_doc
    ):
        await self._setup_mocks(adapter, source_doc_repo, storage_service)
        result_obj = MagicMock()
        result_obj.data = {}
        result_obj.model_dump.return_value = {}
        adapter._client.extraction.extract = AsyncMock(return_value=result_obj)

        await adapter.extract(parsed_doc, {"type": "object"}, {})

        call_kwargs = adapter._client.files.create.call_args.kwargs
        assert call_kwargs["purpose"] == "extract"


class TestExtractConfigPassthrough:
    async def _setup_mocks(self, adapter, source_doc_repo, storage_service):
        source_doc = MagicMock()
        source_doc.storage_uri = "uploads/doc.pdf"
        source_doc_repo.get.return_value = source_doc
        storage_service.get.return_value = b"bytes"
        file_obj = MagicMock()
        file_obj.id = "file-1"
        adapter._client.files.create = AsyncMock(return_value=file_obj)
        result_obj = MagicMock()
        result_obj.data = {}
        result_obj.model_dump.return_value = {}
        adapter._client.extraction.extract = AsyncMock(return_value=result_obj)

    async def test_default_mode_and_target(
        self, adapter, source_doc_repo, storage_service, parsed_doc
    ):
        await self._setup_mocks(adapter, source_doc_repo, storage_service)

        await adapter.extract(parsed_doc, {"type": "object"}, {})

        cfg = adapter._client.extraction.extract.call_args.kwargs["config"]
        assert cfg["extraction_mode"] == "MULTIMODAL"
        assert cfg["extraction_target"] == "PER_DOC"

    async def test_optional_flags_absent_when_not_in_config(
        self, adapter, source_doc_repo, storage_service, parsed_doc
    ):
        await self._setup_mocks(adapter, source_doc_repo, storage_service)

        await adapter.extract(parsed_doc, {"type": "object"}, {})

        cfg = adapter._client.extraction.extract.call_args.kwargs["config"]
        assert "cite_sources" not in cfg
        assert "use_reasoning" not in cfg
        assert "confidence_scores" not in cfg
        assert "page_range" not in cfg
        assert "prompt_override" not in cfg

    async def test_system_prompt_maps_to_prompt_override(
        self, adapter, source_doc_repo, storage_service, parsed_doc
    ):
        await self._setup_mocks(adapter, source_doc_repo, storage_service)

        await adapter.extract(
            parsed_doc,
            {"type": "object"},
            {"system_prompt": "Extract only financial data."},
        )

        cfg = adapter._client.extraction.extract.call_args.kwargs["config"]
        assert cfg["prompt_override"] == "Extract only financial data."
        assert "system_prompt" not in cfg

    async def test_all_optional_flags_forwarded(
        self, adapter, source_doc_repo, storage_service, parsed_doc
    ):
        await self._setup_mocks(adapter, source_doc_repo, storage_service)

        await adapter.extract(
            parsed_doc,
            {"type": "object"},
            {
                "cite_sources": True,
                "use_reasoning": True,
                "confidence_scores": False,
                "page_range": "1-3",
                "extraction_mode": "FAST",
                "extraction_target": "PER_PAGE",
            },
        )

        cfg = adapter._client.extraction.extract.call_args.kwargs["config"]
        assert cfg["cite_sources"] is True
        assert cfg["use_reasoning"] is True
        assert cfg["confidence_scores"] is False
        assert cfg["page_range"] == "1-3"
        assert cfg["extraction_mode"] == "FAST"
        assert cfg["extraction_target"] == "PER_PAGE"

    async def test_schema_passed_as_data_schema(
        self, adapter, source_doc_repo, storage_service, parsed_doc
    ):
        await self._setup_mocks(adapter, source_doc_repo, storage_service)
        schema = {"type": "object", "properties": {"name": {"type": "string"}}}

        await adapter.extract(parsed_doc, schema, {})

        call_kwargs = adapter._client.extraction.extract.call_args.kwargs
        assert call_kwargs["data_schema"] == schema
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run --directory backend python -m pytest tests/adapters/extraction/test_llamaextract.py -v -o "addopts="
```

Expected: `TestGetFileBytes` tests PASS, all new tests FAIL with `NotImplementedError`

- [ ] **Step 3: Implement `extract()`**

Replace the `extract()` method in `backend/app/adapters/extraction/llamaextract.py` (keep everything else the same):

```python
    async def extract(
        self,
        parsed_document: Any,
        schema: dict[str, Any],
        config: dict[str, Any] | None = None,
    ) -> ExtractionOutput:
        config = config or {}

        file_bytes = await self._get_file_bytes(parsed_document.source_document_id)
        file_obj = await self._client.files.create(
            file=("document.pdf", file_bytes, "application/octet-stream"),
            purpose="extract",
        )

        extraction_config: dict[str, Any] = {
            "extraction_mode": config.get("extraction_mode", "MULTIMODAL"),
            "extraction_target": config.get("extraction_target", "PER_DOC"),
        }
        if config.get("cite_sources") is not None:
            extraction_config["cite_sources"] = config["cite_sources"]
        if config.get("use_reasoning") is not None:
            extraction_config["use_reasoning"] = config["use_reasoning"]
        if config.get("confidence_scores") is not None:
            extraction_config["confidence_scores"] = config["confidence_scores"]
        if config.get("page_range") is not None:
            extraction_config["page_range"] = config["page_range"]
        if config.get("system_prompt") is not None:
            extraction_config["prompt_override"] = config["system_prompt"]

        t0 = time.monotonic()
        result = await self._client.extraction.extract(
            data_schema=schema,
            file_id=file_obj.id,
            config=extraction_config,
        )
        latency_ms = int((time.monotonic() - t0) * 1000)

        raw_response = result.model_dump() if hasattr(result, "model_dump") else dict(result)

        return ExtractionOutput(
            structured_data=result.data if result.data is not None else {},
            source_parse_run_id=UUID(parsed_document.parse_run_id),
            citations=None,
            provider_response_raw=raw_response,
            extraction_metadata={
                "latency_ms": latency_ms,
                "file_id": str(file_obj.id),
            },
        )
```

- [ ] **Step 4: Run all adapter tests to verify they pass**

```bash
uv run --directory backend python -m pytest tests/adapters/extraction/ -v -o "addopts="
```

Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/adapters/extraction/llamaextract.py \
        backend/tests/adapters/extraction/test_llamaextract.py
git commit -m "feat(extraction): implement LlamaExtractAdapter.extract() — file upload, config passthrough, output mapping"
```

---

## Task 4: Wire DI in router

The `run_extraction` endpoint currently calls `get_extractor(method, credentials)` without dependencies. Update it to also pass `SourceDocumentRepository` and `StorageService` so that `LlamaExtractAdapter` can resolve file bytes at extraction time.

**Files:**
- Modify: `backend/app/routers/extraction.py`

- [ ] **Step 1: Add missing imports to router**

In `backend/app/routers/extraction.py`, add to the existing repository imports block:

```python
from app.repositories.source_document_repository import SourceDocumentRepository
from app.dependencies.documents import get_storage_service
```

- [ ] **Step 2: Update `run_extraction` endpoint to pass dependencies**

In the `run_extraction` endpoint in `backend/app/routers/extraction.py`, replace:

```python
credentials = _resolve_credentials_from_settings(body.extraction_method)
extractor = get_extractor(body.extraction_method, credentials)
```

with:

```python
credentials = _resolve_credentials_from_settings(body.extraction_method)
extractor = get_extractor(
    body.extraction_method,
    credentials,
    {
        "source_document_repo": SourceDocumentRepository(db),
        "storage_service": get_storage_service(),
    },
)
```

- [ ] **Step 3: Run the full extraction test suite**

```bash
uv run --directory backend python -m pytest tests/adapters/extraction/ tests/services/test_extraction_service.py tests/routers/ -v -o "addopts="
```

Expected: all tests PASS

- [ ] **Step 4: Run the full backend test suite to catch regressions**

```bash
uv run --directory backend python -m pytest -o "addopts="
```

Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/extraction.py
git commit -m "feat(extraction): wire SourceDocumentRepository and StorageService into llamaextract adapter via router DI"
```

---

## Out of Scope (follow-up)

The spec's testing strategy mentions two additional tests not covered in this plan:

1. **Integration test** (marked slow, requires `LLAMA_CLOUD_KEY`): end-to-end against a fixture `ParsedDocument`, asserting `structured_data` is non-empty and `source_parse_run_id` matches. Requires a real API key and fixture document — handle as a separate task after the unit tests are green.

2. **Snapshot test on `provider_response_raw` shape**: to catch unexpected SDK changes. Only meaningful against real API responses — add alongside the integration test.
