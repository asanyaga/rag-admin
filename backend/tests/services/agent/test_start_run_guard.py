import pytest
from app.services.agent.agent_run_service import AgentRunService


class _FakeDefRepo:
    def __init__(self, definition):
        self._definition = definition
        self.created = False

    async def get_by_id(self, _id):
        class D:  # minimal agent-definition stand-in
            definition = self._definition
        return D()


class _FakeRunRepo:
    def __init__(self):
        self.create_called = False

    async def create(self, **kw):
        self.create_called = True
        raise AssertionError("run must not be created for an invalid graph")


@pytest.mark.asyncio
async def test_start_run_rejects_unmet_upstream_before_creating_run():
    invalid = {"nodes": [{"id": "x", "tool": "export"}], "edges": []}
    run_repo = _FakeRunRepo()
    svc = AgentRunService(
        agent_run_repo=run_repo,
        agent_def_repo=_FakeDefRepo(invalid),
        checkpointer=None,
    )
    with pytest.raises(ValueError) as ei:
        await svc.start_run(
            project_id="00000000-0000-0000-0000-000000000001",
            agent_definition_id="00000000-0000-0000-0000-000000000002",
            initial_state={},
            user_id="00000000-0000-0000-0000-000000000003",
        )
    assert "extracted_data" in str(ei.value)
    assert run_repo.create_called is False  # guard runs before create


@pytest.mark.asyncio
async def test_start_run_valid_graph_passes_guard(monkeypatch):
    # A valid single parse node passes the guard (it has no upstream inputs);
    # stop before real execution by asserting create() is reached.
    valid = {"nodes": [{"id": "p", "tool": "parse.llamaparse"}], "edges": []}

    reached = {"create": False}

    class _RunRepo:
        async def create(self, **kw):
            reached["create"] = True
            raise RuntimeError("stop-after-guard")

    class _DefRepo:
        async def get_by_id(self, _id):
            class D: definition = valid
            return D()

    svc = AgentRunService(agent_run_repo=_RunRepo(), agent_def_repo=_DefRepo(),
                          checkpointer=None)
    with pytest.raises(RuntimeError, match="stop-after-guard"):
        await svc.start_run(
            project_id="00000000-0000-0000-0000-000000000001",
            agent_definition_id="00000000-0000-0000-0000-000000000002",
            initial_state={}, user_id="00000000-0000-0000-0000-000000000003")
    assert reached["create"] is True  # guard let a valid graph through


@pytest.mark.asyncio
async def test_start_run_rejects_unknown_tool_slug_before_creating_run():
    # validate_graph skips nodes whose tool isn't registered (get_tool returns
    # None), so this graph passes that guard — but build_agent_graph must
    # still reject it, and it must do so before the run row is created.
    unknown_tool = {"nodes": [{"id": "n1", "tool": "does.not.exist"}], "edges": []}

    class _RunRepo:
        async def create(self, **kw):
            raise AssertionError("run must not be created for an unknown-tool graph")

    class _DefRepo:
        async def get_by_id(self, _id):
            class D: definition = unknown_tool
            return D()

    svc = AgentRunService(agent_run_repo=_RunRepo(), agent_def_repo=_DefRepo(),
                          checkpointer=None)
    with pytest.raises(ValueError, match="Unknown tool"):
        await svc.start_run(
            project_id="00000000-0000-0000-0000-000000000001",
            agent_definition_id="00000000-0000-0000-0000-000000000002",
            initial_state={}, user_id="00000000-0000-0000-0000-000000000003")
