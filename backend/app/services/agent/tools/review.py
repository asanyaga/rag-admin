"""Human review tool — interrupt execution for human-in-the-loop review."""
from app.services.agent.nodes import review_node
from app.services.agent.tools import ToolDefinition, register_tool

register_tool(ToolDefinition(
    slug="human-review",
    name="Human Review",
    category="control",
    description="Pause execution and wait for human approval, edit, or rejection",
    input_keys=["extracted_data"],
    output_keys=["review_action", "reviewed_data"],
    node_fn=review_node,
))
