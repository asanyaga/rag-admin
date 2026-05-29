# Preserve Extraction Failure Data Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When an LLM extraction fails, write `extraction_metadata` (model, provider, latency, token counts) and `provider_response_raw` (full raw LLM response) to the database before marking the result as failed — so every failed run carries as much diagnostic data as a successful one.

**Architecture:** `ExtractionError` is enriched with two optional fields (`raw_response: str | None`, `metadata: dict | None`) so the extractor can bundle partial LLM data into the exception it already raises. `LLMExtractor.extract()` populates these fields at both raise sites. A new `update_failed()` repository method writes `status=failed` + `status_message` + whatever partial data is present atomically. `process_extraction()` switches from `update_status()` to `update_failed()`, unpacking partial data from the exception when it is an `ExtractionError`.

No database migration is needed — `extraction_metadata` and `provider_response_raw` columns already exist; they are just never written on failure today.

**Tech Stack:** Python / FastAPI, SQLAlchemy 2.0 async, pytest + `unittest.mock`.

---

## File Map

### Modify
- `backend/app/ports/data_extraction.py` — add `__init__` to `ExtractionError` with `raw_response: str | None` and `metadata: dict | None`
- `backend/app/adapters/extraction/llm.py` — attach partial data to `ExtractionError` at the connection-error and JSON-parse-error raise sites
- `backend/app/repositories/extraction_result_repository.py` — add `update_failed()` method
- `backend/app/services/extraction_service.py` — switch the `except Exception` handler in `process_extraction` from `update_status()` to `update_failed()`

### Tests — add to existing files
- `backend/tests/ports/test_data_extraction_port.py` — `ExtractionError` carries data
- `backend/tests/adapters/extraction/test_llm_extractor.py` — raised errors carry the right partial data
- `backend/tests/repositories/test_extraction_result_repository.py` — `update_failed()` writes correct fields
- `backend/tests/services/test_extraction_service.py` — `process_extraction` calls `update_failed` with partial data

---

## Task 1: Enrich `ExtractionError` with optional partial data

**Files:**
- Modify: `backend/app/ports/data_extraction.py`
- Test: `backend/tests/ports/test_data_extraction_port.py`

- [ ] **Step 1: Write failing tests**

Add this class to `backend/tests/ports/test_data_extraction_port.py`:

```python
class TestExtractionError:
    def test_default_attributes_are_none(self):
        from app.ports.data_extraction import ExtractionError
        exc = ExtractionError("something failed")
        assert exc.raw_response is None
        assert exc.metadata is None
        assert str(exc) == "something failed"

    def test_carries_raw_response(self):
        from app.ports.data_extraction import ExtractionError
        exc = ExtractionError("parse error", raw_response="not valid json")
        assert exc.raw_response == "not valid json"

    def test_carries_metadata(self):
        from app.ports.data_extraction import ExtractionError
        meta = {"model": "llama3.2:8b", "provider": "ollama_local", "latency_ms": 300}
        exc = ExtractionError("conn failed", metadata=meta)
        assert exc.metadata == meta

    def test_is_still_an_exception(self):
        from app.ports.data_extraction import ExtractionError
        with pytest.raises(ExtractionError):
            raise ExtractionError("test")
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run --directory backend python -m pytest tests/ports/test_data_extraction_port.py::TestExtractionError -x -q 2>&1 | head -20
```

Expected: `TypeError: ExtractionError() takes no keyword arguments` or similar.

- [ ] **Step 3: Replace `ExtractionError` in `backend/app/ports/data_extraction.py`**

Replace:
```python
class ExtractionError(Exception):
    """Raised by LLM extraction adapters for recoverable extraction failures."""
```

With:
```python
class ExtractionError(Exception):
    """Raised by extractors; carries optional partial LLM data for the failure handler."""

    def __init__(
        self,
        message: str,
        raw_response: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.raw_response = raw_response
        self.metadata = metadata
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
uv run --directory backend python -m pytest tests/ports/test_data_extraction_port.py -x -q 2>&1 | tail -5
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/ports/data_extraction.py backend/tests/ports/test_data_extraction_port.py
git commit -m "refactor(extraction): ExtractionError carries optional raw_response and metadata"
```

---

## Task 2: Update `LLMExtractor` to attach partial data at each raise site

**Files:**
- Modify: `backend/app/adapters/extraction/llm.py`
- Test: `backend/tests/adapters/extraction/test_llm_extractor.py`

- [ ] **Step 1: Write failing tests**

Add these two test methods inside the existing `TestLLMExtractorExtract` class in `backend/tests/adapters/extraction/test_llm_extractor.py`:

```python
    async def test_extraction_error_carries_raw_response_and_metadata_on_parse_failure(self, parsed_doc):
        from app.adapters.extraction.llm import LLMExtractor
        from app.ports.data_extraction import ExtractionError
        adapter = _make_adapter("not valid json at all")
        e = LLMExtractor(adapter=adapter, provider="openai")
        with pytest.raises(ExtractionError) as exc_info:
            await e.extract(parsed_doc, {"type": "object", "properties": {}}, {})
        err = exc_info.value
        assert err.raw_response == "not valid json at all"
        assert err.metadata is not None
        assert err.metadata["provider"] == "openai"
        assert "latency_ms" in err.metadata

    async def test_extraction_error_carries_metadata_on_connection_error(self, parsed_doc):
        from app.adapters.extraction.llm import LLMExtractor
        from app.ports.data_extraction import ExtractionError
        from app.services.llm.types import LLMConnectionError
        adapter = MagicMock()
        adapter.complete = AsyncMock(side_effect=LLMConnectionError("timeout"))
        e = LLMExtractor(adapter=adapter, provider="anthropic")
        with pytest.raises(ExtractionError) as exc_info:
            await e.extract(parsed_doc, {"type": "object", "properties": {}}, {})
        err = exc_info.value
        assert err.metadata is not None
        assert err.metadata["provider"] == "anthropic"
        assert err.raw_response is None
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run --directory backend python -m pytest tests/adapters/extraction/test_llm_extractor.py::TestLLMExtractorExtract::test_extraction_error_carries_raw_response_and_metadata_on_parse_failure tests/adapters/extraction/test_llm_extractor.py::TestLLMExtractorExtract::test_extraction_error_carries_metadata_on_connection_error -x -q 2>&1 | tail -10
```

Expected: `AssertionError: assert None is not None` (the error has no metadata yet).

- [ ] **Step 3: Update both raise sites in `backend/app/adapters/extraction/llm.py`**

In `extract()`, replace the connection-error handler (currently lines ~110–114):

```python
        t0 = time.monotonic()
        try:
            result = await self._adapter.complete(messages, llm_config)
        except LLMConnectionError as exc:
            raise ExtractionError(
                f"Cannot connect to LLM provider '{resolved.provider}': {exc}",
                metadata={
                    "model": llm_config.model,
                    "provider": llm_config.provider,
                },
            ) from exc
        latency_ms = int((time.monotonic() - t0) * 1000)
```

Replace the JSON-parse-error handler (currently lines ~118–122):

```python
        try:
            raw = json.loads(_strip_code_fences(result.content))
        except (json.JSONDecodeError, ValueError) as exc:
            raise ExtractionError(
                f"Model returned non-JSON response: {result.content[:200]!r}",
                raw_response=result.content,
                metadata={
                    "model": llm_config.model,
                    "provider": llm_config.provider,
                    "latency_ms": latency_ms,
                    "usage": {
                        "prompt_tokens": result.usage.prompt_tokens,
                        "completion_tokens": result.usage.completion_tokens,
                        "total_tokens": result.usage.total_tokens,
                    } if result.usage else None,
                },
            ) from exc
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
uv run --directory backend python -m pytest tests/adapters/extraction/test_llm_extractor.py -x -q 2>&1 | tail -5
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/adapters/extraction/llm.py backend/tests/adapters/extraction/test_llm_extractor.py
git commit -m "refactor(extraction): attach partial LLM data to ExtractionError at raise sites"
```

---

## Task 3: Add `update_failed()` to `ExtractionResultRepository`

**Files:**
- Modify: `backend/app/repositories/extraction_result_repository.py`
- Test: `backend/tests/repositories/test_extraction_result_repository.py`

- [ ] **Step 1: Write failing tests**

Add this class to `backend/tests/repositories/test_extraction_result_repository.py`:

```python
class TestUpdateFailed:
    @pytest.mark.asyncio
    async def test_sets_status_failed_and_message(self):
        mock_result = _make_mock_result()
        session = AsyncMock()
        session.execute.return_value.scalar_one_or_none.return_value = mock_result
        session.commit = AsyncMock()
        session.refresh = AsyncMock()

        repo = ExtractionResultRepository(session)
        await repo.update_failed(mock_result.id, "something went wrong")

        assert mock_result.status == ExtractionResultStatus.failed
        assert mock_result.status_message == "something went wrong"

    @pytest.mark.asyncio
    async def test_stores_extraction_metadata_when_provided(self):
        mock_result = _make_mock_result()
        session = AsyncMock()
        session.execute.return_value.scalar_one_or_none.return_value = mock_result
        session.commit = AsyncMock()
        session.refresh = AsyncMock()

        meta = {"model": "gpt-4o", "provider": "openai", "latency_ms": 500}
        repo = ExtractionResultRepository(session)
        await repo.update_failed(mock_result.id, "parse failed", extraction_metadata=meta)

        assert mock_result.extraction_metadata == meta

    @pytest.mark.asyncio
    async def test_stores_provider_response_raw_when_provided(self):
        mock_result = _make_mock_result()
        session = AsyncMock()
        session.execute.return_value.scalar_one_or_none.return_value = mock_result
        session.commit = AsyncMock()
        session.refresh = AsyncMock()

        raw = {"raw_content": "not json content here"}
        repo = ExtractionResultRepository(session)
        await repo.update_failed(mock_result.id, "parse failed", provider_response_raw=raw)

        assert mock_result.provider_response_raw == raw

    @pytest.mark.asyncio
    async def test_does_not_overwrite_existing_metadata_when_not_passed(self):
        mock_result = _make_mock_result(extraction_metadata={"prior": "value"})
        session = AsyncMock()
        session.execute.return_value.scalar_one_or_none.return_value = mock_result
        session.commit = AsyncMock()
        session.refresh = AsyncMock()

        repo = ExtractionResultRepository(session)
        await repo.update_failed(mock_result.id, "oops")

        assert mock_result.extraction_metadata == {"prior": "value"}

    @pytest.mark.asyncio
    async def test_returns_none_when_result_not_found(self):
        session = AsyncMock()
        session.execute.return_value.scalar_one_or_none.return_value = None

        repo = ExtractionResultRepository(session)
        result = await repo.update_failed(uuid4(), "oops")

        assert result is None
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run --directory backend python -m pytest tests/repositories/test_extraction_result_repository.py::TestUpdateFailed -x -q 2>&1 | head -15
```

Expected: `AttributeError: 'ExtractionResultRepository' object has no attribute 'update_failed'`.

- [ ] **Step 3: Add `update_failed()` to the repository**

Add this method to `ExtractionResultRepository` in `backend/app/repositories/extraction_result_repository.py`, after `update_status`:

```python
    async def update_failed(
        self,
        result_id: UUID,
        status_message: str,
        extraction_metadata: dict | None = None,
        provider_response_raw: dict | None = None,
    ) -> ExtractionResult | None:
        """Mark as failed, preserving any partial LLM data already collected."""
        extraction_result = await self.get_by_id(result_id)
        if not extraction_result:
            return None
        extraction_result.status = ExtractionResultStatus.failed
        extraction_result.status_message = status_message
        if extraction_metadata is not None:
            extraction_result.extraction_metadata = extraction_metadata
        if provider_response_raw is not None:
            extraction_result.provider_response_raw = provider_response_raw
        await self.session.commit()
        await self.session.refresh(extraction_result)
        return extraction_result
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
uv run --directory backend python -m pytest tests/repositories/test_extraction_result_repository.py -x -q 2>&1 | tail -5
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/repositories/extraction_result_repository.py backend/tests/repositories/test_extraction_result_repository.py
git commit -m "feat(extraction): add update_failed() to repository — writes status + partial LLM data"
```

---

## Task 4: Update `process_extraction` to use `update_failed`

**Files:**
- Modify: `backend/app/services/extraction_service.py`
- Test: `backend/tests/services/test_extraction_service.py`

- [ ] **Step 1: Write failing tests**

Add these three test methods inside the existing `TestProcessExtraction` class in `backend/tests/services/test_extraction_service.py`:

```python
    @pytest.mark.asyncio
    async def test_saves_metadata_and_raw_response_on_extraction_error(self):
        from app.ports.data_extraction import ExtractionError
        parse_run_id = uuid4()
        result_id = uuid4()
        cdm_content = _make_cdm_doc(str(parse_run_id), str(uuid4())).model_dump()

        mock_extraction_result = MagicMock()
        mock_extraction_result.source_parse_run_id = parse_run_id
        mock_extraction_result.schema_definition_snapshot = {"type": "object"}
        mock_extraction_result.config = None

        mock_orm_parsed_doc = MagicMock()
        mock_orm_parsed_doc.content = cdm_content

        mock_result_repo = AsyncMock()
        mock_result_repo.get_by_id.return_value = mock_extraction_result
        mock_parsed_doc_repo = AsyncMock()
        mock_parsed_doc_repo.get_by_run.return_value = mock_orm_parsed_doc

        meta = {"model": "llama3.2:8b", "provider": "ollama_local", "latency_ms": 200}
        extractor = MagicMock()
        extractor.extract = AsyncMock(side_effect=ExtractionError(
            "non-JSON response", raw_response="not json content", metadata=meta,
        ))

        await process_extraction(
            extraction_result_id=result_id,
            result_repo=mock_result_repo,
            parsed_document_repo=mock_parsed_doc_repo,
            extractor=extractor,
        )

        mock_result_repo.update_failed.assert_called_once()
        kwargs = mock_result_repo.update_failed.call_args.kwargs
        assert kwargs["extraction_metadata"] == meta
        assert kwargs["provider_response_raw"] == {"raw_content": "not json content"}
        assert "non-JSON response" in kwargs["status_message"]

    @pytest.mark.asyncio
    async def test_saves_metadata_only_on_connection_error(self):
        from app.ports.data_extraction import ExtractionError
        parse_run_id = uuid4()
        result_id = uuid4()
        cdm_content = _make_cdm_doc(str(parse_run_id), str(uuid4())).model_dump()

        mock_extraction_result = MagicMock()
        mock_extraction_result.source_parse_run_id = parse_run_id
        mock_extraction_result.schema_definition_snapshot = {"type": "object"}
        mock_extraction_result.config = None

        mock_orm_parsed_doc = MagicMock()
        mock_orm_parsed_doc.content = cdm_content

        mock_result_repo = AsyncMock()
        mock_result_repo.get_by_id.return_value = mock_extraction_result
        mock_parsed_doc_repo = AsyncMock()
        mock_parsed_doc_repo.get_by_run.return_value = mock_orm_parsed_doc

        meta = {"model": "gpt-4o", "provider": "openai"}
        extractor = MagicMock()
        extractor.extract = AsyncMock(side_effect=ExtractionError(
            "Cannot connect to LLM provider 'openai'", metadata=meta
        ))

        await process_extraction(
            extraction_result_id=result_id,
            result_repo=mock_result_repo,
            parsed_document_repo=mock_parsed_doc_repo,
            extractor=extractor,
        )

        mock_result_repo.update_failed.assert_called_once()
        kwargs = mock_result_repo.update_failed.call_args.kwargs
        assert kwargs["extraction_metadata"] == meta
        assert kwargs["provider_response_raw"] is None

    @pytest.mark.asyncio
    async def test_saves_no_partial_data_on_generic_exception(self):
        parse_run_id = uuid4()
        result_id = uuid4()
        cdm_content = _make_cdm_doc(str(parse_run_id), str(uuid4())).model_dump()

        mock_extraction_result = MagicMock()
        mock_extraction_result.source_parse_run_id = parse_run_id
        mock_extraction_result.schema_definition_snapshot = {"type": "object"}
        mock_extraction_result.config = None

        mock_orm_parsed_doc = MagicMock()
        mock_orm_parsed_doc.content = cdm_content

        mock_result_repo = AsyncMock()
        mock_result_repo.get_by_id.return_value = mock_extraction_result
        mock_parsed_doc_repo = AsyncMock()
        mock_parsed_doc_repo.get_by_run.return_value = mock_orm_parsed_doc

        extractor = MagicMock()
        extractor.extract = AsyncMock(side_effect=RuntimeError("unexpected crash"))

        await process_extraction(
            extraction_result_id=result_id,
            result_repo=mock_result_repo,
            parsed_document_repo=mock_parsed_doc_repo,
            extractor=extractor,
        )

        mock_result_repo.update_failed.assert_called_once()
        kwargs = mock_result_repo.update_failed.call_args.kwargs
        assert kwargs["extraction_metadata"] is None
        assert kwargs["provider_response_raw"] is None
        assert "unexpected crash" in kwargs["status_message"]
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run --directory backend python -m pytest tests/services/test_extraction_service.py::TestProcessExtraction::test_saves_metadata_and_raw_response_on_extraction_error -x -q 2>&1 | tail -10
```

Expected: `AssertionError` — `update_failed` was not called (only `update_status` is called today).

- [ ] **Step 3: Add `ExtractionError` import to the service**

At the top of `backend/app/services/extraction_service.py`, add:

```python
from app.ports.data_extraction import DataExtractor, ExtractionError
```

(Replace the existing `from app.ports.data_extraction import DataExtractor` line.)

- [ ] **Step 4: Replace the `except Exception` handler in `process_extraction`**

In `backend/app/services/extraction_service.py`, replace:

```python
    except Exception as e:
        logger.exception("Extraction failed for result=%s", extraction_result_id)
        try:
            await result_repo.update_status(
                extraction_result_id,
                ExtractionResultStatus.failed,
                str(e),
            )
        except Exception:
            logger.exception("Failed to update extraction result status for %s", extraction_result_id)
```

With:

```python
    except Exception as e:
        logger.exception("Extraction failed for result=%s", extraction_result_id)
        raw_response: dict | None = None
        metadata: dict | None = None
        if isinstance(e, ExtractionError):
            if e.raw_response is not None:
                raw_response = {"raw_content": e.raw_response}
            metadata = e.metadata
        try:
            await result_repo.update_failed(
                extraction_result_id,
                status_message=str(e),
                extraction_metadata=metadata,
                provider_response_raw=raw_response,
            )
        except Exception:
            logger.exception("Failed to update extraction result status for %s", extraction_result_id)
```

- [ ] **Step 5: Run all new service tests**

```bash
uv run --directory backend python -m pytest tests/services/test_extraction_service.py -x -q 2>&1 | tail -5
```

Expected: all tests pass, including the pre-existing `test_marks_failed_when_parse_run_not_found` which uses `update_status` (that path is unaffected — it returns early before the except block).

- [ ] **Step 6: Run the full backend suite**

```bash
uv run --directory backend python -m pytest -o "addopts=" -q 2>&1 | tail -5
```

Expected: no new failures.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/extraction_service.py backend/tests/services/test_extraction_service.py
git commit -m "feat(extraction): process_extraction saves partial LLM data on failure via update_failed"
```
