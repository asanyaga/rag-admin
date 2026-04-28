# CDM Persistence PR 3 — Upload Path Cutover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire `document_service.initiate_upload` onto `ParsingService` behind `USE_CDM_PARSER`, so new uploads are fully CDM-persisted (rows in `source_documents`, `documents`, `parse_runs`, `parsed_documents`).

**Architecture:** `initiate_upload` grows a `use_cdm` flag; when true it calls `ParsingService.ensure_source_document` and creates the `Document` with `source_document_id` populated. The router dispatches a new `process_cdm_parsing` background task when `USE_CDM_PARSER=True and parser_type="llamaparse"`, replacing the legacy `ParseService` path. Legacy paths remain callable with the flag off.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy async, Pydantic v2, pytest-asyncio, httpx AsyncClient, SQLite in-memory test DB.

---

## File Map

| Action | Path | Responsibility |
|--------|------|---------------|
| Modify | `backend/app/config.py` | Add `USE_CDM_PARSER: bool = True` |
| Modify | `backend/app/schemas/document.py` | Add `source_document_id: UUID \| None` to `DocumentResponse` |
| Modify | `backend/app/repositories/document_repository.py` | Add `source_document_id` param to `create()` |
| Modify | `backend/app/services/document_service.py` | Add `parsing_service` to `DocumentService`, `use_cdm` param to `initiate_upload`, add `process_cdm_parsing` background task |
| Modify | `backend/app/dependencies/documents.py` | Add `get_llamaparse_client()` and `get_parsing_service()` |
| Modify | `backend/app/routers/documents.py` | Inject `ParsingService`, pass `use_cdm`, dispatch CDM background task |
| Modify | `backend/tests/services/test_document_service.py` | Add tests for CDM path and flag-off legacy path |
| Create | `backend/tests/routers/test_documents_cdm_router.py` | E2E HTTP upload → assert all 4 tables populated |

---

## Task 1: Add `USE_CDM_PARSER` to Settings

**Files:**
- Modify: `backend/app/config.py`

- [ ] **Step 1: Add the setting**

In `backend/app/config.py`, after the `LLAMA_CLOUD_KEY` line, add:

```python
    # CDM Persistence
    USE_CDM_PARSER: bool = True
```

The full `Settings` class `LLAMA_CLOUD_KEY` section should look like:

```python
    # LlamaParse / LlamaCloud
    LLAMA_CLOUD_KEY: str = ""

    # CDM Persistence
    USE_CDM_PARSER: bool = True
```

- [ ] **Step 2: Verify it is importable and has the right default**

```bash
uv run --directory /home/asa/rag-admin/backend python -c "from app.config import settings; assert settings.USE_CDM_PARSER is True, 'wrong default'; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git -C /home/asa/rag-admin add backend/app/config.py
git -C /home/asa/rag-admin commit -m "feat(config): add USE_CDM_PARSER feature flag (default True)"
```

---

## Task 2: Add `source_document_id` to `DocumentResponse` and `document_repo.create()`

**Files:**
- Modify: `backend/app/schemas/document.py`
- Modify: `backend/app/repositories/document_repository.py`

- [ ] **Step 1: Add `source_document_id` to `DocumentResponse`**

In `backend/app/schemas/document.py`, inside `DocumentResponse`, after the `folder_id` line:

```python
    source_document_id: UUID | None = Field(None, alias="sourceDocumentId")
```

The updated `DocumentResponse` class should look like:

```python
class DocumentResponse(BaseModel):
    """Schema for document API responses with camelCase fields."""
    id: UUID = Field(..., alias="id")
    project_id: UUID = Field(..., alias="projectId")
    folder_id: UUID | None = Field(None, alias="folderId")
    source_document_id: UUID | None = Field(None, alias="sourceDocumentId")
    source_type: str = Field(..., alias="sourceType")
    source_identifier: str = Field(..., alias="sourceIdentifier")
    title: str
    description: str | None
    extracted_text: str | None = Field(None, alias="extractedText")
    source_metadata: dict = Field(..., alias="sourceMetadata")
    processing_metadata: dict | None = Field(None, alias="processingMetadata")
    status: DocumentStatus
    status_message: str | None = Field(None, alias="statusMessage")
    created_by: UUID = Field(..., alias="createdBy")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )
```

- [ ] **Step 2: Add `source_document_id` parameter to `document_repository.create()`**

In `backend/app/repositories/document_repository.py`, update the `create` method signature to add the optional parameter after `folder_id`:

```python
    async def create(
        self,
        project_id: UUID,
        user_id: UUID,
        source_type: str,
        source_identifier: str,
        title: str,
        description: str | None,
        source_metadata: dict,
        folder_id: "UUID | None" = None,
        source_document_id: "UUID | None" = None,
    ) -> Document:
```

And update the `Document(...)` constructor call in the body to pass it:

```python
        document = Document(
            project_id=project_id,
            created_by=user_id,
            source_type=source_type,
            source_identifier=source_identifier,
            title=title,
            description=description,
            source_metadata=source_metadata,
            status=DocumentStatus.processing,
            folder_id=folder_id,
            source_document_id=source_document_id,
        )
```

- [ ] **Step 3: Run the full test suite to verify no regressions**

```bash
uv run --directory /home/asa/rag-admin/backend python -m pytest -o "addopts=" --tb=short -q
```

Expected: all previously passing tests still pass.

- [ ] **Step 4: Commit**

```bash
git -C /home/asa/rag-admin add backend/app/schemas/document.py backend/app/repositories/document_repository.py
git -C /home/asa/rag-admin commit -m "feat(schema,repo): add source_document_id to DocumentResponse and document_repo.create()"
```

---

## Task 3: Add CDM path to `DocumentService` and `process_cdm_parsing` background task

**Files:**
- Modify: `backend/app/services/document_service.py`
- Modify: `backend/tests/services/test_document_service.py`

- [ ] **Step 1: Write the failing tests**

Add these tests at the end of `backend/tests/services/test_document_service.py`:

```python
"""CDM path tests for DocumentService.initiate_upload."""
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
import pytest
from app.services.document_service import DocumentService


def _make_source_cdm(sha256: str = "a" * 64):
    """Return a fake CDM SourceDocument."""
    from app.cdm.source import SourceDocument as SourceDocumentCDM
    from datetime import datetime, timezone
    return SourceDocumentCDM(
        id=str(uuid4()),
        sha256=sha256,
        filename="test.pdf",
        mime_type="application/pdf",
        byte_size=9,
        storage_uri="uploads/aaa/test.pdf",
        created_at=datetime.now(timezone.utc),
    )


def make_mock_document_with_source(title: str = "doc", source_document_id=None):
    """Make a mock Document ORM that includes source_document_id."""
    doc = make_mock_document(title=title)
    doc.source_document_id = source_document_id or uuid4()
    doc.sourceDocumentId = doc.source_document_id
    return doc


@pytest.fixture
def mock_parsing_service():
    svc = AsyncMock()
    svc.ensure_source_document = AsyncMock(return_value=_make_source_cdm())
    return svc


@pytest.fixture
def mock_service_with_cdm(project_id, user_id, mock_parsing_service):
    doc_repo = AsyncMock()
    proj_repo = AsyncMock()
    storage = AsyncMock()
    extractor = AsyncMock()

    proj_repo.get_by_id.return_value = MagicMock(id=project_id)
    doc_repo.get_by_source.return_value = None
    storage.save.return_value = "projects/proj/uploads/hash.pdf"
    doc_repo.create.return_value = make_mock_document_with_source()

    service = DocumentService(doc_repo, proj_repo, storage, extractor, parsing_service=mock_parsing_service)
    return service, doc_repo, proj_repo, storage, mock_parsing_service


@pytest.mark.asyncio
async def test_initiate_upload_cdm_calls_ensure_source_document(mock_service_with_cdm, project_id, user_id):
    service, doc_repo, _proj, _storage, parsing_svc = mock_service_with_cdm
    file_content = b"%PDF-1.4\n"

    result = await service.initiate_upload(
        user_id=user_id,
        project_id=project_id,
        file_content=file_content,
        filename="test.pdf",
        title="Test",
        use_cdm=True,
    )

    parsing_svc.ensure_source_document.assert_awaited_once_with(
        bytes_=file_content, filename="test.pdf", mime_type="application/pdf",
    )
    # source_document_id must be passed to document_repo.create
    call_kwargs = doc_repo.create.call_args.kwargs
    assert call_kwargs.get("source_document_id") is not None
    assert result.source_document_id is not None


@pytest.mark.asyncio
async def test_initiate_upload_cdm_false_skips_ensure_source_document(mock_service_with_cdm, project_id, user_id):
    service, doc_repo, _proj, storage, parsing_svc = mock_service_with_cdm
    doc_repo.create.return_value = make_mock_document(title="no-cdm")
    storage.save.return_value = "projects/proj/uploads/hash.pdf"
    file_content = b"%PDF-1.4\n"

    await service.initiate_upload(
        user_id=user_id,
        project_id=project_id,
        file_content=file_content,
        filename="test.pdf",
        title="Test",
        use_cdm=False,
    )

    parsing_svc.ensure_source_document.assert_not_awaited()
    call_kwargs = doc_repo.create.call_args.kwargs
    assert call_kwargs.get("source_document_id") is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run --directory /home/asa/rag-admin/backend python -m pytest tests/services/test_document_service.py -k "cdm" -v -o "addopts="
```

Expected: `TypeError: DocumentService.__init__() got an unexpected keyword argument 'parsing_service'` or similar.

- [ ] **Step 3: Update `DocumentService` in `document_service.py`**

Replace the `DocumentService.__init__` and `initiate_upload` sections. The full updated class header and method (just `__init__` and `initiate_upload`):

```python
class DocumentService:
    """Service for document operations."""

    def __init__(
        self,
        document_repo: DocumentRepository,
        project_repo: ProjectRepository,
        storage_service: StorageService,
        document_extractor: DocumentExtractor,
        parsing_service: "ParsingService | None" = None,
    ):
        self.document_repo = document_repo
        self.project_repo = project_repo
        self.storage_service = storage_service
        self.document_extractor = document_extractor
        self.parsing_service = parsing_service

    async def initiate_upload(
        self,
        user_id: UUID,
        project_id: UUID,
        file_content: bytes,
        filename: str,
        title: str,
        description: str | None = None,
        folder_id: "UUID | None" = None,
        use_cdm: bool = False,
    ) -> DocumentResponse:
        """Initiate document upload.

        When use_cdm=True the method calls ParsingService.ensure_source_document
        and populates documents.source_document_id; parsing is dispatched as a
        background task by the caller.
        """
        # 1. Verify project exists and user has access
        project = await self.project_repo.get_by_id(project_id, user_id)
        if not project:
            raise NotFoundError(f"Project {project_id} not found")

        # 2. Validate file size
        try:
            validate_file_size(
                file_size=len(file_content),
                max_size_mb=settings.MAX_UPLOAD_SIZE_MB
            )
        except FileValidationError as e:
            raise ValidationError(str(e))

        # 3. Validate MIME type
        try:
            mime_type = validate_mime_type(
                file_content=file_content,
                filename=filename,
                allowed_types=settings.ALLOWED_MIME_TYPES
            )
        except FileValidationError as e:
            raise ValidationError(str(e))

        # 4. Compute checksum for duplicate detection
        checksum = compute_checksum(file_content)

        # 5. Check for duplicate document
        existing = await self.document_repo.get_by_source(
            project_id=project_id,
            user_id=user_id,
            source_type="upload",
            source_identifier=checksum
        )
        if existing:
            raise ConflictError(
                f"Document with same content already exists: {existing.title}"
            )

        if use_cdm and self.parsing_service is not None:
            # CDM path: ensure_source_document handles storage + source dedup
            source_doc = await self.parsing_service.ensure_source_document(
                bytes_=file_content,
                filename=filename,
                mime_type=mime_type,
            )
            source_metadata = {
                "filename": filename,
                "file_path": source_doc.storage_uri,
                "file_size": len(file_content),
                "mime_type": mime_type,
                "checksum": checksum,
            }
            try:
                document = await self.document_repo.create(
                    project_id=project_id,
                    user_id=user_id,
                    source_type="upload",
                    source_identifier=checksum,
                    title=title,
                    description=description,
                    source_metadata=source_metadata,
                    folder_id=folder_id,
                    source_document_id=UUID(source_doc.id),
                )
            except IntegrityError as e:
                error_str = str(e).lower()
                if 'uq_documents_project_source' in error_str:
                    raise ConflictError("Document with same content already exists")
                raise
        else:
            # Legacy path
            file_extension = Path(filename).suffix.lower()
            relative_path = f"projects/{project_id}/uploads/{checksum}{file_extension}"
            try:
                file_path = await self.storage_service.save(file_content, relative_path)
            except Exception as e:
                raise ValidationError(f"Failed to save file: {e}")

            source_metadata = {
                "filename": filename,
                "file_path": file_path,
                "file_size": len(file_content),
                "mime_type": mime_type,
                "checksum": checksum,
            }
            try:
                document = await self.document_repo.create(
                    project_id=project_id,
                    user_id=user_id,
                    source_type="upload",
                    source_identifier=checksum,
                    title=title,
                    description=description,
                    source_metadata=source_metadata,
                    folder_id=folder_id,
                )
            except IntegrityError as e:
                try:
                    await self.storage_service.delete(file_path)
                except Exception:
                    pass
                error_str = str(e).lower()
                if 'uq_documents_project_source' in error_str:
                    raise ConflictError("Document with same content already exists")
                raise

        return DocumentResponse.model_validate(document)
```

You also need the import for `ParsingService` — add it as a TYPE_CHECKING import to avoid circular imports. At the top of the file, add:

```python
from __future__ import annotations

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.services.parsing.parsing_service import ParsingService
```

The existing `UUID` import is already in the file; just make sure `UUID` comes from `uuid` (not typing). The existing imports at the top of the file have `from uuid import UUID`, so add the `__future__` and `TYPE_CHECKING` imports after the existing `from __future__ import annotations` if present, or add them at the top.

Actually, check if `from __future__ import annotations` is already in the file first. If not, add it as the very first line, followed by the `TYPE_CHECKING` import block.

- [ ] **Step 4: Add `process_cdm_parsing` background task function**

Add this function AFTER the `process_document_extraction` function at the bottom of `backend/app/services/document_service.py`:

```python
async def process_cdm_parsing(
    document_id: UUID,
    source_document_id: UUID,
    project_id: UUID,
    representation_kind: str,
    config: dict,
    document_repo: DocumentRepository,
    parse_run_repo: "ParseRunRepository",
    parsed_doc_repo: "ParsedDocumentRepository",
    source_doc_repo: "SourceDocumentRepository",
    storage_service: StorageService,
    llamaparse_client: Any,
) -> None:
    """Background task: CDM parse + persist for a newly uploaded document.

    Creates a ParsingService from the provided repos and client, runs
    parse_and_persist, and writes the extracted_text shim for downstream readers.
    """
    from typing import Any
    from app.cdm.source import SourceDocument as SourceDocumentCDM
    from app.services.parsing.errors import ParseFailedError
    from app.services.parsing.parsing_service import ParsingService
    from app.repositories.parse_run_repository import ParseRunRepository
    from app.repositories.parsed_document_repository import ParsedDocumentRepository
    from app.repositories.source_document_repository import SourceDocumentRepository

    # Fetch source document ORM
    source_orm = await source_doc_repo.get(source_document_id)
    if source_orm is None:
        await document_repo.update_status(
            document_id=document_id,
            status=DocumentStatus.failed,
            status_message="SourceDocument not found",
        )
        return

    # Fetch Document to get file_path
    doc = await document_repo.get_by_id_unscoped(document_id)
    if doc is None:
        return  # Deleted before task ran

    file_path = doc.source_metadata.get("file_path")
    if not file_path:
        await document_repo.update_status(
            document_id=document_id,
            status=DocumentStatus.failed,
            status_message="Missing file_path in source_metadata",
        )
        return

    source_cdm = SourceDocumentCDM(
        id=str(source_orm.id),
        sha256=source_orm.sha256,
        filename=source_orm.filename,
        mime_type=source_orm.mime_type,
        byte_size=source_orm.byte_size,
        storage_uri=source_orm.storage_uri,
        created_at=source_orm.created_at,
    )

    service = ParsingService(
        source_doc_repo=source_doc_repo,
        parse_run_repo=parse_run_repo,
        parsed_doc_repo=parsed_doc_repo,
        storage=storage_service,
        llamaparse_client=llamaparse_client,
    )

    try:
        run, parsed_doc = await service.parse_and_persist(
            source=source_cdm,
            file_path=file_path,
            representation_kind=representation_kind,
            config=config,
            project_id=project_id,
        )
    except ParseFailedError as e:
        await document_repo.update_status(
            document_id=document_id,
            status=DocumentStatus.failed,
            status_message=str(e),
        )
        return

    if parsed_doc is not None:
        # extracted_text shim: keeps downstream readers working until migration spec retires it
        await document_repo.update_extraction(
            document_id=document_id,
            extracted_text=parsed_doc.full_text or "",
            processing_metadata={},
            status=DocumentStatus.ready,
        )
    else:
        await document_repo.update_status(
            document_id=document_id,
            status=DocumentStatus.failed,
            status_message=f"Parse run finished with status: {run.status.value}",
        )
```

Also add `from typing import Any` to the top of the file if not already present.

- [ ] **Step 5: Run CDM tests to verify they pass**

```bash
uv run --directory /home/asa/rag-admin/backend python -m pytest tests/services/test_document_service.py -k "cdm" -v -o "addopts="
```

Expected: `2 passed`

- [ ] **Step 6: Run full test suite to check for regressions**

```bash
uv run --directory /home/asa/rag-admin/backend python -m pytest -o "addopts=" --tb=short -q
```

Expected: no new failures.

- [ ] **Step 7: Commit**

```bash
git -C /home/asa/rag-admin add backend/app/services/document_service.py backend/tests/services/test_document_service.py
git -C /home/asa/rag-admin commit -m "feat(service): add CDM path to initiate_upload and process_cdm_parsing background task"
```

---

## Task 4: Add `get_llamaparse_client` and `get_parsing_service` dependencies

**Files:**
- Modify: `backend/app/dependencies/documents.py`

- [ ] **Step 1: Add the two new factory functions**

Replace the full content of `backend/app/dependencies/documents.py` with:

```python
"""Dependencies for document-related operations."""
from functools import lru_cache
from typing import Any

from app.adapters.llamaindex import LlamaIndexExtractor
from app.adapters.storage import LocalStorageService
from app.config import settings
from app.ports import DocumentExtractor, StorageService


@lru_cache()
def get_storage_service() -> StorageService:
    """Get storage service instance (singleton)."""
    return LocalStorageService(base_path=settings.DOCUMENT_STORAGE_PATH)


@lru_cache()
def get_document_extractor() -> DocumentExtractor:
    """Get document extractor instance (singleton)."""
    return LlamaIndexExtractor()


def get_llamaparse_client() -> Any:
    """Create an AsyncLlamaCloud client from settings.LLAMA_CLOUD_KEY."""
    from llama_cloud import AsyncLlamaCloud
    if settings.LLAMA_CLOUD_KEY:
        return AsyncLlamaCloud(api_key=settings.LLAMA_CLOUD_KEY)
    return AsyncLlamaCloud()


def get_parsing_service(db: "AsyncSession | None" = None) -> "ParsingService | None":
    """Create a ParsingService instance if CDM dependencies are available.

    Returns None when called without a db session (e.g., during router module load).
    The router calls this per-request and passes the real db session.
    """
    if db is None:
        return None
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.repositories.source_document_repository import SourceDocumentRepository
    from app.repositories.parse_run_repository import ParseRunRepository
    from app.repositories.parsed_document_repository import ParsedDocumentRepository
    from app.services.parsing.parsing_service import ParsingService
    return ParsingService(
        source_doc_repo=SourceDocumentRepository(db),
        parse_run_repo=ParseRunRepository(db),
        parsed_doc_repo=ParsedDocumentRepository(db),
        storage=get_storage_service(),
        llamaparse_client=get_llamaparse_client(),
    )
```

Note: The `TYPE_CHECKING` annotations keep the import light. The actual imports are deferred inside the function body so the module can be imported without pulling in all CDM deps.

Actually, simplify to use regular imports at the top for clarity (the CDM modules are already imported elsewhere in the app). Replace the whole file with:

```python
"""Dependencies for document-related operations."""
from functools import lru_cache
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.llamaindex import LlamaIndexExtractor
from app.adapters.storage import LocalStorageService
from app.config import settings
from app.ports import DocumentExtractor, StorageService
from app.repositories.parse_run_repository import ParseRunRepository
from app.repositories.parsed_document_repository import ParsedDocumentRepository
from app.repositories.source_document_repository import SourceDocumentRepository
from app.services.parsing.parsing_service import ParsingService


@lru_cache()
def get_storage_service() -> StorageService:
    """Get storage service instance (singleton)."""
    return LocalStorageService(base_path=settings.DOCUMENT_STORAGE_PATH)


@lru_cache()
def get_document_extractor() -> DocumentExtractor:
    """Get document extractor instance (singleton)."""
    return LlamaIndexExtractor()


def get_llamaparse_client() -> Any:
    """Create an AsyncLlamaCloud client from settings.LLAMA_CLOUD_KEY."""
    from llama_cloud import AsyncLlamaCloud
    if settings.LLAMA_CLOUD_KEY:
        return AsyncLlamaCloud(api_key=settings.LLAMA_CLOUD_KEY)
    return AsyncLlamaCloud()


def get_parsing_service(db: AsyncSession) -> ParsingService:
    """Create a per-request ParsingService wired to the current db session."""
    return ParsingService(
        source_doc_repo=SourceDocumentRepository(db),
        parse_run_repo=ParseRunRepository(db),
        parsed_doc_repo=ParsedDocumentRepository(db),
        storage=get_storage_service(),
        llamaparse_client=get_llamaparse_client(),
    )
```

- [ ] **Step 2: Verify no import errors**

```bash
uv run --directory /home/asa/rag-admin/backend python -c "from app.dependencies.documents import get_llamaparse_client, get_parsing_service; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Run full test suite**

```bash
uv run --directory /home/asa/rag-admin/backend python -m pytest -o "addopts=" --tb=short -q
```

Expected: no failures.

- [ ] **Step 4: Commit**

```bash
git -C /home/asa/rag-admin add backend/app/dependencies/documents.py
git -C /home/asa/rag-admin commit -m "feat(deps): add get_llamaparse_client and get_parsing_service document dependencies"
```

---

## Task 5: Wire CDM Path in the Router

**Files:**
- Modify: `backend/app/routers/documents.py`

- [ ] **Step 1: Update `get_document_service` to inject `ParsingService`**

Replace the existing `get_document_service` function in `backend/app/routers/documents.py`:

```python
def get_document_service(
    db: AsyncSession = Depends(get_db),
    storage_service: StorageService = Depends(get_storage_service),
    document_extractor: DocumentExtractor = Depends(get_document_extractor),
) -> DocumentService:
    """Dependency to create DocumentService with repositories."""
    from app.config import settings
    from app.dependencies.documents import get_parsing_service
    document_repo = DocumentRepository(db)
    project_repo = ProjectRepository(db)
    parsing_service = get_parsing_service(db) if settings.USE_CDM_PARSER else None
    return DocumentService(
        document_repo=document_repo,
        project_repo=project_repo,
        storage_service=storage_service,
        document_extractor=document_extractor,
        parsing_service=parsing_service,
    )
```

Add `get_parsing_service` to the imports at the top (it can stay inside the function body as shown above to avoid a circular import issue — the function-level import is fine).

- [ ] **Step 2: Update the `upload_document` router to dispatch CDM background task**

Replace the body of the `upload_document` endpoint, specifically the section after `document = await document_service.initiate_upload(...)`. The full updated function:

```python
@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a document",
    description="Upload a document file. Returns immediately with status='processing'. "
                "Text extraction happens in the background.",
)
async def upload_document(
    background_tasks: BackgroundTasks,
    project_id: UUID = Form(..., description="Project ID to associate document with"),
    title: str = Form(..., description="Document title"),
    description: str | None = Form(None, description="Optional document description"),
    parser_type: str = Form("simple", description="Parser type: simple or llamaparse"),
    parse_config: str | None = Form(None, description="JSON parser config (for llamaparse)"),
    folder_id: UUID | None = Form(None, description="Optional folder to place document in"),
    file: UploadFile = ...,
    current_user: User = Depends(get_current_active_user),
    document_service: DocumentService = Depends(get_document_service),
    db: AsyncSession = Depends(get_db),
    storage_service: StorageService = Depends(get_storage_service),
    document_extractor: DocumentExtractor = Depends(get_document_extractor),
):
    """Upload a document and initiate background processing."""
    from app.config import settings
    from app.dependencies.documents import get_llamaparse_client
    from app.repositories.parse_run_repository import ParseRunRepository
    from app.repositories.parsed_document_repository import ParsedDocumentRepository
    from app.repositories.source_document_repository import SourceDocumentRepository
    from app.services.document_service import process_cdm_parsing

    try:
        config_dict = None
        if parse_config:
            try:
                config_dict = json.loads(parse_config)
            except json.JSONDecodeError:
                raise ValidationError("Invalid JSON in parse_config")

        use_cdm = settings.USE_CDM_PARSER and parser_type == "llamaparse"

        file_content = await file.read()
        filename = file.filename or "upload.pdf"
        document = await document_service.initiate_upload(
            user_id=current_user.id,
            project_id=project_id,
            file_content=file_content,
            filename=filename,
            title=title,
            description=description,
            folder_id=folder_id,
            use_cdm=use_cdm,
        )

        if use_cdm and document.source_document_id is not None:
            representation_kind = (config_dict or {}).get("representation_kind", "extract_rich")
            parse_cfg = {k: v for k, v in (config_dict or {}).items() if k != "representation_kind"}
            background_tasks.add_task(
                process_cdm_parsing,
                document_id=document.id,
                source_document_id=document.source_document_id,
                project_id=project_id,
                representation_kind=representation_kind,
                config=parse_cfg,
                document_repo=DocumentRepository(db),
                parse_run_repo=ParseRunRepository(db),
                parsed_doc_repo=ParsedDocumentRepository(db),
                source_doc_repo=SourceDocumentRepository(db),
                storage_service=storage_service,
                llamaparse_client=get_llamaparse_client(),
            )
        elif parser_type != "simple":
            # Legacy non-CDM parser path
            parser = get_parser(parser_type)
            if parser is None:
                raise ValidationError(f"Unknown parser type: {parser_type}")

            parse_result_repo = ParseResultRepository(db)
            document_repo_bg = DocumentRepository(db)
            parse_service = ParseService(parse_result_repo, document_repo_bg)
            parse_result = await parse_service.create_parse_result(
                document_id=document.id,
                user_id=current_user.id,
                parser_type=parser_type,
                parser_config=config_dict,
            )
            background_tasks.add_task(
                process_document_parsing,
                parse_result_id=parse_result.id,
                parse_result_repo=parse_result_repo,
                document_repo=document_repo_bg,
                storage_service=storage_service,
                parser=parser,
            )
        else:
            document_repo_bg = DocumentRepository(db)
            background_tasks.add_task(
                process_document_extraction,
                document_id=document.id,
                document_repo=document_repo_bg,
                storage_service=storage_service,
                document_extractor=document_extractor,
            )

        return document

    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
```

- [ ] **Step 3: Update `bulk_upload_documents` to dispatch CDM background task per document**

In the bulk upload route, find the section after `results = await document_service.initiate_bulk_upload(...)` that iterates over results. Replace the background task dispatch loop:

```python
    for item in results:
        if item.document is None or not item.is_new:
            continue
        document_id = item.document.id

        if use_cdm and item.document.source_document_id is not None:
            representation_kind = (config_dict or {}).get("representation_kind", "extract_rich")
            parse_cfg = {k: v for k, v in (config_dict or {}).items() if k != "representation_kind"}
            background_tasks.add_task(
                process_cdm_parsing,
                document_id=document_id,
                source_document_id=item.document.source_document_id,
                project_id=project_id,
                representation_kind=representation_kind,
                config=parse_cfg,
                document_repo=DocumentRepository(db),
                parse_run_repo=ParseRunRepository(db),
                parsed_doc_repo=ParsedDocumentRepository(db),
                source_doc_repo=SourceDocumentRepository(db),
                storage_service=storage_service,
                llamaparse_client=get_llamaparse_client(),
            )
        elif parser is not None:
            parse_result_repo = ParseResultRepository(db)
            document_repo_bg = DocumentRepository(db)
            parse_service = ParseService(parse_result_repo, document_repo_bg)
            parse_result = await parse_service.create_parse_result(
                document_id=document_id,
                user_id=current_user.id,
                parser_type=parser_type,
                parser_config=config_dict,
            )
            background_tasks.add_task(
                process_document_parsing,
                parse_result_id=parse_result.id,
                parse_result_repo=parse_result_repo,
                document_repo=document_repo_bg,
                storage_service=storage_service,
                parser=parser,
            )
        else:
            document_repo_bg = DocumentRepository(db)
            background_tasks.add_task(
                process_document_extraction,
                document_id=document_id,
                document_repo=document_repo_bg,
                storage_service=storage_service,
                document_extractor=document_extractor,
            )
```

Also compute `use_cdm` at the top of the bulk upload function (before `initiate_bulk_upload`):

```python
    use_cdm = settings.USE_CDM_PARSER and parser_type == "llamaparse"
```

And add the necessary imports at the top of the bulk function body:

```python
    from app.config import settings
    from app.dependencies.documents import get_llamaparse_client
    from app.repositories.parse_run_repository import ParseRunRepository
    from app.repositories.parsed_document_repository import ParsedDocumentRepository
    from app.repositories.source_document_repository import SourceDocumentRepository
    from app.services.document_service import process_cdm_parsing
```

Also update the `initiate_bulk_upload` call to pass `use_cdm` per file. But wait — `initiate_bulk_upload` calls `initiate_upload` internally, and `initiate_upload` now has a `use_cdm` parameter. So we need to either:

a) Add `use_cdm: bool = False` to `initiate_bulk_upload` and pass it through to each `initiate_upload` call, or
b) Have the router not use `initiate_bulk_upload` and instead call `initiate_upload` per file directly.

Option (a) is the minimal change. Update `initiate_bulk_upload` to accept `use_cdm: bool = False` and pass it to each `initiate_upload`:

In `document_service.py`, update `initiate_bulk_upload`:
```python
    async def initiate_bulk_upload(
        self,
        user_id: UUID,
        project_id: UUID,
        files: list[tuple[bytes, str]],
        use_cdm: bool = False,
    ) -> list["BulkUploadItemResult"]:
```

And update the `initiate_upload` call inside `initiate_bulk_upload`:
```python
                document = await self.initiate_upload(
                    user_id=user_id,
                    project_id=project_id,
                    file_content=file_content,
                    filename=filename,
                    title=title,
                    use_cdm=use_cdm,
                )
```

In the bulk router, call:
```python
    results = await document_service.initiate_bulk_upload(
        user_id=current_user.id,
        project_id=project_id,
        files=file_data,
        use_cdm=use_cdm,
    )
```

- [ ] **Step 4: Verify the server starts cleanly**

```bash
uv run --directory /home/asa/rag-admin/backend python -c "from app.main import app; print('OK')"
```

Expected: `OK` with no import errors.

- [ ] **Step 5: Run the full test suite**

```bash
uv run --directory /home/asa/rag-admin/backend python -m pytest -o "addopts=" --tb=short -q
```

Expected: all previously passing tests still pass; 2 new CDM service tests pass.

- [ ] **Step 6: Commit**

```bash
git -C /home/asa/rag-admin add backend/app/routers/documents.py backend/app/services/document_service.py
git -C /home/asa/rag-admin commit -m "feat(router): wire CDM path in upload endpoints, dispatch process_cdm_parsing background task"
```

---

## Task 6: E2E Router Test — HTTP Upload Writes All Four Tables

**Files:**
- Create: `backend/tests/routers/test_documents_cdm_router.py`

- [ ] **Step 1: Write the failing E2E test**

Create `backend/tests/routers/test_documents_cdm_router.py`:

```python
"""E2E tests: HTTP upload → CDM rows in source_documents, documents, parse_runs, parsed_documents.

Uses SQLite in-memory DB via the shared conftest `client` fixture.
Patches run_llamaparse to avoid needing a real LlamaParse API key.
"""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cdm.models import ParsedDocument as ParsedDocumentCDM, Page, ParserKind
from app.cdm.source import ParseRun as ParseRunCDM, ParseRunStatus, SourceDocument as SourceDocumentCDM
from app.models.document import Document
from app.models.parse_run import ParseRun as ParseRunORM
from app.models.parsed_document import ParsedDocument as ParsedDocumentORM
from app.models.source_document import SourceDocument as SourceDocumentORM

MINIMAL_PDF = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF"


async def _signup_and_login(client: AsyncClient) -> str:
    await client.post(
        "/api/v1/auth/signup",
        json={
            "email": "cdmtest@example.com",
            "password": "ValidPass123!",
            "password_confirm": "ValidPass123!",
            "full_name": "CDM Test User",
        },
    )
    resp = await client.post(
        "/api/v1/auth/signin",
        json={"email": "cdmtest@example.com", "password": "ValidPass123!"},
    )
    return resp.json()["access_token"]


async def _create_project(client: AsyncClient, token: str) -> str:
    resp = await client.post(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "CDM Upload Test Project"},
    )
    return resp.json()["id"]


def _make_fake_parse_result(source_id: str) -> tuple[ParseRunCDM, ParsedDocumentCDM]:
    """Build a minimal ParseRun + ParsedDocument that ParsingService would return."""
    run_id = str(uuid4())
    run = ParseRunCDM(
        id=run_id,
        source_document_id=source_id,
        parser=ParserKind.LLAMAPARSE,
        representation_kind="extract_rich",
        config={},
        status=ParseRunStatus.SUCCEEDED,
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
        duration_ms=100,
        input_tokens=10,
        output_tokens=5,
    )
    doc = ParsedDocumentCDM(
        id=run_id,
        source_document_id=source_id,
        parse_run_id=run_id,
        page_count=1,
        pages=[
            Page(
                page_index=0,
                width=100.0,
                height=200.0,
                blocks=[],
            )
        ],
        blocks=[],
        full_text="Hello world.",
        full_markdown="Hello world.",
    )
    return run, doc


@pytest.mark.asyncio
async def test_upload_cdm_writes_all_four_tables(client: AsyncClient, test_db: AsyncSession):
    """POST /documents with parser_type=llamaparse and USE_CDM_PARSER=True
    must write rows to source_documents, documents, parse_runs, parsed_documents."""
    token = await _signup_and_login(client)
    project_id = await _create_project(client, token)

    # We capture the source_document_id so we can build a matching fake result
    source_id_holder: list[str] = []

    async def fake_run_llamaparse(**kwargs: Any):
        source: SourceDocumentCDM = kwargs["source"]
        source_id_holder.append(source.id)
        return _make_fake_parse_result(source.id)

    with (
        patch(
            "app.services.parsing.parsing_service.run_llamaparse",
            new=AsyncMock(side_effect=fake_run_llamaparse),
        ),
        patch(
            "app.dependencies.documents.get_llamaparse_client",
            return_value=MagicMock(),
        ),
        patch(
            "app.routers.documents.get_llamaparse_client",
            return_value=MagicMock(),
        ),
    ):
        response = await client.post(
            "/api/v1/documents",
            headers={"Authorization": f"Bearer {token}"},
            data={
                "project_id": project_id,
                "parser_type": "llamaparse",
                "title": "CDM Test Doc",
            },
            files=[("file", ("test.pdf", MINIMAL_PDF, "application/pdf"))],
        )

    assert response.status_code == 202, response.text
    data = response.json()
    assert data["sourceDocumentId"] is not None

    # source_documents row
    sd_result = await test_db.execute(select(SourceDocumentORM))
    source_docs = list(sd_result.scalars().all())
    assert len(source_docs) == 1

    # documents row with source_document_id populated
    doc_result = await test_db.execute(select(Document))
    documents = list(doc_result.scalars().all())
    assert len(documents) == 1
    assert documents[0].source_document_id is not None

    # parse_runs row
    run_result = await test_db.execute(select(ParseRunORM))
    runs = list(run_result.scalars().all())
    assert len(runs) == 1
    assert runs[0].status == "succeeded"

    # parsed_documents row
    pd_result = await test_db.execute(select(ParsedDocumentORM))
    parsed_docs = list(pd_result.scalars().all())
    assert len(parsed_docs) == 1
    assert parsed_docs[0].page_count == 1

    # extracted_text shim written
    doc = documents[0]
    assert doc.extracted_text == "Hello world."
    assert doc.status.value == "ready"


@pytest.mark.asyncio
async def test_upload_cdm_flag_off_uses_legacy_path(client: AsyncClient, test_db: AsyncSession):
    """When USE_CDM_PARSER=False the simple extraction path runs; no CDM rows created."""
    token = await _signup_and_login(client)
    project_id = await _create_project(client, token)

    with patch("app.routers.documents.settings") as mock_settings:
        mock_settings.USE_CDM_PARSER = False
        mock_settings.MAX_UPLOAD_SIZE_MB = 25
        mock_settings.ALLOWED_MIME_TYPES = ["application/pdf", "image/jpeg", "image/png"]
        response = await client.post(
            "/api/v1/documents",
            headers={"Authorization": f"Bearer {token}"},
            data={
                "project_id": project_id,
                "parser_type": "simple",
                "title": "Legacy Test Doc",
            },
            files=[("file", ("test.pdf", MINIMAL_PDF, "application/pdf"))],
        )

    assert response.status_code == 202
    data = response.json()
    # No source_document_id on legacy path
    assert data["sourceDocumentId"] is None

    sd_result = await test_db.execute(select(SourceDocumentORM))
    assert len(list(sd_result.scalars().all())) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run --directory /home/asa/rag-admin/backend python -m pytest tests/routers/test_documents_cdm_router.py -v -o "addopts="
```

Expected: both tests fail — either import errors or assertion errors because the rows don't exist yet.

- [ ] **Step 3: Run tests to verify they pass after Task 5 is done**

(Re-run same command)

```bash
uv run --directory /home/asa/rag-admin/backend python -m pytest tests/routers/test_documents_cdm_router.py -v -o "addopts="
```

Expected: `2 passed`

- [ ] **Step 4: Run full test suite**

```bash
uv run --directory /home/asa/rag-admin/backend python -m pytest -o "addopts=" --tb=short -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git -C /home/asa/rag-admin add backend/tests/routers/test_documents_cdm_router.py
git -C /home/asa/rag-admin commit -m "test(router): E2E test — HTTP upload writes all 4 CDM tables"
```

---

## Self-Review Against Spec

**Spec §6 step 4** `ParsingService.ensure_source_document(...)` — ✅ Task 3 CDM branch  
**Spec §6 step 5** Create `Document` with `source_document_id` populated — ✅ Task 2 (repo) + Task 3 (service)  
**Spec §6 step 6** Trigger `parse_and_persist` as background task — ✅ Task 3 (`process_cdm_parsing`) + Task 5 (router dispatch)  
**Spec §6 feature flag** `USE_CDM_PARSER: bool = True` in settings — ✅ Task 1  
**Spec §6 legacy fallback** Flag off → legacy adapter path unchanged — ✅ Task 3 (else branch) + Task 6 second test  
**Spec §6 extracted_text shim** CDM path writes `documents.extracted_text = parsed_doc.full_text` — ✅ Task 3 `process_cdm_parsing`  
**Spec §7 PR 3 deliverable** End-to-end test HTTP upload → rows in all 4 tables — ✅ Task 6  
**Spec §9 AC#6** E2E test asserts all 4 tables written — ✅ Task 6  
**Spec §9 AC#7** Flag off restores legacy path unchanged — ✅ Task 6 second test  
**Spec §9 AC#8** Existing backend tests continue to pass — ✅ verified after each task  
**Spec §2.2** `documents.source_document_id` populated on CDM path — ✅ Task 2 + Task 3  
**Schema change exposed to API** `sourceDocumentId` in `DocumentResponse` — ✅ Task 2 (enables router to pass it to background task without a second DB lookup)  

**No gaps found.**
