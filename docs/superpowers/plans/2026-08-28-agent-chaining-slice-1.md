# Agent Chaining — Slice 1 (Backend) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give agent tools a `source`-tagged input contract, validate a graph's pipeline dependencies (reachable-predecessor) with a backend run guard, and retrofit `extract_node` so an extract-rooted chain runs through the generic run path.

**Architecture:** Extends the merged three-way tool contract. `FieldSpec` gains a `source` field distinguishing form-eligible from upstream-only inputs. A `validate_graph` function computes each node's unmet `upstream` inputs from the definition + tool contracts; `AgentRunService.start_run` calls it and 400s before executing. `extract_node` absorbs the document/schema resolution currently done by `ExtractRunService`, via a new `extraction_bridge` (mirroring `parsing_bridge`), with a state fallback so the bespoke entrypoint still works.

**Tech Stack:** Python 3.12, FastAPI, LangGraph 1.1.x, SQLAlchemy 2.0 async, pytest (SQLite in-memory).

**Spec:** [docs/superpowers/specs/2026-08-28-agent-chaining-design.md](../specs/2026-08-28-agent-chaining-design.md)
**Issue:** https://github.com/asanyaga/rag-admin/issues/192

## Global Constraints

- Backend tests: `cd backend && uv run python -m pytest -o "addopts=" <path> -v`.
- `FieldSpec.source` is one of `"form"` | `"upstream"` | `"either"`, default `"form"` (Slice A back-compat).
- Node functions keep the `*, node_config` bound-config param (LangGraph reserves `config`); `parse_node`'s `parser_type` binding is untouched.
- The bespoke `/agent/parse` and `/agent/extract` entrypoints MUST keep working (state fallbacks).
- Frontend is Slice 2 — do not touch `frontend/` in this slice.

---

### Task 1: `source`-tagged inputs + API + retrofit tool contracts

**Files:**
- Modify: `backend/app/services/agent/tools/__init__.py` (`FieldSpec`)
- Modify: `backend/app/services/agent/tools/extract.py`, `review.py`, `export.py` (declare real inputs); `parse.py` (add explicit `source="form"` — optional, default already covers it)
- Modify: `backend/app/schemas/agent.py` (`AgentToolRuntimeInput`), `backend/app/routers/agent.py` (`list_agent_tools` mapping)
- Test: `backend/tests/services/agent/test_tool_input_sources.py` (create)

**Interfaces:**
- Produces: `FieldSpec(key, label, widget, source="form")`.
- Produces: contracts — `llamaextract.runtime_inputs=[document_id(form,document_picker), extraction_schema_id(form,extraction_schema_picker)]`; `human-review.runtime_inputs=[extracted_data(upstream)]`; `export.runtime_inputs=[extracted_data(upstream)]`.
- Produces: `AgentToolRuntimeInput` gains `source: str`; `/agent/tools` returns it.

- [ ] **Step 1: Write the failing test**

`test_tool_input_sources.py`:

```python
from app.services.agent.tools import get_tool


def _inputs(slug):
    return {f.key: f.source for f in get_tool(slug).runtime_inputs}


def test_extract_declares_form_inputs():
    assert _inputs("llamaextract") == {
        "document_id": "form", "extraction_schema_id": "form",
    }


def test_review_and_export_declare_upstream_extracted_data():
    assert _inputs("human-review") == {"extracted_data": "upstream"}
    assert _inputs("export") == {"extracted_data": "upstream"}


def test_parse_source_document_is_form():
    assert _inputs("parse.llamaparse") == {"source_document_id": "form"}
```

- [ ] **Step 2: Run — verify fail**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/agent/test_tool_input_sources.py -v`
Expected: FAIL — `FieldSpec` has no `source`; extract/review/export declare no inputs.

- [ ] **Step 3: Add `source` to `FieldSpec`**

In `tools/__init__.py`:

```python
@dataclass
class FieldSpec:
    """A runtime input a tool needs, how the run form renders it, and where it
    comes from: 'form' (run form or upstream), 'upstream' (only an upstream
    node's output), or 'either'."""
    key: str
    label: str
    widget: str
    source: str = "form"
```

- [ ] **Step 4: Declare the real inputs**

`extract.py` — `runtime_inputs`:

```python
    runtime_inputs=[
        FieldSpec(key="document_id", label="Document", widget="document_picker"),
        FieldSpec(key="extraction_schema_id", label="Extraction schema",
                  widget="extraction_schema_picker"),
    ],
```
(import `FieldSpec` alongside `ToolDefinition, register_tool`; keep `outputs=["extracted_data"]` and the existing `config_schema`.)

`review.py`:

```python
    runtime_inputs=[FieldSpec(key="extracted_data", label="Extracted data",
                              widget="pipeline", source="upstream")],
```
(import `FieldSpec`; keep `outputs=["review_action", "reviewed_data"]`.)

`export.py`:

```python
    runtime_inputs=[FieldSpec(key="extracted_data", label="Extracted data",
                              widget="pipeline", source="upstream")],
```
(import `FieldSpec`; keep outputs + config_schema.)

`parse.py` — no change required (its `FieldSpec(...)` defaults `source="form"`).

- [ ] **Step 5: Expose `source` on the API**

`schemas/agent.py`:

```python
class AgentToolRuntimeInput(BaseModel):
    key: str
    label: str
    widget: str
    source: str = "form"
```

`routers/agent.py` `list_agent_tools` — include `source` in the mapping:

```python
        runtimeInputs=[{"key": f.key, "label": f.label, "widget": f.widget,
                        "source": f.source} for f in t.runtime_inputs],
```

- [ ] **Step 6: Run — verify pass**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/agent/test_tool_input_sources.py tests/services/agent/test_parse_tool_registration.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/agent/tools backend/app/schemas/agent.py backend/app/routers/agent.py backend/tests/services/agent/test_tool_input_sources.py
git commit -m "feat(agent): source-tagged tool inputs; declare extract/review/export deps"
```

---

### Task 2: `validate_graph` — reachable-predecessor rule

**Files:**
- Create: `backend/app/services/agent/validation.py`
- Test: `backend/tests/services/agent/test_graph_validation.py` (create)

**Interfaces:**
- Produces: `UnmetInput(node_id: str, key: str)` dataclass and
  `validate_graph(definition: dict, get_tool_fn: Callable[[str], ToolDefinition | None]) -> list[UnmetInput]`.
  Returns one entry per node input with `source in ("upstream", "either")` whose key is not produced by any **reachable predecessor** (`source == "either"` is never unmet because the form can supply it — so in practice only `upstream` inputs can be unmet; `either` is included in the reachability computation only as a producer/consumer, never reported).

- [ ] **Step 1: Write the failing test**

`test_graph_validation.py`:

```python
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
```

- [ ] **Step 2: Run — verify fail**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/agent/test_graph_validation.py -v`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement**

`validation.py`:

```python
"""Graph validation — a node's pipeline inputs must be produced upstream."""
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class UnmetInput:
    node_id: str
    key: str


def _reachable_predecessors(node_id: str, adjacency: dict[str, set[str]]) -> set[str]:
    """All nodes that can run strictly before node_id (transitive predecessors)."""
    seen: set[str] = set()
    stack = list(adjacency.get(node_id, ()))
    while stack:
        p = stack.pop()
        if p in seen:
            continue
        seen.add(p)
        stack.extend(adjacency.get(p, ()))
    return seen


def validate_graph(definition: dict, get_tool_fn: Callable) -> list[UnmetInput]:
    nodes = definition.get("nodes", [])
    edges = definition.get("edges", [])

    # predecessors[target] = {sources...}, ignoring the synthetic __start__/__end__
    predecessors: dict[str, set[str]] = {n["id"]: set() for n in nodes}
    for e in edges:
        s, t = e["source"], e["target"]
        if s in ("__start__", "__end__") or t in ("__start__", "__end__"):
            continue
        predecessors.setdefault(t, set()).add(s)

    tool_of = {n["id"]: get_tool_fn(n["tool"]) for n in nodes}

    def outputs_of(nid: str) -> set[str]:
        tool = tool_of.get(nid)
        return set(tool.outputs) if tool else set()

    unmet: list[UnmetInput] = []
    for n in nodes:
        nid = n["id"]
        tool = tool_of.get(nid)
        if tool is None:
            continue
        upstream_keys: set[str] = set()
        for pred in _reachable_predecessors(nid, predecessors):
            upstream_keys |= outputs_of(pred)
        for f in tool.runtime_inputs:
            if f.source == "upstream" and f.key not in upstream_keys:
                unmet.append(UnmetInput(node_id=nid, key=f.key))
    return unmet
```

- [ ] **Step 4: Run — verify pass**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/agent/test_graph_validation.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/agent/validation.py backend/tests/services/agent/test_graph_validation.py
git commit -m "feat(agent): validate_graph reachable-predecessor pipeline-input check"
```

---

### Task 3: `start_run` guard — reject invalid graphs with 400

**Files:**
- Modify: `backend/app/services/agent/agent_run_service.py` (`start_run`)
- Test: `backend/tests/services/agent/test_start_run_guard.py` (create)

**Interfaces:**
- Consumes: `validate_graph` (Task 2), `get_tool` from `app.services.agent.tools`.
- Produces: `start_run` raises `ValueError` (mapped to 400 by the router) BEFORE creating the run record, when `validate_graph` returns any unmet input. Message names the first node + key.

- [ ] **Step 1: Write the failing test**

`test_start_run_guard.py` — drive the real `start_run` with fake repos; a lone-export definition must be rejected before any run is created:

```python
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
```

- [ ] **Step 2: Run — verify fail**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/agent/test_start_run_guard.py -v`
Expected: FAIL — no guard yet, so the invalid graph reaches `create` (AssertionError) instead of raising `ValueError`.

- [ ] **Step 3: Add the guard**

In `agent_run_service.py` `start_run`, immediately after fetching `agent_def` and confirming it exists, before `agent_run_repo.create(...)`:

```python
        from app.services.agent.tools import get_tool
        from app.services.agent.validation import validate_graph

        unmet = validate_graph(agent_def.definition, get_tool)
        if unmet:
            first = unmet[0]
            raise ValueError(
                f"Agent graph is not runnable: node '{first.node_id}' needs "
                f"'{first.key}' from an upstream node "
                f"({len(unmet)} unmet input(s) total)."
            )
```

(The router already maps `ValueError` → 400 for `start_run`.)

- [ ] **Step 4: Run — verify pass**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/agent/test_start_run_guard.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/agent/agent_run_service.py backend/tests/services/agent/test_start_run_guard.py
git commit -m "feat(agent): reject unrunnable graphs in start_run with 400 before execution"
```

---

### Task 4: `extract_node` generic retrofit + chain data-flow test

**Files:**
- Create: `backend/app/services/agent/extraction_bridge.py`
- Modify: `backend/app/services/agent/nodes.py` (`extract_node`)
- Test: `backend/tests/services/agent/test_extract_node_generic.py` (create)

**Interfaces:**
- Produces: `extraction_bridge.resolve_document_file_path(session, document_id) -> str` (raises `NotFoundError` when the document or its `source_metadata["file_path"]` is missing) and `resolve_schema_definition(session, schema_id) -> dict` (raises `NotFoundError` when missing).
- Produces: `extract_node(state, *, node_config=None)` resolves `document_id`/`extraction_schema_id` from state via the bridge (opening its own `AsyncSessionLocal()`), falling back to pre-seeded `state["file_path"]`/`state["schema_definition"]`. Output unchanged (`extracted_data`).

- [ ] **Step 1: Write the failing test**

`test_extract_node_generic.py`:

```python
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


def _session_ctx():
    class _Ctx:
        async def __aenter__(self): return "SESSION"
        async def __aexit__(self, *a): return False
    return lambda: _Ctx()
```

- [ ] **Step 2: Run — verify fail**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/agent/test_extract_node_generic.py -v`
Expected: FAIL — `extraction_bridge` missing; `extract_node` reads `state["file_path"]` directly (KeyError in the resolve test).

- [ ] **Step 3: Create `extraction_bridge.py`**

```python
"""Bridge between the agents engine and the extraction subsystem.

Resolves the document/schema ids a run form supplies into the file_path +
schema_definition extract_node needs, so extract composes generically.
"""
from __future__ import annotations
from uuid import UUID

from app.services.exceptions import NotFoundError


async def resolve_document_file_path(session, document_id: UUID | str) -> str:
    from app.repositories.document_repository import DocumentRepository
    doc = await DocumentRepository(session).get_by_id_unscoped(UUID(str(document_id)))
    if doc is None:
        raise NotFoundError(f"Document {document_id} not found")
    file_path = (doc.source_metadata or {}).get("file_path")
    if not file_path:
        raise NotFoundError(f"Document {document_id} has no file path")
    return file_path


async def resolve_schema_definition(session, schema_id: UUID | str) -> dict:
    from app.repositories.extraction_schema_repository import ExtractionSchemaRepository
    schema = await ExtractionSchemaRepository(session).get_by_id(UUID(str(schema_id)))
    if schema is None:
        raise NotFoundError(f"Extraction schema {schema_id} not found")
    return schema.schema_definition
```

- [ ] **Step 4: Retrofit `extract_node`**

Replace `extract_node`'s body so it resolves ids when present, else falls back to seeded state:

```python
async def extract_node(state: dict, *, node_config: dict | None = None) -> dict:
    """Extract structured data from a document using DataExtractor.

    Resolves document_id/extraction_schema_id from state into file_path +
    schema_definition (opening its own session), falling back to pre-seeded
    file_path/schema_definition so the bespoke /agent/extract entrypoint works.
    """
    from app.adapters.extraction.registry import get_extractor
    from app.config import settings
    from app.database import AsyncSessionLocal
    from app.services.agent import extraction_bridge as eb

    file_path = state.get("file_path")
    schema_definition = state.get("schema_definition")
    if not file_path or schema_definition is None:
        async with AsyncSessionLocal() as session:
            if not file_path:
                file_path = await eb.resolve_document_file_path(
                    session, state["document_id"])
            if schema_definition is None:
                schema_definition = await eb.resolve_schema_definition(
                    session, state["extraction_schema_id"])

    credentials = {}
    if settings.LLAMA_CLOUD_KEY:
        credentials["api_key"] = settings.LLAMA_CLOUD_KEY
    extractor = get_extractor("llamaextract", credentials)

    config = dict(state.get("extraction_config") or {})
    config["extraction_target"] = "PER_DOC"

    output = await extractor.extract(
        file_path=file_path, schema=schema_definition, config=config)

    return {**state, "extracted_data": output.structured_data,
            "current_step": "review"}
```

(`AsyncSessionLocal` is imported inside the function here; the test monkeypatches `nodes.AsyncSessionLocal`, so also add a module-level `from app.database import AsyncSessionLocal` at the top of `nodes.py` if not already present — `parse_node` already relies on the module-level name being patchable. Verify and keep one import path.)

- [ ] **Step 5: Add the chain data-flow capstone test**

Append to `test_extract_node_generic.py` — a real 2-node `extract → export` graph, proving the generic multi-node run threads extract's output into export's input (no review, so it completes in one invoke; no checkpointer needed):

```python
@pytest.mark.asyncio
async def test_extract_to_export_chain_threads_data(monkeypatch):
    from app.services.agent.graph import build_agent_graph
    from app.services.agent.state import AgentState
    from app.services.agent import extraction_bridge as eb

    captured = {}

    async def fake_file_path(session, document_id): return "/tmp/doc.pdf"
    async def fake_schema(session, schema_id): return {"type": "object"}

    class FakeOutput:
        structured_data = {"amount": 10}

    class FakeExtractor:
        async def extract(self, *, file_path, schema, config): return FakeOutput()

    async def fake_export(state, *, node_config=None):
        # stand in for export_node: capture the extracted_data it received upstream
        captured["export_saw"] = state.get("extracted_data")
        return {**state, "exported": True, "rows_exported": 1, "current_step": "done"}

    monkeypatch.setattr(eb, "resolve_document_file_path", fake_file_path)
    monkeypatch.setattr(eb, "resolve_schema_definition", fake_schema)
    monkeypatch.setattr(nodes, "AsyncSessionLocal", _session_ctx())
    monkeypatch.setattr("app.adapters.extraction.registry.get_extractor",
                        lambda *_a, **_k: FakeExtractor())
    monkeypatch.setattr(nodes, "export_node", fake_export)

    flow = {
        "nodes": [{"id": "e", "tool": "llamaextract"},
                  {"id": "x", "tool": "export"}],
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

    assert captured["export_saw"] == {"amount": 10}   # extract output → export input
    assert result["exported"] is True
```

Note: the export tool's `node_fn` is bound in `graph.py` via `functools.partial(export_node, node_config=...)`, which captures `nodes.export_node` at build time. Monkeypatching `nodes.export_node` before `build_agent_graph` (as above) is what makes the stand-in take effect — confirm the build reads `get_tool("export").node_fn`, which references the module function; if the partial captured the original, instead assert on the real `export_node` with a faked `DataStoreRepository`. Keep whichever the code supports; the assertion (export received `{"amount": 10}`) is the point.

- [ ] **Step 6: Run — verify pass; then the whole agent dir**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/agent tests/routers/test_agent_parse_router.py -v`
Expected: PASS (incl. the bespoke parse/extract entrypoint tests via fallbacks).

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/agent/extraction_bridge.py backend/app/services/agent/nodes.py backend/tests/services/agent/test_extract_node_generic.py
git commit -m "feat(agent): extract_node resolves document/schema ids; extract->export chain runs generically"
```

---

### Task 5: Full regression + manual verification notes

**Files:** none (verification only).

- [ ] **Step 1: Backend suite**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests -q`
Expected: PASS. Fix any test that assumed the old empty `runtime_inputs` on extract/review/export or the old `extract_node` signature.

- [ ] **Step 2: Manual verification pointer (backend-only slice)**

Not automated: with the app running, `POST /agent/projects/{id}/runs` for a saved `extract → review → export` definition and a body seeding `{ "document_id", "extraction_schema_id" }` starts a run that reaches `waiting_for_input` at review (full completion needs the review resume, exercised in the UI in Slice 2). `POST` for a lone `export` definition returns **400** naming the unmet input. The frontend run form + composer validation land in Slice 2.

- [ ] **Step 3: Comment on issue #192** with the automated result and what's deferred to Slice 2 / manual.

---

## Self-Review

**Spec coverage:** §1 (source-tagged contract + retrofits) → Task 1. §2 (reachable-predecessor validation) → Task 2. §3 backend guard → Task 3; extract_node retrofit + generic run → Task 4. AC1 → Task 1; AC2 → Task 2 (incl. producer-after-consumer); AC3 → Task 3 (real path, `create` not called); AC4 → Task 4 (resolve + fallback tests, parse-router still green); AC5 → Task 4 capstone (extract→export chain data-flow; three-node/review completion is manual per the interrupt/Postgres note); AC6 (frontend) → Slice 2, not here.

**Placeholder scan:** none — every step has real code. Task 4 Steps 4 & 5 flag one thing to confirm against the code (the `AsyncSessionLocal` patch point and whether the `export` partial captures the module function) rather than guess; both are concrete confirmations, not open decisions.

**Type consistency:** `FieldSpec.source` default `"form"` used consistently (Task 1) and read by `validate_graph` (Task 2) and the run guard (Task 3). `UnmetInput(node_id, key)` shape matches across Task 2's function and Task 3's message. `extraction_bridge` function names match between Task 4's interface, implementation, and tests.
