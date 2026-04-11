# Remove Old Agents, Rename Flows to Agents

**Date:** 2026-04-11
**Status:** Approved

## Context

The codebase has two overlapping features under the "agent" umbrella:

1. **Old agents** — A hardcoded receipt processing prototype (AgentConfig, AgentReceipt, agent types registry, receipt pipeline). This was a test implementation and is no longer needed.
2. **Flows** — A generic graph-based execution engine (FlowDefinition, FlowRun, flow composer UI). This is the real system and will evolve to support autonomous multi-turn agents.

The "flows" naming was used during development because "agents" was already taken by the prototype. With the prototype removed, the generic engine should be renamed to "agents" since flows are really single-turn agents, and the system will grow to include more complex agent topologies.

## What Gets Deleted

### Backend

| Category | Files |
|----------|-------|
| Models | `models/agent_config.py`, `models/agent_receipt.py` |
| Repositories | `repositories/agent_config_repository.py`, `repositories/agent_receipt_repository.py` |
| Services | `services/agent/service.py` (receipt pipeline), `services/agent/nodes.py` (receipt nodes), `services/agent/extract_run_service.py` (extraction wrapper) |
| Tools | `services/agent/tools/` directory (extract, review, export tools) |
| Types registry | `services/agent/types/` directory |
| Schemas | Agent config, receipt, and type schemas from `schemas/agent.py` |
| Router endpoints | Agent config, type, and receipt endpoints from `routers/agent.py` |
| Graph helpers | `build_receipt_graph()` and `RECEIPT_PROCESSING_FLOW` from `services/agent/graph.py` |

### Frontend

| Category | Files |
|----------|-------|
| Components | `AgentSetup.tsx`, `AgentFlowGraph.tsx`, `ReceiptDetail.tsx`, `ReceiptList.tsx`, `ReceiptProcessForm.tsx`, `ReceiptReviewForm.tsx`, `StatusBadge.tsx` |
| Hooks | `useAgentConfigs.ts`, `useAgentReceipt.ts`, `useAgentReceipts.ts` |
| Pages | `AgentPage.tsx`, `AgentReceiptPage.tsx` |
| API functions | Agent config, receipt, and type functions from `api/agent.ts` |
| Types | Agent config, receipt, and type definitions from `types/agent.ts` |

### Database

New migration to:
- Drop `agent_configs` table
- Drop `agent_receipts` table

## What Gets Renamed

All `flow`/`Flow` references become `agent`/`Agent`.

### Backend

| From | To |
|------|----|
| `models/flow_definition.py` (class `FlowDefinition`) | `models/agent_definition.py` (class `AgentDefinition`) |
| `models/flow_run.py` (class `FlowRun`) | `models/agent_run.py` (class `AgentRun`) |
| `repositories/flow_definition_repository.py` | `repositories/agent_definition_repository.py` |
| `repositories/flow_run_repository.py` | `repositories/agent_run_repository.py` |
| `services/agent/flow_run_service.py` (class `FlowRunService`) | `services/agent/agent_run_service.py` (class `AgentRunService`) |
| `services/agent/state.py` — `GenericFlowState` | `AgentState` |
| `services/agent/graph.py` — `build_graph_from_definition` | `build_agent_graph` |
| Schemas: `FlowDefinitionCreate`, `FlowRunResponse`, etc. | `AgentDefinitionCreate`, `AgentRunResponse`, etc. |
| Router: `/flows/` endpoints | `/definitions/` endpoints (under `/api/v1/agent/`) |

### Frontend

| From | To |
|------|----|
| `components/agent/FlowList.tsx` | `AgentList.tsx` |
| `components/agent/FlowRunList.tsx` | `AgentRunList.tsx` |
| `components/agent/FlowRunDetail.tsx` | `AgentRunDetail.tsx` |
| `components/agent/FlowRunInputForm.tsx` | `AgentRunInputForm.tsx` |
| `components/agent/FlowComposer.tsx` | `AgentComposer.tsx` |
| `components/agent/flow/` directory | `components/agent/composer/` directory |
| `hooks/useFlowComposer.ts` | `useAgentComposer.ts` |
| `hooks/useFlowDefinitions.ts` | `useAgentDefinitions.ts` |
| `hooks/useFlowRun.ts` | `useAgentRun.ts` |
| `hooks/useFlowRuns.ts` | `useAgentRuns.ts` |
| `pages/FlowComposerPage.tsx` | `AgentComposerPage.tsx` |
| `pages/FlowRunsPage.tsx` | `AgentRunsPage.tsx` |
| `pages/FlowRunDetailPage.tsx` | `AgentRunDetailPage.tsx` |
| Types: `FlowDefinition`, `FlowRun`, etc. | `AgentDefinition`, `AgentRun`, etc. |
| API: `listFlowDefinitions`, etc. | `listAgentDefinitions`, etc. |

### Routes (App.tsx)

| Path | Page |
|------|------|
| `/agent` | Agent list (formerly FlowList on AgentPage) |
| `/agent/new` | Agent composer (new) |
| `/agent/:agentId` | Agent composer (edit) |
| `/agent/:agentId/runs` | Agent runs list |
| `/agent/runs/:runId` | Agent run detail |

### Navigation

- Label stays "Agent", icon stays `Bot`
- Remove receipt-related sub-routes

### Database

New migration to:
- Rename `flow_definitions` table to `agent_definitions`
- Rename `flow_runs` table to `agent_runs`

## What Stays As-Is

- `services/agent/checkpointer.py` — LangGraph checkpointer (already correct naming)
- `app.state.agent_checkpointer` in `main.py`
- `services/agent/` directory name (correct now)

## Non-Goals

- No functional changes to the composer, execution engine, or run management
- No UI/UX changes beyond the naming
- No new features added as part of this work
