from app.services.agent.tools import get_tool
from app.services.agent.validation import validate_graph


def _flow(nodes, edges):
    return {"nodes": nodes, "edges": edges}


def test_valid_extract_review_export_chain_has_no_unmet():
    flow = _flow(
        [{"id": "e", "tool": "llamaextract"},
         {"id": "r", "tool": "human-review"},
         {"id": "x", "tool": "export"}],
        [{"source": "e", "target": "r"}, {"source": "r", "target": "x"}],
    )
    assert validate_graph(flow, get_tool) == []


def test_lone_export_has_unmet_upstream_input():
    flow = _flow([{"id": "x", "tool": "export"}], [])
    unmet = validate_graph(flow, get_tool)
    assert [(u.node_id, u.key) for u in unmet] == [("x", "extracted_data")]


def test_producer_after_consumer_does_not_satisfy():
    # export BEFORE extract: extract's output is not a reachable predecessor of export
    flow = _flow(
        [{"id": "x", "tool": "export"}, {"id": "e", "tool": "llamaextract"}],
        [{"source": "x", "target": "e"}],
    )
    unmet = validate_graph(flow, get_tool)
    assert ("x", "extracted_data") in [(u.node_id, u.key) for u in unmet]
