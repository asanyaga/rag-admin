"""Generic LLM extraction adapter.

Works with any OpenAI-compatible provider. Reads per-run LLM config from
the 'llm_config' key in the config dict (a serialized PromptConfig).
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
from app.schemas.prompt_config import PromptConfig
from app.services.llm.prompt_config import resolve_llm_config

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


class LLMExtractor(OpenAICompatMixin, DataExtractor):
    """Structured extraction via any OpenAI-compatible LLM provider."""

    extractor_type = "llm"
    display_name = "LLM"

    def __init__(
        self,
        default_endpoint: str | None = None,
        default_api_key: str | None = None,
    ) -> None:
        self._default_endpoint = default_endpoint
        self._default_api_key = default_api_key

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

        # Apply constructor defaults when not overridden per-run
        if self._default_endpoint and "endpoint" not in cfg:
            cfg["endpoint"] = self._default_endpoint
        if self._default_api_key and "api_key" not in cfg:
            cfg["api_key"] = self._default_api_key

        # Resolve LLM config from PromptConfig stored in config["llm_config"]
        prompt_config: PromptConfig | None = None
        if cfg.get("llm_config"):
            prompt_config = PromptConfig.model_validate(cfg["llm_config"])
        llm_config = resolve_llm_config(
            prompt_config,
            default_provider="ollama_local",
            default_model="llama3.2:8b",
        )
        cfg["model"] = llm_config.model
        cfg["temperature"] = llm_config.temperature
        cfg["max_tokens"] = llm_config.max_tokens
        if prompt_config and prompt_config.system_prompt:
            cfg["system_prompt"] = prompt_config.system_prompt

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
            provider_response_raw=raw,
            extraction_metadata={"model": cfg.get("model"), "latency_ms": latency_ms},
        )
