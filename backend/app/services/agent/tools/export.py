"""Export tool — mark extracted data as exported for downstream consumption."""
from app.services.agent.nodes import export_node
from app.services.agent.tools import ToolDefinition, register_tool

register_tool(ToolDefinition(
    slug="export",
    name="Export",
    category="export",
    description="Mark extracted data as exported for downstream consumption",
    input_keys=["reviewed_data", "extracted_data"],
    output_keys=["exported"],
    node_fn=export_node,
))
