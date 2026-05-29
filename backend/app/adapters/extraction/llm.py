"""Generic LLM extraction adapter.

Works with any provider supported by create_adapter(). Reads per-run LLM
config from the 'llm_config' key in the config dict (a serialized PromptConfig).
Caller is responsible for pre-resolving credentials (provider, api_key, base_url)
and placing them in the config dict before calling extract().
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
from app.services.llm.factory import create_adapter
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
    """Structured extraction via any LLM provider supported by create_adapter()."""

    extractor_type = "llm"
    display_name = "LLM"

    def __init__(
        self,
        default_provider: str = "ollama_local",
        default_api_key: str = "ollama",
    ) -> None:
        self._default_provider = default_provider
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

        # Resolve provider and credentials from cfg (pre-resolved by caller)
        provider = cfg.get("provider") or self._default_provider
        api_key = cfg.get("api_key") or self._default_api_key
        base_url: str | None = cfg.get("base_url")

        # Resolve LLM config from PromptConfig stored in config["llm_config"]
        prompt_config: PromptConfig | None = None
        if cfg.get("llm_config"):
            prompt_config = PromptConfig.model_validate(cfg["llm_config"])
        resolved = resolve_llm_config(
            prompt_config,
            default_provider=provider,
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

        adapter = create_adapter(resolved.provider, api_key, base_url)

        t0 = time.monotonic()
        try:
            result = await adapter.complete(messages, llm_config)
        except LLMConnectionError as exc:
            raise ExtractionError(f"Cannot connect to LLM provider '{provider}': {exc}") from exc
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
