"""Export tool — write pipeline data to a project data store."""
from app.services.agent.nodes import export_node
from app.services.agent.tools import ToolDefinition, register_tool

register_tool(ToolDefinition(
    slug="export",
    name="Export",
    category="export",
    description="Export data to a project data store",
    input_keys=["reviewed_data", "extracted_data"],
    output_keys=["exported", "rows_exported"],
    config_schema={
        "type": "object",
        "properties": {
            "data_store_id": {
                "type": "string",
                "format": "uuid",
                "description": "Target data store to export rows into",
            },
            "field_mapping": {
                "type": "object",
                "additionalProperties": {"type": "string"},
                "description": "Source dot-path → destination column name mapping",
            },
        },
        "required": ["data_store_id"],
    },
    node_fn=export_node,
))
