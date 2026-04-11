# Remove Old Agents, Rename Flows to Agents — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the hardcoded agent prototype (configs, receipts, types, tools, receipt pipeline) and rename all flow_*/Flow* references to agent_*/Agent* across the entire stack.

**Architecture:** This is a deletion + mechanical rename. The generic execution engine, composer UI, and LangGraph infrastructure stay functionally identical — only names change. Database tables get renamed via Alembic migration; old tables get dropped.

**Tech Stack:** Python/FastAPI/SQLAlchemy/Alembic (backend), React/TypeScript/Vite (frontend), PostgreSQL (database)

---

### Task 1: Backend — Delete Old Agent Models and Repositories

**Files:**
- Delete: `backend/app/models/agent_config.py`
- Delete: `backend/app/models/agent_receipt.py`
- Delete: `backend/app/repositories/agent_config_repository.py`
- Delete: `backend/app/repositories/agent_receipt_repository.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Delete agent config and receipt model files**

```bash
rm backend/app/models/agent_config.py
rm backend/app/models/agent_receipt.py
```

- [ ] **Step 2: Delete agent config and receipt repository files**

```bash
rm backend/app/repositories/agent_config_repository.py
rm backend/app/repositories/agent_receipt_repository.py
```

- [ ] **Step 3: Update models/__init__.py — remove old imports, keep flow models**

Remove these imports from `backend/app/models/__init__.py`:
```python
from app.models.agent_config import AgentConfig
from app.models.agent_receipt import AgentReceipt, AgentReceiptStatus
```

Keep these (they'll be renamed in Task 3):
```python
from app.models.flow_definition import FlowDefinition
from app.models.flow_run import FlowRun, FlowRunStatus
```

Also remove `AgentConfig`, `AgentReceipt`, `AgentReceiptStatus` from the `__all__` list if present.

- [ ] **Step 4: Commit**

```bash
git add -A backend/app/models/ backend/app/repositories/agent_config_repository.py backend/app/repositories/agent_receipt_repository.py
git commit -m "chore: delete old agent config and receipt models and repositories"
```

---

### Task 2: Backend — Delete Old Agent Services, Tools, Types, and Nodes

**Files:**
- Delete: `backend/app/services/agent/service.py`
- Delete: `backend/app/services/agent/nodes.py`
- Delete: `backend/app/services/agent/extract_run_service.py`
- Delete: `backend/app/services/agent/tools/` (entire directory)
- Delete: `backend/app/services/agent/types/` (entire directory)
- Modify: `backend/app/services/agent/graph.py` — remove `build_receipt_graph` and `RECEIPT_PROCESSING_FLOW`

- [ ] **Step 1: Delete old service files**

```bash
rm backend/app/services/agent/service.py
rm backend/app/services/agent/nodes.py
rm backend/app/services/agent/extract_run_service.py
rm -rf backend/app/services/agent/tools/
rm -rf backend/app/services/agent/types/
```

- [ ] **Step 2: Clean up graph.py — remove receipt-specific code**

In `backend/app/services/agent/graph.py`, remove:
- The `RECEIPT_PROCESSING_FLOW` constant (dict with hardcoded receipt nodes/edges)
- The `build_receipt_graph()` function
- The `route_after_review()` function (receipt-specific router)
- The import of `AgentState` (receipt-specific state, will be replaced in Task 3)

Keep:
- The `_routers` registry (`register_router`, `get_router`)
- The `build_graph_from_definition()` function (this is the generic engine)
- The import of `get_tool` from tools registry

Note: `get_tool` import will break after tools/ deletion — that's handled in Task 3 when we restructure. For now, leave the import but it will reference the deleted module. We'll fix the full import chain in Task 3.

- [ ] **Step 3: Commit**

```bash
git add -A backend/app/services/agent/
git commit -m "chore: delete old agent services, tools, types, and receipt pipeline"
```

---

### Task 3: Backend — Rename Flow Models to Agent

**Files:**
- Rename: `backend/app/models/flow_definition.py` → `backend/app/models/agent_definition.py`
- Rename: `backend/app/models/flow_run.py` → `backend/app/models/agent_run.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Rename flow_definition.py → agent_definition.py and update class names**

```bash
mv backend/app/models/flow_definition.py backend/app/models/agent_definition.py
```

In `backend/app/models/agent_definition.py`:
- Rename class `FlowDefinition` → `AgentDefinition`
- Change `__tablename__ = "flow_definitions"` → `__tablename__ = "agent_definitions"`
- Update unique constraint name: `uq_flow_definitions_project_name` → `uq_agent_definitions_project_name`
- Update index name: `ix_flow_definitions_project_id` → `ix_agent_definitions_project_id`

- [ ] **Step 2: Rename flow_run.py → agent_run.py and update class names**

```bash
mv backend/app/models/flow_run.py backend/app/models/agent_run.py
```

In `backend/app/models/agent_run.py`:
- Rename enum `FlowRunStatus` → `AgentRunStatus`
- Rename class `FlowRun` → `AgentRun`
- Change `__tablename__ = "flow_runs"` → `__tablename__ = "agent_runs"`
- Change `flow_definition_id` column → `agent_definition_id`, FK target → `agent_definitions.id`
- Rename relationship `flow_definition` → `agent_definition`
- Update enum name in DB: `flow_run_status` → `agent_run_status`
- Update all index names from `ix_flow_runs_*` → `ix_agent_runs_*`

- [ ] **Step 3: Update models/__init__.py**

Replace the flow imports:
```python
# Old
from app.models.flow_definition import FlowDefinition
from app.models.flow_run import FlowRun, FlowRunStatus

# New
from app.models.agent_definition import AgentDefinition
from app.models.agent_run import AgentRun, AgentRunStatus
```

Update `__all__` accordingly.

- [ ] **Step 4: Commit**

```bash
git add -A backend/app/models/
git commit -m "refactor: rename Flow models to Agent (AgentDefinition, AgentRun)"
```

---

### Task 4: Backend — Rename Flow Repositories to Agent

**Files:**
- Rename: `backend/app/repositories/flow_definition_repository.py` → `backend/app/repositories/agent_definition_repository.py`
- Rename: `backend/app/repositories/flow_run_repository.py` → `backend/app/repositories/agent_run_repository.py`

- [ ] **Step 1: Rename and update flow_definition_repository.py**

```bash
mv backend/app/repositories/flow_definition_repository.py backend/app/repositories/agent_definition_repository.py
```

In `backend/app/repositories/agent_definition_repository.py`:
- Rename class `FlowDefinitionRepository` → `AgentDefinitionRepository`
- Update import: `from app.models.agent_definition import AgentDefinition`
- Replace all `FlowDefinition` references with `AgentDefinition`
- Rename param `flow_id` → `agent_id` in `get_by_id`, `update`, `delete`

- [ ] **Step 2: Rename and update flow_run_repository.py**

```bash
mv backend/app/repositories/flow_run_repository.py backend/app/repositories/agent_run_repository.py
```

In `backend/app/repositories/agent_run_repository.py`:
- Rename class `FlowRunRepository` → `AgentRunRepository`
- Update imports: `AgentRun`, `AgentRunStatus`, `AgentDefinition`
- Replace all `FlowRun` → `AgentRun`, `FlowRunStatus` → `AgentRunStatus`
- Rename param `flow_definition_id` → `agent_definition_id`
- Rename param `run_id` stays as-is (it's generic)
- Rename method `list_by_flow` → `list_by_agent_definition`

- [ ] **Step 3: Commit**

```bash
git add -A backend/app/repositories/
git commit -m "refactor: rename Flow repositories to Agent"
```

---

### Task 5: Backend — Rename Flow Service and State

**Files:**
- Rename: `backend/app/services/agent/flow_run_service.py` → `backend/app/services/agent/agent_run_service.py`
- Modify: `backend/app/services/agent/state.py`
- Modify: `backend/app/services/agent/graph.py`

- [ ] **Step 1: Rename and update flow_run_service.py**

```bash
mv backend/app/services/agent/flow_run_service.py backend/app/services/agent/agent_run_service.py
```

In `backend/app/services/agent/agent_run_service.py`:
- Rename class `FlowRunService` → `AgentRunService`
- Update imports to use `AgentRunRepository`, `AgentDefinitionRepository`, `AgentRun`, `AgentRunStatus`, `AgentRunResponse`, `AgentRunListItem`
- Rename param `flow_run_repo` → `agent_run_repo`, `flow_def_repo` → `agent_def_repo`
- Rename internal references: `flow_definition_id` → `agent_definition_id`
- Rename `build_graph_from_definition` → `build_agent_graph` in the call
- Update `_make_json_safe` helper — stays as-is (it's generic)
- Update all schema references: `FlowRunResponse` → `AgentRunResponse`, `FlowRunListItem` → `AgentRunListItem`

- [ ] **Step 2: Update state.py**

In `backend/app/services/agent/state.py`:
- Remove `AgentState` TypedDict (receipt-specific, no longer used)
- Rename `GenericFlowState = dict` → `AgentState = dict`

The file should become:
```python
"""State type for agent graph execution."""

AgentState = dict
```

- [ ] **Step 3: Update graph.py**

In `backend/app/services/agent/graph.py`:
- Rename function `build_graph_from_definition` → `build_agent_graph`
- Update import of state type: `from app.services.agent.state import AgentState`
- Fix the tools import — since `tools/` directory was deleted, the `get_tool` function needs to be addressed. Check if `build_agent_graph` uses `get_tool()` to resolve node functions. If tools are deleted, we need to keep a minimal tool registry or inline the resolution logic.

**Important:** The `build_agent_graph` function calls `get_tool(node["tool"])` to look up node functions by slug. With the tools directory deleted, we need to either:
a) Keep a minimal `tools/__init__.py` with just the registry (register_tool, get_tool, list_tools, ToolDefinition) but no built-in tools registered, OR
b) Move the registry into graph.py

Option (a) is cleaner — recreate a minimal `backend/app/services/agent/tools/__init__.py` with only the registry:

```python
"""Tool registry for agent node resolution."""
from dataclasses import dataclass, field
from typing import Callable

@dataclass
class ToolDefinition:
    slug: str
    name: str
    category: str
    description: str
    input_keys: list[str]
    output_keys: list[str]
    node_fn: Callable
    config_schema: dict = field(default_factory=dict)

_tools: dict[str, ToolDefinition] = {}

def register_tool(definition: ToolDefinition) -> None:
    _tools[definition.slug] = definition

def get_tool(slug: str) -> ToolDefinition | None:
    return _tools.get(slug)

def list_tools() -> list[ToolDefinition]:
    return list(_tools.values())
```

Remove the `_ensure_loaded()` lazy-loading logic since there are no built-in tools to auto-load.

- [ ] **Step 4: Commit**

```bash
git add -A backend/app/services/agent/
git commit -m "refactor: rename FlowRunService to AgentRunService, update state and graph"
```

---

### Task 6: Backend — Rename Schemas and Clean Up Router

**Files:**
- Modify: `backend/app/schemas/agent.py`
- Modify: `backend/app/routers/agent.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Rewrite schemas/agent.py — remove old, rename remaining**

Delete these schema classes entirely:
- `AgentTypeResponse`
- `AgentConfigCreate`
- `AgentConfigResponse`
- `StartProcessingRequest`
- `SubmitReviewRequest`
- `AgentReceiptResponse`
- `AgentReceiptListItem`
- `StartExtractRunRequest`

Rename these schema classes:
- `FlowNodeSchema` → `AgentNodeSchema`
- `FlowEdgeSchema` → `AgentEdgeSchema`
- `FlowConditionalEdgeSchema` → `AgentConditionalEdgeSchema`
- `FlowDefinitionCreate` → `AgentDefinitionCreate`
- `FlowDefinitionUpdate` → `AgentDefinitionUpdate`
- `FlowDefinitionResponse` → `AgentDefinitionResponse` (update `from_orm_model` to use `AgentDefinition`)
- `StartFlowRunRequest` → `StartAgentRunRequest` (rename field `flow_definition_id` → `agent_definition_id`)
- `ResumeFlowRunRequest` → `ResumeAgentRunRequest`
- `FlowRunResponse` → `AgentRunResponse` (update `from_orm_model` to use `AgentRun`, rename field `flow_definition_id` → `agent_definition_id`)
- `FlowRunListItem` → `AgentRunListItem` (rename field `flow_definition_id` → `agent_definition_id`)

Keep `AgentToolResponse` as-is (it's for the tool registry, still needed by composer).

- [ ] **Step 2: Rewrite routers/agent.py — remove old endpoints, rename remaining**

Delete these endpoints entirely:
- `list_types()` — GET `/agent/types`
- `list_configs()` — GET `/agent/projects/{project_id}/configs`
- `create_config()` — POST `/agent/projects/{project_id}/configs`
- `delete_config()` — DELETE `/agent/configs/{config_id}`
- `start_processing()` — POST `/agent/projects/{project_id}/receipts`
- `list_receipts()` — GET `/agent/projects/{project_id}/receipts`
- `get_receipt()` — GET `/agent/receipts/{receipt_id}`
- `submit_review()` — POST `/agent/receipts/{receipt_id}/review`
- `start_extract_run()` — POST `/agent/extract/projects/{project_id}/runs`

Delete these dependency functions:
- `get_agent_service()`
- `get_extract_run_service()`

Rename remaining endpoints (URL paths change):
- `list_flows()` → `list_definitions()` — GET `/agent/projects/{project_id}/definitions`
- `create_flow()` → `create_definition()` — POST `/agent/projects/{project_id}/definitions`
- `get_flow()` → `get_definition()` — GET `/agent/definitions/{definition_id}`
- `update_flow()` → `update_definition()` — PUT `/agent/definitions/{definition_id}`
- `delete_flow()` → `delete_definition()` — DELETE `/agent/definitions/{definition_id}`
- `start_flow_run()` → `start_run()` — POST `/agent/projects/{project_id}/runs`
- `list_flow_runs()` → `list_runs()` — GET `/agent/projects/{project_id}/runs`
- `get_flow_run()` → `get_run()` — GET `/agent/runs/{run_id}`
- `resume_flow_run()` → `resume_run()` — POST `/agent/runs/{run_id}/resume`
- `delete_flow_run()` → `delete_run()` — DELETE `/agent/runs/{run_id}`
- `list_agent_tools()` stays — GET `/agent/tools`

Update the `get_flow_run_service()` dependency → `get_agent_run_service()`:
```python
async def get_agent_run_service(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AgentRunService:
    return AgentRunService(
        agent_run_repo=AgentRunRepository(db),
        agent_def_repo=AgentDefinitionRepository(db),
        checkpointer=request.app.state.agent_checkpointer,
    )
```

Update all imports to use renamed models, schemas, repositories, and services.

- [ ] **Step 3: Update main.py — remove old agent-related imports if any**

In `backend/app/main.py`, the agent router import and include should stay as-is:
```python
from app.routers import agent
app.include_router(agent.router, prefix="/api/v1")
```

Remove any imports of deleted models (AgentReceipt, AgentConfig) from the alembic env.py if present.

- [ ] **Step 4: Update alembic/env.py — update model imports**

In `backend/alembic/env.py`, update imports:
```python
# Old
from app.models.agent_config import AgentConfig
from app.models.agent_receipt import AgentReceipt, AgentReceiptStatus
from app.models.flow_definition import FlowDefinition
from app.models.flow_run import FlowRun, FlowRunStatus

# New
from app.models.agent_definition import AgentDefinition
from app.models.agent_run import AgentRun, AgentRunStatus
```

- [ ] **Step 5: Commit**

```bash
git add -A backend/app/schemas/ backend/app/routers/ backend/app/main.py backend/alembic/env.py
git commit -m "refactor: rename flow schemas/router to agent, remove old agent endpoints"
```

---

### Task 7: Backend — Create Alembic Migration

**Files:**
- Create: `backend/alembic/versions/<auto>_rename_flows_to_agents_drop_old.py`

- [ ] **Step 1: Generate migration**

```bash
cd backend && uv run alembic revision --autogenerate -m "rename flows to agents and drop old agent tables"
```

If autogenerate doesn't capture everything (table renames are often missed), manually write the migration. The migration should:

**Upgrade:**
```python
def upgrade() -> None:
    # Drop old agent tables
    op.drop_table("agent_receipts")
    op.drop_table("agent_configs")

    # Drop old enum type
    op.execute("DROP TYPE IF EXISTS agent_receipt_status")

    # Rename flow tables to agent
    op.rename_table("flow_definitions", "agent_definitions")
    op.rename_table("flow_runs", "agent_runs")

    # Rename flow_run_status enum to agent_run_status
    op.execute("ALTER TYPE flow_run_status RENAME TO agent_run_status")

    # Rename FK column in agent_runs
    op.alter_column("agent_runs", "flow_definition_id", new_column_name="agent_definition_id")

    # Rename constraints and indexes on agent_definitions
    op.execute("ALTER INDEX ix_flow_definitions_project_id RENAME TO ix_agent_definitions_project_id")
    op.execute("ALTER TABLE agent_definitions RENAME CONSTRAINT uq_flow_definitions_project_name TO uq_agent_definitions_project_name")

    # Rename indexes on agent_runs
    op.execute("ALTER INDEX ix_flow_runs_project_id RENAME TO ix_agent_runs_project_id")
    op.execute("ALTER INDEX ix_flow_runs_status RENAME TO ix_agent_runs_status")
    op.execute("ALTER INDEX ix_flow_runs_flow_definition_id RENAME TO ix_agent_runs_agent_definition_id")
    op.execute("ALTER INDEX ix_flow_runs_thread_id RENAME TO ix_agent_runs_thread_id")

    # Rename FK constraints
    op.execute(
        "ALTER TABLE agent_runs RENAME CONSTRAINT "
        "flow_runs_flow_definition_id_fkey TO agent_runs_agent_definition_id_fkey"
    )
    op.execute(
        "ALTER TABLE agent_runs RENAME CONSTRAINT "
        "flow_runs_project_id_fkey TO agent_runs_project_id_fkey"
    )
    op.execute(
        "ALTER TABLE agent_runs RENAME CONSTRAINT "
        "flow_runs_created_by_fkey TO agent_runs_created_by_fkey"
    )
    op.execute(
        "ALTER TABLE agent_definitions RENAME CONSTRAINT "
        "flow_definitions_project_id_fkey TO agent_definitions_project_id_fkey"
    )
    op.execute(
        "ALTER TABLE agent_definitions RENAME CONSTRAINT "
        "flow_definitions_created_by_fkey TO agent_definitions_created_by_fkey"
    )
```

**Downgrade:**
```python
def downgrade() -> None:
    # Reverse all renames
    op.execute(
        "ALTER TABLE agent_definitions RENAME CONSTRAINT "
        "agent_definitions_created_by_fkey TO flow_definitions_created_by_fkey"
    )
    op.execute(
        "ALTER TABLE agent_definitions RENAME CONSTRAINT "
        "agent_definitions_project_id_fkey TO flow_definitions_project_id_fkey"
    )
    op.execute(
        "ALTER TABLE agent_runs RENAME CONSTRAINT "
        "agent_runs_created_by_fkey TO flow_runs_created_by_fkey"
    )
    op.execute(
        "ALTER TABLE agent_runs RENAME CONSTRAINT "
        "agent_runs_project_id_fkey TO flow_runs_project_id_fkey"
    )
    op.execute(
        "ALTER TABLE agent_runs RENAME CONSTRAINT "
        "agent_runs_agent_definition_id_fkey TO flow_runs_flow_definition_id_fkey"
    )
    op.execute("ALTER INDEX ix_agent_runs_thread_id RENAME TO ix_flow_runs_thread_id")
    op.execute("ALTER INDEX ix_agent_runs_agent_definition_id RENAME TO ix_flow_runs_flow_definition_id")
    op.execute("ALTER INDEX ix_agent_runs_status RENAME TO ix_flow_runs_status")
    op.execute("ALTER INDEX ix_agent_runs_project_id RENAME TO ix_flow_runs_project_id")
    op.execute("ALTER TABLE agent_definitions RENAME CONSTRAINT uq_agent_definitions_project_name TO uq_flow_definitions_project_name")
    op.execute("ALTER INDEX ix_agent_definitions_project_id RENAME TO ix_flow_definitions_project_id")

    op.alter_column("agent_runs", "agent_definition_id", new_column_name="flow_definition_id")
    op.execute("ALTER TYPE agent_run_status RENAME TO flow_run_status")
    op.rename_table("agent_runs", "flow_runs")
    op.rename_table("agent_definitions", "flow_definitions")

    # Recreate old tables would go here but is not needed for a forward-only migration
```

- [ ] **Step 2: Review the generated migration**

Read the generated file and verify it covers all renames and drops.

- [ ] **Step 3: Commit**

```bash
git add backend/alembic/versions/
git commit -m "migrate: rename flow tables to agent, drop old agent_configs and agent_receipts"
```

---

### Task 8: Frontend — Rename Types

**Files:**
- Rewrite: `frontend/src/types/agent.ts`

- [ ] **Step 1: Rewrite types/agent.ts — remove old types, rename flow types**

Delete these types:
- `AgentType`
- `AgentConfig`
- `AgentConfigCreate`
- `AgentReceiptStatus`
- `AgentReceipt`
- `AgentReceiptListItem`
- `StartProcessingRequest`
- `SubmitReviewRequest`
- `StartExtractRunRequest`

Rename these types:
- `FlowNodeDef` → `AgentNodeDef`
- `FlowEdgeDef` → `AgentEdgeDef`
- `FlowConditionalEdgeDef` → `AgentConditionalEdgeDef`
- `FlowDefinitionData` → `AgentDefinitionData`
- `FlowDefinition` → `AgentDefinition`
- `FlowDefinitionCreate` → `AgentDefinitionCreate`
- `FlowDefinitionUpdate` → `AgentDefinitionUpdate`
- `FlowRun` → `AgentRun` (rename field `flowDefinitionId` → `agentDefinitionId`)
- `FlowRunListItem` → `AgentRunListItem` (rename field `flowDefinitionId` → `agentDefinitionId`)
- `FlowRunStatus` → `AgentRunStatus`
- `StartFlowRunRequest` → `StartAgentRunRequest` (rename field `flowDefinitionId` → `agentDefinitionId`)
- `ResumeFlowRunRequest` → `ResumeAgentRunRequest`

Keep `AgentTool` as-is.

- [ ] **Step 2: Commit**

```bash
git add frontend/src/types/agent.ts
git commit -m "refactor: rename Flow types to Agent in frontend"
```

---

### Task 9: Frontend — Rename API Functions

**Files:**
- Rewrite: `frontend/src/api/agent.ts`

- [ ] **Step 1: Rewrite api/agent.ts — remove old functions, rename and re-path remaining**

Delete these functions:
- `listAgentTypes()`
- `listAgentConfigs(projectId)`
- `createAgentConfig(projectId, data)`
- `deleteAgentConfig(configId)`
- `startProcessing(projectId, data)`
- `listReceipts(projectId)`
- `getReceipt(receiptId)`
- `submitReview(receiptId, data)`
- `startExtractRun(projectId, data)`

Rename functions and update URL paths:
- `listFlowDefinitions(projectId)` → `listAgentDefinitions(projectId)` — URL: `/agent/projects/${projectId}/definitions`
- `getFlowDefinition(flowId)` → `getAgentDefinition(agentId)` — URL: `/agent/definitions/${agentId}`
- `createFlowDefinition(projectId, data)` → `createAgentDefinition(projectId, data)` — URL: `/agent/projects/${projectId}/definitions`
- `updateFlowDefinition(flowId, data)` → `updateAgentDefinition(agentId, data)` — URL: `/agent/definitions/${agentId}`
- `deleteFlowDefinition(flowId)` → `deleteAgentDefinition(agentId)` — URL: `/agent/definitions/${agentId}`
- `startFlowRun(projectId, data)` → `startAgentRun(projectId, data)` — URL: `/agent/projects/${projectId}/runs`
- `listFlowRuns(projectId)` → `listAgentRuns(projectId)` — URL: `/agent/projects/${projectId}/runs`
- `getFlowRun(runId)` → `getAgentRun(runId)` — URL: `/agent/runs/${runId}`
- `resumeFlowRun(runId, data)` → `resumeAgentRun(runId, data)` — URL: `/agent/runs/${runId}/resume`
- `deleteFlowRun(runId)` → `deleteAgentRun(runId)` — URL: `/agent/runs/${runId}`
- `listAgentTools()` stays — URL: `/agent/tools`

Update all type references to use renamed types from Task 8.

- [ ] **Step 2: Commit**

```bash
git add frontend/src/api/agent.ts
git commit -m "refactor: rename Flow API functions to Agent, update URL paths"
```

---

### Task 10: Frontend — Delete Old Hooks, Rename Flow Hooks

**Files:**
- Delete: `frontend/src/hooks/useAgentConfigs.ts`
- Delete: `frontend/src/hooks/useAgentReceipt.ts`
- Delete: `frontend/src/hooks/useAgentReceipts.ts`
- Rename: `frontend/src/hooks/useFlowComposer.ts` → `useAgentComposer.ts`
- Rename: `frontend/src/hooks/useFlowDefinitions.ts` → `useAgentDefinitions.ts`
- Rename: `frontend/src/hooks/useFlowRun.ts` → `useAgentRun.ts`
- Rename: `frontend/src/hooks/useFlowRuns.ts` → `useAgentRuns.ts`

- [ ] **Step 1: Delete old hooks**

```bash
rm frontend/src/hooks/useAgentConfigs.ts
rm frontend/src/hooks/useAgentReceipt.ts
rm frontend/src/hooks/useAgentReceipts.ts
```

- [ ] **Step 2: Rename and update useFlowComposer.ts → useAgentComposer.ts**

```bash
mv frontend/src/hooks/useFlowComposer.ts frontend/src/hooks/useAgentComposer.ts
```

In `useAgentComposer.ts`:
- Rename export `useFlowComposer` → `useAgentComposer`
- Rename return type `UseFlowComposerReturn` → `UseAgentComposerReturn`
- Update imports to use renamed API functions (`createAgentDefinition`, `updateAgentDefinition`, `getAgentDefinition`, `listAgentTools`)
- Update imports to use renamed types (`AgentDefinition`, `AgentDefinitionData`, `AgentNodeDef`, `AgentTool`)
- Rename internal references: `savedFlow` → `savedAgent`, `flowName` → `agentName`, `setFlowName` → `setAgentName`, `flowDescription` → `agentDescription`, `setFlowDescription` → `setAgentDescription`
- Rename helper functions: `definitionToReactFlow` → `definitionToReactFlow` (keep, it's about React Flow the library), `reactFlowToDefinition` → `reactFlowToDefinition` (keep)

- [ ] **Step 3: Rename and update useFlowDefinitions.ts → useAgentDefinitions.ts**

```bash
mv frontend/src/hooks/useFlowDefinitions.ts frontend/src/hooks/useAgentDefinitions.ts
```

In `useAgentDefinitions.ts`:
- Rename export `useFlowDefinitions` → `useAgentDefinitions`
- Rename return type field `flows` → `agents`
- Rename `fetchFlows` → `fetchAgents`, `deleteFlow` → `deleteAgent`
- Update imports and API calls to use renamed functions

- [ ] **Step 4: Rename and update useFlowRun.ts → useAgentRun.ts**

```bash
mv frontend/src/hooks/useFlowRun.ts frontend/src/hooks/useAgentRun.ts
```

In `useAgentRun.ts`:
- Rename export `useFlowRun` → `useAgentRun`
- Update types: `FlowRun` → `AgentRun`, `ResumeFlowRunRequest` → `ResumeAgentRunRequest`
- Update API calls: `getFlowRun` → `getAgentRun`, `resumeFlowRun` → `resumeAgentRun`
- Rename `fetchRun` → stays `fetchRun`, `resumeRun` → stays `resumeRun`

- [ ] **Step 5: Rename and update useFlowRuns.ts → useAgentRuns.ts**

```bash
mv frontend/src/hooks/useFlowRuns.ts frontend/src/hooks/useAgentRuns.ts
```

In `useAgentRuns.ts`:
- Rename export `useFlowRuns` → `useAgentRuns`
- Update types: `FlowRunListItem` → `AgentRunListItem`, `StartFlowRunRequest` → `StartAgentRunRequest`
- Update API calls: `listFlowRuns` → `listAgentRuns`, `startFlowRun` → `startAgentRun`, `deleteFlowRun` → `deleteAgentRun`
- Remove `startExtractRun` function and its API import (extract-specific)
- Rename return fields: `startRun` stays, `deleteRun` stays, `runs` stays

- [ ] **Step 6: Commit**

```bash
git add -A frontend/src/hooks/
git commit -m "refactor: delete old agent hooks, rename Flow hooks to Agent"
```

---

### Task 11: Frontend — Delete Old Components, Rename Flow Components

**Files:**
- Delete: `frontend/src/components/agent/AgentSetup.tsx`
- Delete: `frontend/src/components/agent/AgentFlowGraph.tsx`
- Delete: `frontend/src/components/agent/ReceiptDetail.tsx`
- Delete: `frontend/src/components/agent/ReceiptList.tsx`
- Delete: `frontend/src/components/agent/ReceiptProcessForm.tsx`
- Delete: `frontend/src/components/agent/ReceiptReviewForm.tsx`
- Delete: `frontend/src/components/agent/StatusBadge.tsx`
- Rename: `frontend/src/components/agent/FlowList.tsx` → `AgentList.tsx`
- Rename: `frontend/src/components/agent/FlowRunList.tsx` → `AgentRunList.tsx`
- Rename: `frontend/src/components/agent/FlowRunDetail.tsx` → `AgentRunDetail.tsx`
- Rename: `frontend/src/components/agent/FlowRunInputForm.tsx` → `AgentRunInputForm.tsx`
- Rename: `frontend/src/components/agent/FlowComposer.tsx` → `AgentComposer.tsx`
- Rename: `frontend/src/components/agent/flow/` → `frontend/src/components/agent/composer/`

- [ ] **Step 1: Delete old receipt and agent-config components**

```bash
rm frontend/src/components/agent/AgentSetup.tsx
rm frontend/src/components/agent/AgentFlowGraph.tsx
rm frontend/src/components/agent/ReceiptDetail.tsx
rm frontend/src/components/agent/ReceiptList.tsx
rm frontend/src/components/agent/ReceiptProcessForm.tsx
rm frontend/src/components/agent/ReceiptReviewForm.tsx
rm frontend/src/components/agent/StatusBadge.tsx
```

- [ ] **Step 2: Rename flow/ directory to composer/**

```bash
mv frontend/src/components/agent/flow frontend/src/components/agent/composer
```

Update imports within `composer/FlowComposer.tsx` (which also gets renamed):
- `./flow/ComposerNode` → `./composer/ComposerNode` (but since it's now IN the composer dir, just `./ComposerNode`)

- [ ] **Step 3: Rename FlowList.tsx → AgentList.tsx**

```bash
mv frontend/src/components/agent/FlowList.tsx frontend/src/components/agent/AgentList.tsx
```

In `AgentList.tsx`:
- Rename component `FlowList` → `AgentList`
- Rename props `FlowListProps` → `AgentListProps`
- Update types: `FlowDefinition` → `AgentDefinition`
- Rename props: `flows` → `agents`, `onDelete` stays
- Update navigation paths: `/agent/flows/${flow.id}/runs` → `/agent/${agent.id}/runs`, `/agent/flows/${flow.id}` → `/agent/${agent.id}`
- Update "New Flow" button: label → "New Agent", path → `/agent/new`

- [ ] **Step 4: Rename FlowRunList.tsx → AgentRunList.tsx**

```bash
mv frontend/src/components/agent/FlowRunList.tsx frontend/src/components/agent/AgentRunList.tsx
```

In `AgentRunList.tsx`:
- Rename component and props: `FlowRunList` → `AgentRunList`, `FlowRunListProps` → `AgentRunListProps`
- Update types: `FlowRunListItem` → `AgentRunListItem`, `FlowRunStatus` → `AgentRunStatus`
- Update navigation: `/agent/runs/${run.id}` stays (same path structure)

- [ ] **Step 5: Rename FlowRunDetail.tsx → AgentRunDetail.tsx**

```bash
mv frontend/src/components/agent/FlowRunDetail.tsx frontend/src/components/agent/AgentRunDetail.tsx
```

In `AgentRunDetail.tsx`:
- Rename component and props: `FlowRunDetail` → `AgentRunDetail`, `FlowRunDetailProps` → `AgentRunDetailProps`
- Update types: `FlowRun` → `AgentRun`, `FlowDefinition` → `AgentDefinition`
- Remove import of `AgentFlowGraph` (deleted) — replace with a simpler status display or remove the graph visualization section entirely
- Remove import of `ReceiptReviewForm` (deleted) — the resume form for `waiting_for_input` state needs to stay but use a generic JSON input instead of the receipt-specific review form. Replace with a simple textarea + submit button for `resumeValue`.
- Update `SubmitReviewRequest` references → use `ResumeAgentRunRequest` type

- [ ] **Step 6: Rename FlowRunInputForm.tsx → AgentRunInputForm.tsx**

```bash
mv frontend/src/components/agent/FlowRunInputForm.tsx frontend/src/components/agent/AgentRunInputForm.tsx
```

In `AgentRunInputForm.tsx`:
- Rename component and props
- This form currently uses `StartExtractRunRequest` which is being deleted. The form needs to be updated to use `StartAgentRunRequest` instead.
- Remove document/schema dropdowns (extract-specific). Replace with a generic JSON initial state input.
- Update the `onStart` prop to accept `StartAgentRunRequest`

- [ ] **Step 7: Rename FlowComposer.tsx → AgentComposer.tsx**

```bash
mv frontend/src/components/agent/FlowComposer.tsx frontend/src/components/agent/AgentComposer.tsx
```

Note: There may be TWO FlowComposer files — one at `components/agent/FlowComposer.tsx` and one at `components/agent/flow/FlowComposer.tsx`. Check which is the real one. Based on exploration, the one in `flow/` is the actual composer component.

If `components/agent/FlowComposer.tsx` is a re-export or wrapper, delete it and keep only the one in `composer/` (renamed from `flow/`).

In the composer component (now at `components/agent/composer/FlowComposer.tsx`):
- Rename to `AgentComposer.tsx`
- Rename component: `FlowComposer` → `AgentComposer`
- Update props type: reference `UseAgentComposerReturn`
- Update internal references: `flowName` → `agentName`, `flowDescription` → `agentDescription`
- Update navigation: `/agent/flows/${id}/runs` → `/agent/${id}/runs`

```bash
mv frontend/src/components/agent/composer/FlowComposer.tsx frontend/src/components/agent/composer/AgentComposer.tsx
```

- [ ] **Step 8: Commit**

```bash
git add -A frontend/src/components/agent/
git commit -m "refactor: delete old agent components, rename Flow components to Agent"
```

---

### Task 12: Frontend — Update Pages, Delete Old Pages

**Files:**
- Delete: `frontend/src/pages/AgentPage.tsx`
- Delete: `frontend/src/pages/AgentReceiptPage.tsx`
- Rename: `frontend/src/pages/FlowComposerPage.tsx` → `AgentComposerPage.tsx`
- Rename: `frontend/src/pages/FlowRunsPage.tsx` → `AgentRunsPage.tsx`
- Rename: `frontend/src/pages/FlowRunDetailPage.tsx` → `AgentRunDetailPage.tsx`
- Create: `frontend/src/pages/AgentListPage.tsx` (new landing page for /agent)

- [ ] **Step 1: Delete old pages**

```bash
rm frontend/src/pages/AgentPage.tsx
rm frontend/src/pages/AgentReceiptPage.tsx
```

- [ ] **Step 2: Create AgentListPage.tsx**

The old `AgentPage.tsx` combined agent setup + receipts + flow list. The new page just shows the agent list. Create `frontend/src/pages/AgentListPage.tsx`:

```tsx
import { useProject } from '../hooks/useProject';
import { useAgentDefinitions } from '../hooks/useAgentDefinitions';
import AgentList from '../components/agent/AgentList';

export default function AgentListPage() {
  const { projectId } = useProject();
  const { agents, isLoading, deleteAgent } = useAgentDefinitions(projectId);

  const handleDelete = async (agentId: string) => {
    if (!window.confirm('Delete this agent definition? All associated runs will also be deleted.')) return;
    await deleteAgent(agentId);
  };

  return (
    <div className="space-y-6">
      <AgentList agents={agents} isLoading={isLoading} onDelete={handleDelete} />
    </div>
  );
}
```

- [ ] **Step 3: Rename and update FlowComposerPage.tsx → AgentComposerPage.tsx**

```bash
mv frontend/src/pages/FlowComposerPage.tsx frontend/src/pages/AgentComposerPage.tsx
```

In `AgentComposerPage.tsx`:
- Rename component: `FlowComposerPage` → `AgentComposerPage`
- Update hook: `useFlowComposer` → `useAgentComposer`
- Update component: `FlowComposer` → `AgentComposer`
- Update param: `flowId` → `agentId`

- [ ] **Step 4: Rename and update FlowRunsPage.tsx → AgentRunsPage.tsx**

```bash
mv frontend/src/pages/FlowRunsPage.tsx frontend/src/pages/AgentRunsPage.tsx
```

In `AgentRunsPage.tsx`:
- Rename component: `FlowRunsPage` → `AgentRunsPage`
- Update hooks: `useFlowComposer` → `useAgentComposer`, `useFlowRuns` → `useAgentRuns`
- Update components: `FlowRunList` → `AgentRunList`, `FlowRunInputForm` → `AgentRunInputForm`
- Update types and variable names: `flowRuns` → `agentRuns`, `flowId` → `agentId`
- Remove `startExtractRun` — use `startRun` with generic initial state
- Update breadcrumb/navigation paths

- [ ] **Step 5: Rename and update FlowRunDetailPage.tsx → AgentRunDetailPage.tsx**

```bash
mv frontend/src/pages/FlowRunDetailPage.tsx frontend/src/pages/AgentRunDetailPage.tsx
```

In `AgentRunDetailPage.tsx`:
- Rename component: `FlowRunDetailPage` → `AgentRunDetailPage`
- Update hook: `useFlowRun` → `useAgentRun`
- Update component: `FlowRunDetail` → `AgentRunDetail`
- Update types: `FlowDefinition` → `AgentDefinition`
- Update API calls: `getFlowDefinition` → `getAgentDefinition`
- Update navigation paths

- [ ] **Step 6: Commit**

```bash
git add -A frontend/src/pages/
git commit -m "refactor: delete old agent pages, rename Flow pages to Agent, add AgentListPage"
```

---

### Task 13: Frontend — Update Routes and Navigation

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/config/navigation.ts`

- [ ] **Step 1: Update App.tsx routes**

Replace the agent routes section:

```tsx
// Old imports — remove
import AgentPage from './pages/AgentPage'
import AgentReceiptPage from './pages/AgentReceiptPage'
import FlowComposerPage from './pages/FlowComposerPage'
import FlowRunsPage from './pages/FlowRunsPage'
import FlowRunDetailPage from './pages/FlowRunDetailPage'

// New imports
import AgentListPage from './pages/AgentListPage'
import AgentComposerPage from './pages/AgentComposerPage'
import AgentRunsPage from './pages/AgentRunsPage'
import AgentRunDetailPage from './pages/AgentRunDetailPage'
```

Replace route definitions:
```tsx
{/* Old */}
<Route path="/agent" element={<AgentPage />} />
<Route path="/agent/receipts/:receiptId" element={<AgentReceiptPage />} />
<Route path="/agent/flows/new" element={<FlowComposerPage />} />
<Route path="/agent/flows/:flowId" element={<FlowComposerPage />} />
<Route path="/agent/flows/:flowId/runs" element={<FlowRunsPage />} />
<Route path="/agent/runs/:runId" element={<FlowRunDetailPage />} />

{/* New */}
<Route path="/agent" element={<AgentListPage />} />
<Route path="/agent/new" element={<AgentComposerPage />} />
<Route path="/agent/:agentId" element={<AgentComposerPage />} />
<Route path="/agent/:agentId/runs" element={<AgentRunsPage />} />
<Route path="/agent/runs/:runId" element={<AgentRunDetailPage />} />
```

- [ ] **Step 2: Update navigation.ts**

Navigation item stays the same — label "Agent", icon `Bot`, href `/agent`. No changes needed unless the label should be pluralized to "Agents":

```typescript
{ label: 'Agents', href: '/agent', icon: Bot, activeColor: 'border-l-purple-500' }
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/App.tsx frontend/src/config/navigation.ts
git commit -m "refactor: update routes and navigation for agent rename"
```

---

### Task 14: Verification — Build and Lint

- [ ] **Step 1: Run frontend TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```

Fix any type errors from missed renames.

- [ ] **Step 2: Run frontend build**

```bash
cd frontend && npm run build
```

Should complete without errors.

- [ ] **Step 3: Run frontend tests (if any exist for agent/flow features)**

```bash
cd frontend && npx vitest run
```

- [ ] **Step 4: Run backend import check**

```bash
cd backend && uv run python -c "from app.main import app; print('OK')"
```

- [ ] **Step 5: Run backend tests (if any exist)**

```bash
cd backend && uv run python -m pytest -o "addopts=" -x -q
```

- [ ] **Step 6: Fix any issues found, commit fixes**

```bash
git add -A
git commit -m "fix: resolve build/lint issues from agent rename"
```

---

### Task 15: Search for Stale References

- [ ] **Step 1: Grep for remaining "flow" references that should be "agent"**

Search across the entire codebase for remaining flow references that should have been renamed:

```bash
# Backend
grep -rn "FlowDefinition\|FlowRun\|flow_definition\|flow_run\|FlowRunStatus\|GenericFlowState" backend/app/ --include="*.py"

# Frontend
grep -rn "FlowDefinition\|FlowRun\|FlowComposer\|useFlow\|flowDefinitionId\|flow_definition" frontend/src/ --include="*.ts" --include="*.tsx"

# API paths
grep -rn "/flows/" frontend/src/ --include="*.ts" --include="*.tsx"
grep -rn "/receipts/" frontend/src/ --include="*.ts" --include="*.tsx"
```

- [ ] **Step 2: Fix any stale references found**

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "chore: clean up remaining flow/receipt references"
```
