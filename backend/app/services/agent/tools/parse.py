"""Parse tools — one node per parser. Slice A registers LlamaParse only."""
import functools

from app.services.agent.nodes import parse_node
from app.services.agent.tools import FieldSpec, ToolDefinition, register_tool

register_tool(ToolDefinition(
    slug="parse.llamaparse",
    name="LlamaParse",
    category="parsing",
    description="Parse a source document with LlamaParse into a ParsedDocument",
    runtime_inputs=[
        FieldSpec(key="source_document_id", label="Source document",
                  widget="source_document_picker"),
    ],
    outputs=["parse_run_id", "parsed_document_id", "page_count",
             "text_len", "failed_page_count", "block_count"],
    config_schema={
        "type": "object",
        "properties": {
            "representation_kind": {"type": "string", "default": "extract_rich",
                                    "description": "Representation the parser should produce"},
            "parse_config": {"type": "object",
                             "description": "LlamaParse options (edited via the LlamaParse panel)"},
        },
    },
    config_panel="llamaparse",
    node_fn=functools.partial(parse_node, parser_type="llamaparse"),
))
