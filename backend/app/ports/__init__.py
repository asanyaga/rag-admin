"""Port interfaces for dependency injection."""
from app.ports.storage import StorageService
from app.ports.document_processing import DocumentExtractor, ExtractionResult

__all__ = ["StorageService", "DocumentExtractor", "ExtractionResult"]
