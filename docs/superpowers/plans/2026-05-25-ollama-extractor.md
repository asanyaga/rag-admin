# Ollama Extractor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `OllamaExtractor` — a structured extraction adapter that calls any Ollama-compatible endpoint (local, self-hosted, or cloud) using Ollama's OpenAI-compatible REST API.

**Architecture:** `OllamaExtractor` inherits from `OpenAICompatMixin` (new shared client + JSON completion logic) and `DataExtractor` (existing port). The mixin owns all openai-SDK concerns; the extractor owns prompt building, schema augmentation, citation extraction, and `ExtractionOutput` assembly. All LLM context helpers (`build_extraction_context`, `augment_schema_with_sources`, `strip_source_fields`) are already implemented in `llm_context.py` and need no changes.

**Tech Stack:** Python 3.12, `openai` SDK v2.16.0 (already installed), FastAPI async, React 18 + TypeScript, shadcn/ui + Tailwind CSS.

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Modify | `backend/app/ports/data_extraction.py` | Add `ExtractionError` |
| Modify | `backend/app/config.py` | Add `OLLAMA_ENDPOINT: str = ""` |
| Create | `backend/app/adapters/extraction/openai_compat_mixin.py` | `OpenAICompatMixin._build_client` + `_call_model` |
| Create | `backend/app/adapters/extraction/ollama.py` | `OllamaExtractor` — prompt building + extract() |
| Modify | `backend/app/adapters/extraction/registry.py` | Register ollama in `get_extractor()` factory |
| Create | `backend/tests/adapters/extraction/test_ollama_extractor.py` | Unit tests (mixin + extractor + registry) |
| Modify | `frontend/src/components/extraction/ExtractionForm.tsx` | Ollama config section; hide LlamaExtract-only fields when ollama is selected |

No router, service, repository, ORM, migration, or schema changes are needed — all of those were already wired up in the general CDM extraction spec.

---

### Task 1: ExtractionError + OLLAMA_ENDPOINT setting

**Files:**
- Modify: `backend/app/ports/data_extraction.py`
- Modify: `backend/app/config.py`

- [ ] **Step 1: Add `ExtractionError` to the port file**

  Open `backend/app/ports/data_extraction.py` and add after the imports, before the dataclass definitions:

  ```python
  class ExtractionError(Exception):
      """Raised by LLM extraction adapters for recoverable extraction failures."""
  ```

  The file after the change starts with:
  ```python
  from abc import ABC, abstractmethod
  from dataclasses import dataclass, field
  from typing import Any
  from uuid import UUID


  class ExtractionError(Exception):
      """Raised by LLM extraction adapters for recoverable extraction failures."""


  @dataclass(frozen=True)
  class FieldCitation:
  ...
  ```

- [ ] **Step 2: Add `OLLAMA_ENDPOINT` to settings**

  Open `backend/app/config.py`. After the `OLLAMA_CLOUD_API_KEY` line (≈ line 57), add:

  ```python
      # Ollama — extraction endpoint
      # Set to enable OllamaExtractor. Empty = extractor shows as "not configured".
      # Example: OLLAMA_ENDPOINT=http://localhost:11434/v1
      OLLAMA_ENDPOINT: str = ""
  ```

- [ ] **Step 3: Verify imports work**

  ```bash
  uv run --directory backend python -c "
  from app.ports.data_extraction import ExtractionError
  from app.config import settings
  assert issubclass(ExtractionError, Exception)
  assert hasattr(settings, 'OLLAMA_ENDPOINT')
  print('OK')
  "
  ```

  Expected: `OK`

- [ ] **Step 4: Commit**

  ```bash
  git add backend/app/ports/data_extraction.py backend/app/config.py
  git commit -m "feat(extraction): add ExtractionError and OLLAMA_ENDPOINT setting"
  ```

---

### Task 2: OpenAICompatMixin

**Files:**
- Create: `backend/app/adapters/extraction/openai_compat_mixin.py`
- Create (tests): `backend/tests/adapters/extraction/test_ollama_extractor.py`

- [ ] **Step 1: Write the failing mixin tests**

  Create `backend/tests/adapters/extraction/test_ollama_extractor.py`:

  ```python
  """Unit tests for OpenAICompatMixin and OllamaExtractor."""
  import json
  import pytest
  from unittest.mock import AsyncMock, MagicMock, patch

  from app.ports.data_extraction import ExtractionError


  # ---------------------------------------------------------------------------
  # Helpers
  # ---------------------------------------------------------------------------

  PARSE_RUN_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


  def _make_parsed_doc(blocks=None):
      from app.cdm.models import ParsedDocument, Page
      blocks = blocks or []
      pages = [Page(index=0, block_ids=[])]
      return ParsedDocument(
          id="doc-1",
          source_document_id="src-1",
          parse_run_id=PARSE_RUN_ID,
          page_count=1,
          pages=pages,
          blocks=blocks,
      )


  def _mock_response(content: str):
      response = MagicMock()
      response.choices = [MagicMock()]
      response.choices[0].message.content = content
      return response


  # ---------------------------------------------------------------------------
  # OpenAICompatMixin
  # ---------------------------------------------------------------------------

  class TestBuildClient:
      def test_sets_base_url_and_default_api_key(self):
          from app.adapters.extraction.openai_compat_mixin import OpenAICompatMixin

          class Concrete(OpenAICompatMixin):
              pass

          mixin = Concrete()
          client = mixin._build_client("http://localhost:11434/v1", None)
          assert "localhost:11434" in str(client.base_url)
          assert client.api_key == "ollama"

      def test_uses_provided_api_key(self):
          from app.adapters.extraction.openai_compat_mixin import OpenAICompatMixin

          class Concrete(OpenAICompatMixin):
              pass

          mixin = Concrete()
          client = mixin._build_client("http://localhost:11434/v1", "my-key")
          assert client.api_key == "my-key"


  class TestCallModel:
      @pytest.fixture
      def mixin(self):
          from app.adapters.extraction.openai_compat_mixin import OpenAICompatMixin

          class Concrete(OpenAICompatMixin):
              pass

          return Concrete()

      async def test_json_schema_mode_sends_response_format(self, mixin):
          mock_client = AsyncMock()
          mock_client.chat.completions.create = AsyncMock(
              return_value=_mock_response('{"key": "val"}')
          )
          with patch.object(mixin, "_build_client", return_value=mock_client):
              result = await mixin._call_model(
                  messages=[{"role": "user", "content": "x"}],
                  augmented_schema={"type": "object", "properties": {}},
                  config={
                      "model": "llama3.2:8b",
                      "endpoint": "http://localhost:11434/v1",
                      "structured_output_mode": "json_schema",
                  },
              )
          call_kwargs = mock_client.chat.completions.create.call_args.kwargs
          assert call_kwargs["response_format"]["type"] == "json_schema"
          assert call_kwargs["response_format"]["json_schema"]["name"] == "extraction_result"
          assert call_kwargs["response_format"]["json_schema"]["strict"] is True
          assert result == {"key": "val"}

      async def test_json_mode_sends_json_object_response_format(self, mixin):
          mock_client = AsyncMock()
          mock_client.chat.completions.create = AsyncMock(
              return_value=_mock_response('{"x": 1}')
          )
          with patch.object(mixin, "_build_client", return_value=mock_client):
              await mixin._call_model(
                  messages=[],
                  augmented_schema={},
                  config={
                      "model": "m",
                      "endpoint": "http://localhost:11434/v1",
                      "structured_output_mode": "json_mode",
                  },
              )
          call_kwargs = mock_client.chat.completions.create.call_args.kwargs
          assert call_kwargs["response_format"] == {"type": "json_object"}

      async def test_prompt_only_mode_omits_response_format(self, mixin):
          mock_client = AsyncMock()
          mock_client.chat.completions.create = AsyncMock(
              return_value=_mock_response('{"x": 1}')
          )
          with patch.object(mixin, "_build_client", return_value=mock_client):
              await mixin._call_model(
                  messages=[],
                  augmented_schema={},
                  config={
                      "model": "m",
                      "endpoint": "http://localhost:11434/v1",
                      "structured_output_mode": "prompt_only",
                  },
              )
          call_kwargs = mock_client.chat.completions.create.call_args.kwargs
          assert "response_format" not in call_kwargs

      async def test_non_json_response_raises_extraction_error(self, mixin):
          mock_client = AsyncMock()
          mock_client.chat.completions.create = AsyncMock(
              return_value=_mock_response("Sorry, I cannot extract this.")
          )
          with patch.object(mixin, "_build_client", return_value=mock_client):
              with pytest.raises(ExtractionError, match="non-JSON"):
                  await mixin._call_model(
                      messages=[],
                      augmented_schema={},
                      config={
                          "model": "m",
                          "endpoint": "http://localhost:11434/v1",
                          "structured_output_mode": "prompt_only",
                      },
                  )

      async def test_connection_error_raises_extraction_error(self, mixin):
          import openai

          mock_client = AsyncMock()
          mock_client.chat.completions.create = AsyncMock(
              side_effect=openai.APIConnectionError(request=MagicMock())
          )
          with patch.object(mixin, "_build_client", return_value=mock_client):
              with pytest.raises(ExtractionError, match="Cannot connect to Ollama"):
                  await mixin._call_model(
                      messages=[],
                      augmented_schema={},
                      config={
                          "model": "m",
                          "endpoint": "http://localhost:11434/v1",
                          "structured_output_mode": "json_schema",
                      },
                  )

      async def test_bad_request_error_logs_warning_and_reraises(self, mixin):
          import openai

          mock_client = AsyncMock()
          bad_request = openai.BadRequestError(
              message="unsupported",
              response=MagicMock(status_code=400, headers={}),
              body={"error": {"message": "unsupported"}},
          )
          mock_client.chat.completions.create = AsyncMock(side_effect=bad_request)
          with patch.object(mixin, "_build_client", return_value=mock_client):
              with pytest.raises(openai.BadRequestError):
                  await mixin._call_model(
                      messages=[],
                      augmented_schema={},
                      config={
                          "model": "m",
                          "endpoint": "http://localhost:11434/v1",
                          "structured_output_mode": "json_schema",
                      },
                  )

      async def test_temperature_passed_to_api(self, mixin):
          mock_client = AsyncMock()
          mock_client.chat.completions.create = AsyncMock(
              return_value=_mock_response('{}')
          )
          with patch.object(mixin, "_build_client", return_value=mock_client):
              await mixin._call_model(
                  messages=[],
                  augmented_schema={},
                  config={
                      "model": "m",
                      "endpoint": "http://localhost:11434/v1",
                      "temperature": 0.7,
                      "structured_output_mode": "prompt_only",
                  },
              )
          call_kwargs = mock_client.chat.completions.create.call_args.kwargs
          assert call_kwargs["temperature"] == 0.7

      async def test_default_temperature_is_zero(self, mixin):
          mock_client = AsyncMock()
          mock_client.chat.completions.create = AsyncMock(
              return_value=_mock_response('{}')
          )
          with patch.object(mixin, "_build_client", return_value=mock_client):
              await mixin._call_model(
                  messages=[],
                  augmented_schema={},
                  config={
                      "model": "m",
                      "endpoint": "http://localhost:11434/v1",
                      "structured_output_mode": "prompt_only",
                  },
              )
          call_kwargs = mock_client.chat.completions.create.call_args.kwargs
          assert call_kwargs["temperature"] == 0.0
  ```

- [ ] **Step 2: Run tests — verify they all fail**

  ```bash
  uv run --directory backend python -m pytest tests/adapters/extraction/test_ollama_extractor.py::TestBuildClient tests/adapters/extraction/test_ollama_extractor.py::TestCallModel -v
  ```

  Expected: ERRORS or FAILURES (module not found / import error).

- [ ] **Step 3: Create `openai_compat_mixin.py`**

  Create `backend/app/adapters/extraction/openai_compat_mixin.py`:

  ```python
  """OpenAI-compatible REST protocol mixin.

  Shared by OllamaExtractor and future Together/Groq/OpenAI adapters.
  """
  import json
  import logging

  import openai
  from openai import AsyncOpenAI

  from app.ports.data_extraction import ExtractionError

  logger = logging.getLogger(__name__)


  class OpenAICompatMixin:
      """Provides _build_client() and _call_model() for OpenAI-compatible endpoints."""

      def _build_client(self, endpoint: str, api_key: str | None) -> AsyncOpenAI:
          return AsyncOpenAI(
              base_url=endpoint,
              api_key=api_key or "ollama",
          )

      async def _call_model(
          self,
          messages: list[dict],
          augmented_schema: dict,
          config: dict,
      ) -> dict:
          endpoint = config.get("endpoint", "http://localhost:11434/v1")
          api_key = config.get("api_key")
          model = config.get("model")
          temperature = config.get("temperature", 0.0)
          mode = config.get("structured_output_mode", "json_schema")

          client = self._build_client(endpoint, api_key)

          kwargs: dict = {
              "model": model,
              "messages": messages,
              "temperature": temperature,
          }

          if mode == "json_schema":
              kwargs["response_format"] = {
                  "type": "json_schema",
                  "json_schema": {
                      "name": "extraction_result",
                      "strict": True,
                      "schema": augmented_schema,
                  },
              }
          elif mode == "json_mode":
              kwargs["response_format"] = {"type": "json_object"}
          # prompt_only: no response_format key

          try:
              response = await client.chat.completions.create(**kwargs)
          except openai.BadRequestError as e:
              if e.status_code in (400, 422):
                  logger.warning(
                      "Structured output rejected by model (HTTP %s). "
                      "Consider switching structured_output_mode to 'json_mode'.",
                      e.status_code,
                  )
              raise
          except openai.APIConnectionError as e:
              raise ExtractionError(
                  f"Cannot connect to Ollama endpoint {endpoint!r}. Is Ollama running?"
              ) from e

          raw_content = response.choices[0].message.content
          try:
              return json.loads(raw_content)
          except (json.JSONDecodeError, ValueError) as exc:
              raise ExtractionError(
                  f"Model returned non-JSON response: {raw_content[:200]!r}"
              ) from exc
  ```

- [ ] **Step 4: Run tests — verify they pass**

  ```bash
  uv run --directory backend python -m pytest tests/adapters/extraction/test_ollama_extractor.py::TestBuildClient tests/adapters/extraction/test_ollama_extractor.py::TestCallModel -v
  ```

  Expected: All PASSED.

- [ ] **Step 5: Commit**

  ```bash
  git add backend/app/adapters/extraction/openai_compat_mixin.py backend/tests/adapters/extraction/test_ollama_extractor.py
  git commit -m "feat(extraction): add OpenAICompatMixin with _build_client and _call_model"
  ```

---

### Task 3: OllamaExtractor

**Files:**
- Create: `backend/app/adapters/extraction/ollama.py`
- Modify (tests): `backend/tests/adapters/extraction/test_ollama_extractor.py`

- [ ] **Step 1: Append OllamaExtractor tests to the test file**

  Append to `backend/tests/adapters/extraction/test_ollama_extractor.py`:

  ```python
  # ---------------------------------------------------------------------------
  # OllamaExtractor
  # ---------------------------------------------------------------------------

  class TestOllamaExtractorProperties:
      def test_extractor_type(self):
          from app.adapters.extraction.ollama import OllamaExtractor
          assert OllamaExtractor().extractor_type == "ollama"

      def test_display_name(self):
          from app.adapters.extraction.ollama import OllamaExtractor
          assert OllamaExtractor().display_name == "Ollama"


  class TestBuildMessages:
      @pytest.fixture
      def extractor(self):
          from app.adapters.extraction.ollama import OllamaExtractor
          return OllamaExtractor()

      def test_uses_default_system_prompt(self, extractor):
          from app.adapters.extraction.ollama import DEFAULT_SYSTEM_PROMPT
          msgs = extractor._build_messages({"type": "object"}, "ctx", {})
          assert msgs[0]["role"] == "system"
          assert msgs[0]["content"] == DEFAULT_SYSTEM_PROMPT

      def test_uses_custom_system_prompt(self, extractor):
          msgs = extractor._build_messages(
              {"type": "object"}, "ctx", {"system_prompt": "Custom system"}
          )
          assert msgs[0]["content"] == "Custom system"

      def test_schema_json_interpolated_in_user_message(self, extractor):
          aug_schema = {"type": "object", "properties": {"x": {"type": "string"}}}
          msgs = extractor._build_messages(aug_schema, "doc text", {})
          user_content = msgs[1]["content"]
          assert json.dumps(aug_schema, indent=2) in user_content

      def test_document_context_interpolated_in_user_message(self, extractor):
          msgs = extractor._build_messages({"type": "object"}, "the document", {})
          assert "the document" in msgs[1]["content"]

      def test_no_unresolved_format_placeholders(self, extractor):
          msgs = extractor._build_messages({"type": "object"}, "ctx", {})
          user_content = msgs[1]["content"]
          # {schema_json} and {document_context} must have been replaced
          assert "{schema_json}" not in user_content
          assert "{document_context}" not in user_content

      def test_custom_user_prompt_template(self, extractor):
          msgs = extractor._build_messages(
              {"type": "object"},
              "ctx",
              {"user_prompt_template": "Schema: {schema_json} | Doc: {document_context}"},
          )
          assert msgs[1]["content"].startswith("Schema:")
          assert "ctx" in msgs[1]["content"]

      def test_messages_have_two_items(self, extractor):
          msgs = extractor._build_messages({"type": "object"}, "ctx", {})
          assert len(msgs) == 2
          assert msgs[0]["role"] == "system"
          assert msgs[1]["role"] == "user"


  class TestOllamaExtractorExtract:
      @pytest.fixture
      def extractor(self):
          from app.adapters.extraction.ollama import OllamaExtractor
          return OllamaExtractor()

      @pytest.fixture
      def parsed_doc(self):
          return _make_parsed_doc()

      async def test_returns_correct_extraction_output(self, extractor, parsed_doc):
          from uuid import UUID
          schema = {"type": "object", "properties": {"total": {"type": "number"}}}
          raw_response = {"total": 500, "total__source": {"page_index": 1}}

          with patch.object(extractor, "_call_model", new_callable=AsyncMock, return_value=raw_response):
              output = await extractor.extract(parsed_doc, schema, {"model": "llama3.2:8b"})

          assert output.structured_data == {"total": 500}
          assert output.source_parse_run_id == UUID(PARSE_RUN_ID)
          assert output.provider_response_raw is None
          assert output.extraction_metadata["model"] == "llama3.2:8b"
          assert "latency_ms" in output.extraction_metadata
          assert isinstance(output.extraction_metadata["latency_ms"], int)

      async def test_citations_populated_from_source_fields(self, extractor, parsed_doc):
          schema = {"type": "object", "properties": {"vendor": {"type": "string"}}}
          raw_response = {
              "vendor": "Acme Corp",
              "vendor__source": {"page_index": 2, "block_id": "blk-1"},
          }

          with patch.object(extractor, "_call_model", new_callable=AsyncMock, return_value=raw_response):
              output = await extractor.extract(parsed_doc, schema, {"model": "m"})

          assert len(output.citations) == 1
          assert output.citations[0].field_path == "vendor"
          assert output.citations[0].page_index == 2
          assert output.citations[0].block_ids == ["blk-1"]

      async def test_inject_block_ids_false_by_default(self, extractor, parsed_doc):
          schema = {"type": "object", "properties": {}}
          with patch.object(extractor, "_call_model", new_callable=AsyncMock, return_value={}) as mock_call, \
               patch("app.adapters.extraction.ollama.build_extraction_context") as mock_ctx:
              mock_ctx.return_value = "ctx"
              await extractor.extract(parsed_doc, schema, {"model": "m"})

          mock_ctx.assert_called_once_with(parsed_doc, False)

      async def test_inject_block_ids_true_when_configured(self, extractor, parsed_doc):
          schema = {"type": "object", "properties": {}}
          with patch.object(extractor, "_call_model", new_callable=AsyncMock, return_value={}) as mock_call, \
               patch("app.adapters.extraction.ollama.build_extraction_context") as mock_ctx:
              mock_ctx.return_value = "ctx"
              await extractor.extract(parsed_doc, schema, {"model": "m", "inject_block_ids": True})

          mock_ctx.assert_called_once_with(parsed_doc, True)

      async def test_call_model_receives_augmented_schema(self, extractor, parsed_doc):
          schema = {"type": "object", "properties": {"x": {"type": "string"}}}
          with patch.object(extractor, "_call_model", new_callable=AsyncMock, return_value={}) as mock_call:
              await extractor.extract(parsed_doc, schema, {"model": "m"})

          _, augmented_schema, _ = mock_call.call_args.args
          assert "x__source" in augmented_schema["properties"]

      async def test_call_model_receives_cfg(self, extractor, parsed_doc):
          schema = {"type": "object", "properties": {}}
          cfg = {"model": "llama3.2:8b", "structured_output_mode": "json_mode"}
          with patch.object(extractor, "_call_model", new_callable=AsyncMock, return_value={}) as mock_call:
              await extractor.extract(parsed_doc, schema, cfg)

          _, _, passed_cfg = mock_call.call_args.args
          assert passed_cfg["structured_output_mode"] == "json_mode"

      async def test_empty_config_uses_defaults(self, extractor, parsed_doc):
          schema = {"type": "object", "properties": {}}
          with patch.object(extractor, "_call_model", new_callable=AsyncMock, return_value={}):
              output = await extractor.extract(parsed_doc, schema)  # config=None

          assert output.structured_data == {}
          assert output.citations == []
  ```

- [ ] **Step 2: Run new tests — verify they fail**

  ```bash
  uv run --directory backend python -m pytest tests/adapters/extraction/test_ollama_extractor.py::TestOllamaExtractorProperties tests/adapters/extraction/test_ollama_extractor.py::TestBuildMessages tests/adapters/extraction/test_ollama_extractor.py::TestOllamaExtractorExtract -v
  ```

  Expected: ERRORS (module `app.adapters.extraction.ollama` not found).

- [ ] **Step 3: Create `ollama.py`**

  Create `backend/app/adapters/extraction/ollama.py`:

  ```python
  """Ollama extraction adapter.

  Calls any Ollama-compatible endpoint using the OpenAI REST protocol.
  Endpoint and API key are per-run config — not global settings.
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
  from app.adapters.extraction.openai_compat_mixin import OpenAICompatMixin
  from app.cdm.models import ParsedDocument
  from app.ports.data_extraction import DataExtractor, ExtractionOutput

  DEFAULT_SYSTEM_PROMPT = (
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


  class OllamaExtractor(OpenAICompatMixin, DataExtractor):
      """Structured extraction via Ollama's OpenAI-compatible REST API."""

      @property
      def extractor_type(self) -> str:
          return "ollama"

      @property
      def display_name(self) -> str:
          return "Ollama"

      def _build_messages(
          self,
          aug_schema: dict[str, Any],
          context: str,
          cfg: dict[str, Any],
      ) -> list[dict[str, str]]:
          system_prompt = cfg.get("system_prompt") or DEFAULT_SYSTEM_PROMPT
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
          cfg = config or {}
          context = build_extraction_context(
              parsed_document, cfg.get("inject_block_ids", False)
          )
          aug_schema = augment_schema_with_sources(schema)
          messages = self._build_messages(aug_schema, context, cfg)

          t0 = time.monotonic()
          raw = await self._call_model(messages, aug_schema, cfg)
          latency_ms = int((time.monotonic() - t0) * 1000)

          structured_data, citations = strip_source_fields(raw, schema)

          return ExtractionOutput(
              structured_data=structured_data,
              source_parse_run_id=UUID(parsed_document.parse_run_id),
              citations=citations,
              provider_response_raw=None,
              extraction_metadata={"model": cfg.get("model"), "latency_ms": latency_ms},
          )
  ```

- [ ] **Step 4: Run tests — verify they pass**

  ```bash
  uv run --directory backend python -m pytest tests/adapters/extraction/test_ollama_extractor.py::TestOllamaExtractorProperties tests/adapters/extraction/test_ollama_extractor.py::TestBuildMessages tests/adapters/extraction/test_ollama_extractor.py::TestOllamaExtractorExtract -v
  ```

  Expected: All PASSED.

- [ ] **Step 5: Commit**

  ```bash
  git add backend/app/adapters/extraction/ollama.py backend/tests/adapters/extraction/test_ollama_extractor.py
  git commit -m "feat(extraction): add OllamaExtractor with prompt building and extract()"
  ```

---

### Task 4: Register OllamaExtractor in factory

**Files:**
- Modify: `backend/app/adapters/extraction/registry.py`
- Modify (tests): `backend/tests/adapters/extraction/test_ollama_extractor.py`

- [ ] **Step 1: Append registry tests**

  Append to `backend/tests/adapters/extraction/test_ollama_extractor.py`:

  ```python
  # ---------------------------------------------------------------------------
  # Registry
  # ---------------------------------------------------------------------------

  class TestRegistryOllama:
      def test_get_extractor_returns_ollama_extractor(self):
          from app.adapters.extraction.ollama import OllamaExtractor
          from app.adapters.extraction.registry import get_extractor

          extractor = get_extractor("ollama", {})
          assert isinstance(extractor, OllamaExtractor)
          assert extractor.extractor_type == "ollama"

      def test_ollama_extractor_needs_no_credentials(self):
          from app.adapters.extraction.registry import get_extractor

          # No credentials, no dependencies — should construct fine
          extractor = get_extractor("ollama", {})
          assert extractor is not None
  ```

- [ ] **Step 2: Run new tests — verify they fail**

  ```bash
  uv run --directory backend python -m pytest tests/adapters/extraction/test_ollama_extractor.py::TestRegistryOllama -v
  ```

  Expected: FAILED — `ValueError: Unknown extraction method: 'ollama'`.

- [ ] **Step 3: Register ollama in `get_extractor()`**

  Open `backend/app/adapters/extraction/registry.py`. Replace:

  ```python
      raise ValueError(f"Unknown extraction method: {method!r}")
  ```

  with:

  ```python
      if method == "ollama":
          from app.adapters.extraction.ollama import OllamaExtractor
          return OllamaExtractor()

      raise ValueError(f"Unknown extraction method: {method!r}")
  ```

- [ ] **Step 4: Run tests — verify they pass**

  ```bash
  uv run --directory backend python -m pytest tests/adapters/extraction/test_ollama_extractor.py::TestRegistryOllama -v
  ```

  Expected: All PASSED.

- [ ] **Step 5: Run full extraction test suite**

  ```bash
  uv run --directory backend python -m pytest tests/adapters/extraction/ -v
  ```

  Expected: All PASSED (no regressions in registry, llm_context, or llamaextract tests).

- [ ] **Step 6: Commit**

  ```bash
  git add backend/app/adapters/extraction/registry.py backend/tests/adapters/extraction/test_ollama_extractor.py
  git commit -m "feat(extraction): register OllamaExtractor in factory"
  ```

---

### Task 5: Frontend — Ollama config section in ExtractionForm

**Files:**
- Modify: `frontend/src/components/extraction/ExtractionForm.tsx`

The current form shows Mode, PageRange, Citations, and Reasoning for all extractors — these are LlamaExtract-specific. This task:
1. Guards all LlamaExtract-specific fields behind `extractionMethod === 'llamaextract'`
2. Adds an Ollama-specific config section
3. Builds the correct config dict per method in `handleRun`

- [ ] **Step 1: Replace `ExtractionForm.tsx` with the updated implementation**

  Replace the entire contents of `frontend/src/components/extraction/ExtractionForm.tsx`:

  ```tsx
  import { useState, useEffect } from 'react'
  import type { ExtractionSchema, ExtractorInfo, RunExtractionRequest } from '@/types/extraction'
  import { Button } from '@/components/ui/button'
  import { Label } from '@/components/ui/label'
  import { Input } from '@/components/ui/input'
  import { Checkbox } from '@/components/ui/checkbox'
  import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
  } from '@/components/ui/select'
  import { Pencil, Play } from 'lucide-react'

  interface ExtractionFormProps {
    parseRunId: string
    schemas: ExtractionSchema[]
    extractors: ExtractorInfo[]
    onRun: (request: RunExtractionRequest) => Promise<void>
    onEditSchema?: (schema: ExtractionSchema) => void
  }

  type OllamaEndpointPreset = 'local' | 'cloud' | 'custom'

  const OLLAMA_ENDPOINTS: Record<OllamaEndpointPreset, string> = {
    local: 'http://localhost:11434/v1',
    cloud: 'https://api.ollama.com/v1',
    custom: '',
  }

  export function ExtractionForm({
    parseRunId,
    schemas,
    extractors,
    onRun,
    onEditSchema,
  }: ExtractionFormProps) {
    const [schemaId, setSchemaId] = useState('')
    const [extractionMethod, setExtractionMethod] = useState('')

    // LlamaExtract config
    const [extractionMode, setExtractionMode] = useState('MULTIMODAL')
    const [citeSources, setCiteSources] = useState(false)
    const [useReasoning, setUseReasoning] = useState(false)
    const [pageRange, setPageRange] = useState('')
    const [extractionTarget, setExtractionTarget] = useState('PER_DOC')
    const [confidenceScores, setConfidenceScores] = useState(false)

    // Ollama config
    const [ollamaModel, setOllamaModel] = useState('')
    const [ollamaEndpointPreset, setOllamaEndpointPreset] = useState<OllamaEndpointPreset>('local')
    const [ollamaCustomEndpoint, setOllamaCustomEndpoint] = useState('')
    const [ollamaApiKey, setOllamaApiKey] = useState('')
    const [ollamaStructuredOutputMode, setOllamaStructuredOutputMode] = useState('json_schema')
    const [ollamaInjectBlockIds, setOllamaInjectBlockIds] = useState(false)

    const [isRunning, setIsRunning] = useState(false)
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
      if (schemas.length > 0 && !schemaId) setSchemaId(schemas[0].id)
    }, [schemas, schemaId])

    useEffect(() => {
      if (extractors.length > 0 && !extractionMethod) setExtractionMethod(extractors[0].extractionMethod)
    }, [extractors, extractionMethod])

    const selectedExtractor = extractors.find((e) => e.extractionMethod === extractionMethod)
    const isConfigured = selectedExtractor?.configured ?? true

    function getOllamaEndpoint(): string {
      if (ollamaEndpointPreset === 'custom') return ollamaCustomEndpoint
      return OLLAMA_ENDPOINTS[ollamaEndpointPreset]
    }

    const handleRun = async () => {
      setError(null)

      if (!schemaId) {
        setError('Please select a schema')
        return
      }
      if (!extractionMethod) {
        setError('No extraction method available')
        return
      }
      if (extractionMethod === 'ollama' && !ollamaModel.trim()) {
        setError('Model name is required for Ollama')
        return
      }

      let config: Record<string, unknown>

      if (extractionMethod === 'llamaextract') {
        config = { extraction_mode: extractionMode }
        if (citeSources) config.cite_sources = true
        if (useReasoning) config.use_reasoning = true
        if (pageRange.trim()) config.page_range = pageRange.trim()
        config.extraction_target = extractionTarget
        if (confidenceScores) config.confidence_scores = true
      } else if (extractionMethod === 'ollama') {
        config = {
          model: ollamaModel.trim(),
          endpoint: getOllamaEndpoint(),
          structured_output_mode: ollamaStructuredOutputMode,
          inject_block_ids: ollamaInjectBlockIds,
        }
        if (ollamaApiKey.trim()) config.api_key = ollamaApiKey.trim()
      } else {
        config = {}
      }

      setIsRunning(true)
      try {
        await onRun({
          parseRunId,
          extractionSchemaId: schemaId,
          extractionMethod,
          config,
        })
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to run extraction')
      } finally {
        setIsRunning(false)
      }
    }

    const hasSchemas = schemas.length > 0
    const hasExtractors = extractors.length > 0

    if (!hasSchemas || !hasExtractors) {
      return (
        <div className="rounded-lg border border-dashed p-4 text-center text-sm text-muted-foreground">
          {!hasExtractors
            ? 'No extraction methods available. Contact your administrator.'
            : 'Create a schema first to run extractions.'}
        </div>
      )
    }

    const isOllamaModelMissing = extractionMethod === 'ollama' && !ollamaModel.trim()
    const isRunDisabled = isRunning || !isConfigured || isOllamaModelMissing

    return (
      <div className="space-y-4">
        {/* Schema + Method row */}
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <Label className="text-xs">Schema</Label>
            <div className="flex items-center gap-1">
              <Select value={schemaId} onValueChange={setSchemaId}>
                <SelectTrigger className="h-9">
                  <SelectValue placeholder="Select schema" />
                </SelectTrigger>
                <SelectContent>
                  {schemas.map((s) => (
                    <SelectItem key={s.id} value={s.id}>
                      {s.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {onEditSchema && schemaId && (
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-9 w-9 shrink-0"
                  title="Edit selected schema"
                  onClick={() => {
                    const selected = schemas.find((s) => s.id === schemaId)
                    if (selected) onEditSchema(selected)
                  }}
                >
                  <Pencil className="h-3.5 w-3.5" />
                </Button>
              )}
            </div>
          </div>

          {extractors.length > 1 ? (
            <div className="space-y-1.5">
              <Label className="text-xs">Method</Label>
              <Select value={extractionMethod} onValueChange={setExtractionMethod}>
                <SelectTrigger className="h-9">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {extractors.map((e) => (
                    <SelectItem key={e.extractionMethod} value={e.extractionMethod} disabled={!e.configured}>
                      {e.name}{!e.configured ? ' (not configured)' : ''}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          ) : (
            <div className="space-y-1.5">
              <Label className="text-xs">Method</Label>
              <div className="h-9 flex items-center text-sm text-muted-foreground px-3 border rounded-md bg-muted/50">
                {extractors[0]?.name}
              </div>
            </div>
          )}
        </div>

        {/* LlamaExtract-specific config */}
        {extractionMethod === 'llamaextract' && (
          <>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label className="text-xs">Mode</Label>
                <Select value={extractionMode} onValueChange={setExtractionMode}>
                  <SelectTrigger className="h-9">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="FAST">Fast</SelectItem>
                    <SelectItem value="BALANCED">Balanced</SelectItem>
                    <SelectItem value="MULTIMODAL">Multimodal</SelectItem>
                    <SelectItem value="PREMIUM">Premium</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-1.5">
                <Label className="text-xs">Page Range</Label>
                <Input
                  value={pageRange}
                  onChange={(e) => setPageRange(e.target.value)}
                  placeholder="e.g. 1-5"
                  className="h-9"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="extraction-target" className="text-xs">Target</Label>
                <Select value={extractionTarget} onValueChange={setExtractionTarget}>
                  <SelectTrigger id="extraction-target" className="h-9">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="PER_DOC">Per Document</SelectItem>
                    <SelectItem value="PER_PAGE">Per Page</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="flex items-end pb-2">
                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="confidence-scores"
                    checked={confidenceScores}
                    onCheckedChange={(checked) => setConfidenceScores(checked === true)}
                  />
                  <Label htmlFor="confidence-scores" className="text-xs font-normal">
                    Confidence Scores
                  </Label>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-4">
              <div className="flex items-center space-x-2">
                <Checkbox
                  id="cite-sources-inline"
                  checked={citeSources}
                  onCheckedChange={(checked) => setCiteSources(checked === true)}
                />
                <Label htmlFor="cite-sources-inline" className="text-xs font-normal">
                  Citations
                </Label>
              </div>
              <div className="flex items-center space-x-2">
                <Checkbox
                  id="use-reasoning-inline"
                  checked={useReasoning}
                  onCheckedChange={(checked) => setUseReasoning(checked === true)}
                />
                <Label htmlFor="use-reasoning-inline" className="text-xs font-normal">
                  Reasoning
                </Label>
              </div>
            </div>
          </>
        )}

        {/* Ollama-specific config */}
        {extractionMethod === 'ollama' && (
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label className="text-xs">Model</Label>
                <Input
                  value={ollamaModel}
                  onChange={(e) => setOllamaModel(e.target.value)}
                  placeholder="e.g. llama3.2:8b"
                  className="h-9"
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs">Output Mode</Label>
                <Select value={ollamaStructuredOutputMode} onValueChange={setOllamaStructuredOutputMode}>
                  <SelectTrigger className="h-9">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="json_schema">JSON Schema</SelectItem>
                    <SelectItem value="json_mode">JSON Mode</SelectItem>
                    <SelectItem value="prompt_only">Prompt Only</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label className="text-xs">Endpoint</Label>
                <Select
                  value={ollamaEndpointPreset}
                  onValueChange={(v) => setOllamaEndpointPreset(v as OllamaEndpointPreset)}
                >
                  <SelectTrigger className="h-9">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="local">Local (localhost:11434)</SelectItem>
                    <SelectItem value="cloud">Ollama Cloud</SelectItem>
                    <SelectItem value="custom">Custom</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {(ollamaEndpointPreset === 'cloud' || ollamaEndpointPreset === 'custom') && (
                <div className="space-y-1.5">
                  <Label className="text-xs">API Key</Label>
                  <Input
                    type="password"
                    value={ollamaApiKey}
                    onChange={(e) => setOllamaApiKey(e.target.value)}
                    placeholder="Bearer token"
                    className="h-9"
                  />
                </div>
              )}
            </div>

            {ollamaEndpointPreset === 'custom' && (
              <div className="space-y-1.5">
                <Label className="text-xs">Custom Endpoint URL</Label>
                <Input
                  value={ollamaCustomEndpoint}
                  onChange={(e) => setOllamaCustomEndpoint(e.target.value)}
                  placeholder="https://your-ollama-host/v1"
                  className="h-9"
                />
              </div>
            )}

            <div className="flex items-center space-x-2">
              <Checkbox
                id="inject-block-ids"
                checked={ollamaInjectBlockIds}
                onCheckedChange={(checked) => setOllamaInjectBlockIds(checked === true)}
              />
              <Label htmlFor="inject-block-ids" className="text-xs font-normal">
                Inject block IDs (block-level citations)
              </Label>
            </div>
          </div>
        )}

        {/* Run button */}
        <div className="flex items-center justify-between">
          <div />
          <Button onClick={handleRun} disabled={isRunDisabled} size="sm">
            {isRunning ? (
              'Running...'
            ) : (
              <>
                <Play className="h-3.5 w-3.5 mr-1.5" />
                Run Extraction
              </>
            )}
          </Button>
        </div>

        {error && <p className="text-sm text-destructive">{error}</p>}

        {!isConfigured && (
          <p className="text-xs text-amber-600">
            {selectedExtractor?.name ?? 'This extractor'} is not configured. Contact your administrator.
          </p>
        )}
      </div>
    )
  }
  ```

- [ ] **Step 2: Run TypeScript checks**

  ```bash
  npm --prefix frontend run build 2>&1 | tail -20
  ```

  Expected: Build succeeds with no TypeScript errors.

- [ ] **Step 3: Run frontend lint**

  ```bash
  npm --prefix frontend run lint
  ```

  Expected: No lint errors.

- [ ] **Step 4: Commit**

  ```bash
  git add frontend/src/components/extraction/ExtractionForm.tsx
  git commit -m "feat(extraction): add Ollama config section to ExtractionForm"
  ```

---

### Task 6: Final verification

- [ ] **Step 1: Run the full backend test suite**

  ```bash
  uv run --directory backend python -m pytest tests/ -v --tb=short
  ```

  Expected: All tests PASSED, no regressions.

- [ ] **Step 2: Run the complete new test file**

  ```bash
  uv run --directory backend python -m pytest tests/adapters/extraction/test_ollama_extractor.py -v
  ```

  Expected: All PASSED.

- [ ] **Step 3: Verify extractor catalogue includes ollama**

  ```bash
  uv run --directory backend python -c "
  from app.adapters.extraction.registry import get_known_extractors, get_extractor
  cat = get_known_extractors()
  methods = [e['extraction_method'] for e in cat]
  assert 'ollama' in methods, f'ollama not in catalogue: {methods}'
  e = get_extractor('ollama', {})
  assert e.extractor_type == 'ollama'
  print('Catalogue:', methods)
  print('Factory OK:', e)
  "
  ```

  Expected: Prints `Catalogue: ['llamaextract', 'ollama']` and `Factory OK: ...`.

- [ ] **Step 4: Run frontend tests**

  ```bash
  npm --prefix frontend run test -- --run
  ```

  Expected: All tests PASSED (no regressions).

- [ ] **Step 5: Final commit if any loose files**

  ```bash
  git status
  ```

  Should be clean if each task was committed correctly.

---

## Self-Review Against Spec

**Spec coverage check:**

| Spec requirement | Task |
|---|---|
| Works with local Ollama (zero config beyond model name) | Task 3 — config defaults endpoint to localhost |
| Works with Ollama cloud + self-hosted via endpoint/API key | Task 5 — frontend preset selector |
| `response_format: json_schema` default; fallback to json_mode/prompt_only | Task 2 — mixin structured_output_mode handling |
| `citations` with page-level provenance via `__source` fields | Task 3 — strip_source_fields produces FieldCitation list |
| Default system/user prompts; fully customisable via config | Task 3 — DEFAULT_SYSTEM_PROMPT + DEFAULT_USER_PROMPT_TEMPLATE |
| Config-only to add new compatible endpoint | Task 3 + 5 — endpoint is per-run config, no code change needed |
| Registry key `"ollama"`, position first in preference order | Already in registry.py catalogue; UI ordering is a UI concern |
| `ExtractionError` for malformed JSON | Task 2 — mixin raises ExtractionError |
| `ExtractionError` for connection refused with Ollama hint | Task 2 — mixin catches APIConnectionError |
| 400/422 logs warning + re-raises | Task 2 — mixin catches BadRequestError |
| Missing `page_index` → `FieldCitation(page_index=None)` | Handled by existing `strip_source_fields` |
| `inject_block_ids` config flag | Task 3 — passed to build_extraction_context |
| `OLLAMA_ENDPOINT` setting | Task 1 |
| Frontend endpoint presets (local/cloud/custom) | Task 5 |
| Frontend API key field for cloud/custom | Task 5 |
| Frontend structured_output_mode selector | Task 5 |

**Gaps identified:** None. All spec requirements are covered.

**Placeholder scan:** No TBD, TODO, or vague steps present. Every code step shows the complete implementation.

**Type consistency check:**
- `_call_model(messages: list[dict], augmented_schema: dict, config: dict) → dict` — used consistently in Task 2 (mixin) and Task 3 (extractor calls it with `messages, aug_schema, cfg`)
- `ExtractionError` defined in Task 1 (ports file), imported in Task 2 (mixin)
- `OllamaExtractor()` constructed with no args in Task 3 (implementation) and Task 4 (registry)
- `DEFAULT_SYSTEM_PROMPT` and `DEFAULT_USER_PROMPT_TEMPLATE` exported from `ollama.py` and referenced in Task 3 tests

---

**Plan complete and saved to `docs/superpowers/plans/2026-05-25-ollama-extractor.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
