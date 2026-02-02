from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.routers import auth, oauth, users
from app.utils.oauth import setup_oauth

# Import observability module for tracing, logging, and metrics
from app.observability import setup_observability, shutdown_observability, MetricsMiddleware

# Import database engine for SQLAlchemy instrumentation
from app.database import engine

app = FastAPI(
    title="RAG Admin API",
    version="0.1.0",
    debug=settings.DEBUG,
)


@app.on_event("startup")
async def startup_event():
    """
    Initialize application on startup.

    Order matters here:
    1. Observability FIRST - so all subsequent operations are traced/logged
    2. SQLAlchemy instrumentation - traces all database queries
    3. OAuth setup - now any OAuth initialization logs will have trace context
    """
    # Initialize observability (tracing, structured logging, metrics)
    # This MUST be first so all other startup operations are observable
    setup_observability(app)

    # Instrument SQLAlchemy for database query tracing
    # For async engines, we pass the sync_engine (underlying synchronous engine)
    # This creates spans for every database query showing:
    #   - SQL statement (with parameters redacted for security)
    #   - Database system (postgresql)
    #   - Query duration
    from app.observability.tracing import instrument_sqlalchemy
    instrument_sqlalchemy(engine.sync_engine)

    # Initialize OAuth
    setup_oauth(settings)


@app.on_event("shutdown")
async def shutdown_event():
    """
    Clean up on application shutdown.

    This ensures:
    - All pending traces are exported
    - All pending metrics are flushed
    - Connections are properly closed
    """
    shutdown_observability()

# Add MetricsMiddleware FIRST (outermost) to capture full request duration
# This records http_server_requests_total and http_server_request_duration_seconds
# for every request, with labels for method, route, and status_code
app.add_middleware(MetricsMiddleware)

# Add SessionMiddleware for OAuth state management
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SESSION_SECRET_KEY,
    max_age=600,  # Session expires after 10 minutes (enough time for OAuth flow)
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root() -> dict[str, str]:
    return {"app": "RAG Admin", "version": "0.1.0"}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy"}


# Include routers
app.include_router(auth.router, prefix="/api/v1")
app.include_router(oauth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
