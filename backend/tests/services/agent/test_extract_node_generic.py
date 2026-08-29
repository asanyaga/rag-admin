import pytest
from app.services.agent import nodes


@pytest.mark.asyncio
async def test_extract_node_resolves_document_and_schema_ids(monkeypatch):
    captured = {}

    async def fake_file_path(session, document_id):
        captured["document_id"] = str(document_id)
        return "/tmp/doc.pdf"

    async def fake_schema(session, schema_id):
        captured["schema_id"] = str(schema_id)
        return {"type": "object", "properties": {}}

    class FakeOutput:
        structured_data = {"total": 42}

    class FakeExtractor:
        async def extract(self, *, file_path, schema, config):
            captured["file_path"] = file_path
            captured["schema"] = schema
            return FakeOutput()

    from app.services.agent import extraction_bridge as eb
    monkeypatch.setattr(eb, "resolve_document_file_path", fake_file_path)
    monkeypatch.setattr(eb, "resolve_schema_definition", fake_schema)
    monkeypatch.setattr(nodes, "AsyncSessionLocal", _session_ctx())
    monkeypatch.setattr("app.adapters.extraction.registry.get_extractor",
                        lambda *_a, **_k: FakeExtractor())

    state = {"document_id": "00000000-0000-0000-0000-000000000001",
             "extraction_schema_id": "00000000-0000-0000-0000-000000000002",
             "user_id": "00000000-0000-0000-0000-000000000003",
             "project_id": "00000000-0000-0000-0000-000000000004"}
    result = await nodes.extract_node(state)

    assert captured["file_path"] == "/tmp/doc.pdf"
    assert captured["schema"] == {"type": "object", "properties": {}}
    assert result["extracted_data"] == {"total": 42}


@pytest.mark.asyncio
async def test_extract_node_falls_back_to_preseeded_state(monkeypatch):
    """The bespoke /agent/extract entrypoint seeds file_path + schema_definition;
    extract_node must still work without document_id/schema_id."""
    class FakeOutput:
        structured_data = {"ok": True}

    class FakeExtractor:
        async def extract(self, *, file_path, schema, config):
            assert file_path == "/seeded.pdf"
            assert schema == {"seeded": True}
            return FakeOutput()

    monkeypatch.setattr(nodes, "AsyncSessionLocal", _session_ctx())
    monkeypatch.setattr("app.adapters.extraction.registry.get_extractor",
                        lambda *_a, **_k: FakeExtractor())

    state = {"file_path": "/seeded.pdf", "schema_definition": {"seeded": True}}
    result = await nodes.extract_node(state)
    assert result["extracted_data"] == {"ok": True}


@pytest.mark.asyncio
async def test_extract_to_export_chain_threads_data(monkeypatch):
    """Real 2-node extract -> export graph, proving extract's output threads
    into export's input.

    CONFIRM #2: tools/export.py does `from ...nodes import export_node` at
    import time and hands that function object to ToolDefinition(node_fn=...).
    graph.py's functools.partial(tool.node_fn, ...) captures that same object
    reference. Monkeypatching nodes.export_node afterwards does NOT change
    what the compiled graph calls (the ToolDefinition already holds the
    original function object, not a lookup through the nodes module
    namespace). So the graph runs the REAL export_node here; we fake
    DataStoreRepository (which export_node imports locally per call, so
    patching the class at its home module DOES take effect) to capture the
    data it actually persists, without hitting a real database.
    """
    from app.services.agent.graph import build_agent_graph
    from app.services.agent.state import AgentState
    from app.services.agent import extraction_bridge as eb

    captured = {}

    async def fake_file_path(session, document_id):
        return "/tmp/doc.pdf"

    async def fake_schema(session, schema_id):
        return {"type": "object"}

    class FakeOutput:
        structured_data = {"amount": 10}

    class FakeExtractor:
        async def extract(self, *, file_path, schema, config):
            return FakeOutput()

    class FakeStore:
        id = "store-1"
        table_name = "pd_deadbeef"
        schema_definition = [{"name": "amount", "type": "integer"}]

    class FakeDataStoreRepository:
        def __init__(self, session):
            pass

        async def get_by_id(self, store_id, project_id):
            return FakeStore()

        async def bulk_insert(self, table_name, schema_definition, rows, source_metadata=None):
            # capture the row export actually built from upstream extracted_data
            captured["export_saw"] = rows[0] if rows else None
            return len(rows)

        async def count_rows(self, table_name):
            return 1

        async def update_row_count(self, store_id, count):
            return None

    monkeypatch.setattr(eb, "resolve_document_file_path", fake_file_path)
    monkeypatch.setattr(eb, "resolve_schema_definition", fake_schema)
    monkeypatch.setattr(nodes, "AsyncSessionLocal", _session_ctx())
    monkeypatch.setattr("app.adapters.extraction.registry.get_extractor",
                        lambda *_a, **_k: FakeExtractor())
    monkeypatch.setattr(
        "app.repositories.data_store_repository.DataStoreRepository",
        FakeDataStoreRepository,
    )

    flow = {
        "nodes": [{"id": "e", "tool": "llamaextract"},
                  {"id": "x", "tool": "export",
                   "config": {"data_store_id": "55555555-5555-5555-5555-555555555555"}}],
        "edges": [{"source": "__start__", "target": "e"},
                  {"source": "e", "target": "x"},
                  {"source": "x", "target": "__end__"}],
    }
    compiled = build_agent_graph(flow=flow, state_type=AgentState)
    result = await compiled.ainvoke({
        "document_id": "00000000-0000-0000-0000-000000000001",
        "extraction_schema_id": "00000000-0000-0000-0000-000000000002",
        "user_id": "00000000-0000-0000-0000-000000000003",
        "project_id": "00000000-0000-0000-0000-000000000004"})

    assert captured["export_saw"] == {"amount": 10}   # extract output -> export input
    assert result["exported"] is True


def _session_ctx():
    class _Ctx:
        async def __aenter__(self): return "SESSION"
        async def __aexit__(self, *a): return False
    return lambda: _Ctx()
