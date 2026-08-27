import pytest
from app.services.agent import parsing_bridge as pb
from app.services.agent.graph import build_agent_graph
from app.services.agent.tools import get_tool


@pytest.mark.asyncio
async def test_parse_node_merges_full_state_through_graph(monkeypatch):
    # Ensure the parse tool is registered (Task 3 registers it; import guard here).
    assert get_tool("parse") is not None, "register the parse tool (Task 3) first"

    async def fake_resolve_source_cdm(session, sid):
        return object(), "/tmp/doc.pdf"

    async def fake_build_parsing_service(session, user_id, parser_type):
        return object()

    async def fake_run_parse(session, service, source, **kwargs):
        return pb.ParseOutcome(
            parse_run_id="run-1", parsed_document_id="pdoc-1",
            page_count=2, text_len=10, failed_page_count=0, block_count=5,
        )

    monkeypatch.setattr(pb, "resolve_source_cdm", fake_resolve_source_cdm)
    monkeypatch.setattr(pb, "build_parsing_service", fake_build_parsing_service)
    monkeypatch.setattr(pb, "run_parse", fake_run_parse)

    flow = {"nodes": [{"id": "p", "tool": "parse"}], "edges": [], "conditional_edges": []}
    compiled = build_agent_graph(flow)

    initial = {
        "source_document_id": "11111111-1111-1111-1111-111111111111",
        "user_id": "22222222-2222-2222-2222-222222222222",
        "project_id": "33333333-3333-3333-3333-333333333333",
        "representation_kind": "extract_rich",
        "parse_config": {"parser": "simple"},
        "sentinel": "keep-me",  # proves accumulated state survives the node
    }
    result = await compiled.ainvoke(initial)

    # parse outputs present
    assert result["parse_run_id"] == "run-1"
    assert result["parsed_document_id"] == "pdoc-1"
    assert result["block_count"] == 5
    # full-state merge: pre-existing keys are NOT dropped
    assert result["sentinel"] == "keep-me"
    assert result["source_document_id"] == initial["source_document_id"]
