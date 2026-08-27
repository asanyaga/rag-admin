"""Parse tool — parse a source document into a ParsedDocument."""
from app.services.agent.nodes import parse_node
from app.services.agent.tools import ToolDefinition, register_tool

register_tool(ToolDefinition(
    slug="parse",
    name="Parse",
    category="parsing",
    description="Parse a source document into a ParsedDocument",
    input_keys=["source_document_id", "representation_kind", "parse_config",
                "project_id", "user_id"],
    output_keys=["parse_run_id", "parsed_document_id", "page_count",
                 "text_len", "failed_page_count", "block_count"],
    config_schema={
        "type": "object",
        "properties": {
            "parser": {
                "type": "string",
                "enum": ["simple", "llamaparse", "landing_ai", "docling"],
                "default": "simple",
                "description": "Parser engine to use",
            },
            "representation_kind": {
                "type": "string",
                "default": "extract_rich",
                "description": "Representation the parser should produce",
            },
        },
    },
    node_fn=parse_node,
))
