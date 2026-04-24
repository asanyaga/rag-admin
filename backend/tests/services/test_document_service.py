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
    _project_id = project_id or uuid4()
    _user_id = user_id or uuid4()
    _source_metadata = {"filename": f"{title}.pdf", "file_path": "path/to/file.pdf",
                        "file_size": 100, "mime_type": "application/pdf", "checksum": "abc123"}
    _now = datetime.now(timezone.utc)

    # snake_case attributes (used by code)
    doc.id = uuid4()
    doc.project_id = _project_id
    doc.source_type = "upload"
    doc.source_identifier = "abc123"
    doc.title = title
    doc.description = None
    doc.extracted_text = None
    doc.source_metadata = _source_metadata
    doc.processing_metadata = None
    doc.status = DocumentStatus.processing
    doc.status_message = None
    doc.created_by = _user_id
    doc.created_at = _now
    doc.updated_at = _now
    doc.folder_id = None
    doc.source_document_id = None

    # camelCase aliases — Pydantic v2 from_attributes uses the alias name for attribute access
    doc.projectId = _project_id
    doc.sourceType = "upload"
    doc.sourceIdentifier = "abc123"
    doc.extractedText = None
    doc.sourceMetadata = _source_metadata
    doc.processingMetadata = None
    doc.statusMessage = None
    doc.createdBy = _user_id
    doc.createdAt = _now
    doc.updatedAt = _now
    doc.folderId = None
    doc.sourceDocumentId = None

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
