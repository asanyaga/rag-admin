"""LangGraph StateGraph builder for the receipt processing pipeline."""
from langgraph.graph import StateGraph, START, END

from app.services.agent.state import AgentState
from app.services.agent.nodes import extract_node, review_node, export_node


def route_after_review(state: AgentState) -> str:
    """Route to export or end based on review action."""
    if state.get("current_step") == "rejected":
        return END
    return "export"


def build_receipt_graph(checkpointer=None):
    """Build and compile the receipt processing graph."""
    graph = StateGraph(AgentState)

    graph.add_node("extract", extract_node)
    graph.add_node("review", review_node)
    graph.add_node("export", export_node)

    graph.add_edge(START, "extract")
    graph.add_edge("extract", "review")
    graph.add_conditional_edges("review", route_after_review, ["export", END])
    graph.add_edge("export", END)

    return graph.compile(checkpointer=checkpointer)
