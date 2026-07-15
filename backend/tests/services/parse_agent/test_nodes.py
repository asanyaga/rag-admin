import pytest

from app.services.parse_agent.nodes import GRAPH_NODES, NODE_SPECS, health_check_node, make_parse_node


@pytest.mark.asyncio
async def test_health_check_ok_when_text_present_and_no_failed_pages():
    state = {"text_len": 12, "failed_page_count": 0, "block_count": 3}
    out = await health_check_node(state)
    assert out["quality_signal"]["text_non_empty"] is True
    assert out["quality_signal"]["ok"] is True


@pytest.mark.asyncio
async def test_health_check_not_ok_when_empty_text():
    state = {"text_len": 0, "failed_page_count": 0, "block_count": 0}
    out = await health_check_node(state)
    assert out["quality_signal"]["ok"] is False


@pytest.mark.asyncio
async def test_make_parse_node_calls_parsing_service_and_returns_delta():
    class FakeRun:
        id = "run-123"
        failed_pages = []

    class FakeDoc:
        page_count = 2
        full_text = "hello"
        blocks = [1, 2, 3]

    class FakeParsingService:
        def __init__(self):
            self.called_with = None

        async def parse_and_persist(self, **kwargs):
            self.called_with = kwargs
            return FakeRun(), FakeDoc()

    svc = FakeParsingService()
    source = object()  # closed over; not inspected by the node
    node = make_parse_node(svc, source)

    state = {
        "file_path": "local://x.pdf", "project_id": "proj-1",
        "representation_kind": "extract_rich", "config": {"parser": "simple"},
    }
    out = await node(state)

    assert out["parse_run_id"] == "run-123"
    assert out["page_count"] == 2
    assert out["text_len"] == 5
    assert out["failed_page_count"] == 0
    assert out["block_count"] == 3
    assert svc.called_with["file_path"] == "local://x.pdf"
    assert svc.called_with["source"] is source


def test_graph_nodes_order_and_specs():
    assert GRAPH_NODES == ["parse", "health_check"]
    assert set(NODE_SPECS) == {"parse", "health_check"}
    assert "file_path" in NODE_SPECS["parse"].input_keys
    assert "quality_signal" in NODE_SPECS["health_check"].output_keys
