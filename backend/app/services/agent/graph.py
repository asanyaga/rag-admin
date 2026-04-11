"""Dynamic LangGraph builder — constructs StateGraph from flow definitions."""
from typing import Any, Callable

from langgraph.graph import StateGraph, START, END

from app.services.agent.state import AgentState
from app.services.agent.tools import get_tool


# --- Conditional routing functions, referenced by slug in flow definitions ---

_routers: dict[str, Callable] = {}


def register_router(slug: str, fn: Callable) -> None:
    _routers[slug] = fn


def get_router(slug: str) -> Callable:
    fn = _routers.get(slug)
    if fn is None:
        raise ValueError(f"Unknown router: {slug}")
    return fn


def route_after_review(state: AgentState) -> str:
    """Route to export or end based on review action."""
    if state.get("current_step") == "rejected":
        return END
    return "export"


register_router("route_after_review", route_after_review)


# --- Flow definition types ---

FlowDefinition = dict[str, Any]
"""
A flow definition describes how to wire tools into a LangGraph.

Structure:
{
    "nodes": [
        {"id": "extract", "tool": "llamaextract"},
        {"id": "review", "tool": "human-review"},
        {"id": "export", "tool": "receipt-export"},
    ],
    "edges": [
        {"source": "__start__", "target": "extract"},
        {"source": "extract", "target": "review"},
        {"source": "export", "target": "__end__"},
    ],
    "conditional_edges": [
        {
            "source": "review",
            "router": "route_after_review",
            "targets": ["export", "__end__"],
        },
    ],
}
"""


def build_graph_from_definition(
    flow: FlowDefinition,
    checkpointer=None,
) -> Any:
    """Build and compile a LangGraph StateGraph from a flow definition."""
    graph = StateGraph(AgentState)

    # Add nodes
    for node in flow["nodes"]:
        tool = get_tool(node["tool"])
        if tool is None:
            raise ValueError(f"Unknown tool: {node['tool']}")
        graph.add_node(node["id"], tool.node_fn)

    # Add edges
    for edge in flow.get("edges", []):
        source = START if edge["source"] == "__start__" else edge["source"]
        target = END if edge["target"] == "__end__" else edge["target"]
        graph.add_edge(source, target)

    # Add conditional edges
    for cond in flow.get("conditional_edges", []):
        router_fn = get_router(cond["router"])
        targets = [END if t == "__end__" else t for t in cond["targets"]]
        graph.add_conditional_edges(cond["source"], router_fn, targets)

    return graph.compile(checkpointer=checkpointer)


# --- Backwards-compatible helper for the receipt-processing agent type ---

RECEIPT_PROCESSING_FLOW: FlowDefinition = {
    "nodes": [
        {"id": "extract", "tool": "llamaextract"},
        {"id": "review", "tool": "human-review"},
        {"id": "export", "tool": "receipt-export"},
    ],
    "edges": [
        {"source": "__start__", "target": "extract"},
        {"source": "extract", "target": "review"},
        {"source": "export", "target": "__end__"},
    ],
    "conditional_edges": [
        {
            "source": "review",
            "router": "route_after_review",
            "targets": ["export", "__end__"],
        },
    ],
}


def build_receipt_graph(checkpointer=None):
    """Build the receipt processing graph from its flow definition."""
    return build_graph_from_definition(RECEIPT_PROCESSING_FLOW, checkpointer=checkpointer)
