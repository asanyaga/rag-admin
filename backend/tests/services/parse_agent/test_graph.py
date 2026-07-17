import pytest

from app.services.parse_agent.graph import build_parse_graph


class _FakeRun:
    id = "run-xyz"
    failed_pages = []


class _FakeDoc:
    page_count = 1
    full_text = "hi"
    blocks = []


class _FakeParsingService:
    async def parse_and_persist(self, **kwargs):
        return _FakeRun(), _FakeDoc()


@pytest.mark.asyncio
async def test_graph_streams_two_node_updates_in_order():
    compiled = build_parse_graph(_FakeParsingService(), source=object())
    initial = {
        "file_path": "local://x.pdf", "project_id": "12345678-1234-5678-1234-567812345678",
        "representation_kind": "extract_rich", "config": {"parser": "simple"},
    }

    seen: list[str] = []
    async for chunk in compiled.astream(initial, stream_mode="updates"):
        seen.extend(chunk.keys())

    assert seen == ["parse", "health_check"]


@pytest.mark.asyncio
async def test_graph_accumulates_state_to_final():
    compiled = build_parse_graph(_FakeParsingService(), source=object())
    initial = {
        "file_path": "local://x.pdf", "project_id": "12345678-1234-5678-1234-567812345678",
        "representation_kind": "extract_rich", "config": {"parser": "simple"},
    }
    final = await compiled.ainvoke(initial)
    assert final["parse_run_id"] == "run-xyz"
    assert final["quality_signal"]["ok"] is True
