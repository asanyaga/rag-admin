# OllamaExtractor — Spec

**Date:** 2026-05-06
**Status:** Draft
**Depends on:** `2026-05-06-cdm-extraction-general-design.md`

## Overview

New adapter that runs structured extraction against any Ollama-compatible endpoint
(local Ollama runtime, self-hosted Ollama, Ollama's cloud inference, or any future
deployment of the same runtime). The adapter is the primary extractor in the preference
order, expressing the product's commitment to user autonomy and local-first inference.

Internally the adapter uses the OpenAI-compatible REST protocol that Ollama exposes.
This is an implementation detail — it is not surfaced in the registry key, config shape,
or port signature.

---

## Goals

- Works with Ollama running locally (`localhost:11434`) with zero configuration beyond
  a model name
- Works with Ollama cloud (api.ollama.com) and self-hosted deployments with only an
  endpoint and API key change
- Enforces structured output via `response_format: json_schema` where supported;
  falls back gracefully
- Populates `citations` with at minimum page-level provenance for every extracted field
- Prompt is fully customisable through config; adapter provides sensible defaults
- Adding a new compatible endpoint is config, not code

## Non-Goals

- Streaming responses (extraction is a one-shot call)
- Model discovery / listing (config supplies the model name)
- Automatic fallback to a different model on failure (surface error to caller)

---

## Registry Entry

```python
"extraction_method": "ollama"
"name": "Ollama"
"display_name": "Ollama (local / cloud)"
```

Position in `EXTRACTOR_PREFERENCE_ORDER`: first — before all hosted and provider adapters.

Available when `OLLAMA_ENDPOINT` is set in settings, or when the default localhost
endpoint responds to a health-check. If neither condition is met, the entry is omitted
from `get_available_extractors()`.

---

## Config Schema

```python
{
    # Connection
    "model":    str,         # required — e.g. "llama3.2:8b", "mistral:7b"
    "endpoint": str,         # default "http://localhost:11434/v1"
    "api_key":  str | None,  # None for local; Bearer token for cloud/self-hosted

    # LLM behaviour
    "temperature": float,    # default 0.0
    "structured_output_mode": str,
                             # "json_schema" (default) | "json_mode" | "prompt_only"
                             # json_schema: uses response_format with full JSON Schema
                             # json_mode:   uses response_format: {type: "json_object"}
                             # prompt_only: no response_format, JSON enforced via prompt

    # Provenance
    "inject_block_ids": bool,  # default False
                               # True enables phase-2 block-level citations

    # Prompts — null means use adapter default
    "system_prompt":          str | None,
    "user_prompt_template":   str | None,
                              # template receives {schema_json} and {document_context}
}
```

The frontend config form should offer preset endpoint options:
- **Local** (default): `http://localhost:11434/v1`, no API key
- **Ollama Cloud**: `https://api.ollama.com/v1`, API key required
- **Custom**: free-form endpoint + optional API key

---

## Extraction Flow

```
1. build_extraction_context(parsed_doc, inject_block_ids)
   → page-annotated markdown string

2. augment_schema_with_sources(user_schema)
   → schema with __source siblings for every leaf field

3. render prompts
   → system_prompt (config or default)
   → user message (user_prompt_template or default, interpolated)

4. POST /chat/completions
   → model, messages, temperature
   → response_format (per structured_output_mode)

5. parse JSON response

6. strip_source_fields(raw_data, user_schema)
   → structured_data (clean)
   → citations: list[FieldCitation]

7. return ExtractionOutput
```

---

## Default Prompts

### Default system prompt

```
You are a structured data extraction assistant. Extract information from the provided
document according to the given JSON schema. Be precise and faithful to the source text.
Only extract values that are explicitly present in the document.
```

### Default user prompt template

```
Extract structured data from the following document according to this JSON schema:

<schema>
{schema_json}
</schema>

For each field you extract, include a corresponding `{field_name}__source` object
with `page_index` (integer, required) and `block_id` (string, if available) indicating
where in the document you found the value.

<document>
{document_context}
</document>

Return a single JSON object that conforms to the schema (including __source fields).
```

The `{schema_json}` interpolation receives the augmented schema (with `__source`
siblings). `{document_context}` receives the page-annotated markdown from
`build_extraction_context`.

---

## Structured Output Modes

### `json_schema` (default)

Passes the augmented schema to `response_format`:

```python
response_format = {
    "type": "json_schema",
    "json_schema": {
        "name": "extraction_result",
        "strict": True,
        "schema": augmented_schema,
    }
}
```

Requires a model and Ollama version that supports structured output. The adapter detects
a 400/422 response and logs a warning suggesting the user switch to `json_mode`.

### `json_mode`

```python
response_format = {"type": "json_object"}
```

Looser — the model returns valid JSON but is not constrained to the schema. The
post-processor validates and extracts `__source` fields; unexpected fields are ignored.

### `prompt_only`

No `response_format` parameter. JSON conformance is enforced entirely through the
prompt. Use for models that do not support `response_format` at all.

---

## Post-Processing

Delegates to `llm_context.strip_source_fields(raw, user_schema)`:

1. Walk the raw response dict
2. For every key ending in `__source`, extract it into a `FieldCitation`:
   - `field_path` = key without `__source` suffix (normalised to dot notation)
   - `page_index` = `raw[key]["page_index"]` — cast to int; None if missing
   - `block_ids`  = `[raw[key]["block_id"]]` if present, else None
   - `text_spans` = None (phase 1)
3. Remaining keys (no `__source` suffix) form `structured_data`

If `page_index` is missing for a field, the citation is still recorded with
`page_index=None` rather than dropped — provenance is never silently lost.

---

## OpenAI-Compat Mixin

**File:** `backend/app/adapters/extraction/openai_compat_mixin.py`

Provides `_call_model(messages, augmented_schema, config) → dict` using the
`openai` Python SDK pointed at the configured endpoint. This mixin is also used by
future `TogetherExtractor`, `GroqExtractor`, `OpenAIExtractor` adapters.

```python
class OpenAICompatMixin:
    def _build_client(self, endpoint: str, api_key: str | None) -> AsyncOpenAI:
        return AsyncOpenAI(base_url=endpoint, api_key=api_key or "ollama")
```

`api_key` defaults to the string `"ollama"` when None because the `openai` SDK requires
a non-empty value even when the server does not enforce auth.

---

## OllamaExtractor Class

**File:** `backend/app/adapters/extraction/ollama.py`

```python
class OllamaExtractor(OpenAICompatMixin, DataExtractor):

    @property
    def extractor_type(self) -> str:
        return "ollama"

    @property
    def display_name(self) -> str:
        return "Ollama"

    async def extract(
        self,
        parsed_document: ParsedDocument,
        schema: dict,
        config: dict | None = None,
    ) -> ExtractionOutput:
        cfg = config or {}
        context   = build_extraction_context(parsed_document, cfg.get("inject_block_ids", False))
        aug_schema = augment_schema_with_sources(schema)
        messages  = self._build_messages(aug_schema, context, cfg)
        raw       = await self._call_model(messages, aug_schema, cfg)
        structured_data, citations = strip_source_fields(raw, schema)

        return ExtractionOutput(
            structured_data=structured_data,
            source_parse_run_id=UUID(parsed_document.parse_run_id),
            citations=citations,
            provider_response_raw=None,
            extraction_metadata={"model": cfg.get("model"), "latency_ms": latency_ms},
        )
```

---

## Error Handling

| Condition | Behaviour |
|---|---|
| Model returns malformed JSON | Raise `ExtractionError("Model returned non-JSON response")` |
| `json_schema` mode rejected (400/422) | Log warning, re-raise; user should switch to `json_mode` |
| Connection refused on localhost | Raise with message suggesting Ollama is not running |
| Missing `page_index` in `__source` | Record `FieldCitation(page_index=None, ...)`, continue |
| Model omits `__source` for a field | Citation for that field is absent; `structured_data` value kept |

---

## Settings

New environment / settings keys:

```
OLLAMA_ENDPOINT=http://localhost:11434/v1   # optional; falls back to this default
```

No `OLLAMA_API_KEY` setting — API key is per-extraction-run config, not global, since
different users may point at different endpoints.

---

## Testing Strategy

- `build_extraction_context`: unit tests with fixture `ParsedDocument` objects; assert
  page markers appear at correct positions; assert block markers when `inject_block_ids=True`
- `augment_schema_with_sources`: unit tests with flat, nested, and array schemas; assert
  every leaf gets a `__source` sibling; assert non-leaf objects are not augmented
- `strip_source_fields`: round-trip test — augment schema → build fake model output
  with `__source` entries → strip → assert clean `structured_data` and correct
  `FieldCitation` list; assert missing `page_index` yields `None` not an error
- `OllamaExtractor.extract`: mock `_call_model`, assert correct messages, correct
  `response_format` based on `structured_output_mode`, and correct `ExtractionOutput`
- Integration test (marked slow, requires running Ollama): end-to-end with a small
  open-weight model and a fixture CDM document; assert `citations` are populated with
  non-None `page_index` values
