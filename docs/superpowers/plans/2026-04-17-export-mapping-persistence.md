# Export Mapping Persistence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist export field mappings to the database so users can save, load, rename, update, and delete named mapping configurations in the Export Playground.

**Architecture:** New `export_mappings` table scoped to `(project_id, data_store_id)`. Standard router → service → repository stack. Frontend adds a persistence toolbar above `FieldMappingEditor` in `ExportPlaygroundPage` with load/save/rename/delete controls.

**Tech Stack:** Python/FastAPI/SQLAlchemy 2.0 (backend), React 18/TypeScript/shadcn/ui (frontend), PostgreSQL/Alembic (migrations).

**Note on tests:** Backend unit tests that hit the database are skipped in this branch — there is a known SQLite-in-memory issue to be resolved in a separate session. Frontend tests are in scope.

---

## File Map

**Create:**
- `backend/app/models/export_mapping.py` — SQLAlchemy `ExportMapping` model
- `backend/app/schemas/export_mapping.py` — Pydantic request/response schemas
- `backend/app/repositories/export_mapping_repository.py` — DB CRUD operations
- `backend/app/services/export_mapping_service.py` — thin service layer
- `backend/app/routers/export_mappings.py` — REST endpoints
- `backend/alembic/versions/f8a9b0c1d2e3_add_export_mappings_table.py` — migration
- `frontend/src/types/exportMapping.ts` — TypeScript types
- `frontend/src/api/exportMappings.ts` — API wrappers
- `frontend/src/hooks/useExportMappings.ts` — data hook

**Modify:**
- `backend/app/main.py` — register export_mappings router
- `frontend/src/pages/ExportPlaygroundPage.tsx` — persistence toolbar + state

---

## Task 1: SQLAlchemy Model

**Files:**
- Create: `backend/app/models/export_mapping.py`

- [ ] **Step 1: Create the model**

```python
# backend/app/models/export_mapping.py
"""Model for saved export field mapping configurations."""
from datetime import datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import DateTime, ForeignKey, JSON, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ExportMapping(Base):
    """A named, saved field mapping configuration for a data store."""
    __tablename__ = "export_mappings"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=sa.text('gen_random_uuid()')
    )
    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False
    )
    data_store_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("project_data_stores.id", ondelete="CASCADE"),
        nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    field_mapping: Mapped[list] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        server_default=sa.text('NOW()')
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        server_default=sa.text('NOW()')
    )

    __table_args__ = (
        sa.UniqueConstraint(
            'project_id', 'data_store_id', 'name',
            name='uq_export_mappings_project_store_name'
        ),
        sa.Index('ix_export_mappings_project_store', 'project_id', 'data_store_id'),
    )
```

- [ ] **Step 2: Commit**

```bash
cd .worktrees/feat/export-field-mapping
git add backend/app/models/export_mapping.py
git commit -m "feat: add ExportMapping SQLAlchemy model"
```

---

## Task 2: Alembic Migration

**Files:**
- Create: `backend/alembic/versions/f8a9b0c1d2e3_add_export_mappings_table.py`

- [ ] **Step 1: Create the migration file**

```python
# backend/alembic/versions/f8a9b0c1d2e3_add_export_mappings_table.py
"""add_export_mappings_table

Revision ID: f8a9b0c1d2e3
Revises: e6f7a8b9c0d1
Create Date: 2026-04-17 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'f8a9b0c1d2e3'
down_revision: Union[str, None] = 'e6f7a8b9c0d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'export_mappings',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('project_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('data_store_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('project_data_stores.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('field_mapping', sa.JSON, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
    )
    op.create_unique_constraint(
        'uq_export_mappings_project_store_name',
        'export_mappings',
        ['project_id', 'data_store_id', 'name']
    )
    op.create_index(
        'ix_export_mappings_project_store',
        'export_mappings',
        ['project_id', 'data_store_id']
    )


def downgrade() -> None:
    op.drop_index('ix_export_mappings_project_store', table_name='export_mappings')
    op.drop_constraint('uq_export_mappings_project_store_name', 'export_mappings')
    op.drop_table('export_mappings')
```

- [ ] **Step 2: Apply the migration**

```bash
cd .worktrees/feat/export-field-mapping/backend
alembic upgrade head
```

Expected: `Running upgrade e6f7a8b9c0d1 -> f8a9b0c1d2e3, add_export_mappings_table`

- [ ] **Step 3: Commit**

```bash
cd .worktrees/feat/export-field-mapping
git add backend/alembic/versions/f8a9b0c1d2e3_add_export_mappings_table.py
git commit -m "feat: add export_mappings migration"
```

---

## Task 3: Pydantic Schemas

**Files:**
- Create: `backend/app/schemas/export_mapping.py`

- [ ] **Step 1: Create the schemas**

```python
# backend/app/schemas/export_mapping.py
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ExportMappingCreate(BaseModel):
    data_store_id: UUID
    name: str = Field(..., min_length=1, max_length=255)
    field_mapping: list[dict]


class ExportMappingUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    field_mapping: list[dict] | None = None


class ExportMappingResponse(BaseModel):
    id: UUID
    project_id: UUID
    data_store_id: UUID
    name: str
    field_mapping: list[dict]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 2: Commit**

```bash
cd .worktrees/feat/export-field-mapping
git add backend/app/schemas/export_mapping.py
git commit -m "feat: add ExportMapping Pydantic schemas"
```

---

## Task 4: Repository

**Files:**
- Create: `backend/app/repositories/export_mapping_repository.py`

- [ ] **Step 1: Create the repository**

```python
# backend/app/repositories/export_mapping_repository.py
from uuid import UUID

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.export_mapping import ExportMapping
from app.schemas.export_mapping import ExportMappingCreate, ExportMappingUpdate


class ExportMappingRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_by_store(
        self, project_id: UUID, data_store_id: UUID
    ) -> list[ExportMapping]:
        result = await self.session.execute(
            select(ExportMapping)
            .where(
                ExportMapping.project_id == project_id,
                ExportMapping.data_store_id == data_store_id,
            )
            .order_by(ExportMapping.name)
        )
        return list(result.scalars().all())

    async def get_by_id(
        self, mapping_id: UUID, project_id: UUID
    ) -> ExportMapping | None:
        result = await self.session.execute(
            select(ExportMapping).where(
                ExportMapping.id == mapping_id,
                ExportMapping.project_id == project_id,
            )
        )
        return result.scalar_one_or_none()

    async def name_exists(
        self, project_id: UUID, data_store_id: UUID, name: str, exclude_id: UUID | None = None
    ) -> bool:
        q = select(ExportMapping).where(
            ExportMapping.project_id == project_id,
            ExportMapping.data_store_id == data_store_id,
            ExportMapping.name == name,
        )
        if exclude_id:
            q = q.where(ExportMapping.id != exclude_id)
        result = await self.session.execute(q)
        return result.scalar_one_or_none() is not None

    async def create(
        self, project_id: UUID, data: ExportMappingCreate
    ) -> ExportMapping:
        mapping = ExportMapping(
            project_id=project_id,
            data_store_id=data.data_store_id,
            name=data.name,
            field_mapping=data.field_mapping,
        )
        self.session.add(mapping)
        await self.session.commit()
        await self.session.refresh(mapping)
        return mapping

    async def update(
        self, mapping: ExportMapping, data: ExportMappingUpdate
    ) -> ExportMapping:
        if data.name is not None:
            mapping.name = data.name
        if data.field_mapping is not None:
            mapping.field_mapping = data.field_mapping
        await self.session.commit()
        await self.session.refresh(mapping)
        return mapping

    async def delete(self, mapping_id: UUID, project_id: UUID) -> bool:
        result = await self.session.execute(
            delete(ExportMapping).where(
                ExportMapping.id == mapping_id,
                ExportMapping.project_id == project_id,
            )
        )
        await self.session.commit()
        return result.rowcount > 0
```

- [ ] **Step 2: Commit**

```bash
cd .worktrees/feat/export-field-mapping
git add backend/app/repositories/export_mapping_repository.py
git commit -m "feat: add ExportMappingRepository"
```

---

## Task 5: Service

**Files:**
- Create: `backend/app/services/export_mapping_service.py`

- [ ] **Step 1: Create the service**

```python
# backend/app/services/export_mapping_service.py
from uuid import UUID

from app.repositories.export_mapping_repository import ExportMappingRepository
from app.schemas.export_mapping import (
    ExportMappingCreate,
    ExportMappingResponse,
    ExportMappingUpdate,
)
from app.services.exceptions import ConflictError, NotFoundError


class ExportMappingService:
    def __init__(self, repo: ExportMappingRepository):
        self.repo = repo

    async def list_by_store(
        self, project_id: UUID, data_store_id: UUID
    ) -> list[ExportMappingResponse]:
        mappings = await self.repo.list_by_store(project_id, data_store_id)
        return [ExportMappingResponse.model_validate(m) for m in mappings]

    async def create(
        self, project_id: UUID, data: ExportMappingCreate
    ) -> ExportMappingResponse:
        if await self.repo.name_exists(project_id, data.data_store_id, data.name):
            raise ConflictError(f"A mapping named '{data.name}' already exists for this data store.")
        mapping = await self.repo.create(project_id, data)
        return ExportMappingResponse.model_validate(mapping)

    async def update(
        self, mapping_id: UUID, project_id: UUID, data: ExportMappingUpdate
    ) -> ExportMappingResponse:
        mapping = await self.repo.get_by_id(mapping_id, project_id)
        if not mapping:
            raise NotFoundError(f"Export mapping {mapping_id} not found.")
        if data.name and data.name != mapping.name:
            if await self.repo.name_exists(
                project_id, mapping.data_store_id, data.name, exclude_id=mapping_id
            ):
                raise ConflictError(f"A mapping named '{data.name}' already exists for this data store.")
        updated = await self.repo.update(mapping, data)
        return ExportMappingResponse.model_validate(updated)

    async def delete(self, mapping_id: UUID, project_id: UUID) -> None:
        deleted = await self.repo.delete(mapping_id, project_id)
        if not deleted:
            raise NotFoundError(f"Export mapping {mapping_id} not found.")
```

- [ ] **Step 2: Commit**

```bash
cd .worktrees/feat/export-field-mapping
git add backend/app/services/export_mapping_service.py
git commit -m "feat: add ExportMappingService"
```

---

## Task 6: Router + Register

**Files:**
- Create: `backend/app/routers/export_mappings.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Create the router**

```python
# backend/app/routers/export_mappings.py
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_active_user
from app.models import User
from app.repositories.export_mapping_repository import ExportMappingRepository
from app.schemas.export_mapping import (
    ExportMappingCreate,
    ExportMappingResponse,
    ExportMappingUpdate,
)
from app.services.export_mapping_service import ExportMappingService
from app.services.exceptions import ConflictError, NotFoundError

router = APIRouter(
    prefix="/projects/{project_id}/export-mappings",
    tags=["export-mappings"],
)


def get_service(db: AsyncSession = Depends(get_db)) -> ExportMappingService:
    return ExportMappingService(ExportMappingRepository(db))


@router.get("", response_model=list[ExportMappingResponse])
async def list_export_mappings(
    project_id: UUID,
    data_store_id: UUID = Query(...),
    current_user: User = Depends(get_current_active_user),
    service: ExportMappingService = Depends(get_service),
):
    return await service.list_by_store(project_id, data_store_id)


@router.post("", response_model=ExportMappingResponse, status_code=status.HTTP_201_CREATED)
async def create_export_mapping(
    project_id: UUID,
    data: ExportMappingCreate,
    current_user: User = Depends(get_current_active_user),
    service: ExportMappingService = Depends(get_service),
):
    try:
        return await service.create(project_id, data)
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.put("/{mapping_id}", response_model=ExportMappingResponse)
async def update_export_mapping(
    project_id: UUID,
    mapping_id: UUID,
    data: ExportMappingUpdate,
    current_user: User = Depends(get_current_active_user),
    service: ExportMappingService = Depends(get_service),
):
    try:
        return await service.update(mapping_id, project_id, data)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.delete("/{mapping_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_export_mapping(
    project_id: UUID,
    mapping_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: ExportMappingService = Depends(get_service),
):
    try:
        await service.delete(mapping_id, project_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
```

- [ ] **Step 2: Register the router in `main.py`**

In `backend/app/main.py`, add `export_mappings` to the imports and include the router.

Change line 7 from:
```python
from app.routers import auth, oauth, otel_proxy, projects, users, documents, indexes, provider_keys, golden_sets, eval_runs, experiments, parse_results, extraction, extraction_ground_truth, extraction_eval, agent, data_stores
```
To:
```python
from app.routers import auth, oauth, otel_proxy, projects, users, documents, indexes, provider_keys, golden_sets, eval_runs, experiments, parse_results, extraction, extraction_ground_truth, extraction_eval, agent, data_stores, export_mappings
```

Then add after line 168 (`app.include_router(data_stores.router, prefix="/api/v1")`):
```python
app.include_router(export_mappings.router, prefix="/api/v1")
```

- [ ] **Step 3: Verify the server starts without errors**

```bash
cd .worktrees/feat/export-field-mapping/backend
uvicorn app.main:app --reload
```

Expected: Server starts. Visit `http://localhost:8000/docs` and confirm `/api/v1/projects/{project_id}/export-mappings` endpoints appear.

Stop the server (Ctrl+C) before continuing.

- [ ] **Step 4: Commit**

```bash
cd .worktrees/feat/export-field-mapping
git add backend/app/routers/export_mappings.py backend/app/main.py
git commit -m "feat: add export-mappings router and register in main"
```

---

## Task 7: Frontend Types + API Wrappers

**Files:**
- Create: `frontend/src/types/exportMapping.ts`
- Create: `frontend/src/api/exportMappings.ts`

- [ ] **Step 1: Create the TypeScript types**

```typescript
// frontend/src/types/exportMapping.ts
export interface ExportMapping {
  id: string
  projectId: string
  dataStoreId: string
  name: string
  fieldMapping: { sourcePath: string; destinationColumn: string }[]
  createdAt: string
  updatedAt: string
}

export interface ExportMappingCreate {
  dataStoreId: string
  name: string
  fieldMapping: { sourcePath: string; destinationColumn: string }[]
}

export interface ExportMappingUpdate {
  name?: string
  fieldMapping?: { sourcePath: string; destinationColumn: string }[]
}
```

- [ ] **Step 2: Create the API wrappers**

```typescript
// frontend/src/api/exportMappings.ts
import apiClient from './client'
import type { ExportMapping, ExportMappingCreate, ExportMappingUpdate } from '@/types/exportMapping'

function toSnakeCase(data: ExportMappingCreate | ExportMappingUpdate): Record<string, unknown> {
  const result: Record<string, unknown> = {}
  if ('dataStoreId' in data && data.dataStoreId !== undefined) {
    result.data_store_id = data.dataStoreId
  }
  if (data.name !== undefined) result.name = data.name
  if (data.fieldMapping !== undefined) result.field_mapping = data.fieldMapping
  return result
}

function fromApi(raw: Record<string, unknown>): ExportMapping {
  return {
    id: raw.id as string,
    projectId: raw.project_id as string,
    dataStoreId: raw.data_store_id as string,
    name: raw.name as string,
    fieldMapping: raw.field_mapping as ExportMapping['fieldMapping'],
    createdAt: raw.created_at as string,
    updatedAt: raw.updated_at as string,
  }
}

export async function listExportMappings(
  projectId: string,
  dataStoreId: string
): Promise<ExportMapping[]> {
  const response = await apiClient.get<Record<string, unknown>[]>(
    `/projects/${projectId}/export-mappings`,
    { params: { data_store_id: dataStoreId } }
  )
  return response.data.map(fromApi)
}

export async function createExportMapping(
  projectId: string,
  data: ExportMappingCreate
): Promise<ExportMapping> {
  const response = await apiClient.post<Record<string, unknown>>(
    `/projects/${projectId}/export-mappings`,
    toSnakeCase(data)
  )
  return fromApi(response.data)
}

export async function updateExportMapping(
  projectId: string,
  mappingId: string,
  data: ExportMappingUpdate
): Promise<ExportMapping> {
  const response = await apiClient.put<Record<string, unknown>>(
    `/projects/${projectId}/export-mappings/${mappingId}`,
    toSnakeCase(data)
  )
  return fromApi(response.data)
}

export async function deleteExportMapping(
  projectId: string,
  mappingId: string
): Promise<void> {
  await apiClient.delete(`/projects/${projectId}/export-mappings/${mappingId}`)
}
```

- [ ] **Step 3: Commit**

```bash
cd .worktrees/feat/export-field-mapping
git add frontend/src/types/exportMapping.ts frontend/src/api/exportMappings.ts
git commit -m "feat: add ExportMapping types and API wrappers"
```

---

## Task 8: useExportMappings Hook

**Files:**
- Create: `frontend/src/hooks/useExportMappings.ts`

- [ ] **Step 1: Create the hook**

```typescript
// frontend/src/hooks/useExportMappings.ts
import { useState, useCallback, useEffect } from 'react'
import type { ExportMapping, ExportMappingCreate, ExportMappingUpdate } from '@/types/exportMapping'
import * as exportMappingsApi from '@/api/exportMappings'

interface UseExportMappingsReturn {
  mappings: ExportMapping[]
  isLoading: boolean
  error: string | null
  create: (data: ExportMappingCreate) => Promise<ExportMapping>
  update: (mappingId: string, data: ExportMappingUpdate) => Promise<ExportMapping>
  remove: (mappingId: string) => Promise<void>
}

export function useExportMappings(
  projectId: string | null,
  dataStoreId: string | null
): UseExportMappingsReturn {
  const [mappings, setMappings] = useState<ExportMapping[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchMappings = useCallback(async () => {
    if (!projectId || !dataStoreId) {
      setMappings([])
      return
    }
    setIsLoading(true)
    setError(null)
    try {
      const result = await exportMappingsApi.listExportMappings(projectId, dataStoreId)
      setMappings(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch mappings')
    } finally {
      setIsLoading(false)
    }
  }, [projectId, dataStoreId])

  const create = useCallback(
    async (data: ExportMappingCreate): Promise<ExportMapping> => {
      if (!projectId) throw new Error('No project selected')
      const mapping = await exportMappingsApi.createExportMapping(projectId, data)
      await fetchMappings()
      return mapping
    },
    [projectId, fetchMappings]
  )

  const update = useCallback(
    async (mappingId: string, data: ExportMappingUpdate): Promise<ExportMapping> => {
      if (!projectId) throw new Error('No project selected')
      const mapping = await exportMappingsApi.updateExportMapping(projectId, mappingId, data)
      await fetchMappings()
      return mapping
    },
    [projectId, fetchMappings]
  )

  const remove = useCallback(
    async (mappingId: string): Promise<void> => {
      if (!projectId) throw new Error('No project selected')
      await exportMappingsApi.deleteExportMapping(projectId, mappingId)
      await fetchMappings()
    },
    [projectId, fetchMappings]
  )

  useEffect(() => {
    if (projectId && dataStoreId) {
      fetchMappings()
    } else {
      setMappings([])
    }
  }, [projectId, dataStoreId, fetchMappings])

  return { mappings, isLoading, error, create, update, remove }
}
```

- [ ] **Step 2: Commit**

```bash
cd .worktrees/feat/export-field-mapping
git add frontend/src/hooks/useExportMappings.ts
git commit -m "feat: add useExportMappings hook"
```

---

## Task 9: Export Playground Persistence UI

**Files:**
- Modify: `frontend/src/pages/ExportPlaygroundPage.tsx`

The toolbar is added between the "Field Mapping" section header and `<FieldMappingEditor>`. The toolbar contains: **Load** (dropdown), **Save** (overwrite current), **Save As** (new name), **Rename**, **Delete**.

- [ ] **Step 1: Replace `ExportPlaygroundPage.tsx` with the updated version**

```tsx
// frontend/src/pages/ExportPlaygroundPage.tsx
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Separator } from '@/components/ui/separator'
import { AlignLeft, Play, RotateCcw, Eye, Save, SaveAll, Pencil, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { useProject } from '@/contexts/ProjectContext'
import { useDataStores } from '@/hooks/useDataStores'
import { useExportMappings } from '@/hooks/useExportMappings'
import { FieldMappingEditor } from '@/components/export/FieldMappingEditor'
import { FanOutPreview } from '@/components/export/FanOutPreview'
import * as dataStoresApi from '@/api/dataStores'
import type { MappingEntry } from '@/components/export/FieldMappingEditor'
import type { ColumnDefinition } from '@/types/dataStore'

export default function ExportPlaygroundPage() {
  const { currentProject } = useProject()
  const projectId = currentProject?.id || null
  const { dataStores } = useDataStores(projectId)

  const [selectedStoreId, setSelectedStoreId] = useState<string>('')
  const [sourceJson, setSourceJson] = useState('')
  const [jsonError, setJsonError] = useState<string | null>(null)
  const [mapping, setMapping] = useState<MappingEntry[]>([])
  const [previewRows, setPreviewRows] = useState<Record<string, unknown>[] | null>(null)
  const [previewError, setPreviewError] = useState<string | null>(null)
  const [isPreviewLoading, setIsPreviewLoading] = useState(false)
  const [isExecuteLoading, setIsExecuteLoading] = useState(false)

  // Persistence state
  const [activeMappingId, setActiveMappingId] = useState<string | null>(null)
  const [activeMappingName, setActiveMappingName] = useState<string | null>(null)
  const [isDirty, setIsDirty] = useState(false)
  const [saveAsName, setSaveAsName] = useState('')
  const [renameName, setRenameName] = useState('')
  const [isSaveAsOpen, setIsSaveAsOpen] = useState(false)
  const [isRenameOpen, setIsRenameOpen] = useState(false)
  const [isDeleteConfirm, setIsDeleteConfirm] = useState(false)

  const { mappings: savedMappings, create, update, remove } = useExportMappings(
    projectId,
    selectedStoreId || null
  )

  const selectedStore = dataStores.find((s) => s.id === selectedStoreId)
  const columns: ColumnDefinition[] = selectedStore?.schemaDefinition || []

  const validateJson = (value: string) => {
    if (!value.trim()) { setJsonError(null); return }
    try { JSON.parse(value); setJsonError(null) }
    catch { setJsonError('Invalid JSON') }
  }

  const formatJson = () => {
    try {
      setSourceJson(JSON.stringify(JSON.parse(sourceJson), null, 2))
      setJsonError(null)
    } catch { setJsonError('Cannot format — invalid JSON') }
  }

  const buildFieldMapping = (): Record<string, string> => {
    const result: Record<string, string> = {}
    for (const entry of mapping) {
      if (entry.sourcePath && entry.destinationColumn) {
        result[entry.sourcePath] = entry.destinationColumn
      }
    }
    return result
  }

  const handleMappingChange = (newMapping: MappingEntry[]) => {
    setMapping(newMapping)
    if (activeMappingId) setIsDirty(true)
  }

  // Load a saved mapping
  const handleLoad = (mappingId: string) => {
    const saved = savedMappings.find((m) => m.id === mappingId)
    if (!saved) return
    setMapping(saved.fieldMapping)
    setActiveMappingId(saved.id)
    setActiveMappingName(saved.name)
    setIsDirty(false)
  }

  // Save (overwrite) the currently loaded mapping
  const handleSave = async () => {
    if (!activeMappingId || !projectId) return
    try {
      await update(activeMappingId, { fieldMapping: mapping })
      setIsDirty(false)
      toast.success('Mapping saved')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Save failed')
    }
  }

  // Save As (create new)
  const handleSaveAs = async () => {
    if (!projectId || !selectedStoreId || !saveAsName.trim()) return
    try {
      const saved = await create({ dataStoreId: selectedStoreId, name: saveAsName.trim(), fieldMapping: mapping })
      setActiveMappingId(saved.id)
      setActiveMappingName(saved.name)
      setIsDirty(false)
      setSaveAsName('')
      setIsSaveAsOpen(false)
      toast.success(`Saved as "${saved.name}"`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Save failed')
    }
  }

  // Rename the loaded mapping
  const handleRename = async () => {
    if (!activeMappingId || !projectId || !renameName.trim()) return
    try {
      const updated = await update(activeMappingId, { name: renameName.trim() })
      setActiveMappingName(updated.name)
      setRenameName('')
      setIsRenameOpen(false)
      toast.success(`Renamed to "${updated.name}"`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Rename failed')
    }
  }

  // Delete the loaded mapping
  const handleDelete = async () => {
    if (!activeMappingId || !projectId) return
    try {
      await remove(activeMappingId)
      setActiveMappingId(null)
      setActiveMappingName(null)
      setIsDirty(false)
      setIsDeleteConfirm(false)
      toast.success('Mapping deleted')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Delete failed')
    }
  }

  const handlePreview = async () => {
    if (!projectId || !selectedStoreId || !sourceJson.trim()) return
    setIsPreviewLoading(true)
    setPreviewError(null)
    setPreviewRows(null)
    try {
      const result = await dataStoresApi.previewExport(projectId, selectedStoreId, {
        sourceData: JSON.parse(sourceJson),
        fieldMapping: buildFieldMapping(),
      })
      setPreviewRows(result.rows)
    } catch (err) {
      setPreviewError(err instanceof Error ? err.message : 'Preview failed')
    } finally {
      setIsPreviewLoading(false)
    }
  }

  const handleExecute = async () => {
    if (!projectId || !selectedStoreId || !sourceJson.trim()) return
    setIsExecuteLoading(true)
    try {
      const result = await dataStoresApi.executeExport(projectId, selectedStoreId, {
        sourceData: JSON.parse(sourceJson),
        fieldMapping: buildFieldMapping(),
      })
      toast.success(`Exported ${result.rowsImported} rows`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Export failed')
    } finally {
      setIsExecuteLoading(false)
    }
  }

  const handleClear = () => {
    setSourceJson('')
    setJsonError(null)
    setMapping([])
    setPreviewRows(null)
    setPreviewError(null)
    setActiveMappingId(null)
    setActiveMappingName(null)
    setIsDirty(false)
  }

  // When store changes, clear loaded mapping
  const handleStoreChange = (storeId: string) => {
    setSelectedStoreId(storeId)
    setActiveMappingId(null)
    setActiveMappingName(null)
    setIsDirty(false)
    setMapping([])
  }

  if (!projectId) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <p className="text-muted-foreground">Select a project to use the Export Playground.</p>
      </div>
    )
  }

  // Used for accessibility title on Load trigger
  const loadTriggerLabel = activeMappingName || 'Load saved mapping'

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Export Playground</h1>
        <p className="text-muted-foreground">Test field mappings and preview array fan-out before exporting</p>
      </div>

      {/* Section 1: Destination */}
      <div className="space-y-3">
        <Label className="text-sm font-medium">Destination Data Store</Label>
        <Select value={selectedStoreId} onValueChange={handleStoreChange}>
          <SelectTrigger>
            <SelectValue placeholder="Select a data store" />
          </SelectTrigger>
          <SelectContent>
            {dataStores.map((store) => (
              <SelectItem key={store.id} value={store.id}>
                {store.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {columns.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {columns.map((col) => (
              <Badge key={col.name} variant="secondary" className="font-mono text-xs">
                {col.name}: {col.type}{!col.nullable && ' *'}
              </Badge>
            ))}
          </div>
        )}
      </div>

      <Separator />

      {/* Section 2: Source Data */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <Label className="text-sm font-medium">Source Data (JSON)</Label>
          <Button variant="outline" size="sm" onClick={formatJson} disabled={!sourceJson.trim()}>
            <AlignLeft className="h-4 w-4 mr-1" /> Format
          </Button>
        </div>
        <Textarea
          value={sourceJson}
          onChange={(e) => setSourceJson(e.target.value)}
          onBlur={() => validateJson(sourceJson)}
          placeholder='{"receipt_date": "2026-04-15", "vendor": "Costco", "items": [{"description": "Bread", "price": 2.50}]}'
          rows={8}
          className={`font-mono text-sm ${jsonError ? 'border-red-500' : ''}`}
        />
        {jsonError && <p className="text-sm text-red-500">{jsonError}</p>}
      </div>

      <Separator />

      {/* Section 3: Field Mapping */}
      {selectedStoreId && (
        <div className="space-y-3">
          {/* Persistence toolbar */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium">Saved Mappings</span>
              {isDirty && activeMappingId && (
                <span className="text-xs text-muted-foreground">(modified)</span>
              )}
            </div>
            <div className="flex items-center gap-1.5">
              {/* Load */}
              <Select
                value={activeMappingId || ''}
                onValueChange={handleLoad}
                disabled={savedMappings.length === 0}
              >
                <SelectTrigger className="h-8 text-xs w-44" title={loadTriggerLabel}>
                  <SelectValue placeholder="Load saved mapping" />
                </SelectTrigger>
                <SelectContent>
                  {savedMappings.map((m) => (
                    <SelectItem key={m.id} value={m.id} className="text-xs">
                      {m.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              {/* Save (overwrite) */}
              <Button
                variant="outline"
                size="sm"
                className="h-8 text-xs"
                onClick={handleSave}
                disabled={!activeMappingId || !isDirty}
                title="Save changes to current mapping"
              >
                <Save className="h-3.5 w-3.5 mr-1" /> Save
              </Button>

              {/* Save As */}
              <Popover open={isSaveAsOpen} onOpenChange={setIsSaveAsOpen}>
                <PopoverTrigger asChild>
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-8 text-xs"
                    disabled={mapping.length === 0}
                    title="Save as new mapping"
                  >
                    <SaveAll className="h-3.5 w-3.5 mr-1" /> Save As
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-64 p-3" align="end">
                  <div className="space-y-2">
                    <p className="text-xs font-medium">Save mapping as</p>
                    <Input
                      value={saveAsName}
                      onChange={(e) => setSaveAsName(e.target.value)}
                      placeholder="e.g. Receipt extractor"
                      className="text-xs h-8"
                      onKeyDown={(e) => e.key === 'Enter' && handleSaveAs()}
                      autoFocus
                    />
                    <Button
                      size="sm"
                      className="w-full h-7 text-xs"
                      onClick={handleSaveAs}
                      disabled={!saveAsName.trim()}
                    >
                      Save
                    </Button>
                  </div>
                </PopoverContent>
              </Popover>

              {/* Rename */}
              <Popover open={isRenameOpen} onOpenChange={(open) => {
                setIsRenameOpen(open)
                if (open) setRenameName(activeMappingName || '')
              }}>
                <PopoverTrigger asChild>
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-8 text-xs"
                    disabled={!activeMappingId}
                    title="Rename current mapping"
                  >
                    <Pencil className="h-3.5 w-3.5 mr-1" /> Rename
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-64 p-3" align="end">
                  <div className="space-y-2">
                    <p className="text-xs font-medium">Rename mapping</p>
                    <Input
                      value={renameName}
                      onChange={(e) => setRenameName(e.target.value)}
                      className="text-xs h-8"
                      onKeyDown={(e) => e.key === 'Enter' && handleRename()}
                      autoFocus
                    />
                    <Button
                      size="sm"
                      className="w-full h-7 text-xs"
                      onClick={handleRename}
                      disabled={!renameName.trim() || renameName.trim() === activeMappingName}
                    >
                      Rename
                    </Button>
                  </div>
                </PopoverContent>
              </Popover>

              {/* Delete */}
              {isDeleteConfirm ? (
                <div className="flex items-center gap-1">
                  <span className="text-xs text-muted-foreground">Delete?</span>
                  <Button
                    variant="destructive"
                    size="sm"
                    className="h-8 text-xs"
                    onClick={handleDelete}
                  >
                    Yes
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-8 text-xs"
                    onClick={() => setIsDeleteConfirm(false)}
                  >
                    No
                  </Button>
                </div>
              ) : (
                <Button
                  variant="outline"
                  size="sm"
                  className="h-8 text-xs"
                  onClick={() => setIsDeleteConfirm(true)}
                  disabled={!activeMappingId}
                  title="Delete current mapping"
                >
                  <Trash2 className="h-3.5 w-3.5 text-muted-foreground" />
                </Button>
              )}
            </div>
          </div>

          <FieldMappingEditor
            sourceJson={sourceJson}
            destinationColumns={columns}
            mapping={mapping}
            onChange={handleMappingChange}
          />
        </div>
      )}

      <Separator />

      {/* Section 4: Preview & Execute */}
      <div className="space-y-4">
        <div className="flex gap-2">
          <Button
            onClick={handlePreview}
            disabled={!selectedStoreId || !sourceJson.trim() || mapping.length === 0 || isPreviewLoading}
          >
            <Eye className="h-4 w-4 mr-1" />
            {isPreviewLoading ? 'Previewing...' : 'Preview'}
          </Button>
          <Button
            variant="default"
            onClick={handleExecute}
            disabled={!previewRows || previewRows.length === 0 || isExecuteLoading}
          >
            <Play className="h-4 w-4 mr-1" />
            {isExecuteLoading ? 'Exporting...' : 'Execute'}
          </Button>
          <Button variant="outline" onClick={handleClear}>
            <RotateCcw className="h-4 w-4 mr-1" /> Clear
          </Button>
        </div>

        {previewError && (
          <Alert variant="destructive">
            <AlertDescription>{previewError}</AlertDescription>
          </Alert>
        )}

        {previewRows && (
          <FanOutPreview rows={previewRows} columns={columns} />
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Run the frontend linter**

```bash
cd .worktrees/feat/export-field-mapping/frontend
npm run lint
```

Expected: No errors.

- [ ] **Step 3: Run the frontend build**

```bash
cd .worktrees/feat/export-field-mapping/frontend
npm run build
```

Expected: Build succeeds with no TypeScript errors.

- [ ] **Step 4: Commit**

```bash
cd .worktrees/feat/export-field-mapping
git add frontend/src/pages/ExportPlaygroundPage.tsx
git commit -m "feat: add mapping persistence toolbar to Export Playground"
```

---

## Task 10: Manual Verification

- [ ] **Step 1: Start the stack**

```bash
cd .worktrees/feat/export-field-mapping
docker compose -p rag-admin -f docker-compose.local.yml up -d
```

- [ ] **Step 2: Verify the migration ran**

```bash
docker compose -p rag-admin -f docker-compose.local.yml exec db psql -U postgres -d rag_admin -c "\d export_mappings"
```

Expected: Table with columns `id`, `project_id`, `data_store_id`, `name`, `field_mapping`, `created_at`, `updated_at`.

- [ ] **Step 3: Test the full flow in the browser**

Navigate to `http://localhost:5173/export`.

1. Select a data store — the "Saved Mappings" toolbar appears
2. Paste source JSON and configure a field mapping
3. Click **Save As**, enter a name, click Save — toast confirms, mapping appears in Load dropdown
4. Modify a mapping row — Load trigger shows `•` prefix (dirty indicator)
5. Click **Save** — dirty indicator clears
6. Click **Rename**, enter a new name — name updates in dropdown trigger
7. Load a different saved mapping (if you create a second one) — editor updates
8. Click **Delete** → confirm Yes — mapping removed, toolbar resets
9. Click **Clear** — all state resets

---

## Done

All tasks complete. Use `superpowers:finishing-a-development-branch` to create the PR.
