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
