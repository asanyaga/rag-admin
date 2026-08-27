"""LlamaExtract tool — extract structured data from a document."""
from app.services.agent.nodes import extract_node
from app.services.agent.tools import ToolDefinition, register_tool

register_tool(ToolDefinition(
    slug="llamaextract",
    name="LlamaExtract",
    category="extraction",
    description="Extract structured data from a document using LlamaExtract",
    runtime_inputs=[],  # bespoke entrypoint seeds document_id/file_path/schema_definition
    outputs=["extracted_data"],
    config_schema={
        "type": "object",
        "properties": {
            "extraction_target": {
                "type": "string",
                "enum": ["PER_DOC", "PER_PAGE"],
                "default": "PER_DOC",
                "description": "Extract one result per document or per page",
            },
        },
    },
    node_fn=extract_node,
))
