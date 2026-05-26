"""Extractor registry — pure catalogue and credential-aware factory.

The registry never reads settings. Credentials are passed explicitly by the
call site, which resolves them from settings (now) or the database (BYOK).
"""
from app.ports.data_extraction import DataExtractor


def get_known_extractors() -> list[dict]:
    """Catalogue of all known extraction adapters.

    Returns every adapter unconditionally — no credential checks, no settings
    reads. Ordering is a UI concern; this list makes no preference statement.
    """
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
            "extraction_method": "ollama",
            "name": "Ollama",
            "description": (
                "Open-weight extraction via Ollama runtime. "
                "Supports local, self-hosted, and Ollama cloud deployments."
            ),
            "config_schema": {
                "type": "object",
                "properties": {
                    "model": {
                        "type": "string",
                        "description": "Model name, e.g. llama3.2:8b",
                    },
                    "endpoint": {
                        "type": "string",
                        "default": "http://localhost:11434/v1",
                    },
                    "temperature": {"type": "number", "default": 0.0},
                    "structured_output_mode": {
                        "type": "string",
                        "enum": ["json_schema", "json_mode", "prompt_only"],
                        "default": "json_schema",
                    },
                    "inject_block_ids": {"type": "boolean", "default": False},
                    "system_prompt": {"type": "string"},
                    "user_prompt_template": {"type": "string"},
                },
                "required": ["model"],
            },
        },
    ]


def get_extractor(
    method: str,
    credentials: dict,
    dependencies: dict | None = None,
) -> DataExtractor:
    """Construct an adapter with caller-supplied credentials and dependencies.

    Credentials and dependencies are resolved by the call site. Raises ValueError
    for unknown methods.
    """
    if method == "llamaextract":
        from app.adapters.extraction.llamaextract import LlamaExtractAdapter
        deps = dependencies or {}
        return LlamaExtractAdapter(
            api_key=credentials.get("api_key"),
            source_document_repo=deps.get("source_document_repo"),
            storage_service=deps.get("storage_service"),
        )

    if method == "ollama":
        from app.adapters.extraction.ollama import OllamaExtractor
        return OllamaExtractor(
            default_endpoint=credentials.get("endpoint"),
            default_api_key=credentials.get("api_key"),
        )

    raise ValueError(f"Unknown extraction method: {method!r}")
