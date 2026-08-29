"""LlamaExtract tool — extract structured data from a document."""
from app.services.agent.nodes import extract_node
from app.services.agent.tools import FieldSpec, ToolDefinition, register_tool

register_tool(ToolDefinition(
    slug="llamaextract",
    name="LlamaExtract",
    category="extraction",
    description="Extract structured data from a document using LlamaExtract",
    runtime_inputs=[
        FieldSpec(key="document_id", label="Document", widget="document_picker"),
        FieldSpec(key="extraction_schema_id", label="Extraction schema",
                  widget="extraction_schema_picker"),
    ],
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
