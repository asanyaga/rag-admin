"""Graph validation — a node's pipeline inputs must be produced upstream."""
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class UnmetInput:
    node_id: str
    key: str


def _reachable_predecessors(node_id: str, adjacency: dict[str, set[str]]) -> set[str]:
    """All nodes that can run strictly before node_id (transitive predecessors)."""
    seen: set[str] = set()
    stack = list(adjacency.get(node_id, ()))
    while stack:
        p = stack.pop()
        if p in seen:
            continue
        seen.add(p)
        stack.extend(adjacency.get(p, ()))
    return seen


def validate_graph(definition: dict, get_tool_fn: Callable) -> list[UnmetInput]:
    nodes = definition.get("nodes", [])
    edges = definition.get("edges", [])

    # predecessors[target] = {sources...}, ignoring the synthetic __start__/__end__
    predecessors: dict[str, set[str]] = {n["id"]: set() for n in nodes}
    for e in edges:
        s, t = e["source"], e["target"]
        if s in ("__start__", "__end__") or t in ("__start__", "__end__"):
            continue
        predecessors.setdefault(t, set()).add(s)

    tool_of = {n["id"]: get_tool_fn(n["tool"]) for n in nodes}

    def outputs_of(nid: str) -> set[str]:
        tool = tool_of.get(nid)
        return set(tool.outputs) if tool else set()

    unmet: list[UnmetInput] = []
    for n in nodes:
        nid = n["id"]
        tool = tool_of.get(nid)
        if tool is None:
            continue
        upstream_keys: set[str] = set()
        for pred in _reachable_predecessors(nid, predecessors):
            upstream_keys |= outputs_of(pred)
        for f in tool.runtime_inputs:
            if f.source == "upstream" and f.key not in upstream_keys:
                unmet.append(UnmetInput(node_id=nid, key=f.key))
    return unmet
