# LlamaExtractAdapter Refactor — Spec

**Date:** 2026-05-06
**Status:** Draft
**Depends on:** `2026-05-06-cdm-extraction-general-design.md`

## Overview

Refactor `LlamaExtractAdapter` to implement the new CDM-based `DataExtractor` port.
The adapter currently receives a `file_path: str` and opens the file directly. After
this refactor it receives a `ParsedDocument` (CDM Pydantic type) and internally
resolves the file bytes it needs via the `source_document_id` and a `StorageService`.

No file-system details leak into the port or service layer.

---

## Current State

```
extract(file_path, schema, config)
  → open file_path
  → upload bytes to LlamaCloud files API
  → run extraction with schema + config
  → return ExtractionOutput(structured_data, extraction_metadata, metadata)
```

File path comes from `document.source_metadata["file_path"]` — resolved by the
service before calling the adapter.

---

## Target State

```
extract(parsed_document, schema, config)
  → resolve source_document_id from parsed_document
  → fetch storage_uri from SourceDocumentRepository
  → stream file bytes from StorageService
  → upload bytes to LlamaCloud files API
  → run extraction with schema + config
  → return ExtractionOutput(
        structured_data,
        source_parse_run_id,
        provider_response_raw,   ← full LlamaCloud response
        extraction_metadata,
    )
```

---

## Constructor

```python
class LlamaExtractAdapter(DataExtractor):
    def __init__(
        self,
        api_key: str | None,
        source_document_repo: SourceDocumentRepository,
        storage_service: StorageService,
    ):
        self._client = AsyncLlamaCloud(api_key=api_key) if api_key else AsyncLlamaCloud()
        self._source_doc_repo = source_document_repo
        self._storage_service = storage_service
```

The registry factory (`get_extractor("llamaextract")`) is responsible for constructing
the adapter with the correct dependencies from the DI context.

---

## File Resolution

```python
async def _get_file_bytes(self, source_document_id: str) -> bytes:
    source_doc = await self._source_doc_repo.get_by_id(UUID(source_document_id))
    if not source_doc:
        raise ValueError(f"SourceDocument {source_document_id} not found")
    return await self._storage_service.get_file(source_doc.storage_uri)
```

The adapter never touches the filesystem directly. All I/O goes through
`StorageService`, which handles local and cloud storage transparently.

---

## Config Schema

All existing config options are preserved. `system_prompt` from the shared base maps
onto LlamaExtract's `prompt_override` parameter.

```python
{
    "system_prompt":     str | None,   # base — maps to LlamaExtract prompt_override
    "extraction_mode":   str,          # "FAST"|"BALANCED"|"MULTIMODAL"|"PREMIUM"
                                       # default "MULTIMODAL"
    "extraction_target": str,          # "PER_DOC"|"PER_PAGE" — default "PER_DOC"
    "cite_sources":      bool,         # default False
    "use_reasoning":     bool,         # default False
    "confidence_scores": bool,         # default False
    "page_range":        str | None,   # e.g. "1-5"; None = all pages
}
```

`user_prompt_template` from the shared base is ignored — LlamaExtract does not expose
a separate user-turn prompt parameter.

---

## Extraction Call

```python
extraction_config = {
    "extraction_mode":   config.get("extraction_mode", "MULTIMODAL"),
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

result = await self._client.extraction.extract(
    file_id=file_obj.id,
    data_schema=schema,
    config=extraction_config,
)
```

---

## Output Mapping

```python
raw_response = result.model_dump() if hasattr(result, "model_dump") else dict(result)

return ExtractionOutput(
    structured_data=result.data if hasattr(result, "data") else {},
    source_parse_run_id=UUID(parsed_document.parse_run_id),
    citations=None,                          # provider path — no CDM block citations
    provider_response_raw=raw_response,      # full response preserved
    extraction_metadata={
        "latency_ms": latency_ms,
        "file_id": str(file_obj.id),
    },
)
```

The full raw response is preserved in `provider_response_raw`. LlamaExtract returns
source citations in its native format when `cite_sources=True` — these are stored in
the raw response and can be surfaced in the UI or mined later without any schema
commitment today.

---

## Registry Entry

```python
# registry.py
if settings.LLAMA_CLOUD_KEY:
    extractors.append({
        "extraction_method": "llamaextract",
        "name": "LlamaExtract",
        "description": "Structured extraction via LlamaCloud. Multimodal, supports "
                        "citations and reasoning.",
        "config_schema": { ... },  # as above
    })
```

Position in `EXTRACTOR_PREFERENCE_ORDER`: after all LLM-based adapters (`ollama`,
`together_ai`, `groq`, `openai`, `anthropic`), before `landingai`.

---

## Migration Notes

- `extraction_results` rows created before this refactor have no `source_parse_run_id` —
  the column is nullable; no backfill required
- Existing `provider_response_raw` is null for pre-refactor rows — this is expected
- The `extraction_metadata` column continues to hold timing/file-id data as before

---

## Testing Strategy

- Unit test `_get_file_bytes` with a mock `SourceDocumentRepository` and `StorageService`
- Unit test output mapping: given a mock LlamaCloud result, assert `provider_response_raw`
  contains the full dump and `structured_data` is clean
- Integration test (marked slow, requires `LLAMA_CLOUD_KEY`): end-to-end against a
  fixture CDM document, assert `structured_data` is non-empty and
  `source_parse_run_id` matches the input
- Snapshot test on `provider_response_raw` shape to catch unexpected SDK changes early
