"""Parser registry — maps parser type strings to adapter instances."""
from app.config import settings
from app.ports.document_parsing import DocumentParser


def get_parser(parser_type: str) -> DocumentParser | None:
    """Get a parser instance by type string.

    Returns None for "simple" (uses existing extractor flow).
    """
    if parser_type == "simple":
        return None

    if parser_type == "llamaparse":
        from app.adapters.parsing.llamaparse import LlamaParseAdapter
        api_key = settings.LLAMA_CLOUD_KEY or None
        return LlamaParseAdapter(api_key=api_key)

    raise ValueError(f"Unknown parser type: {parser_type}")


def get_available_parsers() -> list[dict]:
    """Return info about all available parsers."""
    parsers = [
        {
            "parser_type": "simple",
            "name": "Simple (local)",
            "description": "Basic text extraction using LlamaIndex SimpleDirectoryReader. Works on clean text-based PDFs.",
            "supported_file_types": ["application/pdf"],
            "config_schema": None,
        },
    ]

    # Only include LlamaParse if API key is configured
    if settings.LLAMA_CLOUD_KEY:
        parsers.append({
            "parser_type": "llamaparse",
            "name": "LlamaParse",
            "description": "Intelligent document parsing via LlamaParse. Handles complex layouts, tables, scanned documents.",
            "supported_file_types": [
                "application/pdf",
                "image/jpeg", "image/png",
            ],
            "config_schema": {
                "type": "object",
                "properties": {
                    "tier": {
                        "type": "string",
                        "enum": ["fast", "cost_effective", "agentic", "agentic_plus"],
                        "default": "agentic",
                        "description": "Processing tier (affects quality and cost)",
                    },
                    "expand": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["text", "markdown", "items", "metadata"],
                        },
                        "default": ["markdown", "text"],
                        "description": "Output types to request",
                    },
                },
            },
        })

    return parsers
