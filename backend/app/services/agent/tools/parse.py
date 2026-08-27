"""Parse tools — one node per parser (fanned out in Slice B)."""
import functools

from app.services.agent.nodes import parse_node
from app.services.agent.tools import FieldSpec, ToolDefinition, register_tool

# (parser_type, display name, config_panel id or None for panel-less parsers)
_PARSERS: list[tuple[str, str, str | None]] = [
    ("simple", "Simple", None),
    ("llamaparse", "LlamaParse", "llamaparse"),
    ("landing_ai", "Landing AI", "landing_ai"),
    ("docling", "Docling", "docling"),
    ("custom_pipeline", "Custom Pipeline", "custom_pipeline"),
]


def _register_parsers() -> None:
    for parser_type, name, config_panel in _PARSERS:
        register_tool(ToolDefinition(
            slug=f"parse.{parser_type}",
            name=name,
            category="parsing",
            description=f"Parse a source document with {name} into a ParsedDocument",
            runtime_inputs=[
                FieldSpec(key="source_document_id", label="Source document",
                          widget="source_document_picker"),
            ],
            outputs=["parse_run_id", "parsed_document_id", "page_count",
                     "text_len", "failed_page_count", "block_count"],
            config_schema={
                "type": "object",
                "properties": {
                    "representation_kind": {
                        "type": "string", "default": "extract_rich",
                        "description": "Representation the parser should produce",
                    },
                    "parse_config": {
                        "type": "object",
                        "description": f"{name} options (edited via its config panel)",
                    },
                },
            },
            config_panel=config_panel,
            node_fn=functools.partial(parse_node, parser_type=parser_type),
        ))


_register_parsers()
