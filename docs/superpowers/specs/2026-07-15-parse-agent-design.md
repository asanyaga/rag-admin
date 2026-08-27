# Parse Agent — v1 Design (the Observability Spine)

> **⚠️ Superseded (2026-08-26):** The parse-agent stack has been retired. Parsing
> is now a tool in the agents feature — see
> `docs/superpowers/specs/2026-08-26-parse-tool-design.md`. This document is kept
> for historical context only.

- **Date:** 2026-07-15
- **Status:** Design — pending review
- **Author:** Brainstormed with Claude

## Objective

Build the first slice of a **parse agent**: a file upload triggers a background
run that parses the document, and the frontend shows a **readable, polled-live
trace of what the run did.**

This is deliberately a *learning-first* build. Two secondary objectives shape
every decision below:

1. **Understand agent + LangGraph primitives from the ground up** — hand-wire the
   graph rather than use `create_agent` / a data-driven builder, so the eventual
   "automagic" composition is grounded in fundamentals.
2. **Avoid framework lock-in** — decide whether rolling our own agent framework is
   worthwhile, and structure v1 so LangGraph stays a swappable execution detail.

## The agency analysis (why this shape)

"Agent" is a spectrum: deterministic **workflow** → **hybrid** (one decision
point) → **fully LLM-driven agent**. Agency is a cost — it buys handling of
situations you couldn't enumerate at design time, and charges latency, money,
nondeterminism, and debuggability.

Parsing's decision space is **small and closed**: finite parsers, finite configs,
*measurable* quality. That's the opposite of where LLM agency pays off. The only
genuine runtime decision is *"this parse is poor — escalate / retry / fall back /
flag?"*, and even that is a small enumerable action set.

**Conclusion:** the parse agent is a deterministic pipeline with (eventually) **one
decision point**. Put agency *at the decision*, not the pipeline. **v1 contains no
agency at all** — it is the deterministic spine plus the observability that makes
every future decision visible. The quality loop, human review, and any LLM policy
bolt onto this spine without reshaping it.

## Goals / Non-goals

**v1 goals**
- Upload a file → background parse run → readable polled-live trace on the frontend.
- Reuse the existing parse stack (`ParsingService`) for the actual parse.
- Establish the **step-log projection boundary** (the anti-lock-in seam).
- Hand-wire the graph with raw LangGraph primitives to learn them.

**Non-goals (deferred, but designed-for)**
- Escalation / quality loop, human review (`interrupt`), LLM policy.
- Ground-truth scoring (TEDS et al.).
- Streamed/SSE transport (v1 is polled).
- Durable task queue (v1 runs in-process).
- Data-driven / composable graph builder.
- Non-upload triggers (directory / drive watchers).

## Background: what already exists

- **A LangGraph POC** (treated as prior art, *not* reused directly for v1): a
  data-driven `build_agent_graph`, a `ToolDefinition` registry, and
  `AgentRunService` with an `AsyncPostgresSaver` checkpointer and `interrupt`-based
  human review. Built to prove data-driven composable graphs are possible.
- **A mature parse stack:** `ParsingService` (sha256 dedup, same-config run reuse,
  persistence of `SourceDocument` / `ParseRun` / `ParsedDocument`), runners for
  `llamaparse` / `landingai` / `simple` / `custom_pipeline`, and a `parser_eval`
  framework with quality scorers (TEDS, table matching, text).

## How this fits the existing parse flow (important)

Parsing already works today, and the agent is a **layer above it**, not a replacement:

- `POST /documents` (upload, `use_cdm=True`) → `DocumentService.initiate_upload` →
  `ParsingService.ensure_source_document` (store bytes by sha256) + create project
  `Document` (status `processing`) → **returns immediately**.
- The router dispatches **`process_cdm_parsing(...)` as a FastAPI background task** →
  `ParsingService.parse_and_persist(...)` → creates a **`ParseRun`** + **`ParsedDocument`**
  (CDM artifacts) → sets `Document` status `ready`/`failed`.
- `GET /parse-runs/{id}`, `/parse-runs/{id}/parsed-document`, `/parse-runs/{id}/raw-payload`,
  `DELETE /parse-runs/{id}` are the **read/delete** endpoints backing the results viewer.
  **There is no `POST /parse-runs`.**

Consequences for this design:

1. **`ParseRun` already means "one parser execution"** (SourceDocument → ParseRun →
   ParsedDocument). The agent's run is a *higher-level* thing that *contains* a ParseRun.
   We must **not** overload `/parse-runs`. → the agent's resource is **`/parse-agent-runs`**.
2. **Background parsing already exists** (`process_cdm_parsing` — a hand-rolled, single-step
   version of the engine here). The agent's `parse` node **calls the same
   `ParsingService.parse_and_persist`**, producing a real `ParseRun` + `ParsedDocument`,
   identical to today. The agent's value-add over `process_cdm_parsing` is exactly
   orchestration + trace (and later, the decision loop).
3. **The results-viewer handoff already has a home:** "open in results viewer ↗" →
   existing `GET /parse-runs/{parse_run_id}/parsed-document`. No new viewer work.

```
parse-agent-run  (new: orchestration + trace)
  ├─ step "parse"        ──calls ParsingService.parse_and_persist──▶  ParseRun + ParsedDocument (existing)
  └─ step "health_check"
  detail "open in results viewer ↗"  ──▶  GET /parse-runs/{parse_run_id}/...  (existing endpoint)
```

## Architecture overview

```
POST /parse-agent-runs (file, config)
  → ensure_source_document(bytes)        # ParsingService, sha256 dedup (as DocumentService does today)
  → start_parse_run(source, config, …)   # trigger-agnostic entry point
       → create parse_agent_run (running)
       → spawn in-process background task → returns 202 { run_id }

[background: ParseAgentRunEngine]
  compiled = build_parse_graph()          # hand-wired, 2 nodes
  async for mode, chunk in compiled.astream(state, cfg,
                        stream_mode=["updates","custom","debug"]):
      INSERT parse_agent_run_step(...)    # <-- projection boundary
      #  parse node internally called ParsingService.parse_and_persist → ParseRun + ParsedDocument
  UPDATE parse_agent_run.status = completed | failed

Frontend  ──poll every ~1s while running──▶  GET /parse-agent-runs/{id}
                                             → { run, steps[], graph_nodes[] }
detail panel "open in results viewer" ─────▶  GET /parse-runs/{parse_run_id}/parsed-document  (existing)
```

## Components

### 1. Trigger entry point — `start_parse_run(source, config, project_id, user_id) → run_id`

The upload router is **caller #1**, not the trigger itself. A future directory/
drive watcher calls the *same* function. Nothing downstream knows the origin.
This one seam keeps the trigger swappable (an explicit v1 requirement).

### 2. The graph (v1, hand-wired)

Two nodes, linear, built with raw LangGraph primitives (`add_node` / `add_edge`)
— chosen for pedagogy over the data-driven builder:

```
START ──▶ parse ──▶ health_check ──▶ END
```

- **`parse`** — calls the **existing** `ParsingService.parse_and_persist(...)`, exactly as
  `process_cdm_parsing` does today, producing a real `ParseRun` + `ParsedDocument`. Writes
  `parse_run_id`, `parsed_document_id`, `page_count` into state. The `parse_run_id` is what
  the trace detail panel links to (existing results-viewer endpoints).
- **`health_check`** — a **reference-free** quality signal (text non-empty? any
  `failed_pages`? sane block count?). Needs no ground truth. Writes
  `quality_signal` into state. This is the stub where the future decision point
  will live.

**State** is a `TypedDict(total=False)` schema (`ParseAgentState`) declaring all keys below. (A bare `dict` schema does NOT work here: in langgraph 1.1.6 `StateGraph(dict)` is a single whole-state `LastValue` channel, so partial-delta node returns overwrite the whole state — the POC only survives this by spreading `{**state}` on every node return. A TypedDict gives per-key channels so partial deltas merge.) Keys:
`file_path`, `source_document_id`, `project_id`, `representation_kind`, parser
`config`, and node outputs `parse_run_id`, `parsed_document_id`, `page_count`,
`quality_signal`.

**Design-for-evolution:** even though we hand-wire, each node is a **contract'd
unit** (slug, `input_keys`, `output_keys`) like the POC's `ToolDefinition`.
Hand-wiring and the future data-driven builder are two *assemblers* over the same
node set — only graph assembly changes, never the nodes, state, engine, or trace.

**Cleanup vs POC:** nodes return **only their declared `output_keys`** (a minimal
delta), not `{**state, ...}`. The spread pattern muddies per-node deltas and makes
traces unreadable.

### 3. Execution engine — `ParseAgentRunEngine` (new)

A **new, purpose-built engine**, not a modification of `AgentRunService`.

- Runs the graph in an **in-process background task** (`asyncio.create_task`).
- Consumes `astream(stream_mode=["updates","custom","debug"])` and writes one
  `parse_agent_run_step` per event.
- Opens its own DB session inside the task (as `process_cdm_parsing` already does —
  long parsers must not run on the request's DB connection).

> **BYOK constraint:** the `parse` node needs **project parser API keys** resolved and
> parser **clients constructed inside the task** (LlamaParse / LandingAI), exactly as
> `process_cdm_parsing` does — keys are never stored in `config` or returned in responses.
> The engine must carry the resolved keys / a client factory into the background task.

> **Why not reuse `AgentRunService`:** it runs `ainvoke` *inside the HTTP request*
> and persists *only terminal state* — the two exact gaps this design fixes.
> Building fresh avoids regressing the extraction agent; extraction can migrate
> onto this engine later ("converge later," not "fork forever").

> **Known limitation:** an in-process task means a server restart mid-run
> **orphans the run** (stuck `running`). Acceptable for a single-dev prototyping
> tool. Fix (durable queue, or a startup reconciler that fails stale runs) is
> deferred.

### 4. Persistence — the projection boundary (the lock-in answer)

Two tables **we own**:

- **`parse_agent_run`** — `id`, `project_id`, `source_document_id`, `status`,
  `started_at`, `finished_at`, `error`.
- **`parse_agent_run_step`** (append-only) — `id`, `run_id`, `seq`, `node`,
  `phase` (`start` | `progress` | `end` | `error`), `status`, `input_keys`,
  `output_keys`, `state_delta` (jsonb), `message`, `duration_ms`, `created_at`.

> **Naming / convergence tension (flagged, not solved in v1):** there are now three
> "run" concepts — CDM **`ParseRun`** (one parser execution), POC **`agent_run`**
> (extraction agent, `agent_definition`-driven, terminal-state), and this design's
> **`parse_agent_run`**. v1 keeps `parse_agent_run` separate for a clean build (the POC
> `agent_run` is FK-bound to `agent_definition`, which v1's hand-wired graph doesn't have).
> Unifying the POC `agent_run` with `parse_agent_run` is a **convergence target** for when
> the data-driven builder lands (see Evolution) — not v1 work.

> **Principle — the checkpointer is LangGraph's private memory; the trace is *our*
> domain model.** The frontend **never reads LangGraph's checkpoint tables**. The
> engine *projects* each run into `parse_agent_run_step`, shaped for the UI. If we later
> replace LangGraph with a hand-rolled runner, the step-log schema, the polling
> API, and the entire frontend are unchanged — we rewrite one file (the engine).
> This is the concrete meaning of "avoid lock-in": not abstracting everything,
> just drawing one clean projection boundary at the framework's edge.

### 5. API

- `POST /parse-agent-runs` — multipart file + parser config → **202** `{ run_id }`
  (returns immediately; parse happens in the background). Distinct from the existing
  read/delete-only `/parse-runs` (CDM) router.
- `GET /parse-agent-runs/{run_id}` — `{ run, steps[], graph_nodes[] }`.
  `graph_nodes` is the static node list for the graph strip.
- Project scoping / auth follow existing router patterns (project-scoped; `ParseRun`
  already carries `project_id`).

### 6. Frontend — the run detail page

Layout (validated via mockups):

- **Graph strip (top)** — nodes colored by state; the natural home for future
  branches/loops (escalate, human-review) so control flow stays *visible*.
- **Timeline (below)** — the run's story; each step shows read/wrote keys and
  nested `progress` messages; selected step highlighted.
- **Detail panel (on select)** — full in/out values, meta (parser version, cost),
  folds for raw payload.

**Polling:** `GET /parse-agent-runs/{id}` every ~1s while `status == running`; stop on
terminal status.

**Results-viewer handoff (validated):** the detail panel **links out** to the
existing parse-**results** viewer (`open parsed_document ↗`) rather than
re-rendering parsed content. Trace = "what the agent did"; results viewer = "what
the parse produced." Clean separation, reuses existing UI.

## Build-vs-buy / lock-in verdict

**Do not roll your own framework now.** For the current shape (deterministic
pipeline + one future decision point over a small closed action space), LangGraph's
`StateGraph` / `add_conditional_edges` / checkpointer / `interrupt` are a good fit,
and the surface we depend on is tiny. Keep LangGraph behind (a) the thin
`ParseAgentRunEngine` and (b) the `parse_agent_run_step` projection boundary. Re-evaluate
rolling our own only if LangGraph's constraints (e.g. the `dict`-state workaround,
checkpointer coupling) start costing more than the boundary saves. **Less agency =
less lock-in**, and v1 has none.

## Evolution path (design-for, not build-now)

- **v2 — quality loop:** `health_check` → conditional route → `escalate` (retry a
  different parser/config). During prototyping the **human is the policy** via
  `interrupt`; watching those calls across many docs reveals the heuristic to
  codify into the router.
- **v3 — human review:** a `human-review` node using `interrupt`; the timeline
  pauses (`waiting_for_input`), resumes via `Command(resume=…)`. Review UI likely
  reuses the parse-results viewer for the vibe-check.
- **v4 — data-driven graphs:** the builder consumes the same contract'd node
  registry; graphs become user-composable. Nodes/state/engine/trace unchanged.
- **Scoring:** `parser_eval` scorers (TEDS) need a **reference** and cannot serve
  the runtime decision loop directly; runtime uses reference-free signals (v1) or
  an LLM-judge (later).

## Architectural callouts (not-ready-to-plug-in / refactoring)

1. **New engine required** — `AgentRunService` is synchronous-in-request and
   terminal-state-only; unsuitable for polled-live tracing.
2. **Node return convention** — the POC's `{**state, ...}` spread must become
   minimal `output_keys` deltas for readable traces.
3. **Two divergent parse abstractions exist** — `ports/document_parsing.py`
   (`DocumentParser` ABC + `ParseOutput`) vs. `ParsingService`'s `_RUNNERS`
   callable dict. The parse agent uses **`ParsingService`**; the ABC appears
   unused/legacy. Flag for reconciliation (out of scope for v1).

## Known limitations (v1)

- Orphaned runs on server restart (see §3).
- No new authorization model; reuse existing project scoping.
- A terminal parse failure (`ParseFailedError` from `ParsingService.parse_and_persist`) marks the
  `parse_agent_run` **failed** at the run level but produces **no per-step trace**, and
  `parse_run_id` is not captured on failure. Per-step failure/quality representation is deferred
  to the v2 escalation/decision loop, where failure signaling is designed.
- The `doc is None` reuse edge (a succeeded/partial run whose parsed-document row is missing) is
  guarded to fail the run with a legible message rather than crash.

## Open question deferred to the plan

- **Relationship to the project `Document`.** Today's upload creates *both* a
  content-addressed `SourceDocument` and a user-facing project `Document`
  (`Document.source_document_id` links them). A parse-agent run needs the
  `SourceDocument` (to parse) and a `project_id` (for scoping/`ParseRun`), but does
  **not** strictly need a `Document`. v1 default: operate at **SourceDocument +
  project** level and do not create a `Document`. Revisit if the debugging tool needs
  to surface agent runs inside the existing documents UI.
