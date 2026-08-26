import pytest
from uuid import uuid4
from app.services.agent.parse_run_service import ParseRunService
from app.services.exceptions import NotFoundError


class _StubSource:
    def __init__(self, sid): self.id = sid


@pytest.mark.asyncio
async def test_start_parse_run_missing_source_raises_notfound():
    class SrcRepo:
        async def get(self, sid): return None

    svc = ParseRunService(agent_run_service=None, source_doc_repo=SrcRepo(),
                          provider_key_repo=None)
    with pytest.raises(NotFoundError):
        await svc.start_parse_run(
            project_id=uuid4(), agent_definition_id=uuid4(),
            source_document_id=uuid4(), parser="simple",
            representation_kind="extract_rich", parse_config={}, user_id=uuid4(),
        )


@pytest.mark.asyncio
async def test_start_parse_run_missing_key_raises_valueerror(monkeypatch):
    sid = uuid4()

    class SrcRepo:
        async def get(self, s): return _StubSource(sid)

    async def no_key(repo, user_id, provider):
        return None

    monkeypatch.setattr(
        "app.services.agent.parse_run_service.resolve_api_key", no_key
    )
    svc = ParseRunService(agent_run_service=None, source_doc_repo=SrcRepo(),
                          provider_key_repo=object())
    with pytest.raises(ValueError):
        await svc.start_parse_run(
            project_id=uuid4(), agent_definition_id=uuid4(),
            source_document_id=sid, parser="llamaparse",
            representation_kind="extract_rich", parse_config={}, user_id=uuid4(),
        )


@pytest.mark.asyncio
async def test_start_parse_run_seeds_initial_state_and_delegates(monkeypatch):
    sid, uid, pid, aid = uuid4(), uuid4(), uuid4(), uuid4()
    captured = {}

    class SrcRepo:
        async def get(self, s): return _StubSource(sid)

    class AgentRunSvc:
        async def start_run(self, *, project_id, agent_definition_id, initial_state, user_id):
            captured["initial_state"] = initial_state
            captured["user_id"] = user_id
            return "RUN_RESPONSE"

    svc = ParseRunService(agent_run_service=AgentRunSvc(), source_doc_repo=SrcRepo(),
                          provider_key_repo=None)
    out = await svc.start_parse_run(
        project_id=pid, agent_definition_id=aid, source_document_id=sid,
        parser="simple", representation_kind="extract_rich",
        parse_config={}, user_id=uid,
    )
    assert out == "RUN_RESPONSE"
    st = captured["initial_state"]
    assert st["source_document_id"] == str(sid)
    assert st["user_id"] == str(uid)
    assert st["parse_config"]["parser"] == "simple"
    assert "api_key" not in str(st)  # no secrets leaked into state
