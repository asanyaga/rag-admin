"""Dependency injection functions."""
from app.dependencies.auth import get_current_user, get_current_active_user
from app.dependencies.documents import get_storage_service, get_document_extractor

__all__ = [
    "get_current_user",
    "get_current_active_user",
    "get_storage_service",
    "get_document_extractor",
]
