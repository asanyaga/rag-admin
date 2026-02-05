"""Custom exceptions for the application."""


class AppException(Exception):
    """Base exception for all application exceptions."""
    pass


class DocumentNotFoundError(AppException):
    """Raised when a document is not found or user doesn't have access."""
    pass


class DuplicateDocumentError(AppException):
    """Raised when attempting to create a document that already exists."""
    pass


class DocumentProcessingError(AppException):
    """Raised when document processing (extraction) fails."""
    pass


class StorageError(AppException):
    """Raised when file storage operations fail."""
    pass


class ProjectNotFoundError(AppException):
    """Raised when a project is not found or user doesn't have access."""
    pass
