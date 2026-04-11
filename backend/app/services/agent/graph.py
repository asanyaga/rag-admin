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
    state_type=None,
) -> Any:
    """Build and compile a LangGraph StateGraph from a flow definition."""
    graph = StateGraph(state_type or AgentState)

    # Add nodes
    for node in flow["nodes"]:
        tool = get_tool(node["tool"])
        if tool is None:
            raise ValueError(f"Unknown tool: {node['tool']}")
        graph.add_node(node["id"], tool.node_fn)

    # Add edges
    has_start = False
    has_end = False
    edge_targets = set()  # nodes that are targets of an edge
    edge_sources = set()  # nodes that are sources of an edge

    for edge in flow.get("edges", []):
        source = START if edge["source"] == "__start__" else edge["source"]
        target = END if edge["target"] == "__end__" else edge["target"]
        if source is START:
            has_start = True
        if target is END:
            has_end = True
        if source is not START:
            edge_sources.add(edge["source"])
        if target is not END:
            edge_targets.add(edge["target"])
        graph.add_edge(source, target)

    # Add conditional edges
    for cond in flow.get("conditional_edges", []):
        router_fn = get_router(cond["router"])
        targets = [END if t == "__end__" else t for t in cond["targets"]]
        edge_sources.add(cond["source"])
        for t in cond["targets"]:
            if t == "__end__":
                has_end = True
            else:
                edge_targets.add(t)
        graph.add_conditional_edges(cond["source"], router_fn, targets)

    # Auto-infer START and END if not explicitly provided
    node_ids = {n["id"] for n in flow["nodes"]}
    if not has_start:
        # Entry nodes: nodes that are never a target of another node
        entry_nodes = node_ids - edge_targets
        if entry_nodes:
            graph.add_edge(START, entry_nodes.pop())
        elif node_ids:
            # Fallback: use the first node in definition order
            graph.add_edge(START, flow["nodes"][0]["id"])

    if not has_end:
        # Exit nodes: nodes that are never a source of another edge
        exit_nodes = node_ids - edge_sources
        if exit_nodes:
            for exit_node in exit_nodes:
                graph.add_edge(exit_node, END)
        elif node_ids:
            # Fallback: use the last node in definition order
            graph.add_edge(flow["nodes"][-1]["id"], END)

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
