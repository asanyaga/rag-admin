# Documents Feature: Implementation Plan

**Status**: Ready for Implementation
**Estimated Time**: ~19 hours over 2 weeks
**Last Updated**: 2025-02-04

---

## Executive Summary

This implementation plan provides detailed, phase-by-phase instructions for building the Documents feature in RAG Admin. The feature enables users to upload PDF documents, extract text, and prepare documents for future RAG indexing.

### Key Decisions Made

1. **Hybrid Schema**: Universal fields as columns, source-specific in JSONB
2. **Page Markers**: Embedded in `extracted_text` as `[Page N]` (no separate `page_texts`)
3. **Simplified Viewer**: Text-only display + download button (no react-pdf for MVP)
4. **Text Storage**: Database TEXT column (not separate file)
5. **No ClamAV**: Skipped for MVP (file validation only)
6. **BackgroundTasks**: FastAPI native (no Redis/ARQ for MVP)

---

## Architecture Overview

```
Upload Request
    ↓
Router → Service → Repository → Database
    ↓
BackgroundTask → Extract Text (LlamaIndex) → Update Status
    ↓
Frontend Polling → Display Ready Document
```

**Ports & Adapters**:
- `StorageService` port → `LocalStorageService` adapter
- `DocumentExtractor` port → `LlamaIndexExtractor` adapter

---

## Phase Breakdown

| Phase | Description | Time | Key Files |
|-------|-------------|------|-----------|
| 1 | Database & Models | 2h | Migration, models, schemas |
| 2 | Ports & Adapters | 3h | Interfaces, adapters, validation |
| 3 | Repository & Service | 3h | Data access, business logic |
| 4 | API Endpoints | 2h | FastAPI routes |
| 5 | Frontend API Layer | 2h | Types, API client, hooks |
| 6 | Frontend UI | 4h | Components, page |
| 7 | Testing | 3h | Unit tests, E2E verification |

---

## Database Schema (Final)

```sql
CREATE TYPE document_status AS ENUM ('processing', 'ready', 'failed');

CREATE TABLE documents (
    -- Identity
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,

    -- Source tracking
    source_type VARCHAR(50) NOT NULL,        -- 'upload', 'gdrive', 'web', etc.
    source_identifier VARCHAR(500) NOT NULL, -- Checksum for uploads, URL for web

    -- Universal metadata
    title VARCHAR(255) NOT NULL,
    description TEXT,

    -- Content (for RAG)
    extracted_text TEXT,  -- Contains [Page N] markers

    -- Source-specific details (JSONB)
    source_metadata JSONB NOT NULL DEFAULT '{}',
    -- For uploads: {filename, file_path, file_size, mime_type, checksum, page_count}

    -- Processing metadata (JSONB)
    processing_metadata JSONB DEFAULT '{}',
    -- {extraction_method, extraction_version, extracted_at, duration_ms, token_count}

    -- Status
    status document_status NOT NULL DEFAULT 'processing',
    status_message TEXT,

    -- Audit
    created_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraints
    CONSTRAINT uq_documents_project_source
    UNIQUE (project_id, source_type, source_identifier)
);

-- Indexes
CREATE INDEX ix_documents_project_id ON documents(project_id);
CREATE INDEX ix_documents_source_type ON documents(source_type);
CREATE INDEX ix_documents_status ON documents(status);
CREATE INDEX ix_documents_created_at ON documents(created_at);
CREATE INDEX ix_documents_source_metadata ON documents USING GIN (source_metadata);
CREATE INDEX ix_documents_processing_metadata ON documents USING GIN (processing_metadata);
```

**Key Design Decisions**:
- `source_identifier` = checksum for files, URL for web, etc. (prevents duplicates)
- `extracted_text` = full text with page markers (no separate page_texts)
- `source_metadata` = flexible JSONB for source-specific fields
- `processing_metadata` = extraction info for debugging/monitoring

---

## Implementation Phases

### Phase 1: Database & Models (2 hours)

**Goal**: Create database schema, SQLAlchemy models, Pydantic schemas

**Files**:
1. `backend/alembic/versions/XXXXX_add_documents_table.py` - Migration
2. `backend/app/models/document.py` - SQLAlchemy model
3. `backend/app/schemas/document.py` - Pydantic schemas
4. `backend/app/models/project.py` - Add relationship

**Key Code**: See full implementation plan sections 1.1-1.4

**Verification**:
```bash
alembic revision --autogenerate -m "Add documents table"
alembic upgrade head
psql -U ragadmin -d ragadmin -c "\d documents"
```

---

### Phase 2: Ports & Adapters (3 hours)

**Goal**: Create port interfaces and adapter implementations

**Files**:
1. `backend/app/ports/storage.py` - StorageService interface
2. `backend/app/ports/document_processing.py` - DocumentExtractor interface
3. `backend/app/adapters/storage/local.py` - LocalStorageService
4. `backend/app/adapters/llamaindex/extractor.py` - LlamaIndexExtractor
5. `backend/app/utils/file_validation.py` - Validation utilities
6. `backend/app/core/dependencies.py` - DI factories

**Key Patterns**:
- Protocol-based interfaces (not ABC)
- Adapter implements protocol
- Factory functions in dependencies.py

**Verification**:
```python
# Test storage
storage = LocalStorageService("/tmp/test")
path = await storage.save(b"test", "test/file.txt")
content = await storage.get(path)

# Test extractor
extractor = LlamaIndexExtractor()
result = await extractor.extract("sample.pdf", "application/pdf")
assert "[Page 1]" in result.text
```

---

### Phase 3: Repository & Service (3 hours)

**Goal**: Implement data access and business logic

**Files**:
1. `backend/app/repositories/document_repository.py` - CRUD operations
2. `backend/app/services/document_service.py` - Business logic
3. `backend/app/exceptions.py` - Custom exceptions

**Key Methods**:
- `DocumentRepository.get_by_id()` - With user access check
- `DocumentService.initiate_upload()` - Validates, saves, creates record
- Background processing function - Extract text, update status

**User Scoping**: All repository methods check `Project.user_id` via JOIN

**Verification**: Unit tests for repository and service

---

### Phase 4: API Endpoints (2 hours)

**Goal**: Create REST API endpoints

**File**: `backend/app/routers/documents.py`

**Endpoints**:
- `POST /documents` - Upload (returns 202 Accepted)
- `GET /documents` - List with optional filters
- `GET /documents/{id}` - Get details
- `GET /documents/{id}/file` - Download original
- `GET /documents/{id}/text` - Get extracted text
- `PATCH /documents/{id}` - Update metadata
- `DELETE /documents/{id}` - Delete

**Background Task**: `process_document_background()` runs after upload response

**Verification**:
```bash
curl -X POST .../documents -F "file=@test.pdf" -F "title=Test"
# Returns 202 with document ID, status='processing'

# Poll status
curl .../documents/{id}
# Eventually status='ready'

# Get text
curl .../documents/{id}/text
```

---

### Phase 5: Frontend API Layer (2 hours)

**Goal**: Create TypeScript types, API client, hooks

**Files**:
1. `frontend/src/types/document.ts` - TypeScript interfaces
2. `frontend/src/api/documents.ts` - API functions
3. `frontend/src/hooks/useDocuments.ts` - State management + polling

**Key Hook**: `useDocuments()` auto-polls processing documents

**Verification**:
```typescript
const { documents, uploadDocument } = useDocuments(projectId);
await uploadDocument({ file, title: "Test" });
// Automatically polls until ready
```

---

### Phase 6: Frontend UI (4 hours)

**Goal**: Build React components and page

**Files**:
1. `DocumentUploadZone.tsx` - Drag-drop with progress
2. `DocumentsTable.tsx` - List with actions
3. `DocumentStatusBadge.tsx` - Animated status
4. `DocumentTextViewer.tsx` - Text display (simplified, no PDF viewer)
5. `DocumentEditDialog.tsx` - Edit metadata
6. `DocumentDeleteDialog.tsx` - Confirmation
7. `ProjectDocumentsPage.tsx` - Main page

**UI Pattern**: Follows shadcn/ui conventions (Card, Dialog, Table, etc.)

**Verification**: Navigate to `/projects/{id}/documents` and test all interactions

---

### Phase 7: Testing (3 hours)

**Goal**: Write tests and perform E2E verification

**Test Files**:
1. `tests/repositories/test_document_repository.py`
2. `tests/services/test_document_service.py`
3. `tests/routers/test_documents.py`
4. Manual E2E checklist

**Run Tests**:
```bash
cd backend
pytest --cov=app --cov-report=html
open htmlcov/index.html
```

**E2E Checklist**: Upload → View → Edit → Download → Delete

---

## Configuration

### Environment Variables

```env
# .env
DOCUMENT_STORAGE_PATH=/data/documents
MAX_UPLOAD_SIZE_MB=25
ALLOWED_MIME_TYPES=application/pdf
RAG_FRAMEWORK=llamaindex
```

### Docker Volume

```yaml
# docker-compose.yml
services:
  backend:
    volumes:
      - documents-data:/data/documents

volumes:
  documents-data:
```

---

## Key Code Patterns

### 1. User Access Control (Repository)

```python
stmt = (
    select(Document)
    .join(Document.project)
    .where(
        and_(
            Document.id == document_id,
            Project.user_id == user_id  # Ensures user owns project
        )
    )
)
```

### 2. Background Processing (Router)

```python
@router.post("", status_code=202)
async def upload_document(background_tasks: BackgroundTasks, ...):
    # Validate, save, create record (sync)
    document = await service.initiate_upload(...)

    # Schedule background task
    background_tasks.add_task(process_document_background, document.id, ...)

    # Return immediately
    return document  # status='processing'
```

### 3. Page Marker Extraction

```python
# LlamaIndex extractor adds markers
pages_with_markers = []
for i, doc in enumerate(documents, 1):
    pages_with_markers.append(f"[Page {i}]\n{doc.text}")

combined_text = "\n\n".join(pages_with_markers)
```

### 4. Frontend Auto-Polling

```typescript
// Start polling processing documents
data.forEach(doc => {
  if (doc.status === 'processing') {
    startPolling(doc.id);  // Poll every 2s
  }
});

// Stop when status changes
if (updated.status !== 'processing') {
  stopPolling(documentId);
}
```

---

## Success Criteria

Feature is complete when:

1. ✅ Users can upload PDFs with drag-drop
2. ✅ Upload returns immediately (202) with status='processing'
3. ✅ Background task extracts text asynchronously
4. ✅ File validation rejects invalid types/sizes
5. ✅ Duplicate detection works (same checksum)
6. ✅ Documents list shows with status indicators
7. ✅ Users can view extracted text (full + by page)
8. ✅ Users can download original PDF
9. ✅ Users can edit title/description
10. ✅ Users can delete documents
11. ✅ Frontend auto-polls processing documents
12. ✅ All backend tests pass
13. ✅ E2E workflow verified manually

---

## Trade-offs & Future Enhancements

### Simplified for MVP

| Feature | MVP Approach | Future Enhancement |
|---------|--------------|-------------------|
| Viewer | Text only + download | Add react-pdf dual-panel |
| Text Storage | Database TEXT column | Move to files if >1MB |
| Malware Scan | File validation only | Add ClamAV |
| Async Jobs | BackgroundTasks | Migrate to ARQ + Redis |
| File Types | PDF only | Add DOCX, PPTX, etc. |
| Sources | Upload only | Add gdrive, web, notion |

### When to Upgrade

**Add Task Queue** when:
- Documents stuck in "processing" after server restart
- Need retry logic with backoff
- Want job monitoring dashboard

**Add react-pdf Viewer** when:
- Users request visual PDF preview
- Need page-level highlighting
- Building annotation features

---

## Troubleshooting

### Common Issues

**Issue**: Migration fails with "type already exists"
```sql
-- Solution: Check if type exists first
DO $$ BEGIN
    CREATE TYPE document_status AS ENUM ('processing', 'ready', 'failed');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;
```

**Issue**: Background task doesn't run
```python
# Solution: Check BackgroundTasks import and usage
from fastapi import BackgroundTasks

# Must pass background_tasks to function
async def upload_document(background_tasks: BackgroundTasks, ...):
    background_tasks.add_task(process_document_background, ...)
```

**Issue**: Frontend polling doesn't stop
```typescript
// Solution: Cleanup on unmount
useEffect(() => {
  return () => {
    pollingIntervals.current.forEach(interval => clearInterval(interval));
  };
}, []);
```

**Issue**: LlamaIndex extraction fails
```bash
# Solution: Check dependencies installed
pip install llama-index llama-index-readers-file
```

---

## Dependencies

### Backend (Python)

```bash
pip install llama-index llama-index-readers-file aiofiles
```

### Frontend (Node)

```bash
npm install date-fns
```

---

## File Checklist

### Backend (13 files)

- [ ] `alembic/versions/XXXXX_add_documents_table.py`
- [ ] `app/models/document.py`
- [ ] `app/schemas/document.py`
- [ ] `app/ports/storage.py`
- [ ] `app/ports/document_processing.py`
- [ ] `app/adapters/storage/local.py`
- [ ] `app/adapters/llamaindex/extractor.py`
- [ ] `app/utils/file_validation.py`
- [ ] `app/repositories/document_repository.py`
- [ ] `app/services/document_service.py`
- [ ] `app/routers/documents.py`
- [ ] `app/core/dependencies.py` (modify)
- [ ] `app/models/project.py` (modify)

### Frontend (10 files)

- [ ] `types/document.ts`
- [ ] `api/documents.ts`
- [ ] `hooks/useDocuments.ts`
- [ ] `components/documents/DocumentUploadZone.tsx`
- [ ] `components/documents/DocumentsTable.tsx`
- [ ] `components/documents/DocumentStatusBadge.tsx`
- [ ] `components/documents/DocumentTextViewer.tsx`
- [ ] `components/documents/DocumentEditDialog.tsx`
- [ ] `components/documents/DocumentDeleteDialog.tsx`
- [ ] `pages/ProjectDocumentsPage.tsx`

### Tests (4 files)

- [ ] `tests/repositories/test_document_repository.py`
- [ ] `tests/services/test_document_service.py`
- [ ] `tests/routers/test_documents.py`
- [ ] `tests/conftest.py` (add fixtures)

**Total**: 27 files

---

## Next Steps

1. Review this plan
2. Start with Phase 1 (Database & Models)
3. Verify each phase before moving to next
4. Run tests after Phase 3 (backend complete)
5. Test E2E after Phase 6 (frontend complete)
6. Deploy and monitor
7. Gather feedback for future enhancements

---

**Ready to implement!** Refer to detailed code in full conversation history.
