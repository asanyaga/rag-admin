"""Extractor registry — maps extraction method strings to adapter instances."""
from app.config import settings
from app.ports.data_extraction import DataExtractor


def get_extractor(extraction_method: str) -> DataExtractor | None:
    """Get an extractor instance by method string."""
    if extraction_method == "llamaextract":
        from app.adapters.extraction.llamaextract import LlamaExtractAdapter
        api_key = settings.LLAMA_CLOUD_KEY or None
        return LlamaExtractAdapter(api_key=api_key)

    raise ValueError(f"Unknown extraction method: {extraction_method}")


def get_available_extractors() -> list[dict]:
    """Return info about all available extraction methods."""
    extractors: list[dict] = []

    if settings.LLAMA_CLOUD_KEY:
        extractors.append({
            "extraction_method": "llamaextract",
            "name": "LlamaExtract",
            "description": "Structured data extraction via LlamaCloud LlamaExtract. Supports multiple extraction modes and targets.",
            "config_schema": {
                "type": "object",
                "properties": {
                    "extraction_mode": {
                        "type": "string",
                        "enum": ["FAST", "BALANCED", "MULTIMODAL", "PREMIUM"],
                        "default": "MULTIMODAL",
                        "description": "Extraction mode (affects quality and cost)",
                    },
                    "cite_sources": {
                        "type": "boolean",
                        "default": False,
                        "description": "Trace extracted values to source pages/text",
                    },
                    "use_reasoning": {
                        "type": "boolean",
                        "default": False,
                        "description": "Include reasoning for extraction decisions",
                    },
                    "page_range": {
                        "type": "string",
                        "description": "Specific pages to extract from (e.g. '1-5')",
                    },
                },
            },
        })

    return extractors
