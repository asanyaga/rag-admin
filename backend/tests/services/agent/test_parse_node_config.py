import pytest
from app.services.agent import nodes


@pytest.mark.asyncio
async def test_parse_node_reads_parser_from_bound_config(monkeypatch):
    captured = {}

    async def fake_resolve(session, sid):
        return ("SRC", "/tmp/f.pdf")

    async def fake_build(session, user_id, parser_type):
        captured["parser"] = parser_type
        return "SERVICE"

    class FakeOutcome:
        def as_state(self):
            return {"parse_run_id": "r1", "parsed_document_id": "p1",
                    "page_count": 1, "text_len": 10,
                    "failed_page_count": 0, "block_count": 2}

    async def fake_run(session, service, source, *, file_path,
                       representation_kind, config, project_id):
        captured["representation_kind"] = representation_kind
        captured["config"] = config
        return FakeOutcome()

    monkeypatch.setattr(nodes, "AsyncSessionLocal", _dummy_session_ctx())
    from app.services.agent import parsing_bridge as pb
    monkeypatch.setattr(pb, "resolve_source_cdm", fake_resolve)
    monkeypatch.setattr(pb, "build_parsing_service", fake_build)
    monkeypatch.setattr(pb, "run_parse", fake_run)

    state = {"source_document_id": "00000000-0000-0000-0000-000000000001",
             "user_id": "00000000-0000-0000-0000-000000000002",
             "project_id": "00000000-0000-0000-0000-000000000003"}
    result = await nodes.parse_node(
        state,
        node_config={"parser": "llamaparse", "representation_kind": "extract_rich",
                     "parse_config": {"tier": "agentic"}},
    )

    assert captured["parser"] == "llamaparse"
    assert captured["representation_kind"] == "extract_rich"
    assert captured["config"] == {"tier": "agentic"}
    assert result["parsed_document_id"] == "p1"
    assert result["current_step"] == "parsed"


@pytest.mark.asyncio
async def test_parse_node_falls_back_to_bound_parser_type_when_unconfigured(monkeypatch):
    """A parse.llamaparse node built without frontend-seeded config (programmatic
    definition, import, or lost key) must still resolve to its bound parser
    identity, not silently default to 'simple'."""
    captured = {}

    async def fake_resolve(session, sid):
        return ("SRC", "/tmp/f.pdf")

    async def fake_build(session, user_id, parser_type):
        captured["parser"] = parser_type
        return "SERVICE"

    class FakeOutcome:
        def as_state(self):
            return {"parse_run_id": "r1", "parsed_document_id": "p1",
                    "page_count": 1, "text_len": 10,
                    "failed_page_count": 0, "block_count": 2}

    async def fake_run(session, service, source, *, file_path,
                       representation_kind, config, project_id):
        return FakeOutcome()

    monkeypatch.setattr(nodes, "AsyncSessionLocal", _dummy_session_ctx())
    from app.services.agent import parsing_bridge as pb
    monkeypatch.setattr(pb, "resolve_source_cdm", fake_resolve)
    monkeypatch.setattr(pb, "build_parsing_service", fake_build)
    monkeypatch.setattr(pb, "run_parse", fake_run)

    state = {"source_document_id": "00000000-0000-0000-0000-000000000001",
             "user_id": "00000000-0000-0000-0000-000000000002",
             "project_id": "00000000-0000-0000-0000-000000000003"}

    # Simulate the tool's bound node_fn: functools.partial(parse_node, parser_type="llamaparse")
    # called with no node_config and no parse_config in state.
    result = await nodes.parse_node(state, node_config=None, parser_type="llamaparse")

    assert captured["parser"] == "llamaparse"
    assert result["parsed_document_id"] == "p1"


@pytest.mark.asyncio
async def test_parse_node_explicit_node_config_wins_over_bound_parser_type(monkeypatch):
    """Explicit node_config['parser'] must still take precedence over the bound
    parser_type fallback."""
    captured = {}

    async def fake_resolve(session, sid):
        return ("SRC", "/tmp/f.pdf")

    async def fake_build(session, user_id, parser_type):
        captured["parser"] = parser_type
        return "SERVICE"

    class FakeOutcome:
        def as_state(self):
            return {"parse_run_id": "r1", "parsed_document_id": "p1",
                    "page_count": 1, "text_len": 10,
                    "failed_page_count": 0, "block_count": 2}

    async def fake_run(session, service, source, *, file_path,
                       representation_kind, config, project_id):
        return FakeOutcome()

    monkeypatch.setattr(nodes, "AsyncSessionLocal", _dummy_session_ctx())
    from app.services.agent import parsing_bridge as pb
    monkeypatch.setattr(pb, "resolve_source_cdm", fake_resolve)
    monkeypatch.setattr(pb, "build_parsing_service", fake_build)
    monkeypatch.setattr(pb, "run_parse", fake_run)

    state = {"source_document_id": "00000000-0000-0000-0000-000000000001",
             "user_id": "00000000-0000-0000-0000-000000000002",
             "project_id": "00000000-0000-0000-0000-000000000003"}

    result = await nodes.parse_node(
        state,
        node_config={"parser": "other_parser"},
        parser_type="llamaparse",
    )

    assert captured["parser"] == "other_parser"
    assert result["parsed_document_id"] == "p1"


def _dummy_session_ctx():
    class _Ctx:
        async def __aenter__(self): return "SESSION"
        async def __aexit__(self, *a): return False
    def _factory(): return _Ctx()
    return _factory


@pytest.mark.asyncio
async def test_parse_simple_node_runs_through_graph_with_bound_identity(monkeypatch):
    import functools
    from app.services.agent import nodes
    from app.services.agent import parsing_bridge as pb
    from app.services.agent.graph import build_agent_graph
    from app.services.agent.state import AgentState

    captured = {}

    async def fake_resolve(session, sid):
        return ("SRC", "/tmp/f.pdf")

    async def fake_build(session, user_id, parser_type):
        captured["parser"] = parser_type
        return "SERVICE"

    class FakeOutcome:
        def as_state(self):
            return {"parse_run_id": "r1", "parsed_document_id": "p1",
                    "page_count": 1, "text_len": 10,
                    "failed_page_count": 0, "block_count": 2}

    async def fake_run(session, service, source, *, file_path,
                       representation_kind, config, project_id):
        return FakeOutcome()

    class _Ctx:
        async def __aenter__(self): return "SESSION"
        async def __aexit__(self, *a): return False

    monkeypatch.setattr(nodes, "AsyncSessionLocal", lambda: _Ctx())
    monkeypatch.setattr(pb, "resolve_source_cdm", fake_resolve)
    monkeypatch.setattr(pb, "build_parsing_service", fake_build)
    monkeypatch.setattr(pb, "run_parse", fake_run)

    flow = {
        "nodes": [{"id": "n1", "tool": "parse.simple", "config": {}}],
        "edges": [{"source": "__start__", "target": "n1"},
                  {"source": "n1", "target": "__end__"}],
    }
    compiled = build_agent_graph(flow=flow, state_type=AgentState)
    result = await compiled.ainvoke({
        "source_document_id": "00000000-0000-0000-0000-000000000001",
        "user_id": "00000000-0000-0000-0000-000000000002",
        "project_id": "00000000-0000-0000-0000-000000000003",
    })

    assert captured["parser"] == "simple"          # bound identity reached the bridge
    assert result["parsed_document_id"] == "p1"
    assert result["current_step"] == "parsed"
