from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.routers import auth, oauth, projects, users
from app.utils.oauth import setup_oauth

# Import database engine for SQLAlchemy instrumentation
from app.database import engine

# ============================================================================
# Observability Setup - MUST happen before app creation/startup
# ============================================================================
# Tracing must be initialized at module level to ensure OpenTelemetry
# middleware is added to FastAPI's middleware stack before uvicorn starts.
#
# CRITICAL: FastAPI builds its middleware stack when the app starts.
# The startup event fires AFTER the stack is built, so instrumenting
# in the startup event is too late - requests will bypass tracing.

from app.observability.tracing import (
    setup_tracing,
    instrument_httpx,
    shutdown_tracing,
)

# Initialize the TracerProvider and OTLP exporter
# This must happen before any instrumentation
setup_tracing(
    service_name=settings.OTEL_SERVICE_NAME,
    service_version="0.1.0",
    otlp_endpoint=settings.OTEL_EXPORTER_ENDPOINT,
    enabled=settings.OTEL_ENABLED,
)

# Instrument httpx for outgoing HTTP request tracing (global, one-time)
# This traces calls to external APIs (Google OAuth, etc.)
instrument_httpx()

# ============================================================================
# Create FastAPI Application
# ============================================================================

app = FastAPI(
    title="RAG Admin API",
    version="0.1.0",
    debug=settings.DEBUG,
)

# ============================================================================
# Instrument FastAPI - IMMEDIATELY after app creation
# ============================================================================
# Add OpenTelemetry middleware directly to trace all HTTP requests.
# Must be added BEFORE other middleware (CORS, Session, etc.) so it's the
# outermost layer and can capture the full request/response cycle.

if settings.OTEL_ENABLED:
    from opentelemetry import trace
    from opentelemetry.instrumentation.asgi import OpenTelemetryMiddleware

    app.add_middleware(
        OpenTelemetryMiddleware,
        excluded_urls="",  # Trace all URLs
        tracer_provider=trace.get_tracer_provider()
    )


@app.on_event("startup")
async def startup_event():
    """
    Initialize application components that require the event loop.

    Note: Tracing is already initialized at module level.
    This event only handles components that need async context or engine access.
    """
    # Instrument SQLAlchemy for database query tracing
    # This instruments the sync engine that underlies our AsyncEngine.
    # Creates child spans for every database query showing SQL, duration, etc.
    from app.observability.tracing import instrument_sqlalchemy
    instrument_sqlalchemy(engine.sync_engine)

    # Initialize OAuth client
    setup_oauth(settings)


@app.on_event("shutdown")
async def shutdown_event():
    """
    Clean up on application shutdown.
    Ensures all pending traces are exported before exit.
    """
    shutdown_tracing()

# ============================================================================
# Add Additional Middleware
# ============================================================================
# Note: OpenTelemetry middleware was already added via FastAPIInstrumentor above.
# Additional middleware is added here in reverse order (last added = first executed).

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
app.include_router(projects.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
