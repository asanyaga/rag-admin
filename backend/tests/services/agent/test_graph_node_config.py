import pytest
from app.services.agent.graph import build_agent_graph
from app.services.agent.state import AgentState
from app.services.agent.tools import ToolDefinition, register_tool


@pytest.mark.asyncio
async def test_two_nodes_of_same_tool_get_independent_config():
    seen: list[dict] = []

    async def probe_node(state: dict, *, node_config: dict) -> dict:
        seen.append(node_config)
        return {**state, "last_tag": node_config.get("tag")}

    register_tool(ToolDefinition(
        slug="probe", name="Probe", category="control",
        description="test probe", node_fn=probe_node,
    ))

    flow = {
        "nodes": [
            {"id": "a", "tool": "probe", "config": {"tag": "A"}},
            {"id": "b", "tool": "probe", "config": {"tag": "B"}},
        ],
        "edges": [
            {"source": "__start__", "target": "a"},
            {"source": "a", "target": "b"},
            {"source": "b", "target": "__end__"},
        ],
    }
    compiled = build_agent_graph(flow=flow, state_type=AgentState)
    result = await compiled.ainvoke({})

    assert {c["tag"] for c in seen} == {"A", "B"}      # each node saw its own config
    assert result["last_tag"] == "B"
    assert "node_config" not in result                  # config not persisted in state
    assert "tag" not in result                          # design-time config absent from state
