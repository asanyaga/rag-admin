# Parse in the Composer — Definition 1 via a Three-Way Tool Contract

- **Date:** 2026-08-27
- **Status:** Design — pending review
- **Author:** Brainstormed with Claude
- **Builds on:** [2026-08-26-parse-tool-design.md](2026-08-26-parse-tool-design.md) (the parse tool + engine this refines).
- **Supersedes (direction of):** the "Known Gap" per-node config plumbing deferred in that spec — fixed here.

## Objective

Make **parsing a first-class, composer-native capability** that matches the
product's "Definition 1 (single-tool agent)" vision: the composer's **Parsing**
section lists one node per parser (Simple, LlamaParse, Landing AI, Docling,
Custom Pipeline); selecting a node shows **the exact same config panel used in
the document workbench**; running the agent shows **the exact same file-select
component used in the workbench**. Single-tool and multi-tool agents are the
same mechanism — a single-tool agent is just a one-node graph.

To do this correctly, introduce a **three-way tool contract** (config vs runtime
input vs output) and **fix per-node config plumbing** — the load-bearing pieces
that also make Definition 2 (chaining) coherent later.

## Product framing (decisions taken during brainstorming)

1. **One node per parser.** Parser identity = node identity. Each placed node
   carries one parser's real config panel. (Not: one "Parse" node with a parser
   dropdown.)
2. **Everything via the composer.** A single-tool agent is a one-node agent in
   the same drag-drop composer. No separate "quick run a tool" surface.
3. **Auto-derived run form.** The run form is computed from the graph's unbound
   runtime inputs and reuses real workbench pickers — not a bespoke form per
   tool. One generic run path; bespoke entrypoints (`/agent/parse`,
   `/agent/extract`) keep working and are retired later, not in this slice.
4. **Small, valuable iterations.** Ship one parser end-to-end first (Slice A),
   then fan out the rest (Slice B).

## Current state (what exists today)

- A general composable agent engine: `AgentDefinition` (graph JSON) + `AgentRun`
  (checkpointed, supports `interrupt`/resume), `AgentRunService` builds a
  LangGraph via `build_agent_graph` and runs it inline in the request.
- A tool registry (`ToolDefinition`: slug, category, `input_keys`,
  `output_keys`, `node_fn`, `config_schema`). Tools: `parse`, `extract`,
  `review`, `export`.
- A drag-drop composer (`AgentComposer`), a generic `NodeConfigPanel` (renders
  JSON-schema fields), runs list / run detail.
- Bespoke domain entrypoints `POST /agent/parse/...` and `/agent/extract/...`
  that seed a run's `initial_state` from domain inputs.
- **The workbench parser panels are already host-agnostic** — `LlamaParseConfig`,
  `DoclingConfig`, `LandingAIConfig`, `CustomPipelineConfig` all take
  `{ config, onChange, disabled?, compact? }` and know nothing about the
  Documents page. `PARSER_REGISTRY` (in `ParseMethodSelector.tsx`) holds each
  parser's label / description / default config.

### The gap this design closes

`ToolDefinition` lumps everything into `input_keys` + `config_schema` with no
rule for who binds what. Consequently **per-node config is not plumbed**:

- `export_node` reads `state.get("node_config", {})` — a single shared key that
  nothing ever writes, and that could not distinguish two export nodes anyway.
- `parse_node` reads `state.get("parse_config")` — a top-level key seeded by the
  bespoke entrypoint, again shared and node-blind.

Both Definition 1 (a configured single tool) and Definition 2 (a chain of
configured tools) require per-node config. Fixing it is the foundation.

## Design

### §1 — The three-way tool contract

Replace the ambiguous `input_keys` + `config_schema` with an explicit split:

```
ToolDefinition(
    slug, name, category, description,
    config_schema:   {...}          # design-time: bound in the node config panel
    runtime_inputs:  [FieldSpec]    # bound at run-time OR by an upstream output
    outputs:         [str]          # keys this node writes into state
    node_fn,
    config_panel:    "llamaparse"   # id the frontend maps to a real panel component
)
```

- **`config_schema`** — design-time knobs only (parser params). Plumbed per-node
  into the running graph (see §2).
- **`runtime_inputs`** — each a `FieldSpec` `(key, label, widget)` where `widget`
  is a hint (`source_document_picker`, `parsed_document_picker`,
  `extraction_schema_picker`, …). The run form renders these with real workbench
  pickers, and only for inputs no upstream node produces.
- **`outputs`** — seed downstream state and validate edges
  (`upstream.outputs ⊇ downstream.runtime_inputs`).
- **`config_panel`** — a stable id the frontend maps to the actual reused
  component. "The exact same panel as the workbench" is a lookup, not a
  reimplementation.

Consequences that fall out for free: per-node config gets a defined home and
plumbing path; edge validity and the run form are both computable from the
contract.

**Ambient keys are not part of the contract.** `project_id` and `user_id` are
injected into every run's `initial_state` by `AgentRunService` from
auth/context. They never appear in `runtime_inputs` and never in the run form.

### §2 — Per-node config plumbing

**Bind each node's design-time config at graph-build time, as a keyword arg —
never through state.**

```python
# graph.py — build_agent_graph, per node:
node_fn = functools.partial(tool.node_fn, config=node.get("config", {}))
graph.add_node(node["id"], node_fn)
```

Node functions gain an explicit `config` parameter:

```python
async def parse_node(state: dict, *, config: dict) -> dict:
    parser_type = config["parser"]            # design-time, from this node
    source = state["source_document_id"]      # runtime, from state
    ...
    return {**state, **outcome.as_state()}    # only runtime data merges into state
```

Why binding, not a state key:

- **Per-node isolation** — two Docling nodes each get their own config. The
  shared `node_config` / `parse_config` keys cannot do this.
- **Config never persists in run state** — it is structural and lives in the
  `AgentDefinition` JSON. Run state stays purely the runtime data flowing through
  the graph. (This also removes design-time config leaking into every
  checkpoint.)
- **Maps 1:1 to §1** — `config_schema` → the bound `config` arg;
  `runtime_inputs` / `outputs` → state.

Smaller pieces this settles:

- **Frontend:** the composer serializes each node's panel values into
  `node["config"]` in the saved definition (today held in `node.data.config`).
- **Existing tools migrate:** `export_node` and `parse_node` switch from reading
  state keys to reading `config`; entrypoints stop seeding `node_config` /
  `parse_config`. Backward-compatible: bound config defaults to `{}`.
- **Optional (included):** validate `node["config"]` against the tool's
  `config_schema` at save time — a clean composer-time error rather than a
  runtime failure.

### §3 — Auto-derived run form + input resolution

**Derivation rule (topology-independent for v1):**

```
form_fields = ( ⋃ every node's runtime_inputs )  −  ( ⋃ every node's outputs )
```

An input a node needs is either produced upstream (some node lists it in
`outputs`) or must be collected at run time. For a single Docling node that is
just `source_document_id`; for `parse → extract` it is still just the file,
because `parse.outputs` covers `extract`'s `parsed_document_id`.

The rule ignores ordering — a key produced by *any* node counts as satisfied.
Correct for single nodes and valid linear chains (which §1 edge-validation
enforces). When Definition 2 introduces arbitrary graphs, this refines to
"produced by a reachable predecessor." **Deliberate v1 simplification.**

**Rendering — real workbench pickers.** Each `FieldSpec.widget` maps to a
component:

| widget | component reused |
|--------|------------------|
| `source_document_picker` | `SourceDocumentBrowser` |
| `parsed_document_picker` | `ParsedDocumentPicker` |
| `extraction_schema_picker` | existing schema selector |

**Flow:**

1. Frontend loads the saved definition + `GET /agent/tools`, computes
   `form_fields`, renders the run form with real pickers.
2. Collected values → `initial_state`; POST to the generic
   `/agent/projects/{id}/runs` with `agent_definition_id` + `initial_state`.
3. `AgentRunService` injects ambient `project_id` / `user_id`, runs the graph.

Bespoke `/agent/parse` and `/agent/extract` remain untouched and working; they
become redundant once the generic form covers their cases and are retired in a
later cleanup — no big-bang rewrite.

### §4 — Frontend composer integration

**1. Palette: one entry per parser.** Backend registers N parse tools
(`parse.simple`, `parse.llamaparse`, `parse.landing_ai`, `parse.docling`,
`parse.custom_pipeline`), all sharing one `parse_node`, each carrying its own
`parser_type` and `config_panel` id. The `parsing` category renders them as
distinct draggable nodes.

**2. `NodeConfigPanel` becomes a dispatcher.** If the tool declares a
`config_panel`, render the real component via a small frontend map, driven by
the node's own config:

```tsx
const PANELS = { simple: null, llamaparse: LlamaParseConfig,
                 landing_ai: LandingAIConfig, docling: DoclingConfig,
                 custom_pipeline: CustomPipelineConfig }
<Panel config={node.data.config} onChange={c => updateNodeConfig(node.id, c)} compact />
```

Else (export, review) → keep the generic JSON renderer. Both hosts coexist.

**3. Sensible defaults on drop.** A freshly dropped node seeds `node.data.config`
from `PARSER_REGISTRY[parser].defaultConfig` — the same registry the workbench
uses, so defaults never drift.

**4. Run form: `AgentRunForm`.** Takes the §3-derived `form_fields`, renders each
by `widget` → real picker. Replaces the bespoke `ParseRunInputForm` for the
generic path.

**5. Save serializes config (from §2).**

`PARSER_REGISTRY` is the shared source of truth for palette metadata and
defaults, so the composer and the Documents page cannot disagree about what a
parser is.

## Build order

### Slice A — one parser, whole vertical (LlamaParse)

LlamaParse chosen: hosted, no local ML deps, easiest to run headless in
CI/verification.

- **Backend:** three-way `ToolDefinition` contract (§1); `functools.partial`
  config binding (§2); register `parse.llamaparse`; refactor `parse_node` to
  read bound `config`; **migrate `export_node`** to the bound-config signature in
  the same pass (the other consumer of the broken `node_config`), so the engine
  is never half-migrated.
- **Frontend:** `NodeConfigPanel` dispatcher rendering `LlamaParseConfig`; node
  default config on drop; `AgentRunForm` with `SourceDocumentBrowser`; save
  serializes `node.config`.
- **Ships as:** drop a LlamaParse node → configure in its real panel → pick a
  file → Run → parsed document. Definition 1 works for one parser; all
  architectural risk retired.

### Slice B — fan out the parsers

- Register `parse.simple`, `parse.docling`, `parse.landing_ai`,
  `parse.custom_pipeline`; wire their panels into the dispatcher map.
- Low risk — pure repetition of Slice A's pattern.
- **Ships as:** the full "Parsing" section of Definition 1.

### Later specs (out of scope here)

- Definition 2: chaining + edge validation from the contract.
- Additional categories: classify, index, query.
- Definition 3: orchestrator workflow.
- Ambitious target: deploy a workflow/agent as a custom API endpoint.

## Acceptance criteria (this spec: Slices A + B)

1. `ToolDefinition` exposes `config_schema` / `runtime_inputs` / `outputs` /
   `config_panel`; `GET /agent/tools` reflects the split.
2. Per-node config is bound via `functools.partial(node_fn, config=...)`;
   `parse_node` and `export_node` read bound `config`, not shared state keys; two
   same-tool nodes in one graph carry independent config.
3. Design-time config does not appear in persisted run state.
4. The `parsing` category lists one node per parser; each node renders **the
   real workbench config panel** for its parser.
5. The run form is auto-derived (`⋃ runtime_inputs − ⋃ outputs`), renders real
   workbench pickers, and starts a run via the generic
   `POST /agent/projects/{id}/runs`.
6. A one-node LlamaParse agent runs end-to-end from the composer (Slice A); all
   five parser nodes are available and functional (Slice B).
7. Existing bespoke entrypoints still work; app builds; backend tests pass;
   `npm run build` succeeds with no dangling imports.

## Risks / open questions

- **Inline execution cost.** The engine runs the graph inline in the request; a
  large parse could make the run request slow. Inherited from the existing
  engine; candidate for moving agent runs to a background task later. Not
  addressed here.
- **BYOK key resolution** stays inside the node (resolved from `user_id`, never
  persisted), as in the current `parse_node` via `parsing_bridge`. The generic
  run path loses the entrypoint's upfront key pre-validation, so a missing key
  surfaces as a failed run rather than a clean 400 — acceptable for v1; a generic
  pre-flight validation hook is future work.
- **`representation_kind`** is treated as design-time config (with a default),
  not a runtime input — it describes what the node produces, not per-run data.
- **Config-schema validation depth** — v1 validates presence/shape against
  `config_schema`; it does not deeply validate parser-specific option
  combinations (the panels already prevent most invalid combinations client-side).
```
