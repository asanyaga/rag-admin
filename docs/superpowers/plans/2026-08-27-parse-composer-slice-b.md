# Parse in the Composer — Slice B Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fan out the remaining four parser nodes (Simple, Docling, Landing AI, Custom Pipeline) in the agent composer, completing Definition 1's "Parsing" section on top of Slice A's foundation.

**Architecture:** Slice A proved the whole vertical on `parse.llamaparse`. This slice repeats that pattern for the other four parsers: register each as a `parse.<parser>` tool sharing `parse_node` (parser identity bound via `functools.partial`), and wire each parser's real workbench config panel into the frontend `PARSER_PANELS` dispatcher. Simple has no config panel; the panel host is refined so a parser without a panel shows a "no options" message instead of raw config-schema fields.

**Tech Stack:** Python 3.12, FastAPI, LangGraph 1.1.x, pytest (SQLite). React 18 + TypeScript, @xyflow/react, shadcn/ui, vitest.

**Spec:** [docs/superpowers/specs/2026-08-27-parse-tool-composer-design.md](../specs/2026-08-27-parse-tool-composer-design.md) §4.2
**Issue:** https://github.com/asanyaga/rag-admin/issues/190

## Global Constraints

- **Parser identity is bound at the tool boundary**, never inferred at runtime: each tool's `node_fn` is `functools.partial(parse_node, parser_type="<parser>")`. `parse_node`'s bound-config param is named `node_config` (LangGraph reserves `config`); this slice does not change `parse_node`.
- **`config_panel` value equals the parser key** for parsers that have a panel (`llamaparse`, `landing_ai`, `docling`, `custom_pipeline`) — the frontend keys `PARSER_PANELS`, `PARSER_REGISTRY`, and the drop-seed on this exact string. **Simple has `config_panel=None`** (no panel; needs no seed — its run works purely from the bound `parser_type`).
- Backend tests: `cd backend && uv run python -m pytest -o "addopts=" <path> -v`.
- Frontend tests: `cd frontend && npx vitest run <path>`; build: `cd frontend && npm run build`.
- Do not touch the bespoke `/agent/parse` / `/agent/extract` entrypoints or the extract/review tools.

---

### Task 1: Register all five parser tools (data-driven) + tests

**Files:**
- Modify: `backend/app/services/agent/tools/parse.py` (rewrite to register from a spec list)
- Test: `backend/tests/services/agent/test_parse_tool_registration.py` (assert all five)
- Test: `backend/tests/services/agent/test_parse_node_config.py` (add a `parse.simple`-through-the-graph case)

**Interfaces:**
- Consumes: `parse_node` (unchanged), `ToolDefinition`, `FieldSpec`, `register_tool`.
- Produces: registered tool slugs `parse.simple`, `parse.llamaparse`, `parse.landing_ai`, `parse.docling`, `parse.custom_pipeline`; each `node_fn = functools.partial(parse_node, parser_type=<parser>)`; `config_panel` = the parser key for the four with panels, `None` for `simple`.

- [ ] **Step 1: Write the failing registration test**

Append to `test_parse_tool_registration.py`:

```python
def test_all_five_parsers_registered_with_bound_parser_type():
    import functools
    expected = {
        "parse.simple": ("simple", None),
        "parse.llamaparse": ("llamaparse", "llamaparse"),
        "parse.landing_ai": ("landing_ai", "landing_ai"),
        "parse.docling": ("docling", "docling"),
        "parse.custom_pipeline": ("custom_pipeline", "custom_pipeline"),
    }
    for slug, (parser_type, config_panel) in expected.items():
        tool = get_tool(slug)
        assert tool is not None, slug
        assert tool.category == "parsing"
        assert tool.config_panel == config_panel
        assert isinstance(tool.node_fn, functools.partial)
        assert tool.node_fn.keywords.get("parser_type") == parser_type
        assert [f.key for f in tool.runtime_inputs] == ["source_document_id"]
        assert "parsed_document_id" in tool.outputs
```

- [ ] **Step 2: Run it — verify it fails**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/agent/test_parse_tool_registration.py::test_all_five_parsers_registered_with_bound_parser_type -v`
Expected: FAIL — only `parse.llamaparse` is registered.

- [ ] **Step 3: Rewrite `parse.py` data-driven**

```python
"""Parse tools — one node per parser (fanned out in Slice B)."""
import functools

from app.services.agent.nodes import parse_node
from app.services.agent.tools import FieldSpec, ToolDefinition, register_tool

# (parser_type, display name, config_panel id or None for panel-less parsers)
_PARSERS: list[tuple[str, str, str | None]] = [
    ("simple", "Simple", None),
    ("llamaparse", "LlamaParse", "llamaparse"),
    ("landing_ai", "Landing AI", "landing_ai"),
    ("docling", "Docling", "docling"),
    ("custom_pipeline", "Custom Pipeline", "custom_pipeline"),
]


def _register_parsers() -> None:
    for parser_type, name, config_panel in _PARSERS:
        register_tool(ToolDefinition(
            slug=f"parse.{parser_type}",
            name=name,
            category="parsing",
            description=f"Parse a source document with {name} into a ParsedDocument",
            runtime_inputs=[
                FieldSpec(key="source_document_id", label="Source document",
                          widget="source_document_picker"),
            ],
            outputs=["parse_run_id", "parsed_document_id", "page_count",
                     "text_len", "failed_page_count", "block_count"],
            config_schema={
                "type": "object",
                "properties": {
                    "representation_kind": {
                        "type": "string", "default": "extract_rich",
                        "description": "Representation the parser should produce",
                    },
                    "parse_config": {
                        "type": "object",
                        "description": f"{name} options (edited via its config panel)",
                    },
                },
            },
            config_panel=config_panel,
            node_fn=functools.partial(parse_node, parser_type=parser_type),
        ))


_register_parsers()
```

- [ ] **Step 4: Run the registration tests — verify pass**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/agent/test_parse_tool_registration.py -v`
Expected: PASS (both the existing three-way-contract test and the new five-parser test).

- [ ] **Step 5: Add a "Simple runs through the generic graph" test**

Append to `test_parse_node_config.py` a graph-level test that proves the generic run path works for `parse.simple` (parser identity resolves to `simple` with no config), faking the parse boundary like the existing tests:

```python
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
```

- [ ] **Step 6: Run the whole agent dir — verify pass**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/agent -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/agent/tools/parse.py backend/tests/services/agent/test_parse_tool_registration.py backend/tests/services/agent/test_parse_node_config.py
git commit -m "feat(agent): register all five parser tools data-driven (Slice B)"
```

---

### Task 2: Frontend — wire the parser panels + refine the panel-less parsing case

**Files:**
- Modify: `frontend/src/components/agent/composer/NodeConfigPanel.tsx`
- Test: `frontend/src/components/agent/composer/NodeConfigPanel.test.tsx`

**Interfaces:**
- Consumes: `AgentTool.configPanel` / `.category` (from Slice A); the existing workbench panels.
- Produces: `PARSER_PANELS` maps `llamaparse`, `landing_ai`, `docling`, `custom_pipeline` to their real config components; a `parsing`-category tool with no mapped panel (Simple) renders a "no options" message rather than the generic config-schema field renderer.

- [ ] **Step 1: Write the failing tests**

Add to `NodeConfigPanel.test.tsx` (keep the existing LlamaParse test):

```tsx
import { LandingAIConfig } from '@/components/documents/parser-configs/LandingAIConfig' // noqa: only to confirm import path exists

const doclingTool = {
  slug: 'parse.docling', name: 'Docling', category: 'parsing',
  description: '', runtimeInputs: [], outputs: [],
  configSchema: {}, configPanel: 'docling',
} as AgentTool

const doclingNode = {
  id: 'n2', type: 'composerNode', position: { x: 0, y: 0 },
  data: { toolSlug: 'parse.docling', label: 'Docling', category: 'parsing',
          config: { parser: 'docling', parse_config: {} } },
} as never

const simpleTool = {
  slug: 'parse.simple', name: 'Simple', category: 'parsing',
  description: '', runtimeInputs: [], outputs: [],
  configSchema: { type: 'object', properties: {
    representation_kind: { type: 'string', default: 'extract_rich' },
    parse_config: { type: 'object' },
  } },
  configPanel: null,
} as AgentTool

const simpleNode = {
  id: 'n3', type: 'composerNode', position: { x: 0, y: 0 },
  data: { toolSlug: 'parse.simple', label: 'Simple', category: 'parsing', config: {} },
} as never

it('renders the real Docling panel for a docling parsing node', () => {
  render(<NodeConfigPanel node={doclingNode} tools={[doclingTool]}
                          onUpdateConfig={vi.fn()} onClose={vi.fn()} />)
  // DoclingConfig renders a "Pipeline" control
  expect(screen.getByText(/pipeline/i)).toBeInTheDocument()
})

it('shows a no-options message for a panel-less parsing node (Simple)', () => {
  render(<NodeConfigPanel node={simpleNode} tools={[simpleTool]}
                          onUpdateConfig={vi.fn()} onClose={vi.fn()} />)
  expect(screen.getByText(/no options/i)).toBeInTheDocument()
  // must NOT fall through to the generic schema field renderer
  expect(screen.queryByText(/parse_config/i)).not.toBeInTheDocument()
  expect(screen.queryByText(/representation_kind/i)).not.toBeInTheDocument()
})
```

(Drop the `LandingAIConfig` import line if your linter objects to the unused import — it is only there to confirm the path; the real assertion is on Docling. If DoclingConfig's visible label differs from "Pipeline", open `frontend/src/components/documents/parser-configs/DoclingConfig.tsx` and assert on a real label it renders.)

- [ ] **Step 2: Run — verify failure**

Run: `cd frontend && npx vitest run src/components/agent/composer/NodeConfigPanel.test.tsx`
Expected: FAIL — Docling panel not mapped; Simple falls through to generic fields (`representation_kind`/`parse_config` rendered), no "no options" text.

- [ ] **Step 3: Add the panels + the refinement**

In `NodeConfigPanel.tsx`, extend the imports and map:

```tsx
import { LlamaParseConfig } from '@/components/documents/parser-configs/LlamaParseConfig'
import { LandingAIConfig } from '@/components/documents/parser-configs/LandingAIConfig'
import { DoclingConfig } from '@/components/documents/parser-configs/DoclingConfig'
import { CustomPipelineConfig } from '@/components/documents/parser-configs/CustomPipelineConfig'

const PARSER_PANELS: Record<string, ComponentType<{
  config: ParseConfig; onChange: (c: ParseConfig) => void; compact?: boolean
}>> = {
  llamaparse: LlamaParseConfig,
  landing_ai: LandingAIConfig,
  docling: DoclingConfig,
  custom_pipeline: CustomPipelineConfig,
}
```

Add `const isParsing = tool?.category === 'parsing'` (near the `Panel` line), and change the two `!Panel && …` branches so a parsing tool never uses the generic renderer:

```tsx
{Panel && ( /* unchanged: renders the parser panel */ )}

{!Panel && isParsing && (
  <>
    <Separator />
    <p className="text-xs text-muted-foreground">This parser has no options.</p>
  </>
)}

{!Panel && !isParsing && hasConfig && ( /* unchanged generic field renderer */ )}

{!Panel && !isParsing && !hasConfig && ( /* unchanged "no configurable options" */ )}
```

- [ ] **Step 4: Run — verify pass**

Run: `cd frontend && npx vitest run src/components/agent/composer/NodeConfigPanel.test.tsx`
Expected: PASS (LlamaParse, Docling, and Simple cases).

- [ ] **Step 5: Build**

Run: `cd frontend && npm run build`
Expected: success, no dangling imports.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/agent/composer/NodeConfigPanel.tsx frontend/src/components/agent/composer/NodeConfigPanel.test.tsx
git commit -m "feat(agent): wire Docling/LandingAI/CustomPipeline panels; no-options for Simple"
```

---

### Task 3: Full regression + manual verification notes

**Files:** none (verification only).

- [ ] **Step 1: Backend + frontend suites**

Run: `cd backend && uv run python -m pytest -o "addopts=" tests/services/agent tests/routers -v`
Run: `cd frontend && npx vitest run && npm run build`
Expected: all PASS; build clean. Fix any dangling reference the fan-out introduced.

- [ ] **Step 2: Manual verification pointer (for the user)**

Not automated. In the composed UI: the Parsing palette shows five nodes (Simple, LlamaParse, Landing AI, Docling, Custom Pipeline). Each with a panel opens its real workbench config; Simple shows "This parser has no options." A **Simple** run completes end-to-end (headless-safe). **Docling** and **Custom Pipeline** parse runs are verified manually by the user (local ML deps); **Landing AI** needs a BYOK key.

- [ ] **Step 3: Comment on issue #190** with the automated result and the parsers deferred to manual verification.

---

## Self-Review

**Spec coverage:** §4.2 (fan out remaining parsers) → Task 1 (backend) + Task 2 (frontend). AC1 (five tools + config_panel + bound parser_type) → Task 1 tests. AC2 (palette + seed) → already works via the `parsing` category + `configPanel`-keyed seed from Slice A (no code needed; confirmed in manual step). AC3 (real panels + Simple no-options) → Task 2. AC4 (tests + Simple generic-path run) → Task 1 Step 5 + Task 2. AC5 (green, no regression) → Task 3.

**Placeholder scan:** none — every code step has real content. Task 2 Step 1 notes the fallback if DoclingConfig's label differs (mechanical confirmation, not a hidden decision).

**Type consistency:** `parser_type` bound-kwarg name matches Slice A across `parse.py` and the tests; `config_panel` values (`docling`/`landing_ai`/`custom_pipeline`, `None` for simple) match `PARSER_PANELS` keys and `PARSER_REGISTRY` keys. `FieldSpec`/`runtime_inputs`/`outputs` consistent with the merged contract.

**Note (no code needed):** `useAgentComposer.addNode` seeds a parsing node's default config from `tool.configPanel`; this is correct for all four panel parsers (config_panel == parser key) and correctly no-ops for Simple (`configPanel=null` → config `{}`, which runs fine because `parser_type` is bound at the tool boundary). No change required.
