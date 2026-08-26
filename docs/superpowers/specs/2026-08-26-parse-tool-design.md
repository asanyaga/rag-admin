# Parse Tool in the Agents Feature — Design

- **Date:** 2026-08-26
- **Status:** Design — pending review
- **Author:** Brainstormed with Claude
- **Supersedes:** the `parse-agent` learning stack (see [2026-07-15-parse-agent-design.md](2026-07-15-parse-agent-design.md)), which this work retires.

## Objective

Add **parsing as a first-class tool** in the composable agents feature, so a
document can be parsed as one node in an agent graph (composable with
`extract` → `human-review` → `export`) and also triggered on its own. In the
same change, **retire the standalone `parse-agent` learning stack**, whose
composition/observability role is now fully served by the agents engine.

## Background: two stacks, one keeper

Two parallel implementations exist today:

1. **Agents feature** (`services/agent/`) — the keeper. A data-driven LangGraph
   builder (`build_agent_graph`), a `ToolDefinition` registry, `AgentRunService`
   with an `AsyncPostgresSaver` checkpointer and `interrupt`/resume for
   human-in-the-loop, run persistence, and a drag-drop visual composer on the
   frontend. Tools today: `llamaextract`, `human-review`, `export`.

2. **Parse-agent** (`services/parse_agent/`) — a deliberately separate,
   pedagogical build (hand-wired graph, own run tables, own router, own trace
   UI, TypedDict per-key channels). It duplicates the composition and
   observability the agents feature already provides. **It is retired here.**

The parse-agent is not transferred structurally. Three things from it *are*
carried forward as reference:

- The `ParsingService` invocation (`parse_and_persist`) and the metrics pulled
  from its result — reused in the new `parse_node`.
- The BYOK key-resolution + source-document setup pattern from its router — the
  new entrypoint reuses the *same* shared helpers (`_resolve_parser_key`,
  `ensure_source_document`, `get_parsing_service`) rather than copying code.
- The `health_check` quality-signal idea — deferred to a future separate
  `quality-check` tool (the natural home for the one decision point), not built
  here.

## Scope

**In scope**
- A composable `parse` tool (node + `ToolDefinition`) in the agents feature.
- A domain entrypoint (`ParseRunService` + `POST /agent/parse/.../runs`) that
  seeds an agent run from an existing `source_document_id`, mirroring
  `ExtractRunService` / the extract entrypoint.
- Frontend: a `parsing` tool category in the palette + a parse input form for
  the standalone entrypoint.
- Full removal of the `parse-agent` stack (backend, DB tables, frontend).

**Out of scope (deferred)**
- Quality/escalation loop, LLM policy, `quality-check` tool.
- Fixing per-node `config_schema` plumbing generically (see Known Gap below).
- Upload-based parse triggering from within the agent UI (entrypoint takes an
  already-uploaded `source_document_id`; uploading lives on the existing
  SourceDocuments page).

## Design

### The `parse` tool

`services/agent/tools/parse.py`:

```
ToolDefinition(
    slug="parse",
    name="Parse",
    category="parsing",           # new category
    description="Parse a source document into a ParsedDocument",
    input_keys=["source_document_id", "representation_kind", "parse_config",
                "project_id", "user_id"],
    output_keys=["parse_run_id", "parsed_document_id", "page_count",
                 "text_len", "failed_page_count", "block_count"],
    config_schema={ parser: enum, representation_kind: string },
    node_fn=parse_node,
)
```

Registered in `tools/__init__._ensure_loaded()` alongside the others.

### `parse_node` (`services/agent/nodes.py`)

Follows the `export_node` shape (opens its own `AsyncSessionLocal()`), because
the agents engine runs the graph **inline within the request** — the node
executes during `AgentRunService.start_run`, not in a background task.

Behaviour:
1. Open a session. Load the `SourceDocument` by `state["source_document_id"]`;
   derive `file_path = source.storage_uri`. Build the `SourceDocument` CDM.
2. Resolve BYOK parser keys via the shared `_resolve_parser_key(db,
   state["user_id"], parser)` helper — **keys are resolved inside the node from
   `user_id`, never carried in state** (so they are never persisted in the run's
   JSON state). Build `ParsingService` with the resolved clients + storage.
3. Call `parsing_service.parse_and_persist(source=…, file_path=…,
   representation_kind=…, config=…, project_id=…)`.
4. Return **full merged state** (`return {**state, …}`) with `parse_run_id`,
   `parsed_document_id`, and the metrics. `current_step` advances to the next
   logical step (`"extract"` when composed, else `"done"`).

**Critical convention:** this feature's `AgentState = dict` and every node
returns the *entire* merged state. `parse_node` must do `return {**state, …}`.
Copying parse-agent's partial-delta return here would silently drop accumulated
state (that pattern only works with parse-agent's per-key TypedDict channels).

### Entrypoint: `ParseRunService` + router

`services/agent/parse_run_service.py`, mirroring `ExtractRunService`:

- `start_parse_run(project_id, agent_definition_id, source_document_id,
  parser, representation_kind, parse_config, user_id)`
- Validates the `SourceDocument` exists, builds `initial_state`
  (`source_document_id`, `representation_kind`, `parse_config` seeded with
  `parser`, `project_id`, `user_id`, `current_step="parse"`), delegates to
  `AgentRunService.start_run`.

Router: `POST /agent/parse/projects/{project_id}/runs` with
`StartParseRunRequest`, mirroring `start_extract_run`.

### Parse parameters and the per-node config gap

**Known gap (documented, not fixed here):** `config_schema` values are surfaced
by the composer's `NodeConfigPanel`, but nothing writes them into the running
graph — `export_node` reads `state.get("node_config", {})`, which no code
populates, and there is only one shared `node_config` key (can't distinguish
nodes in a multi-node graph). Per-node config is therefore **not** reliably
plumbed today.

To avoid inheriting a broken seam, v1 supplies parse parameters (`parser`,
`representation_kind`, `parse_config`) through the **entrypoint into top-level
`initial_state` keys** — exactly how `extract` seeds `schema_definition` /
`extraction_config`. The `config_schema` on the tool still describes the
parameters (for palette display and future use), but the node reads them from
state. Properly plumbing per-node `config_schema` → node is separate future
work that benefits all tools.

### Frontend

- `ToolPalette.tsx`: add `parsing` to `categoryIcons` + `categoryColors`.
- Parse input form for the standalone entrypoint (source-document picker,
  parser select, representation_kind), mirroring `AgentRunInputForm` / the
  extract flow. Palette drag-drop, node rendering, and `NodeConfigPanel` work
  for free from `GET /agent/tools`.

### Retiring the parse-agent stack (same PR)

Self-contained — its router is the only trigger for `run_parse_agent`; nothing
else depends on it.

- **Backend delete:** `services/parse_agent/`, `routers/parse_agent_runs.py`,
  `repositories/parse_agent_run_repository.py`, `models/parse_agent_run.py`
  (+ remove `models/__init__.py` exports), `schemas/parse_agent_run.py`, the
  `parse_agent_runs` import + `include_router` in `main.py`, and
  `tests/**/parse_agent*` / `test_parse_agent_run_*`.
- **DB:** new Alembic migration dropping `parse_agent_run` +
  `parse_agent_run_steps`, chained onto current head.
- **Frontend delete:** `pages/ParseAgentRuns*`, `components/parse-agent/`,
  `hooks/useParseAgentRun*`, `api/parseAgent.ts`, `types/parseAgent.ts`, and the
  two `parse-agent` routes + imports in `App.tsx` (+ any nav link).
- **Docs:** mark the three `parse-agent` spec/plan files as superseded by this
  spec (retain for history).

## Acceptance criteria

1. `GET /agent/tools` includes a `parse` tool under a `parsing` category.
2. `parse` can be placed in an agent definition and executes: given a
   `source_document_id`, it runs `parse_and_persist` and writes `parse_run_id`
   + `parsed_document_id` + metrics into the run state (full-state merge; no
   accumulated keys dropped).
3. A `parse` → `extract` composed definition runs end-to-end, with the parsed
   output available to the downstream node.
4. `POST /agent/parse/projects/{id}/runs` starts a run from a
   `source_document_id` and returns an `AgentRunResponse`.
5. Parser API keys are resolved inside the node via `_resolve_parser_key`
   (user-scoped) and never appear in the persisted run state; the entrypoint
   pre-validates key presence so a missing key returns a clean 400 rather than a
   failed run.
6. The frontend palette shows the parse tool with a `parsing` icon/color, and a
   parse run can be started from the UI.
7. The entire `parse-agent` stack is removed; a migration drops its tables; the
   app builds, backend tests pass, and `npm run build` succeeds with no dangling
   imports/routes.

## Risks / open questions

- **BYOK in a graph node:** verified — `_resolve_parser_key(db, user_id,
  parser_type)` resolves **user-scoped** BYOK keys via `resolve_api_key(...)`
  and raises HTTP 400 when a required key is missing. `parse_node` resolves from
  `state["user_id"]` inside its own session (keys never persisted). Caveat:
  `AgentRunService.start_run` wraps execution in a broad `except Exception` that
  marks the run *failed*, so a missing-key `HTTPException` inside the node
  surfaces as a **failed run**, not a clean 400. Mitigation: the entrypoint
  (`ParseRunService`, request context) pre-validates key presence
  (resolve-and-discard) to return an upfront 400; the node still resolves for
  real. Extract, by contrast, uses global `settings.LLAMA_CLOUD_KEY`.
- **Inline execution cost:** the agents engine runs the graph inline in the
  request. A large parse could make `start_parse_run` slow/timeout, unlike the
  parse-agent's background task. Acceptable for v1; note as a candidate for
  moving agent runs to a background task later.
- **Per-node config gap** (above) — flagged, deferred.
```
