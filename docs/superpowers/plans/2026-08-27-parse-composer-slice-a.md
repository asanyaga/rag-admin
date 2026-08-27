# Parse in the Composer — Slice A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a LlamaParse parser node composable in the agent composer end-to-end — configured via the real workbench `LlamaParseConfig` panel, run via an auto-derived run form — on the foundation of a three-way tool contract and fixed per-node config plumbing.

**Architecture:** The agent engine already builds a LangGraph from a saved `AgentDefinition` (nodes carry a `config` blob) and runs it inline. Slice A (1) splits `ToolDefinition` into design-time `config_schema` / `runtime_inputs` / `outputs` / `config_panel`, (2) binds each node's saved `config` into its node function at graph-build time (so per-node config finally reaches the node), and (3) exposes one LlamaParse node whose config panel and run form reuse existing workbench components.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 (async), LangGraph 1.1.x, pytest (SQLite in-memory via `test_db` fixture). React 18 + TypeScript, @xyflow/react, shadcn/ui, vitest.

**Spec:** [docs/superpowers/specs/2026-08-27-parse-tool-composer-design.md](../specs/2026-08-27-parse-tool-composer-design.md)
**Issue:** https://github.com/asanyaga/rag-admin/issues/188

## Global Constraints

- **LangGraph reserves the `config` parameter name** for its own `RunnableConfig`. The bound per-node config MUST use a different name: node functions take `*, node_config: dict` and are bound with `functools.partial(fn, node_config=...)`. Never name it `config`.
- **Full-state merge convention:** every node returns the entire merged state (`return {**state, ...}`). `AgentState = dict` (LangGraph must preserve all keys). Partial-delta returns silently drop accumulated state — never use them here.
- **Design-time config is never persisted in run state.** It lives in `AgentDefinition.definition` JSON and is injected via binding, not carried in `initial_state`/`current_state`.
- **Backend tests:** `cd backend && uv run python -m pytest -o "addopts=" <path> -v` (the `-o "addopts="` disables coverage/strict-markers).
- **Frontend tests:** `cd frontend && npx vitest run <path>`. Build check: `cd frontend && npm run build`.
- **Bespoke entrypoints stay working:** `POST /agent/parse/...` and `/agent/extract/...` must not break (they seed top-level state keys; the parse node keeps a state fallback for that path).

---

### Task 1: Three-way tool contract on `ToolDefinition`, registry, and `/agent/tools`

**Files:**
- Modify: `backend/app/services/agent/tools/__init__.py` (dataclass)
- Modify: `backend/app/services/agent/tools/parse.py`, `extract.py`, `review.py`, `export.py` (registrations)
- Modify: `backend/app/schemas/agent.py:13-23` (`AgentToolResponse`)
- Modify: `backend/app/routers/agent.py:46-56` (mapping in `list_agent_tools`)
- Test: `backend/tests/services/agent/test_parse_tool_registration.py`

**Interfaces:**
- Produces: `FieldSpec(key: str, label: str, widget: str)` dataclass; `ToolDefinition` fields `config_schema: dict`, `runtime_inputs: list[FieldSpec]`, `outputs: list[str]`, `config_panel: str | None`, `node_fn: Callable`. (Removes `input_keys` / `output_keys`.)
- Produces: `AgentToolResponse` fields `configSchema`, `runtimeInputs: list[{key,label,widget}]`, `outputs: list[str]`, `configPanel: str | None`.

- [ ] **Step 1: Write the failing test**

In `test_parse_tool_registration.py`, replace the body with:

```python
from app.services.agent.tools import get_tool, list_tools


def test_llamaparse_tool_registered_with_three_way_contract():
    tool = get_tool("parse.llamaparse")
    assert tool is not None
    assert tool.category == "parsing"
    assert tool.config_panel == "llamaparse"
    # runtime inputs: only the file; parser/config are design-time
    assert [f.key for f in tool.runtime_inputs] == ["source_document_id"]
    assert tool.runtime_inputs[0].widget == "source_document_picker"
    # outputs feed downstream nodes
    assert "parsed_document_id" in tool.outputs
    assert "parse_run_id" in tool.outputs


def test_all_tools_expose_contract_fields():
    for tool in list_tools():
        assert isinstance(tool.runtime_inputs, list)
        assert isinstance(tool.outputs, list)
        assert hasattr(tool, "config_panel")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/agent/test_parse_tool_registration.py -v`
Expected: FAIL — `parse.llamaparse` not found / `ToolDefinition` has no `runtime_inputs`.

- [ ] **Step 3: Update the dataclass**

In `tools/__init__.py`, replace the `ToolDefinition` dataclass:

```python
@dataclass
class FieldSpec:
    """A runtime input a tool needs, and how the run form should render it."""
    key: str
    label: str
    widget: str  # e.g. "source_document_picker", "parsed_document_picker"


@dataclass
class ToolDefinition:
    """A reusable tool wired into an agent graph.

    Three channels, kept distinct:
      - config_schema: design-time knobs, bound per-node into the graph.
      - runtime_inputs: data supplied at run-time OR by an upstream node's output.
      - outputs: keys this node writes into state.
    """
    slug: str
    name: str
    category: str
    description: str
    node_fn: Callable
    runtime_inputs: list[FieldSpec] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    config_schema: dict[str, Any] = field(default_factory=dict)
    config_panel: str | None = None
```

- [ ] **Step 4: Update the four registrations**

`export.py` — keep its `config_schema`; replace keys:

```python
register_tool(ToolDefinition(
    slug="export", name="Export", category="export",
    description="Export data to a project data store",
    runtime_inputs=[],  # consumes upstream reviewed_data/extracted_data
    outputs=["exported", "rows_exported"],
    config_schema={  # unchanged
        "type": "object",
        "properties": {
            "data_store_id": {"type": "string", "format": "uuid",
                              "description": "Target data store to export rows into"},
            "field_mapping": {"type": "object",
                              "additionalProperties": {"type": "string"},
                              "description": "Source dot-path → destination column name mapping"},
        },
        "required": ["data_store_id"],
    },
    node_fn=export_node,
))
```

`review.py` — inspect its current `input_keys`/`output_keys` and mirror them into `runtime_inputs=[]` (review consumes `extracted_data` from upstream) and `outputs=["review_action", "reviewed_data"]`; keep its `config_schema` as-is.

`extract.py` — `runtime_inputs=[]` for now (its bespoke entrypoint seeds `document_id`/`file_path`/`schema_definition`; generic run-form support for extract is a later slice), `outputs=["extracted_data"]`, keep `config_schema`.

`parse.py` — replace the whole file (registers **`parse.llamaparse`**, not `parse`):

```python
"""Parse tools — one node per parser. Slice A registers LlamaParse only."""
from app.services.agent.nodes import parse_node
from app.services.agent.tools import FieldSpec, ToolDefinition, register_tool

register_tool(ToolDefinition(
    slug="parse.llamaparse",
    name="LlamaParse",
    category="parsing",
    description="Parse a source document with LlamaParse into a ParsedDocument",
    runtime_inputs=[
        FieldSpec(key="source_document_id", label="Source document",
                  widget="source_document_picker"),
    ],
    outputs=["parse_run_id", "parsed_document_id", "page_count",
             "text_len", "failed_page_count", "block_count"],
    config_schema={
        "type": "object",
        "properties": {
            "representation_kind": {"type": "string", "default": "extract_rich",
                                    "description": "Representation the parser should produce"},
            "parse_config": {"type": "object",
                             "description": "LlamaParse options (edited via the LlamaParse panel)"},
        },
    },
    config_panel="llamaparse",
    node_fn=parse_node,
))
```

- [ ] **Step 5: Update `AgentToolResponse` and the router mapping**

`schemas/agent.py` — replace `input_keys`/`output_keys` on `AgentToolResponse`:

```python
class AgentToolRuntimeInput(BaseModel):
    key: str
    label: str
    widget: str


class AgentToolResponse(BaseModel):
    slug: str
    name: str
    category: str
    description: str
    runtime_inputs: list[AgentToolRuntimeInput] = Field(default_factory=list, alias="runtimeInputs")
    outputs: list[str] = Field(default_factory=list)
    config_schema: dict[str, Any] = Field(default_factory=dict, alias="configSchema")
    config_panel: str | None = Field(None, alias="configPanel")

    model_config = ConfigDict(populate_by_name=True)
```

`routers/agent.py` `list_agent_tools` — map with new fields:

```python
return [
    AgentToolResponse(
        slug=t.slug, name=t.name, category=t.category, description=t.description,
        runtimeInputs=[{"key": f.key, "label": f.label, "widget": f.widget}
                       for f in t.runtime_inputs],
        outputs=t.outputs,
        configSchema=t.config_schema,
        configPanel=t.config_panel,
    )
    for t in list_tools()
]
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/agent/test_parse_tool_registration.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/agent/tools backend/app/schemas/agent.py backend/app/routers/agent.py backend/tests/services/agent/test_parse_tool_registration.py
git commit -m "feat(agent): three-way tool contract (config/runtime_inputs/outputs/config_panel)"
```

---

### Task 2: Bind per-node config in the graph builder + inject ambient keys

**Files:**
- Modify: `backend/app/services/agent/graph.py:35-39` (node loop)
- Modify: `backend/app/services/agent/agent_run_service.py:51-85` (`start_run` ambient injection)
- Test: `backend/tests/services/agent/test_graph_node_config.py` (create)

**Interfaces:**
- Consumes: `ToolDefinition.node_fn` (Task 1).
- Produces: node functions are added as `functools.partial(tool.node_fn, node_config=node.get("config", {}))`. Every `node_fn` must accept `*, node_config: dict`.
- Produces: `AgentRunService.start_run` injects `project_id` and `user_id` (as `str`) into `initial_state` before invoke.

- [ ] **Step 1: Write the failing test**

Create `test_graph_node_config.py`:

```python
import pytest
from app.services.agent.graph import build_agent_graph
from app.services.agent.state import AgentState
from app.services.agent.tools import ToolDefinition, register_tool


@pytest.mark.asyncio
async def test_two_nodes_of_same_tool_get_independent_config():
    seen: list[dict] = []

    async def probe_node(state: dict, *, node_config: dict) -> dict:
        seen.append(node_config)
        return {**state, "last_tag": node_config.get("tag")}

    register_tool(ToolDefinition(
        slug="probe", name="Probe", category="control",
        description="test probe", node_fn=probe_node,
    ))

    flow = {
        "nodes": [
            {"id": "a", "tool": "probe", "config": {"tag": "A"}},
            {"id": "b", "tool": "probe", "config": {"tag": "B"}},
        ],
        "edges": [
            {"source": "__start__", "target": "a"},
            {"source": "a", "target": "b"},
            {"source": "b", "target": "__end__"},
        ],
    }
    compiled = build_agent_graph(flow=flow, state_type=AgentState)
    result = await compiled.ainvoke({})

    assert {c["tag"] for c in seen} == {"A", "B"}      # each node saw its own config
    assert result["last_tag"] == "B"
    assert "node_config" not in result                  # config not persisted in state
    assert "tag" not in result                          # design-time config absent from state
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/agent/test_graph_node_config.py -v`
Expected: FAIL — `probe_node` receives no `node_config` (TypeError: missing keyword-only argument).

- [ ] **Step 3: Bind config in `build_agent_graph`**

`graph.py` — add `import functools` at top; change the node loop:

```python
    for node in flow["nodes"]:
        tool = get_tool(node["tool"])
        if tool is None:
            raise ValueError(f"Unknown tool: {node['tool']}")
        bound = functools.partial(tool.node_fn, node_config=node.get("config", {}))
        graph.add_node(node["id"], bound)
```

- [ ] **Step 4: Inject ambient keys in `start_run`**

`agent_run_service.py` `start_run`, right after creating the run record and before `compiled.ainvoke`, seed ambient identity into the invoked state (not persisted separately — they are legitimate runtime inputs):

```python
        invoke_state = {
            **initial_state,
            "project_id": str(project_id),
            "user_id": str(user_id),
        }
        ...
        result = await compiled.ainvoke(invoke_state, config=config)
```

(Use `invoke_state` in the `ainvoke` call; leave `initial_state` as the persisted record.)

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/agent/test_graph_node_config.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/agent/graph.py backend/app/services/agent/agent_run_service.py backend/tests/services/agent/test_graph_node_config.py
git commit -m "feat(agent): bind per-node config via partial; inject ambient project/user"
```

---

### Task 3: `parse_node` + `export_node` read bound `node_config`

**Files:**
- Modify: `backend/app/services/agent/nodes.py:55-136` (`export_node`), `:139-171` (`parse_node`)
- Test: `backend/tests/services/agent/test_parse_node_config.py` (create)

**Interfaces:**
- Consumes: binding from Task 2 (`node_config` keyword).
- Produces: `parse_node(state, *, node_config)` reads `node_config["parser"]` (default `"simple"`), `node_config["representation_kind"]` (default `"extract_rich"`), `node_config["parse_config"]` — **with a fallback to top-level state keys** so the bespoke `/agent/parse` entrypoint (which seeds `state["parse_config"]` / `state["representation_kind"]`) keeps working.
- Produces: `export_node(state, *, node_config)` reads `node_config` instead of `state["node_config"]`.

- [ ] **Step 1: Write the failing test**

Create `test_parse_node_config.py` (fakes the parsing bridge so no real parser runs):

```python
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


def _dummy_session_ctx():
    class _Ctx:
        async def __aenter__(self): return "SESSION"
        async def __aexit__(self, *a): return False
    def _factory(): return _Ctx()
    return _factory
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/agent/test_parse_node_config.py -v`
Expected: FAIL — `parse_node` doesn't accept `node_config`.

- [ ] **Step 3: Rewrite `parse_node`**

`nodes.py` — new signature and config source (keep the fallback for the bespoke entrypoint):

```python
async def parse_node(state: dict, *, node_config: dict | None = None) -> dict:
    """Parse a source document into a ParsedDocument, then merge into state.

    Reads parser settings from the node's bound design-time config. Falls back to
    top-level state keys so the bespoke /agent/parse entrypoint (which seeds
    parse_config/representation_kind in initial_state) keeps working.
    """
    from uuid import UUID
    from app.database import AsyncSessionLocal
    from app.services.agent import parsing_bridge as pb

    cfg = node_config or {}
    parse_config = dict(cfg.get("parse_config") or state.get("parse_config") or {})
    parser_type = cfg.get("parser") or parse_config.get("parser") or "simple"
    representation_kind = (cfg.get("representation_kind")
                           or state.get("representation_kind") or "extract_rich")

    logger.info("parse_node: parsing source_document %s with %s",
                state.get("source_document_id"), parser_type)

    async with AsyncSessionLocal() as session:
        source, file_path = await pb.resolve_source_cdm(
            session, UUID(str(state["source_document_id"])))
        service = await pb.build_parsing_service(
            session, UUID(str(state["user_id"])), parser_type)
        outcome = await pb.run_parse(
            session, service, source, file_path=file_path,
            representation_kind=representation_kind, config=parse_config,
            project_id=state["project_id"])

    return {**state, **outcome.as_state(), "current_step": "parsed"}
```

- [ ] **Step 4: Rewrite `export_node` signature to read `node_config`**

`nodes.py` — change `async def export_node(state: dict) -> dict:` to `async def export_node(state: dict, *, node_config: dict | None = None) -> dict:` and replace `config = state.get("node_config", {})` with `config = node_config or {}`. Leave the rest of the body unchanged.

- [ ] **Step 5: Run the agent test suite**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/agent tests/routers/test_agent_parse_router.py -v`
Expected: PASS (parse-node config test passes; the bespoke parse-router test still passes via the state fallback). If the router test referenced the old `parse` slug in a definition, update it to `parse.llamaparse`.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/agent/nodes.py backend/tests/services/agent/test_parse_node_config.py
git commit -m "feat(agent): parse_node/export_node read bound node_config (with state fallback)"
```

---

### Task 4: Composer renders the real LlamaParse panel + seeds parse-node defaults

**Files:**
- Modify: `frontend/src/types/agent.ts:3-11` (`AgentTool`)
- Modify: `frontend/src/components/agent/composer/NodeConfigPanel.tsx` (dispatcher)
- Modify: `frontend/src/hooks/useAgentComposer.ts:237-256` (`addNode` default config)
- Test: `frontend/src/components/agent/composer/NodeConfigPanel.test.tsx` (create)

**Interfaces:**
- Consumes: `AgentTool` now has `runtimeInputs: {key,label,widget}[]`, `outputs: string[]`, `configPanel: string | null` (replacing `inputKeys`/`outputKeys`).
- Produces: `NodeConfigPanel` renders the real parser panel for a tool with `configPanel`, bound to `node.data.config.parse_config`.
- Produces: dropping a `parsing`-category node seeds `config = { parser, representation_kind: "extract_rich", parse_config: PARSER_REGISTRY[parser].defaultConfig }` where `parser = tool.configPanel`.

- [ ] **Step 1: Update `AgentTool` type**

`types/agent.ts` — replace `inputKeys`/`outputKeys`:

```ts
export interface AgentToolRuntimeInput {
  key: string
  label: string
  widget: string
}

export interface AgentTool {
  slug: string
  name: string
  category: string
  description: string
  runtimeInputs: AgentToolRuntimeInput[]
  outputs: string[]
  configSchema: Record<string, unknown>
  configPanel: string | null
}
```

Then fix the two now-broken references in `NodeConfigPanel.tsx` (the `Inputs:`/`Outputs:` block reads `tool.inputKeys`/`tool.outputKeys`) — repoint to `tool.runtimeInputs.map(f => f.key)` and `tool.outputs`.

- [ ] **Step 2: Write the failing test**

Create `NodeConfigPanel.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { NodeConfigPanel } from './NodeConfigPanel'
import type { AgentTool } from '@/types/agent'

const llamaTool: AgentTool = {
  slug: 'parse.llamaparse', name: 'LlamaParse', category: 'parsing',
  description: 'Parse with LlamaParse', runtimeInputs: [], outputs: [],
  configSchema: {}, configPanel: 'llamaparse',
}

const node = {
  id: 'n1', type: 'composerNode', position: { x: 0, y: 0 },
  data: { toolSlug: 'parse.llamaparse', label: 'LlamaParse', category: 'parsing',
          config: { parser: 'llamaparse', parse_config: { tier: 'agentic' } } },
} as never

it('renders the real LlamaParse panel for a parsing tool', () => {
  render(<NodeConfigPanel node={node} tools={[llamaTool]}
                          onUpdateConfig={vi.fn()} onClose={vi.fn()} />)
  // LlamaParseConfig renders a "Tier" control — assert its presence
  expect(screen.getByText(/tier/i)).toBeInTheDocument()
})
```

(If `LlamaParseConfig`'s visible label differs, open `frontend/src/components/documents/parser-configs/LlamaParseConfig.tsx` and assert on a real label it renders.)

- [ ] **Step 3: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/agent/composer/NodeConfigPanel.test.tsx`
Expected: FAIL — panel renders generic JSON fields, no Tier control.

- [ ] **Step 4: Add the dispatcher**

`NodeConfigPanel.tsx` — add a panel map and render it when the tool has `configPanel`. Import the real panels:

```tsx
import { LlamaParseConfig } from '@/components/documents/parser-configs/LlamaParseConfig'
import type { ParseConfig } from '@/types/parsing'

const PARSER_PANELS: Record<string, React.ComponentType<{
  config: ParseConfig; onChange: (c: ParseConfig) => void; compact?: boolean
}>> = {
  llamaparse: LlamaParseConfig,
  // landing_ai / docling / custom_pipeline added in Slice B
}
```

In the component body, before the generic `hasConfig` block:

```tsx
const Panel = tool?.configPanel ? PARSER_PANELS[tool.configPanel] : undefined
const parseConfig = (config.parse_config ?? {}) as ParseConfig
```

And render, when `Panel` is set, instead of the generic fields:

```tsx
{Panel && (
  <>
    <Separator />
    <Panel
      config={parseConfig}
      onChange={(pc) => onUpdateConfig(node.id, { ...config, parse_config: pc })}
      compact
    />
  </>
)}
{!Panel && hasConfig && ( /* existing generic renderer */ )}
{!Panel && !hasConfig && ( /* existing "no options" message */ )}
```

- [ ] **Step 5: Seed defaults on drop**

`useAgentComposer.ts` `addNode` — seed parsing-node config from `PARSER_REGISTRY`:

```ts
import { PARSER_REGISTRY } from '@/components/documents/ParseMethodSelector'
```

```ts
    const parser = tool.configPanel ?? undefined
    const initialConfig =
      tool.category === 'parsing' && parser
        ? { parser, representation_kind: 'extract_rich',
            parse_config: PARSER_REGISTRY[parser]?.defaultConfig ?? {} }
        : {}
    const newNode: Node = {
      id, type: 'composerNode', position,
      data: { toolSlug: tool.slug, label: tool.name,
              category: tool.category, config: initialConfig },
      sourcePosition: Position.Right, targetPosition: Position.Left,
    }
```

- [ ] **Step 6: Run test + typecheck**

Run: `cd frontend && npx vitest run src/components/agent/composer/NodeConfigPanel.test.tsx && npm run build`
Expected: test PASS; build succeeds (no dangling `inputKeys`/`outputKeys` references).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/types/agent.ts frontend/src/components/agent/composer/NodeConfigPanel.tsx frontend/src/components/agent/composer/NodeConfigPanel.test.tsx frontend/src/hooks/useAgentComposer.ts
git commit -m "feat(agent): composer renders real LlamaParse panel + seeds parse-node defaults"
```

---

### Task 5: Auto-derived `AgentRunForm` + wire the generic run

**Files:**
- Create: `frontend/src/components/agent/AgentRunForm.tsx`
- Create: `frontend/src/components/agent/AgentRunForm.test.tsx`
- Modify: `frontend/src/pages/AgentRunsPage.tsx` (use `AgentRunForm` for definitions with a `parsing` entry node)

**Interfaces:**
- Consumes: `AgentTool.runtimeInputs`/`outputs` (Task 4); `agentApi.startAgentRun(projectId, { agentDefinitionId, initialState })` (existing, `api/agent.ts:72`); `useSourceDocuments()` (existing hook, same data source as the workbench browser).
- Produces: `AgentRunForm({ projectId, definition, tools, onStarted })` — computes `formFields = ⋃ runtimeInputs − ⋃ outputs` over the definition's nodes' tools, renders a source-document `<select>` for the `source_document_picker` widget, and POSTs `initialState = { source_document_id }`.

**Deviation note (from spec §3):** the spec named `SourceDocumentBrowser` for the `source_document_picker` widget. That component is a Sheet that also selects a parser (`onAdd(id, parserType, parseConfig)`), which would duplicate the node's parser choice. This task instead reuses the **same data source** (`useSourceDocuments`) with a plain select. Extracting a shared `SourceDocumentPicker` from `SourceDocumentBrowser` is deferred to Slice B.

- [ ] **Step 1: Write the failing test**

Create `AgentRunForm.test.tsx`:

```tsx
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { AgentRunForm } from './AgentRunForm'
import type { AgentTool } from '@/types/agent'

vi.mock('@/hooks/useSourceDocuments', () => ({
  useSourceDocuments: () => ({
    sourceDocuments: [{ id: 'sd-1', filename: 'invoice.pdf' }], isLoading: false,
  }),
}))
const startAgentRun = vi.fn(async () => ({ id: 'run-1' }))
vi.mock('@/api/agent', () => ({ startAgentRun: (...a: unknown[]) => startAgentRun(...a) }))

const tools: AgentTool[] = [{
  slug: 'parse.llamaparse', name: 'LlamaParse', category: 'parsing',
  description: '', runtimeInputs: [{ key: 'source_document_id',
    label: 'Source document', widget: 'source_document_picker' }],
  outputs: ['parsed_document_id'], configSchema: {}, configPanel: 'llamaparse',
}]
const definition = { nodes: [{ id: 'n1', tool: 'parse.llamaparse', config: {} }], edges: [] }

beforeEach(() => startAgentRun.mockClear())

it('derives a source-document field and starts a generic run', async () => {
  render(<AgentRunForm projectId="p1" definitionId="def-1"
                       definition={definition} tools={tools} onStarted={vi.fn()} />)
  await userEvent.selectOptions(await screen.findByLabelText(/source document/i), 'sd-1')
  await userEvent.click(screen.getByRole('button', { name: /run/i }))
  await waitFor(() => expect(startAgentRun).toHaveBeenCalledWith('p1', {
    agentDefinitionId: 'def-1', initialState: { source_document_id: 'sd-1' },
  }))
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/agent/AgentRunForm.test.tsx`
Expected: FAIL — `AgentRunForm` does not exist.

- [ ] **Step 3: Implement `AgentRunForm`**

Create `AgentRunForm.tsx`:

```tsx
import { useMemo, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Play } from 'lucide-react'
import { useSourceDocuments } from '@/hooks/useSourceDocuments'
import { startAgentRun } from '@/api/agent'
import type { AgentTool, AgentDefinitionData } from '@/types/agent'

interface Props {
  projectId: string
  definitionId: string
  definition: AgentDefinitionData
  tools: AgentTool[]
  onStarted: (runId: string) => void
}

/** form fields = ⋃ runtime_inputs − ⋃ outputs across the graph's tools */
function deriveFields(definition: AgentDefinitionData, tools: AgentTool[]) {
  const bySlug = new Map(tools.map((t) => [t.slug, t]))
  const used = definition.nodes.map((n) => bySlug.get(n.tool)).filter(Boolean) as AgentTool[]
  const produced = new Set(used.flatMap((t) => t.outputs))
  const seen = new Set<string>()
  const fields = []
  for (const t of used)
    for (const f of t.runtimeInputs)
      if (!produced.has(f.key) && !seen.has(f.key)) { seen.add(f.key); fields.push(f) }
  return fields
}

export function AgentRunForm({ projectId, definitionId, definition, tools, onStarted }: Props) {
  const fields = useMemo(() => deriveFields(definition, tools), [definition, tools])
  const { sourceDocuments } = useSourceDocuments()
  const [values, setValues] = useState<Record<string, string>>({})
  const [isStarting, setStarting] = useState(false)

  const ready = fields.every((f) => values[f.key])

  const handleRun = async () => {
    setStarting(true)
    try {
      const run = await startAgentRun(projectId, {
        agentDefinitionId: definitionId, initialState: { ...values },
      })
      onStarted(run.id)
    } finally { setStarting(false) }
  }

  return (
    <div className="space-y-3">
      {fields.map((f) => (
        <div key={f.key} className="space-y-1.5">
          <Label htmlFor={f.key} className="text-xs">{f.label}</Label>
          {f.widget === 'source_document_picker' ? (
            <select id={f.key} aria-label={f.label}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={values[f.key] ?? ''}
              onChange={(e) => setValues((v) => ({ ...v, [f.key]: e.target.value }))}>
              <option value="">Select a document...</option>
              {sourceDocuments.map((sd) => (
                <option key={sd.id} value={sd.id}>{sd.filename ?? sd.id}</option>
              ))}
            </select>
          ) : (
            <span className="text-xs text-muted-foreground">Unsupported input: {f.widget}</span>
          )}
        </div>
      ))}
      <Button size="sm" disabled={!ready || isStarting} onClick={handleRun}>
        <Play className="h-4 w-4 mr-1.5" />{isStarting ? 'Starting...' : 'Run'}
      </Button>
    </div>
  )
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/agent/AgentRunForm.test.tsx`
Expected: PASS.

- [ ] **Step 5: Wire into `AgentRunsPage`**

In `AgentRunsPage.tsx`, render `AgentRunForm` (passing the loaded definition + tools) when the agent's entry node is in the `parsing` category; keep the existing `AgentRunInputForm` path for extract-based agents. Open `AgentRunsPage.tsx` first to match its existing data-loading (it already loads the definition and has `projectId`); pass `onStarted={(runId) => navigate(\`/agent/runs/${runId}\`)}` following the page's existing navigation pattern.

- [ ] **Step 6: Build**

Run: `cd frontend && npx vitest run src/components/agent && npm run build`
Expected: tests PASS; build succeeds.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/agent/AgentRunForm.tsx frontend/src/components/agent/AgentRunForm.test.tsx frontend/src/pages/AgentRunsPage.tsx
git commit -m "feat(agent): auto-derived AgentRunForm wired to the generic run endpoint"
```

---

### Task 6: Full-suite regression + manual end-to-end verification (AC #6, #7)

**Files:** none (verification only).

- [ ] **Step 1: Backend suite**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/agent tests/routers -v`
Expected: PASS. Fix any test that still references the removed `parse` slug or `input_keys`/`output_keys`.

- [ ] **Step 2: Frontend suite + build**

Run: `cd frontend && npx vitest run && npm run build`
Expected: PASS + clean build.

- [ ] **Step 3: Manual end-to-end (AC #6)**

Per CLAUDE.md "Local Testing (Docker)": build frontend, start `docker-compose.local.yml -p rag-admin`, then in the UI:
1. Compose an agent: drag one **LlamaParse** node onto the canvas; confirm its config panel is the real LlamaParse panel (Tier / expand controls). Save.
2. Open the agent's runs page; the run form shows a **Source document** picker (no parser re-selection). Pick a source document → Run.
3. Confirm the run reaches `completed` and the run's `current_state` carries `parsed_document_id`.

Use a source document **not previously parsed** so BYOK/parse actually executes. Requires a LlamaParse BYOK key configured for the user.

- [ ] **Step 4: Update the issue**

Comment on issue #188 with the verification result (pass/fail + any follow-ups), and note Slice B (remaining parser nodes) as the next slice.

---

## Self-Review

**Spec coverage:**
- §1 three-way contract → Task 1. ✅
- §2 per-node config plumbing (binding) + config not persisted + frontend serializes (already done in `reactFlowToDefinition`) → Task 2 (+ existing code). ✅
- §3 auto-derived run form + ambient injection → Task 5 (form) + Task 2 (ambient). ✅
- §4 NodeConfigPanel dispatcher + defaults on drop + palette one-node-per-parser (LlamaParse) → Task 4 (+ Task 1 registration). ✅
- AC #2 "two same-tool nodes independent config" → Task 2 test. ✅
- AC #3 "config not in persisted state" → Task 2 test. ✅
- AC #7 "bespoke entrypoints still work" → Task 3 state fallback + Task 3 Step 5. ✅

**Placeholder scan:** No TBD/TODO; each code step carries real code. Task 5 Step 5 and Task 1 Step 4 (`review.py`) ask the implementer to read an existing file first because exact current contents must be matched — acceptable (mechanical mirroring), not a hidden decision.

**Type consistency:** `node_config` keyword name used consistently across graph binding (Task 2), `parse_node`/`export_node` (Task 3). `configPanel`/`runtimeInputs`/`outputs` consistent across backend response (Task 1), TS type (Task 4), form derivation (Task 5). `FieldSpec(key,label,widget)` ↔ `AgentToolRuntimeInput` ↔ TS `runtimeInputs[]` aligned.

**Known deviations surfaced:** (1) bound param named `node_config`, not `config` (LangGraph reserves `config`); (2) run form reuses `useSourceDocuments` data, not the `SourceDocumentBrowser` Sheet (which bundles parser choice). Both documented at point of use.
