# LangGraph Agent — Receipt Processing Pipeline

**Status:** Ready for Implementation
**Date:** 2026-04-10
**Scope:** LangGraph-based agent module for processing receipt photos through extract → human review → export pipeline

---

## Overview

Add a new Agent module to rag-admin that uses LangGraph to orchestrate receipt photo processing. The agent runs a 3-node graph (extract → review → export) with a human-in-the-loop interrupt at the review step. This reuses the existing extraction infrastructure (DataExtractor port, LlamaExtract adapter, extraction schemas) and adds LangGraph for workflow orchestration and state management.

The primary goal is to learn LangGraph patterns (StateGraph, interrupts, checkpointing) while building a production-style document processing pipeline. The receipts (~30 photos) are the test case, with future extensibility to mpesa statements, bank statements, etc.

---

## Architecture

```
User uploads receipt via Documents → Selects document + schema in Agent UI
                                              ↓
                                    POST /agent/projects/{id}/receipts
                                              ↓
                                    AgentService.start_processing()
                                              ↓
                                    LangGraph StateGraph invoked
                                              ↓
                            ┌─────────────────────────────────┐
                            │  extract_node                   │
                            │  (calls DataExtractor.extract()) │
                            └──────────────┬──────────────────┘
                                           ↓
                            ┌─────────────────────────────────┐
                            │  review_node                    │
                            │  interrupt() → returns to API   │
                            │  User reviews in UI             │
                            │  POST .../review resumes graph  │
                            └──────────────┬──────────────────┘
                                           ↓
                              ┌──────────┴──────────┐
                              ↓                     ↓
                         approve/edit             reject
                              ↓                     ↓
                    ┌──────────────────┐          END
                    │  export_node     │
                    │  saves to DB     │
                    └────────┬─────────┘
                             ↓
                            END
```

### Reused Infrastructure

| Component | Location | Usage |
|---|---|---|
| DataExtractor port | `app/ports/data_extraction.py` | Interface for extraction — called by extract_node |
| LlamaExtract adapter | `app/adapters/extraction/llamaextract.py` | Handles OCR + structured extraction in MULTIMODAL mode |
| Extractor registry | `app/adapters/extraction/registry.py` | `get_extractor("llamaextract")` |
| ExtractionSchema model | `app/models/extraction_schema.py` | Stores receipt JSON schema definition |
| StorageService | `app/ports/storage.py` | File path lookup for receipt images |
| DocumentRepository | `app/repositories/document_repository.py` | Document metadata + file path |

---

## Dependencies

| Package | Version | Purpose |
|---|---|---|
| `langgraph` | >=0.4.0 | StateGraph, nodes, edges, interrupt |
| `langgraph-checkpoint-postgres` | >=2.0.0 | AsyncPostgresSaver for persisting graph state |

No new frontend dependencies — uses existing shadcn/ui components.

---

## Data Model

### `agent_receipts` table

| Column | Type | Constraints | Description |
|---|---|---|---|
| id | UUID | PK, default gen_random_uuid() | |
| project_id | UUID | FK projects.id, CASCADE, NOT NULL | |
| document_id | UUID | FK documents.id, CASCADE, NOT NULL | Receipt image document |
| extraction_schema_id | UUID | FK extraction_schemas.id, NOT NULL | JSON schema used for extraction |
| status | agent_receipt_status enum | NOT NULL, default 'pending' | Pipeline status |
| status_message | TEXT | nullable | Error or info message |
| extracted_data | JSON | nullable | Raw extraction output |
| reviewed_data | JSON | nullable | Human-corrected data (null until review) |
| thread_id | VARCHAR(64) | nullable, indexed | LangGraph thread for checkpointing |
| created_by | UUID | FK users.id, NOT NULL | |
| created_at | TIMESTAMPTZ | NOT NULL, default NOW() | |
| updated_at | TIMESTAMPTZ | NOT NULL, default NOW() | |

### `AgentReceiptStatus` enum

`pending` → `extracting` → `reviewing` → `approved` / `exported` / `failed`

---

## API Design

### Start Processing

```
POST /api/v1/agent/projects/{project_id}/receipts
Content-Type: application/json

{
  "documentId": "uuid",
  "extractionSchemaId": "uuid"
}
```

**Response 202:**
```json
{
  "id": "uuid",
  "projectId": "uuid",
  "documentId": "uuid",
  "extractionSchemaId": "uuid",
  "status": "reviewing",
  "extractedData": { "vendor": "Naivas", "total": 2450, ... },
  "reviewedData": null,
  "threadId": "uuid-string",
  "createdAt": "2026-04-10T...",
  "updatedAt": "2026-04-10T..."
}
```

Note: The graph runs extract synchronously (may take 10-30s), then interrupts at review. The response comes back with status=reviewing and extracted_data populated.

### List Receipts

```
GET /api/v1/agent/projects/{project_id}/receipts
```

**Response 200:** Array of `AgentReceiptListItem` (id, status, vendor, total, date, createdAt).

### Get Receipt Detail

```
GET /api/v1/agent/receipts/{receipt_id}
```

**Response 200:** Full `AgentReceiptResponse`.

### Submit Review

```
POST /api/v1/agent/receipts/{receipt_id}/review
Content-Type: application/json

{
  "action": "approve" | "edit" | "reject",
  "data": { ... }  // required if action is "edit"
}
```

**Response 200:** Updated `AgentReceiptResponse` with status=exported (approve/edit) or status=failed (reject).

---

## LangGraph Graph Definition

### State

```python
class AgentState(TypedDict, total=False):
    receipt_id: str
    document_id: str
    file_path: str
    extraction_schema_id: str
    schema_definition: dict
    extraction_config: dict
    extracted_data: dict
    review_action: str          # "approve", "edit", "reject"
    reviewed_data: dict | None
    exported: bool
    error: str | None
    current_step: str
```

### Nodes

1. **extract_node** — calls `get_extractor("llamaextract").extract(file_path, schema_definition, config)`
2. **review_node** — calls `interrupt(extracted_data)`, receives `{action, data}` on resume
3. **export_node** — writes final data to AgentReceipt row

### Edges

```
START → extract → review → conditional:
  - approve/edit → export → END
  - reject → END
```

### Checkpointer

`AsyncPostgresSaver` from `langgraph-checkpoint-postgres`, using the existing PostgreSQL database. Connection string converted from `postgresql+asyncpg://` to `postgresql://` (psycopg format). Checkpoint tables created automatically via `setup()`.

---

## Frontend UX

### Agent Page (`/agent`)

Two-section layout:
- **Top/Right:** Form to start processing — select document (dropdown), select extraction schema (dropdown), "Process" button
- **Main:** Table of receipts with columns: Status (badge), Vendor, Total, Date, Created. Each row links to detail page.

### Receipt Detail Page (`/agent/receipts/:id`)

- **Status timeline** showing pipeline progress
- **When status=reviewing:** Editable form with extracted fields + Approve / Edit & Approve / Reject buttons
- **When status=exported:** Read-only view of final data
- **When status=failed:** Error message display

### Status Badges

| Status | Color | Label |
|---|---|---|
| pending | gray | Pending |
| extracting | blue | Extracting |
| reviewing | amber | Needs Review |
| approved | green | Approved |
| exported | emerald | Exported |
| failed | red | Failed |

---

## File Structure

### Backend (new files)

```
backend/app/
  models/agent_receipt.py              # Model + status enum
  repositories/agent_receipt_repository.py  # CRUD
  services/agent/
    __init__.py
    state.py                           # AgentState TypedDict
    nodes.py                           # extract, review, export nodes
    graph.py                           # StateGraph builder
    checkpointer.py                    # AsyncPostgresSaver singleton
    service.py                         # AgentService
  schemas/agent.py                     # Pydantic request/response
  routers/agent.py                     # API endpoints
```

### Backend (modified files)

```
backend/pyproject.toml                 # Add langgraph deps
backend/app/models/__init__.py         # Register model
backend/app/main.py                    # Register router + init checkpointer
backend/alembic/versions/...          # Migration
```

### Frontend (new files)

```
frontend/src/
  types/agent.ts
  api/agent.ts
  hooks/useAgentReceipts.ts
  hooks/useAgentReceipt.ts
  components/agent/
    ReceiptProcessForm.tsx
    ReceiptList.tsx
    ReceiptReviewForm.tsx
    ReceiptDetail.tsx
    StatusBadge.tsx
  pages/AgentPage.tsx
  pages/AgentReceiptPage.tsx
```

### Frontend (modified files)

```
frontend/src/config/navigation.ts      # Add Agent nav item
frontend/src/App.tsx                   # Add routes
```

---

## Out of Scope

- Natural language query/analysis layer (future milestone)
- Batch processing of multiple receipts
- Non-receipt document types (mpesa, bank statements — future)
- File upload in Agent UI (uses existing Documents upload)
- Receipt image preview in review UI (future enhancement)

---

## Future: Per-Project Agent Types & Registry

### Motivation

Different projects need different agent workflows:
- **Personal Budget** project → receipt processing (extract → review → export)
- **REIT Financial Analysis** project → financial research (research → analyze → review → report)
- **Digital Ocean Analysis** project → its own flow

The Agent page should show only the flows relevant to the current project. Adding a new flow means writing a new Python module — Claude Code writes and tests each one.

### Design: Agent Types as Code Modules

```
backend/app/services/agent/types/
  __init__.py                          # Registry — discovers available agent types
  receipt_processing/
    __init__.py                        # AgentTypeDefinition metadata
    graph.py                           # StateGraph builder
    nodes.py                           # Node functions
    state.py                           # TypedDict state
  financial_research/
    __init__.py
    graph.py
    nodes.py
    state.py
```

Each agent type module exports an `AgentTypeDefinition` with:
- `slug`: unique identifier (e.g., `receipt-processing`)
- `name`: display name
- `description`: what this flow does
- `graph_builder`: function that returns a compiled StateGraph
- `node_descriptions`: ordered list of node names + labels for UI status display
- `review_schema`: hints for what the review UI should render (JSON editor, form fields, etc.)

### Data Model Changes

**`agent_configs` table** — links projects to agent types:

| Column | Type | Description |
|---|---|---|
| id | UUID | PK |
| project_id | UUID | FK projects.id |
| agent_type | VARCHAR | Slug matching a registered agent type |
| config | JSON | Per-project config overrides (LLM model, prompts, etc.) |
| enabled | BOOLEAN | Toggle without deleting |
| created_at | TIMESTAMPTZ | |

**`agent_runs` table** — generalizes `agent_receipts` for any agent type:

| Column | Type | Description |
|---|---|---|
| id | UUID | PK |
| project_id | UUID | FK |
| agent_config_id | UUID | FK agent_configs.id |
| status | enum | Pipeline status |
| input_data | JSON | What was fed into the graph |
| extracted_data | JSON | Output from processing nodes |
| reviewed_data | JSON | Human-reviewed output |
| thread_id | VARCHAR | LangGraph checkpointer thread |
| created_by | UUID | FK |
| created_at / updated_at | TIMESTAMPTZ | |

### Frontend Changes

- Agent page queries agent configs for current project
- If no configs → shows "Configure an agent for this project" prompt
- If configs exist → shows tabs/sections per enabled agent type
- Each agent type can declare its own review component (or fall back to JSON editor)

### Adding a New Agent Type (Developer Workflow)

1. Create new directory under `services/agent/types/<slug>/`
2. Define state, nodes, graph, and metadata
3. Register in the type registry `__init__.py`
4. Create an `agent_config` row linking it to a project
5. The UI picks it up automatically
