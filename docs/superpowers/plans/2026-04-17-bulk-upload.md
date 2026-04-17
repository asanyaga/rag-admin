# Bulk Document Upload Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `POST /documents/bulk` endpoint and a `BulkUploadQueue` UI component so users can upload up to 20 files at once with a single parser configuration.

**Architecture:** New `POST /documents/bulk` endpoint fans out to the existing `initiate_upload()` service method per file, then registers existing background tasks per document. A class-level `asyncio.Semaphore(5)` on `LlamaParseAdapter` caps concurrent LlamaParse jobs globally. Frontend adds a `BulkUploadQueue` component rendered inside `DocumentUploadDialog` when bulk mode is active.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, Pydantic v2 (backend); React 18, TypeScript, shadcn/ui, Tailwind CSS (frontend); Vitest + Testing Library (frontend tests); pytest + httpx (backend tests).

---

## File Map

**Create:**
- `frontend/src/components/documents/BulkUploadQueue.tsx` — queue UI with per-file status chips
- `frontend/src/components/documents/BulkUploadQueue.test.tsx` — component tests
- `backend/tests/routers/test_documents_router.py` — router integration tests
- `backend/tests/services/test_document_service.py` — service unit tests

**Modify:**
- `backend/app/adapters/parsing/llamaparse.py` — add class-level semaphore
- `backend/tests/adapters/test_llamaparse_adapter.py` — add semaphore concurrency test
- `backend/app/schemas/document.py` — add `BulkUploadItemResponse`, `BulkUploadResponse`
- `backend/app/services/document_service.py` — add `BulkUploadItemResult` dataclass + `initiate_bulk_upload()`
- `backend/app/routers/documents.py` — add `POST /documents/bulk` endpoint
- `frontend/src/types/document.ts` — add `BulkDocumentUpload`, `BulkUploadItem`, `BulkUploadResponse`, `QueueItem`, `QueueItemStatus`
- `frontend/src/api/documents.ts` — add `bulkUploadDocuments()`
- `frontend/src/hooks/useDocuments.ts` — add `uploadDocumentsBulk()`
- `frontend/src/components/documents/DocumentUploadZone.tsx` — add `multiple` + `onBulkUpload` props
- `frontend/src/components/documents/DocumentUploadDialog.tsx` — add bulk mode support
- `frontend/src/pages/ProjectDocumentsPage.tsx` — add Bulk Upload button and dialog

---

## Task 1: Add concurrency semaphore to LlamaParseAdapter

**Files:**
- Modify: `backend/app/adapters/parsing/llamaparse.py`
- Modify: `backend/tests/adapters/test_llamaparse_adapter.py`

- [ ] **Step 1: Add semaphore concurrency test**

Append to `backend/tests/adapters/test_llamaparse_adapter.py`, inside `class TestLlamaParseAdapter`:

```python
@pytest.mark.asyncio
async def test_semaphore_limits_concurrency_to_five(self):
    """At most 5 parse calls should run concurrently."""
    import asyncio
    from app.adapters.parsing.llamaparse import LlamaParseAdapter

    # Reset semaphore for test isolation
    LlamaParseAdapter._semaphore = asyncio.Semaphore(5)

    concurrent_count = 0
    max_concurrent = 0

    async def mock_parse(**kwargs):
        nonlocal concurrent_count, max_concurrent
        concurrent_count += 1
        max_concurrent = max(max_concurrent, concurrent_count)
        await asyncio.sleep(0.02)
        concurrent_count -= 1
        return MockParseResult(text_pages=[MockTextPage(1, "text")])

    mock_client = MagicMock()
    mock_client.parsing.parse = mock_parse

    with patch("app.adapters.parsing.llamaparse.AsyncLlamaCloud", return_value=mock_client):
        adapter = LlamaParseAdapter(api_key="test-key")
        await asyncio.gather(*[adapter.parse("/tmp/test.pdf", {"tier": "fast"}) for _ in range(10)])

    assert max_concurrent <= 5
```

- [ ] **Step 2: Run test to verify it fails**

```
cd backend && uv run python -m pytest tests/adapters/test_llamaparse_adapter.py::TestLlamaParseAdapter::test_semaphore_limits_concurrency_to_five -v -o "addopts="
```

Expected: FAIL — `LlamaParseAdapter` has no `_semaphore` attribute yet.

- [ ] **Step 3: Add semaphore to LlamaParseAdapter**

In `backend/app/adapters/parsing/llamaparse.py`, add `import asyncio` at the top and the class-level semaphore + wrap the parse call:

```python
"""LlamaParse adapter using the llama-cloud SDK >= 1.0."""
import asyncio
import time
from typing import Any

from llama_cloud import AsyncLlamaCloud

from app.ports.document_parsing import (
    DocumentParser,
    ParseOutput,
    ParserType,
    ParseFidelity,
)


class LlamaParseAdapter(DocumentParser):
    """LlamaParse adapter using the llama-cloud SDK >= 1.0."""

    _semaphore = asyncio.Semaphore(5)  # shared across all instances

    def __init__(self, api_key: str | None = None):
        self.client = AsyncLlamaCloud(api_key=api_key) if api_key else AsyncLlamaCloud()

    @property
    def parser_type(self) -> ParserType:
        return ParserType.LLAMAPARSE

    @property
    def default_fidelity(self) -> ParseFidelity:
        return ParseFidelity.MARKDOWN

    def supported_file_types(self) -> list[str]:
        return [
            "application/pdf",
            "image/jpeg", "image/png", "image/gif", "image/bmp", "image/tiff", "image/webp",
        ]

    async def parse(self, file_path: str, config: dict[str, Any] | None = None) -> ParseOutput:
        """Parse a document using LlamaParse API (v1.0+ SDK)."""
        config = config or {}
        tier = config.get("tier", "agentic")
        requested_expand = config.get("expand", ["markdown", "text"])

        if tier == "fast":
            expand = ["text"]
        else:
            expand = [e for e in requested_expand if e in ["text", "markdown", "items", "metadata"]]
            if not expand:
                expand = ["text"]

        start_time = time.time()

        async with self._semaphore:
            result = await self.client.parsing.parse(
                upload_file=file_path,
                tier=tier,
                version=config.get("version", "latest"),
                expand=expand,
            )

        latency_ms = int((time.time() - start_time) * 1000)

        # Extract text
        raw_text = ""
        if hasattr(result, "text") and result.text:
            raw_text_parts = []
            for page in result.text.pages:
                raw_text_parts.append(f"[Page {page.page_number}]\n{page.text}")
            raw_text = "\n\n".join(raw_text_parts)

        # Extract markdown
        markdown_text = None
        pages: list[dict[str, Any]] = []
        if hasattr(result, "markdown") and result.markdown:
            md_parts = []
            for page in result.markdown.pages:
                if page.success:
                    md_parts.append(page.markdown)
                    pages.append({
                        "page_number": page.page_number,
                        "markdown": page.markdown,
                    })
            markdown_text = "\n\n".join(md_parts) if md_parts else None

        if not markdown_text and hasattr(result, "markdown_full"):
            markdown_text = result.markdown_full

        if not raw_text and hasattr(result, "text_full"):
            raw_text = result.text_full or ""

        document_structure = None
        if hasattr(result, "items") and result.items:
            items = []
            for page in result.items.pages:
                if page.success:
                    for item in page.items:
                        items.append({
                            "type": getattr(item, "type", None),
                            "value": getattr(item, "value", ""),
                            "md": getattr(item, "md", ""),
                            "page": page.page_number,
                            "bbox": item.bbox[0].__dict__ if getattr(item, "bbox", None) else None,
                        })
            if items:
                document_structure = {"items": items}

        if document_structure:
            fidelity = "layout_json"
        elif markdown_text:
            fidelity = "markdown"
        else:
            fidelity = "text"

        if not raw_text and markdown_text:
            raw_text = markdown_text

        job_id = result.job.id if hasattr(result, "job") else None

        return ParseOutput(
            raw_text=raw_text,
            markdown=markdown_text,
            pages=pages if pages else None,
            document_structure=document_structure,
            fidelity=fidelity,
            parser_type="llamaparse",
            parser_config={"tier": tier, "expand": expand, "version": config.get("version", "latest")},
            metadata={
                "llamaparse_job_id": job_id,
                "latency_ms": latency_ms,
                "page_count": len(pages) if pages else 0,
            },
        )
```

- [ ] **Step 4: Run test to verify it passes**

```
cd backend && uv run python -m pytest tests/adapters/test_llamaparse_adapter.py -v -o "addopts="
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/adapters/parsing/llamaparse.py backend/tests/adapters/test_llamaparse_adapter.py
git commit -m "feat: add concurrency semaphore to LlamaParseAdapter (max 5 concurrent jobs)"
```

---

## Task 2: Add bulk response schemas

**Files:**
- Modify: `backend/app/schemas/document.py`

- [ ] **Step 1: Add BulkUploadItemResponse and BulkUploadResponse**

Append to the end of `backend/app/schemas/document.py`:

```python
class BulkUploadItemResponse(BaseModel):
    """Schema for a single item in a bulk upload response."""
    filename: str
    document: DocumentResponse | None = None
    error: str | None = None


class BulkUploadResponse(BaseModel):
    """Schema for bulk upload API response."""
    results: list[BulkUploadItemResponse]
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/schemas/document.py
git commit -m "feat: add BulkUploadItemResponse and BulkUploadResponse schemas"
```

---

## Task 3: Implement `initiate_bulk_upload()` in DocumentService

**Files:**
- Modify: `backend/app/services/document_service.py`
- Create: `backend/tests/services/test_document_service.py`

- [ ] **Step 1: Write failing service tests**

Create `backend/tests/services/test_document_service.py`:

```python
"""Tests for DocumentService.initiate_bulk_upload()."""
import pytest
from dataclasses import dataclass
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.models.document import DocumentStatus
from app.services.document_service import DocumentService


def make_mock_document(title: str = "doc", project_id=None, user_id=None):
    """Create a mock Document ORM object with all required attributes."""
    doc = MagicMock()
    doc.id = uuid4()
    doc.project_id = project_id or uuid4()
    doc.source_type = "upload"
    doc.source_identifier = "abc123"
    doc.title = title
    doc.description = None
    doc.extracted_text = None
    doc.source_metadata = {"filename": f"{title}.pdf", "file_path": "path/to/file.pdf",
                           "file_size": 100, "mime_type": "application/pdf", "checksum": "abc123"}
    doc.processing_metadata = None
    doc.status = DocumentStatus.processing
    doc.status_message = None
    doc.created_by = user_id or uuid4()
    doc.created_at = datetime.now(timezone.utc)
    doc.updated_at = datetime.now(timezone.utc)
    return doc


@pytest.fixture
def project_id():
    return uuid4()


@pytest.fixture
def user_id():
    return uuid4()


@pytest.fixture
def mock_service(project_id, user_id):
    doc_repo = AsyncMock()
    proj_repo = AsyncMock()
    storage = AsyncMock()
    extractor = AsyncMock()

    proj_repo.get_by_id.return_value = MagicMock(id=project_id)
    doc_repo.get_by_source.return_value = None
    storage.save.return_value = "projects/proj/uploads/hash.pdf"

    service = DocumentService(doc_repo, proj_repo, storage, extractor)
    return service, doc_repo, proj_repo, storage


@pytest.mark.asyncio
async def test_initiate_bulk_upload_success(mock_service, project_id, user_id):
    """Successfully uploads two files and returns is_new=True for both."""
    service, doc_repo, _, _ = mock_service
    doc_repo.create.side_effect = [
        make_mock_document("file1", project_id, user_id),
        make_mock_document("file2", project_id, user_id),
    ]

    with patch("app.services.document_service.validate_mime_type", return_value="application/pdf"), \
         patch("app.services.document_service.validate_file_size"):
        results = await service.initiate_bulk_upload(
            user_id=user_id,
            project_id=project_id,
            files=[(b"%PDF-1.4", "file1.pdf"), (b"%PDF-1.5 x", "file2.pdf")],
        )

    assert len(results) == 2
    assert all(r.document is not None for r in results)
    assert all(r.error is None for r in results)
    assert all(r.is_new is True for r in results)


@pytest.mark.asyncio
async def test_initiate_bulk_upload_duplicate_returns_existing(mock_service, project_id, user_id):
    """Duplicate file returns the existing document silently with is_new=False."""
    from app.services.exceptions import ConflictError
    service, doc_repo, _, _ = mock_service

    existing_doc = make_mock_document("existing", project_id, user_id)
    doc_repo.get_by_source.return_value = existing_doc

    with patch("app.services.document_service.validate_mime_type", return_value="application/pdf"), \
         patch("app.services.document_service.validate_file_size"), \
         patch.object(service, "initiate_upload", side_effect=ConflictError("duplicate")):
        results = await service.initiate_bulk_upload(
            user_id=user_id,
            project_id=project_id,
            files=[(b"%PDF-1.4", "dup.pdf")],
        )

    assert len(results) == 1
    assert results[0].document is not None
    assert results[0].error is None
    assert results[0].is_new is False


@pytest.mark.asyncio
async def test_initiate_bulk_upload_validation_failure_is_per_file(mock_service, project_id, user_id):
    """A validation error on one file does not prevent others from uploading."""
    from app.services.exceptions import ValidationError
    service, doc_repo, _, _ = mock_service

    good_doc = make_mock_document("good", project_id, user_id)

    call_count = 0

    async def side_effect_upload(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ValidationError("File too large")
        return MagicMock()  # patched model_validate handles the rest

    with patch("app.services.document_service.validate_mime_type", return_value="application/pdf"), \
         patch("app.services.document_service.validate_file_size"), \
         patch.object(service, "initiate_upload", side_effect=side_effect_upload), \
         patch("app.services.document_service.DocumentResponse.model_validate", return_value=good_doc):
        results = await service.initiate_bulk_upload(
            user_id=user_id,
            project_id=project_id,
            files=[(b"%PDF-1.4", "bad.pdf"), (b"%PDF-1.5", "good.pdf")],
        )

    assert len(results) == 2
    assert results[0].error == "File too large"
    assert results[0].document is None
    assert results[1].error is None


@pytest.mark.asyncio
async def test_initiate_bulk_upload_title_uses_filename_stem(mock_service, project_id, user_id):
    """Title is set to the filename stem (without extension)."""
    service, doc_repo, _, _ = mock_service
    doc_repo.create.return_value = make_mock_document("my document", project_id, user_id)

    captured_title = None
    original_initiate = service.initiate_upload

    async def capture_title(**kwargs):
        nonlocal captured_title
        captured_title = kwargs.get("title")
        return await original_initiate(**kwargs)

    with patch("app.services.document_service.validate_mime_type", return_value="application/pdf"), \
         patch("app.services.document_service.validate_file_size"), \
         patch.object(service, "initiate_upload", side_effect=capture_title):
        await service.initiate_bulk_upload(
            user_id=user_id,
            project_id=project_id,
            files=[(b"%PDF-1.4", "my document.pdf")],
        )

    assert captured_title == "my document"
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd backend && uv run python -m pytest tests/services/test_document_service.py -v -o "addopts="
```

Expected: FAIL — `initiate_bulk_upload` does not exist yet.

- [ ] **Step 3: Add `BulkUploadItemResult` dataclass and `initiate_bulk_upload()` to DocumentService**

In `backend/app/services/document_service.py`, add after the imports block (before `class DocumentService`):

```python
from dataclasses import dataclass, field
```

Then add the dataclass:

```python
@dataclass
class BulkUploadItemResult:
    """Result for a single file in a bulk upload."""
    filename: str
    document: "DocumentResponse | None" = None
    error: str | None = None
    is_new: bool = True
```

Then add this method inside `class DocumentService`, after `initiate_upload`:

```python
async def initiate_bulk_upload(
    self,
    user_id: UUID,
    project_id: UUID,
    files: list[tuple[bytes, str]],
) -> list["BulkUploadItemResult"]:
    """Initiate upload for multiple files. Each file is processed independently.

    Args:
        user_id: User UUID
        project_id: Project UUID
        files: List of (file_content, filename) tuples

    Returns:
        List of BulkUploadItemResult — one per file, with document or error set.
        Duplicates are returned as the existing document with is_new=False.
    """
    results: list[BulkUploadItemResult] = []
    for file_content, filename in files:
        title = Path(filename).stem
        try:
            document = await self.initiate_upload(
                user_id=user_id,
                project_id=project_id,
                file_content=file_content,
                filename=filename,
                title=title,
            )
            results.append(BulkUploadItemResult(filename=filename, document=document, is_new=True))
        except ConflictError:
            checksum = compute_checksum(file_content)
            existing = await self.document_repo.get_by_source(
                project_id=project_id,
                user_id=user_id,
                source_type="upload",
                source_identifier=checksum,
            )
            doc_response = DocumentResponse.model_validate(existing) if existing else None
            results.append(BulkUploadItemResult(filename=filename, document=doc_response, is_new=False))
        except (ValidationError, NotFoundError) as e:
            results.append(BulkUploadItemResult(filename=filename, error=str(e)))
    return results
```

Also update the top of the file to add `dataclass` to the import:

```python
from dataclasses import dataclass
```

- [ ] **Step 4: Run tests to verify they pass**

```
cd backend && uv run python -m pytest tests/services/test_document_service.py -v -o "addopts="
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/document_service.py backend/tests/services/test_document_service.py
git commit -m "feat: add initiate_bulk_upload to DocumentService"
```

---

## Task 4: Add `POST /documents/bulk` router endpoint

**Files:**
- Modify: `backend/app/routers/documents.py`
- Create: `backend/tests/routers/test_documents_router.py`

- [ ] **Step 1: Write failing router integration tests**

Create `backend/tests/routers/test_documents_router.py`:

```python
"""Integration tests for POST /documents/bulk."""
import pytest
from httpx import AsyncClient

# Minimal valid PDF bytes — distinct checksums so no duplicate conflict
MINIMAL_PDF_1 = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF"
MINIMAL_PDF_2 = b"%PDF-1.5\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF"


async def create_user_and_login(client: AsyncClient) -> str:
    await client.post(
        "/api/v1/auth/signup",
        json={
            "email": "bulktest@example.com",
            "password": "ValidPass123!",
            "password_confirm": "ValidPass123!",
            "full_name": "Bulk Test User",
        },
    )
    response = await client.post(
        "/api/v1/auth/signin",
        json={"email": "bulktest@example.com", "password": "ValidPass123!"},
    )
    return response.json()["access_token"]


async def create_project(client: AsyncClient, token: str) -> str:
    response = await client.post(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Bulk Upload Test Project"},
    )
    return response.json()["id"]


@pytest.mark.asyncio
async def test_bulk_upload_returns_202_with_results(client: AsyncClient):
    token = await create_user_and_login(client)
    project_id = await create_project(client, token)

    response = await client.post(
        "/api/v1/documents/bulk",
        headers={"Authorization": f"Bearer {token}"},
        data={"project_id": project_id, "parser_type": "simple"},
        files=[
            ("files", ("doc1.pdf", MINIMAL_PDF_1, "application/pdf")),
            ("files", ("doc2.pdf", MINIMAL_PDF_2, "application/pdf")),
        ],
    )

    assert response.status_code == 202
    data = response.json()
    assert "results" in data
    assert len(data["results"]) == 2
    for result in data["results"]:
        assert result["document"] is not None
        assert result["error"] is None
        assert result["document"]["status"] == "processing"


@pytest.mark.asyncio
async def test_bulk_upload_rejects_more_than_20_files(client: AsyncClient):
    token = await create_user_and_login(client)
    project_id = await create_project(client, token)

    files = [
        ("files", (f"doc{i}.pdf", f"%PDF-1.4 file{i}".encode(), "application/pdf"))
        for i in range(21)
    ]

    response = await client.post(
        "/api/v1/documents/bulk",
        headers={"Authorization": f"Bearer {token}"},
        data={"project_id": project_id, "parser_type": "simple"},
        files=files,
    )

    assert response.status_code == 400
    assert "20" in response.json()["detail"]


@pytest.mark.asyncio
async def test_bulk_upload_mixed_valid_invalid_files(client: AsyncClient):
    """Invalid file type returns per-item error; valid file succeeds."""
    token = await create_user_and_login(client)
    project_id = await create_project(client, token)

    response = await client.post(
        "/api/v1/documents/bulk",
        headers={"Authorization": f"Bearer {token}"},
        data={"project_id": project_id, "parser_type": "simple"},
        files=[
            ("files", ("valid.pdf", MINIMAL_PDF_1, "application/pdf")),
            ("files", ("bad.txt", b"plain text content here", "text/plain")),
        ],
    )

    assert response.status_code == 202
    data = response.json()
    results = {r["filename"]: r for r in data["results"]}
    assert results["valid.pdf"]["document"] is not None
    assert results["valid.pdf"]["error"] is None
    assert results["bad.txt"]["document"] is None
    assert results["bad.txt"]["error"] is not None


@pytest.mark.asyncio
async def test_bulk_upload_requires_auth(client: AsyncClient):
    response = await client.post(
        "/api/v1/documents/bulk",
        data={"project_id": "00000000-0000-0000-0000-000000000000"},
        files=[("files", ("doc.pdf", MINIMAL_PDF_1, "application/pdf"))],
    )
    assert response.status_code == 401
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd backend && uv run python -m pytest tests/routers/test_documents_router.py -v -o "addopts="
```

Expected: FAIL — endpoint does not exist (404).

- [ ] **Step 3: Add `POST /documents/bulk` to the router**

In `backend/app/routers/documents.py`, update the FastAPI imports to include `File`:

```python
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
```

Update the schemas import to include the new bulk types:

```python
from app.schemas.document import (
    DocumentResponse,
    DocumentListResponse,
    DocumentUpdate,
    BulkUploadItemResponse,
    BulkUploadResponse,
)
```

Update the service import to include `BulkUploadItemResult`:

```python
from app.services.document_service import DocumentService, process_document_extraction, BulkUploadItemResult
```

Add this endpoint to the router **before** the `GET ""` list endpoint (route ordering matters in FastAPI — `/bulk` must come before `/{document_id}`):

```python
@router.post(
    "/bulk",
    response_model=BulkUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Bulk upload documents",
    description="Upload up to 20 documents at once. Files are processed independently — "
                "a failure on one file does not block the rest. Titles are auto-set from filenames.",
)
async def bulk_upload_documents(
    background_tasks: BackgroundTasks,
    project_id: UUID = Form(..., description="Project ID to associate documents with"),
    parser_type: str = Form("simple", description="Parser type applied to all files"),
    parse_config: str | None = Form(None, description="JSON parser config (for llamaparse)"),
    files: list[UploadFile] = File(..., description="Files to upload (max 20)"),
    current_user: User = Depends(get_current_active_user),
    document_service: DocumentService = Depends(get_document_service),
    db: AsyncSession = Depends(get_db),
    storage_service: StorageService = Depends(get_storage_service),
    document_extractor: DocumentExtractor = Depends(get_document_extractor),
):
    """Bulk upload documents and initiate background processing for each."""
    if len(files) > 20:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 20 files per batch",
        )

    config_dict = None
    if parse_config:
        try:
            config_dict = json.loads(parse_config)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON in parse_config",
            )

    # Validate parser type upfront
    parser = None
    if parser_type != "simple":
        parser = get_parser(parser_type)
        if parser is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown parser type: {parser_type}",
            )

    # Read all file contents
    file_data: list[tuple[bytes, str]] = []
    for f in files:
        content = await f.read()
        file_data.append((content, f.filename or "upload.pdf"))

    results: list[BulkUploadItemResult] = await document_service.initiate_bulk_upload(
        user_id=current_user.id,
        project_id=project_id,
        files=file_data,
    )

    # Register background tasks for newly created documents only
    for item in results:
        if item.document is None or not item.is_new:
            continue
        document_id = item.document.id
        if parser is not None:
            parse_result_repo = ParseResultRepository(db)
            document_repo = DocumentRepository(db)
            parse_service = ParseService(parse_result_repo, document_repo)
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
                document_repo=document_repo,
                storage_service=storage_service,
                parser=parser,
            )
        else:
            document_repo = DocumentRepository(db)
            background_tasks.add_task(
                process_document_extraction,
                document_id=document_id,
                document_repo=document_repo,
                storage_service=storage_service,
                document_extractor=document_extractor,
            )

    return BulkUploadResponse(
        results=[
            BulkUploadItemResponse(
                filename=item.filename,
                document=item.document,
                error=item.error,
            )
            for item in results
        ]
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```
cd backend && uv run python -m pytest tests/routers/test_documents_router.py -v -o "addopts="
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/documents.py backend/tests/routers/test_documents_router.py
git commit -m "feat: add POST /documents/bulk endpoint"
```

---

## Task 5: Add frontend types

**Files:**
- Modify: `frontend/src/types/document.ts`

- [ ] **Step 1: Add bulk upload types**

Append to the end of `frontend/src/types/document.ts`:

```typescript
export interface BulkDocumentUpload {
  projectId: string
  files: File[]
  parserType?: string
  parseConfig?: Record<string, unknown>
}

export interface BulkUploadItem {
  filename: string
  document: Document | null
  error: string | null
}

export interface BulkUploadResponse {
  results: BulkUploadItem[]
}

export type QueueItemStatus = 'pending' | 'uploading' | 'processing' | 'ready' | 'failed'

export interface QueueItem {
  file: File
  status: QueueItemStatus
  documentId: string | null
  error: string | null
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/types/document.ts
git commit -m "feat: add bulk upload types to frontend"
```

---

## Task 6: Add `bulkUploadDocuments()` API function

**Files:**
- Modify: `frontend/src/api/documents.ts`

- [ ] **Step 1: Add the function**

Append to the end of `frontend/src/api/documents.ts`:

```typescript
export async function bulkUploadDocuments(
  data: BulkDocumentUpload
): Promise<BulkUploadResponse> {
  const formData = new FormData()
  formData.append('project_id', data.projectId)
  if (data.parserType) {
    formData.append('parser_type', data.parserType)
  }
  if (data.parseConfig) {
    formData.append('parse_config', JSON.stringify(data.parseConfig))
  }
  data.files.forEach((file) => {
    formData.append('files', file)
  })
  const response = await apiClient.post<BulkUploadResponse>(
    '/documents/bulk',
    formData,
    { headers: { 'Content-Type': 'multipart/form-data' } }
  )
  return response.data
}
```

Update the imports at the top of `frontend/src/api/documents.ts` to include the new types:

```typescript
import apiClient from './client'
import {
  Document,
  DocumentListItem,
  DocumentUpload,
  DocumentUpdate,
  DocumentTextResponse,
  DocumentStatus,
  BulkDocumentUpload,
  BulkUploadResponse,
} from '@/types/document'
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/api/documents.ts
git commit -m "feat: add bulkUploadDocuments API function"
```

---

## Task 7: Add `uploadDocumentsBulk()` to useDocuments

**Files:**
- Modify: `frontend/src/hooks/useDocuments.ts`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/hooks/useDocuments.test.ts`:

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useDocuments } from './useDocuments'
import * as documentsApi from '@/api/documents'

vi.mock('@/api/documents')

const mockDocumentListItem = (id: string, status = 'processing') => ({
  id,
  projectId: 'project-1',
  sourceType: 'upload',
  title: id,
  description: null,
  status,
  statusMessage: null,
  createdAt: '2026-01-01T00:00:00Z',
  updatedAt: '2026-01-01T00:00:00Z',
})

const mockDocument = (id: string, status = 'processing') => ({
  ...mockDocumentListItem(id, status),
  sourceIdentifier: 'hash',
  extractedText: null,
  sourceMetadata: {},
  processingMetadata: null,
  createdBy: 'user-1',
})

describe('useDocuments.uploadDocumentsBulk', () => {
  beforeEach(() => {
    vi.mocked(documentsApi.listDocuments).mockResolvedValue([])
  })

  it('adds successful documents to state and starts polling for processing ones', async () => {
    const bulkResponse = {
      results: [
        { filename: 'doc1.pdf', document: mockDocument('id-1', 'processing'), error: null },
        { filename: 'doc2.pdf', document: null, error: 'File too large' },
      ],
    }
    vi.mocked(documentsApi.bulkUploadDocuments).mockResolvedValue(bulkResponse)
    vi.mocked(documentsApi.getDocument).mockResolvedValue(mockDocument('id-1', 'ready'))

    const { result } = renderHook(() => useDocuments('project-1'))

    await act(async () => {
      await result.current.uploadDocumentsBulk({
        projectId: 'project-1',
        files: [new File(['content'], 'doc1.pdf'), new File(['content'], 'doc2.pdf')],
      })
    })

    // Only the successful document should be added to the list
    expect(result.current.documents).toHaveLength(1)
    expect(result.current.documents[0].id).toBe('id-1')
  })

  it('does not add failed documents to state', async () => {
    const bulkResponse = {
      results: [
        { filename: 'bad.pdf', document: null, error: 'Invalid file type' },
      ],
    }
    vi.mocked(documentsApi.bulkUploadDocuments).mockResolvedValue(bulkResponse)

    const { result } = renderHook(() => useDocuments('project-1'))

    await act(async () => {
      await result.current.uploadDocumentsBulk({
        projectId: 'project-1',
        files: [new File(['content'], 'bad.pdf')],
      })
    })

    expect(result.current.documents).toHaveLength(0)
  })

  it('throws and sets error on network failure', async () => {
    vi.mocked(documentsApi.bulkUploadDocuments).mockRejectedValue(new Error('Network error'))

    const { result } = renderHook(() => useDocuments('project-1'))

    await act(async () => {
      await expect(
        result.current.uploadDocumentsBulk({ projectId: 'project-1', files: [] })
      ).rejects.toThrow('Network error')
    })

    expect(result.current.error).toBe('Network error')
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

```
cd frontend && npx vitest run src/hooks/useDocuments.test.ts
```

Expected: FAIL — `uploadDocumentsBulk` does not exist on the hook return value.

- [ ] **Step 3: Add `uploadDocumentsBulk` to the hook**

In `frontend/src/hooks/useDocuments.ts`, update the imports at the top:

```typescript
import {
  Document,
  DocumentListItem,
  DocumentUpload,
  DocumentUpdate,
  DocumentStatus,
  BulkDocumentUpload,
  BulkUploadResponse,
} from '@/types/document'
```

Update the `UseDocumentsReturn` interface to add the new method:

```typescript
interface UseDocumentsReturn {
  documents: DocumentListItem[]
  isLoading: boolean
  error: string | null
  uploadDocument: (data: DocumentUpload) => Promise<Document>
  uploadDocumentsBulk: (data: BulkDocumentUpload) => Promise<BulkUploadResponse>
  fetchDocuments: () => Promise<void>
  updateDocument: (id: string, data: DocumentUpdate) => Promise<Document>
  deleteDocument: (id: string) => Promise<void>
  downloadDocument: (id: string, filename: string) => Promise<void>
}
```

Add the `uploadDocumentsBulk` callback inside the hook body, after `uploadDocument`:

```typescript
const uploadDocumentsBulk = useCallback(
  async (data: BulkDocumentUpload): Promise<BulkUploadResponse> => {
    try {
      const response = await documentsApi.bulkUploadDocuments(data)

      response.results.forEach((item) => {
        if (!item.document) return
        const doc = item.document
        setDocuments((prev) => [
          {
            id: doc.id,
            projectId: doc.projectId,
            sourceType: doc.sourceType,
            title: doc.title,
            description: doc.description,
            status: doc.status,
            statusMessage: doc.statusMessage,
            createdAt: doc.createdAt,
            updatedAt: doc.updatedAt,
          },
          ...prev,
        ])
        if (doc.status === 'processing') {
          startPollingRef.current?.(doc.id)
        }
      })

      return response
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : 'Failed to upload documents'
      setError(errorMessage)
      throw err
    }
  },
  []
)
```

Add `uploadDocumentsBulk` to the return value:

```typescript
return {
  documents,
  isLoading,
  error,
  uploadDocument,
  uploadDocumentsBulk,
  fetchDocuments,
  updateDocument,
  deleteDocument,
  downloadDocument,
}
```

- [ ] **Step 4: Run tests to verify they pass**

```
cd frontend && npx vitest run src/hooks/useDocuments.test.ts
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/hooks/useDocuments.ts frontend/src/hooks/useDocuments.test.ts
git commit -m "feat: add uploadDocumentsBulk to useDocuments hook"
```

---

## Task 8: Create `BulkUploadQueue` component

**Files:**
- Create: `frontend/src/components/documents/BulkUploadQueue.tsx`
- Create: `frontend/src/components/documents/BulkUploadQueue.test.tsx`

- [ ] **Step 1: Write failing component tests**

Create `frontend/src/components/documents/BulkUploadQueue.test.tsx`:

```typescript
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { BulkUploadQueue } from './BulkUploadQueue'

const makeFile = (name: string, sizeBytes: number, type = 'application/pdf') => {
  const file = new File(['x'], name, { type })
  Object.defineProperty(file, 'size', { value: sizeBytes })
  return file
}

const defaultProps = {
  projectId: 'project-1',
  documents: [],
  onBulkUpload: vi.fn().mockResolvedValue({ results: [] }),
  onClose: vi.fn(),
}

describe('BulkUploadQueue', () => {
  it('renders all files up to max 20', () => {
    const files = Array.from({ length: 5 }, (_, i) => makeFile(`doc${i}.pdf`, 100))
    render(<BulkUploadQueue {...defaultProps} initialFiles={files} />)
    expect(screen.getAllByText(/\.pdf/)).toHaveLength(5)
  })

  it('shows truncation warning and limits to 20 files when more than 20 provided', () => {
    const files = Array.from({ length: 25 }, (_, i) => makeFile(`doc${i}.pdf`, 100))
    render(<BulkUploadQueue {...defaultProps} initialFiles={files} />)
    expect(screen.getByText(/maximum 20 files/i)).toBeInTheDocument()
    // Only 20 filenames rendered
    expect(screen.getAllByText(/doc\d+\.pdf/)).toHaveLength(20)
  })

  it('flags files exceeding 25MB as failed with an error message', () => {
    const files = [makeFile('big.pdf', 30 * 1024 * 1024), makeFile('ok.pdf', 100)]
    render(<BulkUploadQueue {...defaultProps} initialFiles={files} />)
    expect(screen.getByText(/exceeds 25mb/i)).toBeInTheDocument()
  })

  it('disables submit button when all files are invalid', () => {
    const files = [makeFile('big.pdf', 30 * 1024 * 1024)]
    render(<BulkUploadQueue {...defaultProps} initialFiles={files} />)
    expect(screen.getByRole('button', { name: /upload/i })).toBeDisabled()
  })

  it('submit button label shows count of valid files', () => {
    const files = [
      makeFile('ok.pdf', 100),
      makeFile('ok2.pdf', 100),
      makeFile('big.pdf', 30 * 1024 * 1024),
    ]
    render(<BulkUploadQueue {...defaultProps} initialFiles={files} />)
    expect(screen.getByRole('button', { name: /upload 2 files/i })).toBeInTheDocument()
  })

  it('calls onBulkUpload with valid files only on submit', async () => {
    const onBulkUpload = vi.fn().mockResolvedValue({ results: [] })
    const files = [makeFile('ok.pdf', 100), makeFile('big.pdf', 30 * 1024 * 1024)]
    render(
      <BulkUploadQueue {...defaultProps} initialFiles={files} onBulkUpload={onBulkUpload} />
    )
    await userEvent.click(screen.getByRole('button', { name: /upload 1 file/i }))
    expect(onBulkUpload).toHaveBeenCalledWith(
      expect.objectContaining({ files: [files[0]] })
    )
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd frontend && npx vitest run src/components/documents/BulkUploadQueue.test.tsx
```

Expected: FAIL — component does not exist yet.

- [ ] **Step 3: Create the BulkUploadQueue component**

Create `frontend/src/components/documents/BulkUploadQueue.tsx`:

```typescript
import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { ParseMethodSelector } from './ParseMethodSelector'
import type { ParseConfig } from '@/types/parsing'
import type {
  BulkDocumentUpload,
  BulkUploadResponse,
  DocumentListItem,
  QueueItem,
  QueueItemStatus,
} from '@/types/document'

const MAX_FILES = 20
const MAX_SIZE_BYTES = 25 * 1024 * 1024
const ALLOWED_TYPES = ['application/pdf', 'image/jpeg', 'image/png']

interface BulkUploadQueueProps {
  projectId: string
  initialFiles: File[]
  documents: DocumentListItem[]
  onBulkUpload: (data: BulkDocumentUpload) => Promise<BulkUploadResponse>
  onClose: () => void
}

function validateFile(file: File): string | null {
  if (file.size > MAX_SIZE_BYTES) return 'File exceeds 25MB limit'
  if (!ALLOWED_TYPES.includes(file.type)) return 'Unsupported file type (PDF, JPEG, PNG only)'
  return null
}

function QueueStatusBadge({ status }: { status: QueueItemStatus }) {
  const styles: Record<QueueItemStatus, string> = {
    pending: 'bg-gray-100 text-gray-700',
    uploading: 'bg-blue-100 text-blue-700',
    processing: 'bg-yellow-100 text-yellow-700',
    ready: 'bg-green-100 text-green-700',
    failed: 'bg-red-100 text-red-700',
  }
  const labels: Record<QueueItemStatus, string> = {
    pending: 'Pending',
    uploading: 'Uploading',
    processing: 'Processing',
    ready: 'Ready',
    failed: 'Failed',
  }
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap',
        styles[status]
      )}
    >
      {labels[status]}
    </span>
  )
}

export function BulkUploadQueue({
  projectId,
  initialFiles,
  documents,
  onBulkUpload,
  onClose,
}: BulkUploadQueueProps) {
  const truncated = initialFiles.length > MAX_FILES
  const cappedFiles = initialFiles.slice(0, MAX_FILES)

  const [queueItems, setQueueItems] = useState<QueueItem[]>(() =>
    cappedFiles.map((file) => {
      const error = validateFile(file)
      return {
        file,
        status: error ? ('failed' as QueueItemStatus) : ('pending' as QueueItemStatus),
        documentId: null,
        error,
      }
    })
  )
  const [parserType, setParserType] = useState('simple')
  const [parseConfig, setParseConfig] = useState<ParseConfig>({
    tier: 'agentic',
    expand: ['markdown', 'text'],
  })
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [uploadStarted, setUploadStarted] = useState(false)
  const [networkError, setNetworkError] = useState<string | null>(null)

  // Watch the documents list for processing status updates
  useEffect(() => {
    setQueueItems((prev) =>
      prev.map((item) => {
        if (!item.documentId) return item
        const doc = documents.find((d) => d.id === item.documentId)
        if (!doc) return item
        const newStatus = doc.status as QueueItemStatus
        if (newStatus === item.status) return item
        return { ...item, status: newStatus, error: doc.statusMessage ?? null }
      })
    )
  }, [documents])

  const validItems = queueItems.filter((item) => item.status === 'pending')
  const validCount = validItems.length

  const handleSubmit = async () => {
    if (validCount === 0) return
    setIsSubmitting(true)
    setUploadStarted(true)
    setNetworkError(null)

    setQueueItems((prev) =>
      prev.map((item) =>
        item.status === 'pending' ? { ...item, status: 'uploading' as QueueItemStatus } : item
      )
    )

    try {
      const response = await onBulkUpload({
        projectId,
        files: validItems.map((item) => item.file),
        parserType,
        parseConfig: parserType === 'llamaparse' ? parseConfig : undefined,
      })

      const responseMap = new Map(response.results.map((r) => [r.filename, r]))

      setQueueItems((prev) =>
        prev.map((item) => {
          if (item.status !== 'uploading') return item
          const result = responseMap.get(item.file.name)
          if (!result) return { ...item, status: 'failed' as QueueItemStatus, error: 'No response received' }
          if (result.error) return { ...item, status: 'failed' as QueueItemStatus, error: result.error }
          return {
            ...item,
            status: result.document!.status as QueueItemStatus,
            documentId: result.document!.id,
          }
        })
      )
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Upload failed'
      setNetworkError(message)
      setQueueItems((prev) =>
        prev.map((item) =>
          item.status === 'uploading'
            ? { ...item, status: 'failed' as QueueItemStatus, error: message }
            : item
        )
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="space-y-4">
      {truncated && (
        <div className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-md p-3">
          Maximum 20 files per batch. Showing first 20 of {initialFiles.length} selected files.
        </div>
      )}

      {networkError && (
        <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-md p-3">
          {networkError}
        </div>
      )}

      <div className="border rounded-md divide-y max-h-64 overflow-y-auto">
        {queueItems.map((item, index) => (
          <div key={index} className="flex items-center justify-between p-3 text-sm gap-3">
            <div className="flex-1 min-w-0">
              <p className="truncate font-medium">{item.file.name}</p>
              <p className="text-xs text-muted-foreground">
                {(item.file.size / 1024 / 1024).toFixed(2)} MB
                {item.status === 'pending' && (
                  <span className="ml-1 text-muted-foreground/60">→ will use as title</span>
                )}
              </p>
              {item.error && item.status === 'failed' && !item.documentId && (
                <p className="text-xs text-red-500 mt-0.5">{item.error}</p>
              )}
            </div>
            <QueueStatusBadge status={item.status} />
          </div>
        ))}
      </div>

      <ParseMethodSelector
        parserType={parserType}
        config={parseConfig}
        onParserTypeChange={setParserType}
        onConfigChange={setParseConfig}
        disabled={isSubmitting || uploadStarted}
      />

      <div className="flex gap-2 justify-end">
        <Button variant="outline" onClick={onClose} disabled={isSubmitting}>
          {uploadStarted ? 'Close' : 'Cancel'}
        </Button>
        {!uploadStarted && (
          <Button onClick={handleSubmit} disabled={validCount === 0 || isSubmitting}>
            {isSubmitting
              ? 'Uploading...'
              : `Upload ${validCount} file${validCount !== 1 ? 's' : ''}`}
          </Button>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Run tests to verify they pass**

```
cd frontend && npx vitest run src/components/documents/BulkUploadQueue.test.tsx
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/documents/BulkUploadQueue.tsx frontend/src/components/documents/BulkUploadQueue.test.tsx
git commit -m "feat: add BulkUploadQueue component"
```

---

## Task 9: Add `multiple` prop to DocumentUploadZone

**Files:**
- Modify: `frontend/src/components/documents/DocumentUploadZone.tsx`

- [ ] **Step 1: Update the component interface and handlers**

Replace the existing `DocumentUploadZoneProps` interface and function signature in `frontend/src/components/documents/DocumentUploadZone.tsx`:

```typescript
interface DocumentUploadZoneProps {
  projectId: string
  onUpload: (
    file: File,
    title: string,
    description?: string,
    parserType?: string,
    parseConfig?: ParseConfig
  ) => Promise<void>
  onBulkUpload?: (files: File[]) => void
  multiple?: boolean
  disabled?: boolean
}
```

Update the function signature:

```typescript
export function DocumentUploadZone({
  onUpload,
  onBulkUpload,
  multiple = false,
  disabled = false,
}: DocumentUploadZoneProps) {
```

Update `handleDrop` to handle multiple files when `multiple=true`:

```typescript
const handleDrop = useCallback((e: DragEvent<HTMLDivElement>) => {
  e.preventDefault()
  setIsDragging(false)

  if (multiple && onBulkUpload) {
    const droppedFiles = Array.from(e.dataTransfer.files)
    if (droppedFiles.length > 0) {
      onBulkUpload(droppedFiles)
    }
    return
  }

  const droppedFile = e.dataTransfer.files[0]
  if (droppedFile) {
    handleFile(droppedFile)
  }
}, [handleFile, multiple, onBulkUpload])
```

Update `handleFileInput` to handle multiple files when `multiple=true`:

```typescript
const handleFileInput = (e: ChangeEvent<HTMLInputElement>) => {
  if (multiple && onBulkUpload) {
    const selectedFiles = Array.from(e.target.files ?? [])
    if (selectedFiles.length > 0) {
      onBulkUpload(selectedFiles)
    }
    return
  }
  const selectedFile = e.target.files?.[0]
  if (selectedFile) {
    handleFile(selectedFile)
  }
}
```

Update the file `<Input>` element to conditionally add the `multiple` attribute:

```typescript
<Input
  id="file-upload"
  type="file"
  accept={acceptString}
  onChange={handleFileInput}
  className="sr-only"
  disabled={disabled}
  multiple={multiple}
/>
```

- [ ] **Step 2: Run the frontend build to verify no type errors**

```
cd frontend && npm run build 2>&1 | tail -20
```

Expected: Build succeeds with no TypeScript errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/documents/DocumentUploadZone.tsx
git commit -m "feat: add multiple and onBulkUpload props to DocumentUploadZone"
```

---

## Task 10: Update `DocumentUploadDialog` for bulk mode

**Files:**
- Modify: `frontend/src/components/documents/DocumentUploadDialog.tsx`

- [ ] **Step 1: Rewrite the dialog to support bulk mode**

Replace the contents of `frontend/src/components/documents/DocumentUploadDialog.tsx`:

```typescript
import { useState, useEffect } from 'react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { DocumentUploadZone } from './DocumentUploadZone'
import { BulkUploadQueue } from './BulkUploadQueue'
import type { ParseConfig } from '@/types/parsing'
import type {
  BulkDocumentUpload,
  BulkUploadResponse,
  DocumentListItem,
} from '@/types/document'

interface DocumentUploadDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onUpload: (
    file: File,
    title: string,
    description?: string,
    parserType?: string,
    parseConfig?: ParseConfig
  ) => Promise<void>
  onBulkUpload?: (data: BulkDocumentUpload) => Promise<BulkUploadResponse>
  documents?: DocumentListItem[]
  projectId: string
  mode?: 'single' | 'bulk'
}

export function DocumentUploadDialog({
  open,
  onOpenChange,
  onUpload,
  onBulkUpload,
  documents = [],
  projectId,
  mode = 'single',
}: DocumentUploadDialogProps) {
  const [bulkFiles, setBulkFiles] = useState<File[]>([])

  // Reset bulk files when the dialog closes
  useEffect(() => {
    if (!open) setBulkFiles([])
  }, [open])

  const handleUpload = async (
    file: File,
    title: string,
    description?: string,
    parserType?: string,
    parseConfig?: ParseConfig
  ) => {
    await onUpload(file, title, description, parserType, parseConfig)
    if (mode === 'single') onOpenChange(false)
  }

  const showQueue = mode === 'bulk' && bulkFiles.length > 0

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>
            {mode === 'bulk' ? 'Bulk Upload Documents' : 'Upload Document'}
          </DialogTitle>
          <DialogDescription>
            {mode === 'bulk'
              ? 'Select multiple files to upload at once. Titles are set from filenames.'
              : 'Upload a PDF document to extract and index its content'}
          </DialogDescription>
        </DialogHeader>

        {showQueue ? (
          <BulkUploadQueue
            projectId={projectId}
            initialFiles={bulkFiles}
            documents={documents}
            onBulkUpload={onBulkUpload!}
            onClose={() => onOpenChange(false)}
          />
        ) : (
          <DocumentUploadZone
            projectId={projectId}
            onUpload={handleUpload}
            onBulkUpload={mode === 'bulk' ? setBulkFiles : undefined}
            multiple={mode === 'bulk'}
          />
        )}
      </DialogContent>
    </Dialog>
  )
}
```

- [ ] **Step 2: Run build to verify no type errors**

```
cd frontend && npm run build 2>&1 | tail -20
```

Expected: Build succeeds.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/documents/DocumentUploadDialog.tsx
git commit -m "feat: add bulk mode support to DocumentUploadDialog"
```

---

## Task 11: Wire up bulk upload in ProjectDocumentsPage

**Files:**
- Modify: `frontend/src/pages/ProjectDocumentsPage.tsx`

- [ ] **Step 1: Add bulk upload state, handler, and dialog**

In `frontend/src/pages/ProjectDocumentsPage.tsx`, update the `useDocuments` destructuring to include `uploadDocumentsBulk`:

```typescript
const {
  documents,
  isLoading,
  error,
  uploadDocument,
  uploadDocumentsBulk,
  updateDocument,
  deleteDocument,
  downloadDocument,
} = useDocuments(projectId || null)
```

Add `bulkUploadOpen` state after the existing `useState` declarations:

```typescript
const [bulkUploadOpen, setBulkUploadOpen] = useState(false)
```

Add the `handleBulkUpload` function after `handleUpload`:

```typescript
const handleBulkUpload = async (data: BulkDocumentUpload): Promise<BulkUploadResponse> => {
  try {
    const response = await uploadDocumentsBulk(data)
    const successCount = response.results.filter((r) => r.document !== null).length
    const failureCount = response.results.filter((r) => r.error !== null).length
    if (failureCount === 0) {
      toast.success(`${successCount} document${successCount !== 1 ? 's' : ''} uploaded`)
    } else {
      toast.success(`${successCount} uploaded`, {
        description: `${failureCount} failed — check the queue for details`,
      })
    }
    return response
  } catch (err) {
    toast.error('Bulk upload failed', {
      description: err instanceof Error ? err.message : 'An error occurred',
    })
    throw err
  }
}
```

Update the imports at the top of the file to include `DocumentUploadDialog` and the needed types:

```typescript
import { DocumentUploadDialog } from '@/components/documents/DocumentUploadDialog'
import type { BulkDocumentUpload, BulkUploadResponse } from '@/types/document'
```

Add a "Bulk Upload" button to the header section. Replace the existing header `<div>` that contains only the back button and title:

```typescript
{/* Header */}
<div className="flex items-center justify-between">
  <div>
    <Button
      variant="ghost"
      size="sm"
      onClick={() => navigate('/projects')}
      className="mb-2"
    >
      <svg
        className="h-4 w-4 mr-2"
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 20 20"
        fill="currentColor"
      >
        <path
          fillRule="evenodd"
          d="M17 10a.75.75 0 01-.75.75H5.612l4.158 3.96a.75.75 0 11-1.04 1.08l-5.5-5.25a.75.75 0 010-1.08l5.5-5.25a.75.75 0 111.04 1.08L5.612 9.25H16.25A.75.75 0 0117 10z"
          clipRule="evenodd"
        />
      </svg>
      Back to Projects
    </Button>
    <h1 className="text-3xl font-bold">Documents</h1>
    <p className="text-muted-foreground mt-1">
      Upload and manage your documents
    </p>
  </div>
  <Button variant="outline" onClick={() => setBulkUploadOpen(true)}>
    Bulk Upload
  </Button>
</div>
```

Add the bulk upload dialog just before the closing `</div>` of the page return:

```typescript
{/* Bulk Upload Dialog */}
<DocumentUploadDialog
  open={bulkUploadOpen}
  onOpenChange={setBulkUploadOpen}
  onUpload={handleUpload}
  onBulkUpload={handleBulkUpload}
  documents={documents}
  projectId={projectId}
  mode="bulk"
/>
```

- [ ] **Step 2: Run lint and build**

```
cd frontend && npm run lint && npm run build 2>&1 | tail -30
```

Expected: No lint errors, build succeeds.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/ProjectDocumentsPage.tsx
git commit -m "feat: add Bulk Upload button and dialog to ProjectDocumentsPage"
```

---

## Task 12: Run full test suites

- [ ] **Step 1: Run all backend tests**

```
cd backend && uv run python -m pytest -o "addopts=" -v 2>&1 | tail -40
```

Expected: All tests pass. No regressions.

- [ ] **Step 2: Run all frontend tests**

```
cd frontend && npx vitest run 2>&1 | tail -30
```

Expected: All tests pass. No regressions.

- [ ] **Step 3: Run frontend lint**

```
cd frontend && npm run lint
```

Expected: No errors.
