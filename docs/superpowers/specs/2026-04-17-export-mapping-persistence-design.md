# Export Mapping Persistence Design

**Date:** 2026-04-17
**Branch:** feat/export-field-mapping

## Overview

Add persistence for field mapping configurations in the Export Playground. Users can save, load, rename, and delete named mappings scoped to a specific project and data store. Saved mappings survive browser refreshes and are accessible from any machine. The data model is designed so that a future session can wire saved mappings into the agent export tool config without schema changes.

## Data Model

New table `export_mappings`:

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | `gen_random_uuid()` |
| `project_id` | UUID FK → `projects.id` | CASCADE delete |
| `data_store_id` | UUID FK → `project_data_stores.id` | CASCADE delete |
| `name` | VARCHAR(255) | |
| `field_mapping` | JSON | List of `{sourcePath, destinationColumn}` objects |
| `created_at` | TIMESTAMPTZ | `NOW()` default |
| `updated_at` | TIMESTAMPTZ | `NOW()` default, updated on write |

**Constraints:**
- Unique on `(project_id, data_store_id, name)` — no duplicate names within the same store
- Index on `(project_id, data_store_id)` for list queries

**Scoping:** All queries filter by both `project_id` and `data_store_id`. The `project_id` is always verified against the authenticated user's project membership before returning results.

## Backend

### Files

- `backend/app/models/export_mapping.py` — SQLAlchemy `ExportMapping` model
- `backend/app/schemas/export_mapping.py` — Pydantic schemas: `ExportMappingCreate`, `ExportMappingUpdate`, `ExportMappingResponse`
- `backend/app/repositories/export_mapping_repository.py` — `list_by_store`, `create`, `update`, `delete`
- `backend/app/services/export_mapping_service.py` — thin service; raises `ValueError` on name collision
- `backend/app/routers/export_mappings.py` — REST endpoints, mounted at `/api/projects/{project_id}/export-mappings`
- Alembic migration — `down_revision = 'e6f7a8b9c0d1'` (current data stores migration)

### API Endpoints

| Method | Path | Body / Query | Response |
|---|---|---|---|
| `GET` | `/api/projects/{project_id}/export-mappings` | `?data_store_id=<uuid>` | `list[ExportMappingResponse]` |
| `POST` | `/api/projects/{project_id}/export-mappings` | `ExportMappingCreate` | `ExportMappingResponse` |
| `PUT` | `/api/projects/{project_id}/export-mappings/{mapping_id}` | `ExportMappingUpdate` | `ExportMappingResponse` |
| `DELETE` | `/api/projects/{project_id}/export-mappings/{mapping_id}` | — | `204 No Content` |

**Schemas:**

```python
class ExportMappingCreate(BaseModel):
    data_store_id: UUID
    name: str
    field_mapping: list[dict]  # [{sourcePath, destinationColumn}]

class ExportMappingUpdate(BaseModel):
    name: str | None = None
    field_mapping: list[dict] | None = None

class ExportMappingResponse(BaseModel):
    id: UUID
    project_id: UUID
    data_store_id: UUID
    name: str
    field_mapping: list[dict]
    created_at: datetime
    updated_at: datetime
```

**Error handling:** Service raises `ValueError("name already exists")` on unique constraint violation; router returns `409 Conflict`.

## Frontend

### Files

- `frontend/src/types/exportMapping.ts` — `ExportMapping`, `ExportMappingCreate`, `ExportMappingUpdate` TypeScript types
- `frontend/src/api/exportMappings.ts` — wrappers: `listExportMappings`, `createExportMapping`, `updateExportMapping`, `deleteExportMapping`
- `frontend/src/hooks/useExportMappings.ts` — auto-fetches on `(projectId, storeId)` change; exposes `mappings`, `isLoading`, `create`, `update`, `remove`

### Playground UI

`ExportPlaygroundPage.tsx` gains:
- `activeMappingId: string | null` — ID of the currently loaded saved mapping
- `activeMappingName: string | null` — display name for the loaded mapping
- `isDirty: boolean` — true when the mapping has been edited since loading

The Field Mapping section header row is updated:

```
Field Mapping                    [Load ▾] [Save As] [Rename] [Delete]
```

**Load dropdown** (`Select` component):
- Trigger displays `activeMappingName` (with `•` prefix when `isDirty`) or "Load saved mapping" when none is loaded
- Lists saved mappings for the selected store
- Selecting replaces the current `mapping` state and sets `activeMappingId` / `activeMappingName`; clears `isDirty`

**Save As** button:
- Opens a `Popover` with a name `Input` and confirm button
- Calls `create`; sets `activeMappingId` / `activeMappingName`; clears `isDirty`
- Disabled when `mapping` is empty

**Rename** button:
- Opens a `Popover` pre-filled with current name
- Calls `update({ name })`; updates `activeMappingName`
- Disabled when `activeMappingId` is null

**Delete** button:
- Shows inline confirmation (button changes to "Confirm?")
- Calls `remove`; clears `activeMappingId` / `activeMappingName`
- Disabled when `activeMappingId` is null

**Unsaved indicator:** A `•` appears next to the loaded mapping name in the Load dropdown trigger when `isDirty` is true.

**`isDirty` tracking:** Set to `true` whenever `mapping` state changes after a load; reset to `false` on load or save.

## Out of Scope

- Wiring saved mappings into the agent export tool config (planned for a future session)
- Copying a saved mapping to a different data store
- Versioning or history of mapping changes
