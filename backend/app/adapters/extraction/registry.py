"""Extractor registry — pure catalogue and credential-aware factory.

The registry never reads settings. Credentials are passed explicitly by the
call site, which resolves them from settings (now) or the database (BYOK).
"""
from app.ports.data_extraction import DataExtractor


def get_known_extractors() -> list[dict]:
    """Catalogue of all known extraction adapters."""
    return [
        {
            "extraction_method": "llamaextract",
            "name": "LlamaExtract",
            "description": (
                "Structured extraction via LlamaCloud. "
                "Multimodal, supports citations and reasoning."
            ),
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
        },
        {
            "extraction_method": "llm",
            "name": "LLM",
            "description": (
                "Structured extraction via any LLM provider "
                "(Ollama, OpenAI, Anthropic, Groq, …)"
            ),
            "config_schema": {
                "type": "object",
                "properties": {
                    "structured_output_mode": {
                        "type": "string",
                        "enum": ["json_schema", "json_mode", "prompt_only"],
                        "default": "json_schema",
                    },
                    "inject_block_ids": {"type": "boolean", "default": False},
                    "user_prompt_template": {"type": "string"},
                },
            },
        },
    ]


def get_extractor(
    method: str,
    credentials: dict,
    dependencies: dict | None = None,
) -> DataExtractor:
    """Construct an adapter with caller-supplied credentials and dependencies."""
    if method == "llamaextract":
        from app.adapters.extraction.llamaextract import LlamaExtractAdapter
        deps = dependencies or {}
        return LlamaExtractAdapter(
            api_key=credentials.get("api_key"),
            source_document_repo=deps.get("source_document_repo"),
            storage_service=deps.get("storage_service"),
        )

    if method == "llm":
        from app.adapters.extraction.llm import LLMExtractor
        return LLMExtractor(
            default_provider=credentials.get("provider", "ollama_local"),
            default_api_key=credentials.get("api_key", "ollama"),
        )

    raise ValueError(f"Unknown extraction method: {method!r}")
