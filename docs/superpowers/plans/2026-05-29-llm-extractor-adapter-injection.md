# LLMExtractor Adapter Injection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor `LLMExtractor` to receive an `LLMPort` adapter at construction time — matching the `LLMClassifier` pattern — so the extraction router resolves credentials once via `resolve_api_key` + `create_adapter`, and `LLMExtractor` never does its own credential resolution.

**Architecture:** The extraction router reads the provider from `body.llm_config.provider`, calls `resolve_api_key` (already used elsewhere in this router) to decrypt the key, calls `create_adapter` to build the typed adapter, and passes it into `get_extractor` via the `dependencies` dict. `LLMExtractor.__init__` drops `default_provider`/`default_api_key` in favour of `adapter: LLMPort` + `provider: str`. `_resolve_credentials_from_settings` is deleted entirely. This is identical to how `build_classifier` works in `classifier_factory.py`.

**Tech Stack:** Python/FastAPI, `app.services.llm.port.LLMPort`, `app.services.llm.factory.create_adapter`, `app.services.provider_key_service.resolve_api_key`. Tests: pytest + `unittest.mock.AsyncMock/MagicMock`.

---

## File Map

### Modify
- `backend/app/adapters/extraction/llm.py` — drop constructor defaults, accept `adapter: LLMPort` + `provider: str`, remove internal `create_adapter` call
- `backend/app/adapters/extraction/registry.py` — read `adapter` + `provider` from `dependencies` dict for `"llm"` method
- `backend/app/routers/extraction.py` — inline credential resolution for each method, delete `_resolve_credentials_from_settings`

### Tests — rewrite
- `backend/tests/adapters/extraction/test_llm_extractor.py` — all tests that patched `create_adapter` are replaced with direct adapter injection; registry tests updated

---

## Task 1: Refactor `LLMExtractor` — inject `LLMPort`, remove internal `create_adapter`

**Files:**
- Modify: `backend/app/adapters/extraction/llm.py`
- Test: `backend/tests/adapters/extraction/test_llm_extractor.py`

- [ ] **Step 1: Write failing tests that verify the new constructor and adapter-call behaviour**

Replace the *entire* contents of `backend/tests/adapters/extraction/test_llm_extractor.py`:

```python
"""Unit tests for LLMExtractor — adapter injected at construction, no internal create_adapter."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

from app.services.llm.types import CompletionResult, TokenUsage

PARSE_RUN_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def _make_parsed_doc():
    from app.cdm.models import ParsedDocument, Page
    pages = [Page(index=0, block_ids=[])]
    return ParsedDocument(
        id="doc-1", source_document_id="src-1", parse_run_id=PARSE_RUN_ID,
        page_count=1, pages=pages, blocks=[],
    )


def _make_adapter(content: str = "{}") -> MagicMock:
    adapter = MagicMock()
    adapter.complete = AsyncMock(return_value=CompletionResult(
        content=content,
        usage=TokenUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
        latency_ms=100.0, model="llama3.2:8b", provider="ollama_local",
    ))
    return adapter


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------

class TestLLMExtractorProperties:
    def test_extractor_type(self):
        from app.adapters.extraction.llm import LLMExtractor
        assert LLMExtractor(adapter=_make_adapter(), provider="ollama_local").extractor_type == "llm"

    def test_display_name(self):
        from app.adapters.extraction.llm import LLMExtractor
        assert LLMExtractor(adapter=_make_adapter(), provider="ollama_local").display_name == "LLM"

    def test_provider_stored(self):
        from app.adapters.extraction.llm import LLMExtractor
        e = LLMExtractor(adapter=_make_adapter(), provider="anthropic")
        assert e._provider == "anthropic"

    def test_adapter_stored(self):
        from app.adapters.extraction.llm import LLMExtractor
        adapter = _make_adapter()
        e = LLMExtractor(adapter=adapter, provider="openai")
        assert e._adapter is adapter


# ---------------------------------------------------------------------------
# _build_messages (no dependency on provider/adapter)
# ---------------------------------------------------------------------------

class TestLLMExtractorBuildMessages:
    @pytest.fixture
    def extractor(self):
        from app.adapters.extraction.llm import LLMExtractor
        return LLMExtractor(adapter=_make_adapter(), provider="ollama_local")

    def test_uses_default_system_prompt(self, extractor):
        from app.adapters.extraction.llm import DEFAULT_EXTRACTION_SYSTEM_PROMPT
        msgs = extractor._build_messages({"type": "object"}, "ctx", {})
        assert msgs[0]["role"] == "system"
        assert msgs[0]["content"] == DEFAULT_EXTRACTION_SYSTEM_PROMPT

    def test_uses_custom_system_prompt_from_cfg(self, extractor):
        msgs = extractor._build_messages(
            {"type": "object"}, "ctx", {"system_prompt": "Be precise."}
        )
        assert msgs[0]["content"] == "Be precise."

    def test_schema_json_interpolated(self, extractor):
        aug_schema = {"type": "object", "properties": {"name": {"type": "string"}}}
        msgs = extractor._build_messages(aug_schema, "doc text", {})
        assert json.dumps(aug_schema, indent=2) in msgs[1]["content"]

    def test_two_messages_system_then_user(self, extractor):
        msgs = extractor._build_messages({"type": "object"}, "ctx", {})
        assert len(msgs) == 2
        assert msgs[0]["role"] == "system"
        assert msgs[1]["role"] == "user"


# ---------------------------------------------------------------------------
# extract() — injected adapter is used directly, no create_adapter() call
# ---------------------------------------------------------------------------

class TestLLMExtractorExtract:
    @pytest.fixture
    def adapter(self):
        return _make_adapter("{}")

    @pytest.fixture
    def extractor(self, adapter):
        from app.adapters.extraction.llm import LLMExtractor
        return LLMExtractor(adapter=adapter, provider="ollama_local")

    @pytest.fixture
    def parsed_doc(self):
        return _make_parsed_doc()

    async def test_injected_adapter_complete_is_called(self, extractor, adapter, parsed_doc):
        """extract() calls self._adapter.complete — never create_adapter()."""
        schema = {"type": "object", "properties": {}}
        await extractor.extract(parsed_doc, schema, {})
        adapter.complete.assert_called_once()

    async def test_provider_flows_into_llm_config(self, parsed_doc):
        """The provider passed to __init__ ends up in LLMConfig.provider."""
        from app.adapters.extraction.llm import LLMExtractor
        adapter = _make_adapter("{}")
        e = LLMExtractor(adapter=adapter, provider="anthropic")
        schema = {"type": "object", "properties": {}}
        await e.extract(parsed_doc, schema, {})
        llm_config_arg = adapter.complete.call_args.args[1]
        assert llm_config_arg.provider == "anthropic"

    async def test_prompt_config_model_forwarded(self, extractor, adapter, parsed_doc):
        schema = {"type": "object", "properties": {}}
        llm_cfg_dict = {"provider": "ollama_local", "model": "llama3.2:8b", "maxTokens": 8192}
        await extractor.extract(parsed_doc, schema, {"llm_config": llm_cfg_dict})
        llm_config_arg = adapter.complete.call_args.args[1]
        assert llm_config_arg.max_tokens == 8192

    async def test_structured_output_schema_passed_for_json_schema_mode(self, parsed_doc):
        from app.adapters.extraction.llm import LLMExtractor
        adapter = _make_adapter('{"total": 99}')
        e = LLMExtractor(adapter=adapter, provider="openai")
        schema = {"type": "object", "properties": {"total": {"type": "number"}}}
        await e.extract(parsed_doc, schema, {})
        llm_config_arg = adapter.complete.call_args.args[1]
        assert llm_config_arg.structured_output_mode == "json_schema"
        assert llm_config_arg.structured_output_schema is not None

    async def test_returns_structured_data_without_source_fields(self, extractor, adapter, parsed_doc):
        schema = {"type": "object", "properties": {"total": {"type": "number"}}}
        raw = {"total": 500, "total__source": {"page_index": 1}}
        adapter.complete = AsyncMock(return_value=CompletionResult(
            content=json.dumps(raw),
            usage=TokenUsage(10, 20, 30), latency_ms=50, model="m", provider="p",
        ))
        output = await extractor.extract(parsed_doc, schema, {})
        assert output.structured_data == {"total": 500}
        assert output.source_parse_run_id == UUID(PARSE_RUN_ID)

    async def test_usage_recorded_in_extraction_metadata(self, extractor, parsed_doc):
        schema = {"type": "object", "properties": {}}
        output = await extractor.extract(parsed_doc, schema, {})
        assert output.extraction_metadata["usage"]["prompt_tokens"] == 10
        assert output.extraction_metadata["usage"]["completion_tokens"] == 20

    async def test_raises_extraction_error_on_non_json_response(self, parsed_doc):
        from app.adapters.extraction.llm import LLMExtractor
        from app.ports.data_extraction import ExtractionError
        adapter = _make_adapter("not valid json at all")
        e = LLMExtractor(adapter=adapter, provider="openai")
        schema = {"type": "object", "properties": {}}
        with pytest.raises(ExtractionError, match="non-JSON"):
            await e.extract(parsed_doc, schema, {})

    async def test_citations_populated_from_source_fields(self, parsed_doc):
        from app.adapters.extraction.llm import LLMExtractor
        schema = {"type": "object", "properties": {"vendor": {"type": "string"}}}
        raw = {"vendor": "Acme", "vendor__source": {"page_index": 2, "block_id": "blk-1"}}
        adapter = _make_adapter(json.dumps(raw))
        e = LLMExtractor(adapter=adapter, provider="openai")
        output = await e.extract(parsed_doc, schema, {})
        assert len(output.citations) == 1
        assert output.citations[0].field_path == "vendor"


# ---------------------------------------------------------------------------
# Registry integration
# ---------------------------------------------------------------------------

class TestRegistryLLM:
    def test_get_extractor_returns_llm_extractor(self):
        from app.adapters.extraction.llm import LLMExtractor
        from app.adapters.extraction.registry import get_extractor
        extractor = get_extractor("llm", {}, {"adapter": _make_adapter(), "provider": "openai"})
        assert isinstance(extractor, LLMExtractor)

    def test_get_extractor_llm_raises_without_adapter(self):
        from app.adapters.extraction.registry import get_extractor
        with pytest.raises(ValueError, match="adapter"):
            get_extractor("llm", {}, {})

    def test_llm_method_in_catalogue(self):
        from app.adapters.extraction.registry import get_known_extractors
        methods = {e["extraction_method"] for e in get_known_extractors()}
        assert "llm" in methods
```

- [ ] **Step 2: Run the new tests to confirm they fail**

```bash
uv run --directory backend python -m pytest tests/adapters/extraction/test_llm_extractor.py -x -q 2>&1 | head -30
```

Expected: failures because `LLMExtractor()` still takes `default_provider`/`default_api_key` and `get_extractor("llm", {}, {})` doesn't raise.

- [ ] **Step 3: Rewrite `backend/app/adapters/extraction/llm.py`**

Replace the entire file:

```python
"""Generic LLM extraction adapter.

Receives a pre-built LLMPort adapter at construction time.
The caller (router or test) is responsible for resolving credentials
and calling create_adapter() before instantiating LLMExtractor.
"""
import json
import time
from typing import Any
from uuid import UUID

from app.adapters.extraction.llm_context import (
    augment_schema_with_sources,
    build_extraction_context,
    strip_source_fields,
)
from app.cdm.models import ParsedDocument
from app.ports.data_extraction import DataExtractor, ExtractionError, ExtractionOutput
from app.schemas.prompt_config import PromptConfig
from app.services.llm.port import LLMPort
from app.services.llm.prompt_config import resolve_llm_config
from app.services.llm.types import LLMConfig, LLMConnectionError

DEFAULT_EXTRACTION_SYSTEM_PROMPT = (
    "You are a structured data extraction assistant. Extract information from the provided "
    "document according to the given JSON schema. Be precise and faithful to the source text. "
    "Only extract values that are explicitly present in the document."
)

DEFAULT_USER_PROMPT_TEMPLATE = """\
Extract structured data from the following document according to this JSON schema:

<schema>
{schema_json}
</schema>

For each field you extract, include a corresponding `{{field_name}}__source` object \
with `page_index` (integer, required) and `block_id` (string, if available) indicating \
where in the document you found the value.

<document>
{document_context}
</document>

Return a single JSON object that conforms to the schema (including __source fields)."""


class LLMExtractor(DataExtractor):
    """Structured extraction via any LLMPort adapter."""

    extractor_type = "llm"
    display_name = "LLM"

    def __init__(self, adapter: LLMPort, provider: str = "ollama_local") -> None:
        self._adapter = adapter
        self._provider = provider

    def _build_messages(
        self,
        aug_schema: dict[str, Any],
        context: str,
        cfg: dict[str, Any],
    ) -> list[dict[str, str]]:
        system_prompt = cfg.get("system_prompt") or DEFAULT_EXTRACTION_SYSTEM_PROMPT
        schema_json = json.dumps(aug_schema, indent=2)
        template = cfg.get("user_prompt_template") or DEFAULT_USER_PROMPT_TEMPLATE
        user_content = template.format(schema_json=schema_json, document_context=context)
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

    async def extract(
        self,
        parsed_document: ParsedDocument,
        schema: dict[str, Any],
        config: dict[str, Any] | None = None,
    ) -> ExtractionOutput:
        cfg = dict(config or {})

        prompt_config: PromptConfig | None = None
        if cfg.get("llm_config"):
            prompt_config = PromptConfig.model_validate(cfg["llm_config"])
        resolved = resolve_llm_config(
            prompt_config,
            default_provider=self._provider,
            default_model="llama3.2:8b",
        )
        if prompt_config and prompt_config.system_prompt:
            cfg["system_prompt"] = prompt_config.system_prompt

        structured_output_mode = cfg.get("structured_output_mode", "json_schema")
        context = build_extraction_context(parsed_document, cfg.get("inject_block_ids", False))
        aug_schema = augment_schema_with_sources(schema)
        messages = self._build_messages(aug_schema, context, cfg)

        llm_config = LLMConfig(
            provider=resolved.provider,
            model=resolved.model,
            temperature=resolved.temperature,
            max_tokens=resolved.max_tokens,
            structured_output_mode=structured_output_mode,
            structured_output_schema=aug_schema if structured_output_mode == "json_schema" else None,
        )

        t0 = time.monotonic()
        try:
            result = await self._adapter.complete(messages, llm_config)
        except LLMConnectionError as exc:
            raise ExtractionError(
                f"Cannot connect to LLM provider '{resolved.provider}': {exc}"
            ) from exc
        latency_ms = int((time.monotonic() - t0) * 1000)

        try:
            raw = json.loads(result.content)
        except (json.JSONDecodeError, ValueError) as exc:
            raise ExtractionError(
                f"Model returned non-JSON response: {result.content[:200]!r}"
            ) from exc

        structured_data, citations = strip_source_fields(raw, schema)

        return ExtractionOutput(
            structured_data=structured_data,
            source_parse_run_id=UUID(parsed_document.parse_run_id),
            citations=citations,
            provider_response_raw=raw,
            extraction_metadata={
                "model": llm_config.model,
                "provider": llm_config.provider,
                "latency_ms": latency_ms,
                "usage": {
                    "prompt_tokens": result.usage.prompt_tokens,
                    "completion_tokens": result.usage.completion_tokens,
                    "total_tokens": result.usage.total_tokens,
                } if result.usage else None,
            },
        )
```

- [ ] **Step 4: Run tests and confirm they pass**

```bash
uv run --directory backend python -m pytest tests/adapters/extraction/test_llm_extractor.py -x -q 2>&1 | tail -10
```

Expected: all tests pass except the two registry tests (`test_get_extractor_returns_llm_extractor`, `test_get_extractor_llm_raises_without_adapter`) which fail because the registry hasn't been updated yet.

- [ ] **Step 5: Commit**

```bash
git add backend/app/adapters/extraction/llm.py backend/tests/adapters/extraction/test_llm_extractor.py
git commit -m "refactor(extraction): LLMExtractor takes adapter: LLMPort, removes internal create_adapter"
```

---

## Task 2: Update `get_extractor` registry — read adapter from dependencies

**Files:**
- Modify: `backend/app/adapters/extraction/registry.py:81-86`

- [ ] **Step 1: Update the `"llm"` branch in `get_extractor`**

In `backend/app/adapters/extraction/registry.py`, replace the `if method == "llm":` block:

```python
    if method == "llm":
        from app.adapters.extraction.llm import LLMExtractor
        deps = dependencies or {}
        adapter = deps.get("adapter")
        if adapter is None:
            raise ValueError(
                "LLMExtractor requires 'adapter' in the dependencies dict. "
                "Call create_adapter() in the router and pass the result as dependencies['adapter']."
            )
        provider = deps.get("provider", "ollama_local")
        return LLMExtractor(adapter=adapter, provider=provider)
```

- [ ] **Step 2: Run the full extractor test suite**

```bash
uv run --directory backend python -m pytest tests/adapters/extraction/ -x -q 2>&1 | tail -10
```

Expected: all tests pass (including the two registry tests that were failing after Task 1).

- [ ] **Step 3: Commit**

```bash
git add backend/app/adapters/extraction/registry.py
git commit -m "refactor(extraction): registry passes adapter from dependencies to LLMExtractor"
```

---

## Task 3: Update extraction router — inline credential resolution, delete `_resolve_credentials_from_settings`

**Files:**
- Modify: `backend/app/routers/extraction.py`

- [ ] **Step 1: Add `create_adapter` import**

At the top of `backend/app/routers/extraction.py`, add alongside the existing LLM imports:

```python
from app.services.llm.factory import create_adapter
```

- [ ] **Step 2: Replace the `run_extraction` endpoint body**

Find the `async def run_extraction(...)` function. Replace its `try` block (from the `provider_key_repo = ProviderKeyRepository(db)` line through `return result`) with:

```python
    try:
        provider_key_repo = ProviderKeyRepository(db)

        if body.extraction_method == "llm":
            provider = (body.llm_config.provider if body.llm_config else None) or "ollama_local"
            api_key = await resolve_api_key(provider_key_repo, current_user.id, provider)
            if api_key is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"No API key configured for provider '{provider}'",
                )
            adapter = create_adapter(provider, api_key)
            extractor = get_extractor(
                "llm",
                {},
                {
                    "source_document_repo": SourceDocumentRepository(db),
                    "storage_service": get_storage_service(),
                    "adapter": adapter,
                    "provider": provider,
                },
            )
        else:
            llama_key = await resolve_api_key(provider_key_repo, current_user.id, "llama_cloud")
            extractor = get_extractor(
                body.extraction_method,
                {"api_key": llama_key} if llama_key else {},
                {
                    "source_document_repo": SourceDocumentRepository(db),
                    "storage_service": get_storage_service(),
                },
            )

        result = await service.run_extraction(
            parse_run_id=body.parse_run_id,
            extraction_schema_id=body.extraction_schema_id,
            extraction_method=body.extraction_method,
            user_id=current_user.id,
            config=body.config,
            llm_config=body.llm_config,
            user_prompt_template=body.user_prompt_template,
        )

        background_tasks.add_task(
            process_extraction,
            extraction_result_id=result.id,
            result_repo=ExtractionResultRepository(db),
            parsed_document_repo=ParsedDocumentRepository(db),
            extractor=extractor,
        )

        return result

    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
```

- [ ] **Step 3: Delete `_resolve_credentials_from_settings`**

Remove the entire `_resolve_credentials_from_settings` function (lines 53–85 in the original file — the async function and its docstring).

Also remove these now-unused imports from the top of the router file:
```python
from app.config import settings  # only used by _resolve_credentials_from_settings
```
Check that `settings` is not referenced anywhere else in the file before removing it. If it is, keep the import.

- [ ] **Step 4: Run the extraction test suite**

```bash
uv run --directory backend python -m pytest tests/adapters/extraction/ tests/routers/test_extraction_router.py -x -q 2>&1 | tail -15
```

Expected: all tests pass.

- [ ] **Step 5: Run the full backend suite to check for regressions**

```bash
uv run --directory backend python -m pytest -o "addopts=" -q 2>&1 | tail -10
```

Expected: no new failures.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/extraction.py
git commit -m "refactor(extraction): router resolves credentials + builds adapter, deletes _resolve_credentials_from_settings"
```
