"""Hand-wired parse-agent graph: START -> parse -> health_check -> END.

Raw LangGraph primitives on purpose (pedagogy). No checkpointer in v1 — there is
no interrupt/human-review yet; durability comes from the persisted step log.

State schema is a TypedDict (per-key LastValue channels) rather than a plain
`dict`. In langgraph 1.1.6, `StateGraph(dict)` collapses the whole state into a
single `__root__` LastValue channel, so a node's partial-delta return *replaces*
the entire state — dropping keys accumulated by earlier nodes. A TypedDict
schema gives one LastValue channel per key, so partial deltas merge per-key and
state accumulates across the graph while nodes stay partial-delta (clean
`updates` traces).
"""
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app.services.parse_agent.nodes import health_check_node, make_parse_node


class ParseAgentState(TypedDict, total=False):
    file_path: str
    source_document_id: str
    project_id: str
    representation_kind: str
    config: dict
    parse_run_id: str
    page_count: int
    text_len: int
    failed_page_count: int
    block_count: int
    quality_signal: dict


def build_parse_graph(parsing_service, source):
    graph = StateGraph(ParseAgentState)
    graph.add_node("parse", make_parse_node(parsing_service, source))
    graph.add_node("health_check", health_check_node)
    graph.add_edge(START, "parse")
    graph.add_edge("parse", "health_check")
    graph.add_edge("health_check", END)
    return graph.compile()
