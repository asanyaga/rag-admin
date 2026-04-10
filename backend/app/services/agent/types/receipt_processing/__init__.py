"""Receipt processing agent type — extract → review → export pipeline."""
from app.services.agent.graph import build_receipt_graph
from app.services.agent.types import AgentTypeDefinition, register_agent_type

definition = AgentTypeDefinition(
    slug="receipt-processing",
    name="Receipt Processing",
    description="Extract structured data from receipt photos, review, and export",
    nodes=[
        {"name": "extract", "label": "Extract Data"},
        {"name": "review", "label": "Human Review"},
        {"name": "export", "label": "Export"},
    ],
    graph_builder=build_receipt_graph,
)

register_agent_type(definition)
