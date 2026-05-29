"""Generic LLM extraction adapter.

Receives a pre-built LLMPort adapter at construction time.
The caller (router or test) is responsible for resolving credentials
and calling create_adapter() before instantiating LLMExtractor.
"""
import json
import re
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

_CODE_FENCE_RE = re.compile(r'```(?:json)?\s*\n?(.*?)\n?\s*```', re.DOTALL)


def _strip_code_fences(content: str) -> str:
    """Extract JSON from inside a code fence anywhere in the response.

    Handles models that add preamble/trailing text around the fence.
    Returns content unchanged if no fence is found.
    """
    m = _CODE_FENCE_RE.search(content.strip())
    return m.group(1).strip() if m else content.strip()


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
            default_max_tokens=4096,
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
            raw = json.loads(_strip_code_fences(result.content))
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
