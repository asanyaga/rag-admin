# Parse Tool in the Agents Feature — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a composable `parse` tool to the agents feature (a graph node + standalone entrypoint) and retire the standalone `parse-agent` learning stack in the same change.

**Architecture:** A new `parse` `ToolDefinition` whose `node_fn` opens its own DB session, resolves the `SourceDocument`, builds a `ParsingService` with user-scoped BYOK keys, runs `parse_and_persist`, and returns **full merged state**. A thin `ParseRunService` entrypoint (mirroring `ExtractRunService`) seeds `initial_state` from a `source_document_id` and pre-validates the parser key so a missing key returns a clean 400. The `parse-agent` parallel stack (own graph, tables, router, trace UI) is deleted; a merge migration drops its tables.

**Tech Stack:** Python 3.12, FastAPI (async), SQLAlchemy 2.0 async, LangGraph, Alembic; React 18 + TypeScript + Vite + shadcn/ui.

**Spec:** `docs/superpowers/specs/2026-08-26-parse-tool-design.md`
**Issue:** https://github.com/asanyaga/rag-admin/issues/186

## Global Constraints

- All new backend code is `async` with type hints; data flow is router → service → repository (services raise, routers catch).
- **State convention:** the agents engine uses `AgentState = dict`; every node returns the **entire merged state** (`return {**state, ...}`). Partial-delta returns silently drop accumulated keys — never use them here.
- **Secrets:** parser API keys are resolved inside the node from `state["user_id"]`; they are **never** placed in `initial_state` or any persisted run state.
- Repositories commit internally (e.g. `ParseRunRepository.create` calls `session.commit()`), so a node opening its own `AsyncSessionLocal()` persists correctly — mirror `export_node`.
- Backend tests run on the in-memory SQLite `test_db` fixture. Run tests with: `cd backend && uv run python -m pytest -o "addopts=" <path>`.
- Frontend must pass `cd frontend && npm run build` and `npx vitest run` with no dangling imports/routes.
- Commit after every task. Branch: `feat/agent-parse-tool` (create before Task 1; never commit to `main`).

---

## Part A — The parse tool

### Task 1: Parsing bridge (`ParsingService` construction + parse execution)

Encapsulates all parse-subsystem wiring behind functions the node calls and tests can substitute. Keeps `nodes.py` clean and gives a monkeypatch seam. No router imports (avoids router→service inversion): uses the service-layer `resolve_api_key` primitive directly.

**Files:**
- Create: `backend/app/services/agent/parsing_bridge.py`
- Test: `backend/tests/services/agent/test_parsing_bridge.py`
- Create: `backend/tests/services/agent/__init__.py` (empty, if missing)

**Interfaces:**
- Produces:
  - `PARSER_PROVIDER: dict[str, str]` — `{"llamaparse": "llama_cloud", "landing_ai": "landing_ai"}`
  - `parser_provider(parser_type: str) -> str | None`
  - `async def resolve_source_cdm(session, source_document_id: UUID) -> tuple[SourceDocumentCDM, str]` — returns `(source_cdm, file_path)`; raises `NotFoundError` if the source document is missing.
  - `async def build_parsing_service(session, user_id: UUID, parser_type: str) -> ParsingService`
  - `@dataclass ParseOutcome` with `parse_run_id: str`, `parsed_document_id: str | None`, `page_count: int`, `text_len: int`, `failed_page_count: int`, `block_count: int`; method `as_state() -> dict`.
  - `async def run_parse(session, service, source, *, file_path, representation_kind, config, project_id) -> ParseOutcome`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/services/agent/test_parsing_bridge.py
import pytest
from app.services.agent import parsing_bridge as pb


def test_parser_provider_maps_known_parsers():
    assert pb.parser_provider("llamaparse") == "llama_cloud"
    assert pb.parser_provider("landing_ai") == "landing_ai"
    assert pb.parser_provider("simple") is None
    assert pb.parser_provider("docling") is None


def test_parse_outcome_as_state_exposes_output_keys():
    outcome = pb.ParseOutcome(
        parse_run_id="r1", parsed_document_id="d1",
        page_count=3, text_len=42, failed_page_count=0, block_count=7,
    )
    assert outcome.as_state() == {
        "parse_run_id": "r1", "parsed_document_id": "d1",
        "page_count": 3, "text_len": 42,
        "failed_page_count": 0, "block_count": 7,
    }


@pytest.mark.asyncio
async def test_run_parse_shapes_outcome_from_service(monkeypatch):
    class FakeRun:
        id = "run-123"
        failed_pages = ["p2"]

    class FakeDoc:
        page_count = 4
        full_text = "hello world"
        blocks = [1, 2, 3]

    class FakeService:
        async def parse_and_persist(self, **kwargs):
            return FakeRun(), FakeDoc()

    class FakeParsedDocRow:
        id = "pdoc-9"

    async def fake_get_by_run(self, run_id):
        return FakeParsedDocRow()

    monkeypatch.setattr(
        "app.repositories.parsed_document_repository.ParsedDocumentRepository.get_by_run",
        fake_get_by_run,
    )

    outcome = await pb.run_parse(
        session=object(), service=FakeService(), source=object(),
        file_path="/tmp/x.pdf", representation_kind="extract_rich",
        config={"parser": "simple"}, project_id="proj-1",
    )
    assert outcome.parse_run_id == "run-123"
    assert outcome.parsed_document_id == "pdoc-9"
    assert outcome.page_count == 4
    assert outcome.text_len == len("hello world")
    assert outcome.failed_page_count == 1
    assert outcome.block_count == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/agent/test_parsing_bridge.py -v`
Expected: FAIL — `ModuleNotFoundError: app.services.agent.parsing_bridge`.

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/services/agent/parsing_bridge.py
"""Bridge between the agents engine and the parsing subsystem.

Isolates all parse-subsystem wiring (BYOK key resolution, ParsingService
construction, parse execution + result shaping) so agent nodes stay thin and
tests can substitute these functions.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.cdm.models import ParserKind
from app.cdm.source import SourceDocument as SourceDocumentCDM
from app.services.exceptions import NotFoundError

PARSER_PROVIDER: dict[str, str] = {
    "llamaparse": "llama_cloud",
    "landing_ai": "landing_ai",
}


def parser_provider(parser_type: str) -> str | None:
    """Return the provider-key name for a parser, or None if it needs no key."""
    return PARSER_PROVIDER.get(parser_type)


async def resolve_source_cdm(session, source_document_id: UUID) -> tuple[SourceDocumentCDM, str]:
    """Load a SourceDocument ORM row and project it to a CDM + its storage path."""
    from app.repositories.source_document_repository import SourceDocumentRepository

    orm = await SourceDocumentRepository(session).get(source_document_id)
    if orm is None:
        raise NotFoundError(f"Source document {source_document_id} not found")
    cdm = SourceDocumentCDM(
        id=str(orm.id), sha256=orm.sha256, filename=orm.filename,
        mime_type=orm.mime_type, byte_size=orm.byte_size,
        storage_uri=orm.storage_uri, created_at=orm.created_at,
    )
    return cdm, orm.storage_uri


async def build_parsing_service(session, user_id: UUID, parser_type: str):
    """Construct a ParsingService with the client needed for `parser_type`.

    Resolves the parser's BYOK key from the user's provider keys (env fallback
    inside resolve_api_key). The key is used to build the client and is never
    returned or stored.
    """
    from app.dependencies.documents import get_document_extractor, get_storage_service
    from app.repositories.parse_run_repository import ParseRunRepository
    from app.repositories.parsed_document_repository import ParsedDocumentRepository
    from app.repositories.provider_key_repository import ProviderKeyRepository
    from app.repositories.source_document_repository import SourceDocumentRepository
    from app.services.parsing.parsing_service import ParsingService
    from app.services.provider_key_service import resolve_api_key

    clients: dict[ParserKind, Any] = {ParserKind.SIMPLE: get_document_extractor()}

    provider = parser_provider(parser_type)
    key = None
    if provider:
        key = await resolve_api_key(ProviderKeyRepository(session), user_id, provider)

    if parser_type == "llamaparse" and key:
        from llama_cloud import AsyncLlamaCloud
        clients[ParserKind.LLAMAPARSE] = AsyncLlamaCloud(api_key=key)
    elif parser_type == "landing_ai" and key:
        from landingai_ade import LandingAIADE
        clients[ParserKind.LANDING_AI] = LandingAIADE(apikey=key)

    return ParsingService(
        source_doc_repo=SourceDocumentRepository(session),
        parse_run_repo=ParseRunRepository(session),
        parsed_doc_repo=ParsedDocumentRepository(session),
        storage=get_storage_service(),
        clients=clients,
    )


@dataclass
class ParseOutcome:
    parse_run_id: str
    parsed_document_id: str | None
    page_count: int
    text_len: int
    failed_page_count: int
    block_count: int

    def as_state(self) -> dict:
        return {
            "parse_run_id": self.parse_run_id,
            "parsed_document_id": self.parsed_document_id,
            "page_count": self.page_count,
            "text_len": self.text_len,
            "failed_page_count": self.failed_page_count,
            "block_count": self.block_count,
        }


async def run_parse(
    session, service, source, *,
    file_path: str, representation_kind: str, config: dict, project_id,
) -> ParseOutcome:
    """Run parse_and_persist and shape the result into a ParseOutcome."""
    from app.repositories.parsed_document_repository import ParsedDocumentRepository

    run, doc = await service.parse_and_persist(
        source=source, file_path=file_path,
        representation_kind=representation_kind, config=config,
        project_id=UUID(str(project_id)),
    )
    if doc is None:
        raise RuntimeError(f"parse produced no document for parse_run {run.id}")

    parsed_row = await ParsedDocumentRepository(session).get_by_run(run.id)
    full_text = getattr(doc, "full_text", "") or ""
    return ParseOutcome(
        parse_run_id=str(run.id),
        parsed_document_id=str(parsed_row.id) if parsed_row else None,
        page_count=doc.page_count,
        text_len=len(full_text),
        failed_page_count=len(run.failed_pages),
        block_count=len(doc.blocks),
    )
```

> **Verified signatures** (`app/dependencies/documents.py`): `get_storage_service()` and `get_document_extractor()` take **no** arguments. Note a `get_parsing_service(db)` helper already exists but wires **global/env** parser clients (`get_llamaparse_client()` / `get_landingai_client()`) — we deliberately do **not** reuse it here, because the parse tool must use **user-scoped BYOK** keys (per the spec), which is why `build_parsing_service` resolves the key and constructs the client itself.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/agent/test_parsing_bridge.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/agent/parsing_bridge.py backend/tests/services/agent/
git commit -m "feat(agent): add parsing bridge for the parse tool"
```

---

### Task 2: `parse_node` and the full-state-merge seam

**Files:**
- Modify: `backend/app/services/agent/nodes.py` (add `parse_node`)
- Test: `backend/tests/services/agent/test_parse_node.py`

**Interfaces:**
- Consumes: `parsing_bridge.resolve_source_cdm`, `build_parsing_service`, `run_parse` (Task 1).
- Produces: `async def parse_node(state: dict) -> dict` — reads `state["source_document_id"]`, `state["user_id"]`, `state["project_id"]`, `state["representation_kind"]`, `state["parse_config"]` (a dict containing `"parser"`); returns `{**state, **ParseOutcome.as_state(), "current_step": ...}`.

- [ ] **Step 1: Write the failing test** — drives the REAL dispatch path (`build_agent_graph`) to prove full-state merge, not a node called in isolation.

```python
# backend/tests/services/agent/test_parse_node.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/agent/test_parse_node.py -v`
Expected: FAIL — the `parse` tool isn't registered yet / `parse_node` undefined. (This test also depends on Task 3; if running strictly in order, expect the assertion "register the parse tool (Task 3) first" to fail. Implement Step 3 here, then Task 3, then re-run — or run Tasks 2+3 together and commit at the end of Task 3.)

- [ ] **Step 3: Write minimal implementation** — append to `backend/app/services/agent/nodes.py`:

```python
async def parse_node(state: dict) -> dict:
    """Parse a source document into a ParsedDocument, then merge results into state.

    Opens its own session (like export_node) because the agents engine runs the
    graph inline within the request. Resolves BYOK keys from state["user_id"];
    keys are never read from or written to state.
    """
    from uuid import UUID

    from app.database import AsyncSessionLocal
    from app.services.agent import parsing_bridge as pb

    logger.info("parse_node: parsing source_document %s", state.get("source_document_id"))

    parse_config = dict(state.get("parse_config") or {})
    parser_type = parse_config.get("parser", "simple")

    async with AsyncSessionLocal() as session:
        source, file_path = await pb.resolve_source_cdm(
            session, UUID(str(state["source_document_id"]))
        )
        service = await pb.build_parsing_service(
            session, UUID(str(state["user_id"])), parser_type
        )
        outcome = await pb.run_parse(
            session, service, source,
            file_path=file_path,
            representation_kind=state["representation_kind"],
            config=parse_config,
            project_id=state["project_id"],
        )

    return {**state, **outcome.as_state(), "current_step": "parsed"}
```

- [ ] **Step 4: Run test to verify it passes** (after Task 3 registration exists)

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/agent/test_parse_node.py -v`
Expected: PASS.

- [ ] **Step 5: Commit** (bundle with Task 3 if implemented together)

```bash
git add backend/app/services/agent/nodes.py backend/tests/services/agent/test_parse_node.py
git commit -m "feat(agent): add parse_node with full-state merge"
```

---

### Task 3: Register the `parse` tool

**Files:**
- Create: `backend/app/services/agent/tools/parse.py`
- Modify: `backend/app/services/agent/tools/__init__.py` (add import in `_ensure_loaded`)
- Test: `backend/tests/services/agent/test_parse_tool_registration.py`

**Interfaces:**
- Consumes: `parse_node` (Task 2), `ToolDefinition`, `register_tool`.
- Produces: a registered tool with `slug="parse"`, `category="parsing"`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/services/agent/test_parse_tool_registration.py
from app.services.agent.tools import get_tool, list_tools


def test_parse_tool_is_registered_under_parsing_category():
    tool = get_tool("parse")
    assert tool is not None
    assert tool.category == "parsing"
    assert "source_document_id" in tool.input_keys
    assert "parse_run_id" in tool.output_keys
    assert "parsed_document_id" in tool.output_keys


def test_parse_tool_listed():
    slugs = {t.slug for t in list_tools()}
    assert "parse" in slugs
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/agent/test_parse_tool_registration.py -v`
Expected: FAIL — `get_tool("parse")` returns `None`.

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/services/agent/tools/parse.py
"""Parse tool — parse a source document into a ParsedDocument."""
from app.services.agent.nodes import parse_node
from app.services.agent.tools import ToolDefinition, register_tool

register_tool(ToolDefinition(
    slug="parse",
    name="Parse",
    category="parsing",
    description="Parse a source document into a ParsedDocument",
    input_keys=["source_document_id", "representation_kind", "parse_config",
                "project_id", "user_id"],
    output_keys=["parse_run_id", "parsed_document_id", "page_count",
                 "text_len", "failed_page_count", "block_count"],
    config_schema={
        "type": "object",
        "properties": {
            "parser": {
                "type": "string",
                "enum": ["simple", "llamaparse", "landing_ai", "docling"],
                "default": "simple",
                "description": "Parser engine to use",
            },
            "representation_kind": {
                "type": "string",
                "default": "extract_rich",
                "description": "Representation the parser should produce",
            },
        },
    },
    node_fn=parse_node,
))
```

Then add to `backend/app/services/agent/tools/__init__.py` inside `_ensure_loaded()`:

```python
    from app.services.agent.tools import parse  # noqa: F401
```

- [ ] **Step 4: Run tests to verify they pass** (Task 2 + Task 3 now green)

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/agent/ -v`
Expected: PASS (all agent bridge/node/tool tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/agent/tools/parse.py backend/app/services/agent/tools/__init__.py backend/tests/services/agent/test_parse_tool_registration.py
git commit -m "feat(agent): register parse tool under parsing category"
```

---

### Task 4: `ParseRunService` entrypoint (with BYOK pre-validation)

**Files:**
- Create: `backend/app/services/agent/parse_run_service.py`
- Test: `backend/tests/services/agent/test_parse_run_service.py`

**Interfaces:**
- Consumes: `AgentRunService.start_run` (existing), `SourceDocumentRepository`, `ProviderKeyRepository`, `resolve_api_key`, `parsing_bridge.parser_provider`.
- Produces: `ParseRunService(agent_run_service, source_doc_repo, provider_key_repo)` with
  `async def start_parse_run(project_id, agent_definition_id, source_document_id, parser, representation_kind, parse_config, user_id) -> AgentRunResponse`.
  Raises `NotFoundError` (missing source doc) and `ValueError` (missing required parser key) — the router maps these to 404 / 400.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/services/agent/test_parse_run_service.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/agent/test_parse_run_service.py -v`
Expected: FAIL — module/class missing.

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/services/agent/parse_run_service.py
"""Parse run service — resolves a source document into a generic agent run."""
import logging
from uuid import UUID

from app.schemas.agent import AgentRunResponse
from app.services.agent.agent_run_service import AgentRunService
from app.services.agent.parsing_bridge import parser_provider
from app.services.exceptions import NotFoundError
from app.services.provider_key_service import resolve_api_key

logger = logging.getLogger(__name__)


class ParseRunService:
    """Thin service that resolves parse inputs into a generic initial state."""

    def __init__(self, agent_run_service: AgentRunService, source_doc_repo, provider_key_repo):
        self.agent_run_service = agent_run_service
        self.source_doc_repo = source_doc_repo
        self.provider_key_repo = provider_key_repo

    async def start_parse_run(
        self, *, project_id: UUID, agent_definition_id: UUID,
        source_document_id: UUID, parser: str, representation_kind: str,
        parse_config: dict, user_id: UUID,
    ) -> AgentRunResponse:
        source = await self.source_doc_repo.get(source_document_id)
        if source is None:
            raise NotFoundError(f"Source document {source_document_id} not found")

        # Pre-validate BYOK key presence so a missing key is a clean 400, not a
        # failed run. The key is discarded here; the node re-resolves for real.
        provider = parser_provider(parser)
        if provider:
            key = await resolve_api_key(self.provider_key_repo, user_id, provider)
            if not key:
                raise ValueError(
                    f"No API key configured for parser '{parser}'. "
                    "Add one in Settings → API Keys."
                )

        config = dict(parse_config or {})
        config["parser"] = parser
        initial_state = {
            "source_document_id": str(source_document_id),
            "project_id": str(project_id),
            "user_id": str(user_id),
            "representation_kind": representation_kind,
            "parse_config": config,
            "current_step": "parse",
        }
        return await self.agent_run_service.start_run(
            project_id=project_id,
            agent_definition_id=agent_definition_id,
            initial_state=initial_state,
            user_id=user_id,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/agent/test_parse_run_service.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/agent/parse_run_service.py backend/tests/services/agent/test_parse_run_service.py
git commit -m "feat(agent): add ParseRunService entrypoint with BYOK pre-validation"
```

---

### Task 5: Schema + router endpoint

**Files:**
- Modify: `backend/app/schemas/agent.py` (add `StartParseRunRequest` after `StartExtractRunRequest`)
- Modify: `backend/app/routers/agent.py` (add `get_parse_run_service` dependency + `POST /agent/parse/projects/{project_id}/runs`)
- Test: `backend/tests/routers/test_agent_parse_router.py`

**Interfaces:**
- Consumes: `ParseRunService` (Task 4).
- Produces: `POST /agent/parse/projects/{project_id}/runs` returning `AgentRunResponse` (202); `ValueError → 400`, `NotFoundError → 404`.

- [ ] **Step 1: Add the schema** — in `backend/app/schemas/agent.py`:

```python
class StartParseRunRequest(BaseModel):
    """Request to start a parse agent run."""
    agent_definition_id: UUID = Field(..., alias="agentDefinitionId")
    source_document_id: UUID = Field(..., alias="sourceDocumentId")
    parser: str = Field("simple")
    representation_kind: str = Field("extract_rich", alias="representationKind")
    parse_config: dict[str, Any] = Field(default_factory=dict, alias="parseConfig")

    model_config = ConfigDict(populate_by_name=True)
```

- [ ] **Step 2: Write the failing router test**

```python
# backend/tests/routers/test_agent_parse_router.py
# Mirror an existing router test's client/auth fixtures (see other tests in
# backend/tests/routers/). Override get_parse_run_service with a stub that returns
# a canned AgentRunResponse for success and raises ValueError for the 400 case.
import pytest


@pytest.mark.asyncio
async def test_start_parse_run_returns_202(client_with_stubbed_parse_service):
    resp = await client_with_stubbed_parse_service.post(
        "/api/v1/agent/parse/projects/33333333-3333-3333-3333-333333333333/runs",
        json={
            "agentDefinitionId": "44444444-4444-4444-4444-444444444444",
            "sourceDocumentId": "55555555-5555-5555-5555-555555555555",
            "parser": "simple",
        },
    )
    assert resp.status_code == 202


@pytest.mark.asyncio
async def test_start_parse_run_missing_key_returns_400(client_with_missing_key_parse_service):
    resp = await client_with_missing_key_parse_service.post(
        "/api/v1/agent/parse/projects/33333333-3333-3333-3333-333333333333/runs",
        json={
            "agentDefinitionId": "44444444-4444-4444-4444-444444444444",
            "sourceDocumentId": "55555555-5555-5555-5555-555555555555",
            "parser": "llamaparse",
        },
    )
    assert resp.status_code == 400
```

> Implement the two fixtures by copying the auth/client + `app.dependency_overrides` pattern from an existing router test in `backend/tests/routers/` (e.g. an agent or extraction test). Override `get_parse_run_service` to return a stub whose `start_parse_run` returns a valid `AgentRunResponse` (success) or raises `ValueError` (missing key). If the existing router-test harness is heavy, per the project's testing-pragmatism note it is acceptable to assert the service-level behaviour (Task 4) and cover the router with a lighter smoke test — but attempt the real HTTP test first.

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/routers/test_agent_parse_router.py -v`
Expected: FAIL — route 404 (not registered).

- [ ] **Step 4: Add the dependency + endpoint** — in `backend/app/routers/agent.py`:

```python
def get_parse_run_service(
    db: AsyncSession = Depends(get_db),
) -> "ParseRunService":
    from app.main import app
    from app.repositories.provider_key_repository import ProviderKeyRepository
    from app.repositories.source_document_repository import SourceDocumentRepository
    from app.services.agent.parse_run_service import ParseRunService

    checkpointer = app.state.agent_checkpointer
    return ParseRunService(
        agent_run_service=AgentRunService(
            agent_run_repo=AgentRunRepository(db),
            agent_def_repo=AgentDefinitionRepository(db),
            checkpointer=checkpointer,
        ),
        source_doc_repo=SourceDocumentRepository(db),
        provider_key_repo=ProviderKeyRepository(db),
    )


@router.post(
    "/agent/parse/projects/{project_id}/runs",
    response_model=AgentRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start a parse agent run",
)
async def start_parse_run(
    project_id: UUID,
    body: StartParseRunRequest,
    current_user: User = Depends(get_current_active_user),
    service: "ParseRunService" = Depends(get_parse_run_service),
):
    try:
        return await service.start_parse_run(
            project_id=project_id,
            agent_definition_id=body.agent_definition_id,
            source_document_id=body.source_document_id,
            parser=body.parser,
            representation_kind=body.representation_kind,
            parse_config=body.parse_config,
            user_id=current_user.id,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
```

Add `StartParseRunRequest` to the `from app.schemas.agent import (...)` block at the top of the router.

- [ ] **Step 5: Run test + full agent suite; commit**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/routers/test_agent_parse_router.py tests/services/agent/ -v`
Expected: PASS.

```bash
git add backend/app/schemas/agent.py backend/app/routers/agent.py backend/tests/routers/test_agent_parse_router.py
git commit -m "feat(agent): add POST /agent/parse/.../runs endpoint"
```

---

### Task 6: Frontend types + API client

**Files:**
- Modify: `frontend/src/types/agent.ts` (add `StartParseRunRequest`)
- Modify: `frontend/src/api/agent.ts` (add `startParseRun`)

**Interfaces:**
- Produces: `startParseRun(projectId, data: StartParseRunRequest): Promise<AgentRun>` → `POST /agent/parse/projects/{projectId}/runs`.

- [ ] **Step 1: Add the type** — in `frontend/src/types/agent.ts` after `StartExtractRunRequest`:

```typescript
export interface StartParseRunRequest {
  agentDefinitionId: string
  sourceDocumentId: string
  parser?: string
  representationKind?: string
  parseConfig?: Record<string, unknown>
}
```

- [ ] **Step 2: Add the API function** — in `frontend/src/api/agent.ts` (import the new type, add after `startExtractRun`):

```typescript
export async function startParseRun(
  projectId: string,
  data: StartParseRunRequest
): Promise<AgentRun> {
  const response = await apiClient.post<AgentRun>(
    `/agent/parse/projects/${projectId}/runs`,
    data
  )
  return response.data
}
```

- [ ] **Step 3: Typecheck**

Run: `cd frontend && npm run build`
Expected: builds with no type errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/agent.ts frontend/src/api/agent.ts
git commit -m "feat(agent): frontend types + api for startParseRun"
```

---

### Task 7: Palette `parsing` category

**Files:**
- Modify: `frontend/src/components/agent/composer/ToolPalette.tsx`

- [ ] **Step 1: Add icon + color** — extend the two maps (import a `FileText` icon from lucide-react):

```typescript
const categoryIcons: Record<string, LucideIcon> = {
  extraction: FileSearch,
  parsing: FileText,
  control: UserCheck,
  export: Upload,
  indexing: Database,
  trigger: Zap,
}

const categoryColors: Record<string, string> = {
  extraction: 'border-blue-300 bg-blue-50 text-blue-700',
  parsing: 'border-cyan-300 bg-cyan-50 text-cyan-700',
  control: 'border-amber-300 bg-amber-50 text-amber-700',
  export: 'border-emerald-300 bg-emerald-50 text-emerald-700',
  indexing: 'border-purple-300 bg-purple-50 text-purple-700',
  trigger: 'border-orange-300 bg-orange-50 text-orange-700',
}
```

- [ ] **Step 2: Verify** — `cd frontend && npm run build`; expected: passes. The parse tool now renders under a "parsing" group (data comes from `GET /agent/tools`).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/agent/composer/ToolPalette.tsx
git commit -m "feat(agent): add parsing tool category to palette"
```

---

### Task 8: Parse run input form (standalone entrypoint UI)

Wires a form that starts a parse run from a source-document picker. Mirror the extract run trigger UI. Reuse the existing `useSourceDocuments` hook + `sourceDocuments` API.

**Files:**
- Create: `frontend/src/components/agent/ParseRunInputForm.tsx`
- Modify: wherever agent runs are launched (find the extract trigger; likely `frontend/src/pages/AgentRunsPage.tsx` or `AgentComposerPage.tsx`) to mount the new form for parse-first agents.
- Test: `frontend/src/components/agent/ParseRunInputForm.test.tsx`

**Interfaces:**
- Consumes: `startParseRun` (Task 6), `useSourceDocuments`, `AgentDefinition`.
- Produces: `<ParseRunInputForm projectId agentDefinitionId onStarted={(run) => ...} />`.

- [ ] **Step 1: Locate the extract trigger** — inspect how an extract run is started from the UI (grep `startExtractRun` in `frontend/src`), and reuse its layout/patterns (dialog vs inline, react-query mutation, toast on error).

- [ ] **Step 2: Write the failing component test**

```tsx
// frontend/src/components/agent/ParseRunInputForm.test.tsx
import { render, screen } from '@testing-library/react'
import { ParseRunInputForm } from './ParseRunInputForm'
// Mirror the query-client + mocking setup from an existing *.test.tsx in this dir.

it('renders a source document picker and parser select', () => {
  // wrap with the app's test providers (QueryClientProvider etc.)
  render(<ParseRunInputForm projectId="p1" agentDefinitionId="a1" onStarted={() => {}} />)
  expect(screen.getByText(/source document/i)).toBeInTheDocument()
  expect(screen.getByText(/parser/i)).toBeInTheDocument()
})
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/agent/ParseRunInputForm.test.tsx`
Expected: FAIL — component missing.

- [ ] **Step 4: Implement the form** — a source-document `<Select>` (options from `useSourceDocuments(projectId)`), a parser `<Select>` (`simple` / `llamaparse` / `landing_ai` / `docling`), an optional representation-kind field (default `extract_rich`), and a submit that calls `startParseRun(projectId, { agentDefinitionId, sourceDocumentId, parser, representationKind })` via a react-query mutation, calling `onStarted` with the returned run and surfacing a toast on error (the 400 "No API key configured…" message). Follow shadcn/ui + the existing form patterns in `frontend/src/components/agent/`.

- [ ] **Step 5: Mount it** in the agent run launch surface for definitions whose first node is `parse` (detect via the definition's `nodes[0].tool === 'parse'`, mirroring how the extract form is chosen).

- [ ] **Step 6: Run test + build**

Run: `cd frontend && npx vitest run src/components/agent/ParseRunInputForm.test.tsx && npm run build`
Expected: PASS + clean build.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/agent/ParseRunInputForm.tsx frontend/src/components/agent/ParseRunInputForm.test.tsx frontend/src/pages/
git commit -m "feat(agent): add parse run input form and mount it"
```

---

## Part B — Retire the parse-agent stack

> Do Part B only after Part A is green. The stack is self-contained (its router is the only trigger for `run_parse_agent`), so removal is mechanical. Verify by build/tests, not TDD.

### Task 9: Remove backend parse-agent code

**Files:**
- Delete: `backend/app/services/parse_agent/` (whole dir), `backend/app/routers/parse_agent_runs.py`, `backend/app/repositories/parse_agent_run_repository.py`, `backend/app/models/parse_agent_run.py`, `backend/app/schemas/parse_agent_run.py`, `backend/tests/services/parse_agent/`, `backend/tests/models/test_parse_agent_run_model.py`, `backend/tests/repositories/test_parse_agent_run_repository.py`, `backend/tests/routers/test_parse_agent_runs_router.py`.
- Modify: `backend/app/main.py` — remove `parse_agent_runs` from the `from app.routers import ...` line (7) and the `app.include_router(parse_agent_runs.router, ...)` line (178).
- Modify: `backend/app/models/__init__.py` — remove the `ParseAgentRun, ParseAgentRunStep, ParseAgentRunStatus` import and their `__all__` entries.

- [ ] **Step 1: Delete files + edit `main.py` / `models/__init__.py`** as listed.

- [ ] **Step 2: Grep for stragglers**

Run: `cd backend && grep -rn "parse_agent\|ParseAgentRun\|run_parse_agent" app/ | grep -v "services/agent"`
Expected: no output (everything under the new `services/agent` parse tool is unrelated).

- [ ] **Step 3: Import + boot check**

Run: `cd backend && uv run python -c "import app.main"`
Expected: imports cleanly (no reference to deleted modules).

- [ ] **Step 4: Backend test suite**

Run: `cd backend && uv run python -m pytest -o "addopts=" -q`
Expected: PASS, no collection errors from deleted test dirs.

- [ ] **Step 5: Commit**

```bash
git add -A backend/
git commit -m "chore(parse-agent): remove backend parse-agent stack"
```

---

### Task 10: Migration to drop parse-agent tables (merge current heads)

The repo currently reports **multiple Alembic heads**; the entrypoint runs `alembic upgrade head` (singular), which requires a single head. Author this as a **merge migration** across all current heads that also drops the parse-agent tables — resolving multi-head as a side benefit.

**Files:**
- Create: `backend/alembic/versions/<generated>_drop_parse_agent_tables.py`

- [ ] **Step 1: Get the real current heads** (they drift as other branches merge — do not hardcode from this plan)

Run: `cd backend && alembic heads`
Record every head revision id printed.

- [ ] **Step 2: Create the migration** — set `down_revision` to a tuple of ALL current head ids, and drop the two tables in `upgrade()`:

```python
"""drop parse_agent tables (merge heads)

Revision ID: <generated>
Revises: <head1>, <head2>, <head3>
"""
from alembic import op

revision = "<generated>"
down_revision = ("<head1>", "<head2>", "<head3>")  # ALL current heads from `alembic heads`
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("parse_agent_run_steps")
    op.drop_table("parse_agent_run")


def downgrade() -> None:
    # Recreation is intentionally not supported — the parse-agent stack is retired.
    raise NotImplementedError("parse_agent tables are retired; no downgrade")
```

> Confirm the exact table names and drop order against `backend/alembic/versions/12035df46d0d_create_parse_agent_run_tables.py` (drop the child/steps table before the parent; account for FK constraints). If `alembic heads` shows a single head, use it as a scalar `down_revision` instead of a tuple.

- [ ] **Step 3: Verify single head + upgrade applies**

Run: `cd backend && alembic heads` → expect exactly one head (the new revision).
Run (against a scratch/dev DB): `cd backend && alembic upgrade head`
Expected: applies cleanly; `parse_agent_run` / `parse_agent_run_steps` are gone.

- [ ] **Step 4: Commit**

```bash
git add backend/alembic/versions/
git commit -m "chore(parse-agent): drop parse_agent tables and merge alembic heads"
```

---

### Task 11: Remove frontend parse-agent code

**Files:**
- Delete: `frontend/src/pages/ParseAgentRunsPage.tsx`, `frontend/src/pages/ParseAgentRunDetailPage.tsx`, `frontend/src/components/parse-agent/` (whole dir), `frontend/src/hooks/useParseAgentRun.ts`, `frontend/src/hooks/useParseAgentRun.test.ts`, `frontend/src/hooks/useParseAgentRuns.ts`, `frontend/src/hooks/useParseAgentRuns.test.ts`, `frontend/src/api/parseAgent.ts`, `frontend/src/types/parseAgent.ts`.
- Modify: `frontend/src/App.tsx` — remove the two `ParseAgentRuns*` imports (lines ~45-46) and the two `parse-agent` route entries (lines ~103-109). Remove any nav-menu link to `parse-agent` (grep for it).

- [ ] **Step 1: Delete files + edit `App.tsx`** + remove nav link.

- [ ] **Step 2: Grep for stragglers**

Run: `cd frontend && grep -rn "parse-agent\|ParseAgent\|parseAgent" src/`
Expected: no output.

- [ ] **Step 3: Build + tests**

Run: `cd frontend && npm run build && npx vitest run`
Expected: clean build, no missing-import errors, tests pass.

- [ ] **Step 4: Commit**

```bash
git add -A frontend/
git commit -m "chore(parse-agent): remove frontend parse-agent pages/components"
```

---

### Task 12: Mark parse-agent docs superseded

**Files:**
- Modify: `docs/superpowers/specs/2026-07-15-parse-agent-design.md`, `docs/superpowers/plans/2026-07-15-parse-agent-backend.md`, `docs/superpowers/plans/2026-07-17-parse-agent-frontend-trace-ui.md`

- [ ] **Step 1: Add a superseded banner** at the top of each of the three files:

```markdown
> **⚠️ Superseded (2026-08-26):** The parse-agent stack has been retired. Parsing
> is now a tool in the agents feature — see
> `docs/superpowers/specs/2026-08-26-parse-tool-design.md`. This document is kept
> for historical context only.
```

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/
git commit -m "docs(parse-agent): mark retired parse-agent docs as superseded"
```

---

## Final verification (before PR)

- [ ] `cd backend && uv run python -m pytest -o "addopts=" -q` — all pass.
- [ ] `cd backend && uv run python -c "import app.main"` — clean import.
- [ ] `cd backend && alembic heads` — exactly one head.
- [ ] `cd frontend && npm run build && npx vitest run && npm run lint` — all pass.
- [ ] Manual smoke: create an agent with a single `parse` node, start a run via `POST /agent/parse/projects/{id}/runs` with a real `source_document_id`, confirm the run completes and `parse_run_id` + `parsed_document_id` appear in the run state; try a `llamaparse` run with no key configured and confirm a 400.
- [ ] Open PR linked to issue #186; wait for user to merge before cleanup.

## Self-review notes

- **Spec coverage:** parse tool (Tasks 2-3), entrypoint + BYOK pre-validation (Tasks 4-5), palette category (Task 7), input form (Task 8), full parse-agent removal + table drop (Tasks 9-11), docs superseded (Task 12). All acceptance criteria mapped.
- **Full-state-merge gotcha:** enforced and *tested through the real dispatch path* in Task 2 (the `sentinel` assertion).
- **Secrets:** never in state — asserted in Task 4; node re-resolves from `user_id` in Task 2.
- **Known gap (per-node config plumbing):** deliberately sidestepped — parse params flow through the entrypoint's `initial_state`, not `node_config`.
```
