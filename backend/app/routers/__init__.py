"""API routers."""
from app.routers import auth, oauth, otel_proxy, projects, users, documents, indexes, provider_keys

__all__ = ["auth", "oauth", "otel_proxy", "projects", "users", "documents", "indexes", "provider_keys"]
