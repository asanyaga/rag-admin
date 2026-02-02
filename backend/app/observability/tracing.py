"""
Distributed Tracing Setup for OpenTelemetry
============================================

This module configures distributed tracing, which captures the journey of each
request through your application. When a user makes a request, tracing records:
- When the request started and ended
- What database queries were executed
- What external APIs were called
- Where time was spent

KEY CONCEPTS:
-------------

1. TRACE: The complete journey of a single request
   - Has a unique trace_id (e.g., "a1b2c3d4e5f6...")
   - Contains multiple spans (units of work)

2. SPAN: A single unit of work within a trace
   - Has a name (e.g., "POST /api/v1/auth/signin")
   - Has a start time and end time (duration)
   - Has attributes (key-value metadata)
   - Can have a parent span (creating a tree structure)

3. CONTEXT PROPAGATION: How trace_id flows between services
   - The trace_id is passed in HTTP headers (traceparent, tracestate)
   - This links spans across different services into one trace

4. AUTO-INSTRUMENTATION: Zero-code tracing
   - Libraries like FastAPI, SQLAlchemy, httpx can be traced automatically
   - The instrumentor wraps these libraries to create spans

ARCHITECTURE:
------------

    ┌─────────────────────────────────────────────────────────────────┐
    │                        TracerProvider                            │
    │  (Central registry - creates Tracers for your application)       │
    ├─────────────────────────────────────────────────────────────────┤
    │                                                                  │
    │   Resource                    SpanProcessor                      │
    │   ┌──────────────┐           ┌──────────────────────────┐       │
    │   │ service.name │           │ BatchSpanProcessor       │       │
    │   │ service.ver  │           │ - Batches spans (512)    │       │
    │   │ deployment   │           │ - Sends every 5 seconds  │       │
    │   └──────────────┘           │ - Retries on failure     │       │
    │         │                    └───────────┬──────────────┘       │
    │         │                                │                       │
    │         ▼                                ▼                       │
    │   Attached to every              OTLPSpanExporter                │
    │   span as metadata               ┌──────────────────────────┐   │
    │                                  │ Sends to OTel Collector  │   │
    │                                  │ via gRPC on port 4317    │   │
    │                                  └──────────────────────────┘   │
    │                                                                  │
    └─────────────────────────────────────────────────────────────────┘
"""

import logging
from typing import Optional

# -----------------------------------------------------------------------------
# OpenTelemetry Imports - Understanding the Package Structure
# -----------------------------------------------------------------------------
#
# opentelemetry.sdk.trace: The SDK implementation for tracing
#   - TracerProvider: Creates and manages tracers
#   - sampling: Controls which spans are recorded (all, none, percentage)
#
# opentelemetry.sdk.resources: Describes what is generating telemetry
#   - Resource: Key-value pairs identifying your service
#   - SERVICE_NAME, SERVICE_VERSION: Standard attribute keys
#
# opentelemetry.exporter.otlp.proto.grpc: Sends data to OTel Collector
#   - OTLPSpanExporter: Exports spans via gRPC protocol
#
# opentelemetry.instrumentation.*: Auto-instrumentation libraries
#   - These wrap popular libraries to automatically create spans

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider, Span
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

logger = logging.getLogger(__name__)

# Module-level state to track initialization
_tracer_provider: Optional[TracerProvider] = None


def setup_tracing(
    service_name: str,
    service_version: str,
    otlp_endpoint: str,
    enabled: bool = True,
) -> Optional[TracerProvider]:
    """
    Initialize distributed tracing for the application.

    This function sets up the entire tracing pipeline:
    1. Creates a Resource (service identity)
    2. Creates a TracerProvider (span factory)
    3. Configures an OTLP exporter (sends to collector)
    4. Attaches a BatchSpanProcessor (efficient batching)
    5. Sets up auto-instrumentation (FastAPI, SQLAlchemy, httpx)

    Args:
        service_name: Identifies this service in traces (e.g., "rag-admin-backend")
        service_version: Version string for debugging (e.g., "0.1.0")
        otlp_endpoint: Where to send traces (e.g., "http://collector:4317")
        enabled: Set to False to disable tracing entirely

    Returns:
        The configured TracerProvider, or None if tracing is disabled

    Example:
        >>> setup_tracing(
        ...     service_name="rag-admin-backend",
        ...     service_version="0.1.0",
        ...     otlp_endpoint="http://signoz-otel-collector:4317"
        ... )
    """
    global _tracer_provider

    # ---------------------------------------------------------------------
    # Early exit if tracing is disabled
    # ---------------------------------------------------------------------
    # This allows you to completely skip tracing overhead in development
    # or testing. No spans are created, no data is sent.

    if not enabled:
        logger.info("Tracing is disabled via configuration")
        return None

    # Prevent double initialization
    if _tracer_provider is not None:
        logger.warning("Tracing already initialized, skipping")
        return _tracer_provider

    logger.info(f"Initializing tracing for service: {service_name}")

    # ---------------------------------------------------------------------
    # Step 1: Create a Resource
    # ---------------------------------------------------------------------
    # A Resource describes WHO is generating the telemetry.
    # These attributes appear on every span, making it easy to filter
    # traces by service in the SigNoz UI.
    #
    # Standard attributes (from semantic conventions):
    #   - service.name: The logical name of your service
    #   - service.version: Version string for correlation with deployments
    #
    # Why this matters:
    #   In a microservices architecture, you might have dozens of services.
    #   The resource lets you filter: "Show me all traces from rag-admin-backend"

    resource = Resource.create(
        attributes={
            SERVICE_NAME: service_name,
            SERVICE_VERSION: service_version,
            # You can add more attributes here:
            # "deployment.environment": "production",
            # "host.name": socket.gethostname(),
        }
    )

    logger.debug(f"Created resource with attributes: {resource.attributes}")

    # ---------------------------------------------------------------------
    # Step 2: Create the TracerProvider
    # ---------------------------------------------------------------------
    # The TracerProvider is the central component that:
    #   - Creates Tracer instances (one per module/component)
    #   - Manages the lifecycle of spans
    #   - Routes completed spans to processors
    #
    # Think of it as a factory: you ask it for a Tracer, and it gives you
    # one that's properly configured with your Resource and processors.

    _tracer_provider = TracerProvider(resource=resource)

    # ---------------------------------------------------------------------
    # Step 3: Create the OTLP Span Exporter
    # ---------------------------------------------------------------------
    # The exporter is responsible for SENDING span data somewhere.
    # OTLP (OpenTelemetry Protocol) is the standard format.
    #
    # We use gRPC because:
    #   - It's more efficient than HTTP for streaming data
    #   - It handles connection pooling automatically
    #   - It supports bidirectional communication (for future features)
    #
    # The endpoint should be your OTel Collector's gRPC port (4317).
    # The collector then forwards to ClickHouse/SigNoz.
    #
    # Determine if we should use TLS based on endpoint protocol.
    # - http:// = insecure (Docker network, localhost)
    # - https:// = secure (internet, different machine)

    use_tls = otlp_endpoint.startswith("https://")

    otlp_exporter = OTLPSpanExporter(
        endpoint=otlp_endpoint,
        insecure=not use_tls,  # Use TLS if endpoint is https://
    )

    logger.debug(
        f"Created OTLP exporter pointing to: {otlp_endpoint} "
        f"(TLS: {'enabled' if use_tls else 'disabled'})"
    )

    # ---------------------------------------------------------------------
    # Step 4: Create a BatchSpanProcessor
    # ---------------------------------------------------------------------
    # The processor sits between span creation and export.
    # BatchSpanProcessor batches spans for efficiency:
    #
    #   Instead of: Span created → Immediately send to collector
    #   We do:      Span created → Add to queue → Send batch every 5s
    #
    # Benefits:
    #   - Reduces network overhead (fewer, larger requests)
    #   - Doesn't block your code waiting for network I/O
    #   - Handles retries if the collector is temporarily unavailable
    #
    # Default settings (can be customized):
    #   - max_queue_size: 2048 spans in memory
    #   - schedule_delay_millis: 5000ms between exports
    #   - max_export_batch_size: 512 spans per batch
    #   - export_timeout_millis: 30000ms timeout

    span_processor = BatchSpanProcessor(otlp_exporter)
    _tracer_provider.add_span_processor(span_processor)

    logger.debug("Attached BatchSpanProcessor to TracerProvider")

    # ---------------------------------------------------------------------
    # Step 5: Register as the Global TracerProvider
    # ---------------------------------------------------------------------
    # This makes our provider THE provider for the entire application.
    # When any code calls `trace.get_tracer()`, it will use our provider.
    #
    # This is important for auto-instrumentation libraries, which call
    # `trace.get_tracer()` internally to create their spans.

    trace.set_tracer_provider(_tracer_provider)

    logger.info("Tracing initialized successfully")

    return _tracer_provider


def instrument_fastapi(app) -> None:
    """
    Auto-instrument a FastAPI application.

    This wraps every FastAPI endpoint to automatically create spans.
    For each HTTP request, you'll see a span with:
      - http.method: GET, POST, etc.
      - http.route: /api/v1/users/{id}
      - http.status_code: 200, 404, 500, etc.
      - http.url: Full URL path

    HOW IT WORKS:
    -------------
    FastAPIInstrumentor adds middleware that:
    1. Starts a span when a request arrives
    2. Extracts trace context from headers (traceparent)
    3. Sets span attributes from the request
    4. Ends the span when the response is sent
    5. Records errors if an exception occurs

    The span hierarchy looks like:

        HTTP POST /api/v1/auth/signin
        └── Your endpoint code runs here
            └── Database queries (if SQLAlchemy is instrumented)
            └── External HTTP calls (if httpx is instrumented)

    Args:
        app: The FastAPI application instance

    Example:
        >>> from fastapi import FastAPI
        >>> app = FastAPI()
        >>> instrument_fastapi(app)
    """
    if _tracer_provider is None:
        logger.debug("Tracing not initialized, skipping FastAPI instrumentation")
        return

    try:
        # Instrument the specific FastAPI app instance by adding middleware
        # This must happen during app startup, before any requests are processed

        # First, check if middleware is already present
        middleware_names = [str(m) for m in app.user_middleware]
        if any('OpenTelemetry' in name for name in middleware_names):
            logger.debug("OpenTelemetry middleware already present")
            return

        # Add OpenTelemetry middleware directly with explicit tracer provider
        from opentelemetry.instrumentation.fastapi import OpenTelemetryMiddleware

        # Get the global tracer provider
        tracer_provider = trace.get_tracer_provider()

        # Add the middleware with explicit tracer provider
        app.add_middleware(
            OpenTelemetryMiddleware,
            tracer_provider=tracer_provider
        )

        logger.info(f"FastAPI auto-instrumentation enabled (middleware added with explicit tracer provider)")
        logger.debug(f"Tracer provider: {type(tracer_provider)}")
        logger.debug(f"Middleware count: {len(app.user_middleware)}")

    except Exception as e:
        logger.error(f"Failed to instrument FastAPI: {e}", exc_info=True)


def instrument_sqlalchemy(engine) -> None:
    """
    Auto-instrument SQLAlchemy to trace all database queries.

    Every database query will create a child span showing:
      - db.system: postgresql
      - db.name: ragadmin
      - db.statement: The SQL query (with parameters redacted)
      - db.operation: SELECT, INSERT, UPDATE, DELETE

    WHY THIS IS VALUABLE:
    --------------------
    Database queries are often the slowest part of a request.
    With this instrumentation, you can:
      - See which queries are slow (N+1 query problem!)
      - Identify missing indexes (long SELECT times)
      - Track transaction durations

    Example trace with SQLAlchemy instrumentation:

        POST /api/v1/auth/signin (450ms total)
        ├── SELECT * FROM users WHERE email = ? (50ms)
        ├── bcrypt.verify (350ms)  <- custom span you'd add
        └── INSERT INTO refresh_tokens (50ms)

    Args:
        engine: SQLAlchemy engine or async engine

    Example:
        >>> from sqlalchemy.ext.asyncio import create_async_engine
        >>> engine = create_async_engine("postgresql+asyncpg://...")
        >>> instrument_sqlalchemy(engine)
    """
    if _tracer_provider is None:
        logger.debug("Tracing not initialized, skipping SQLAlchemy instrumentation")
        return

    SQLAlchemyInstrumentor().instrument(engine=engine)
    logger.info("SQLAlchemy auto-instrumentation enabled")


def instrument_httpx() -> None:
    """
    Auto-instrument httpx to trace outgoing HTTP requests.

    Every HTTP request made with httpx will create a span:
      - http.method: GET, POST, etc.
      - http.url: The URL being called
      - http.status_code: Response status

    WHY THIS IS VALUABLE:
    --------------------
    Your app calls external APIs (Google OAuth, maybe external RAG services).
    With this instrumentation, you can:
      - See how long external calls take
      - Identify when external services are slow
      - Track which requests are failing

    CONTEXT PROPAGATION:
    -------------------
    When httpx makes a request, the instrumentor automatically:
      - Adds traceparent header to the request
      - This links the external call to your trace

    If the external service also uses OpenTelemetry, the trace
    continues into that service! This is distributed tracing.

    Example:
        Your app ──► Google OAuth API

        Trace shows:
        POST /api/v1/auth/google/callback (800ms)
        └── GET https://oauth2.googleapis.com/tokeninfo (600ms)
    """
    if _tracer_provider is None:
        logger.debug("Tracing not initialized, skipping httpx instrumentation")
        return

    HTTPXClientInstrumentor().instrument()
    logger.info("httpx auto-instrumentation enabled")


def get_tracer(name: str):
    """
    Get a tracer for creating custom spans.

    While auto-instrumentation handles HTTP requests and DB queries,
    you may want to trace specific business logic:
      - Password verification (CPU-intensive)
      - File processing
      - Complex calculations

    USAGE:
    ------
    ```python
    from app.observability.tracing import get_tracer

    tracer = get_tracer(__name__)

    async def verify_password(plain: str, hashed: str) -> bool:
        with tracer.start_as_current_span("verify_password") as span:
            # Add attributes for context
            span.set_attribute("auth.method", "bcrypt")

            # Do the work
            result = bcrypt.verify(plain, hashed)

            # Record the outcome
            span.set_attribute("auth.success", result)
            return result
    ```

    The span will show in your trace as a child of the current span
    (usually the HTTP request span).

    Args:
        name: Usually __name__ to identify the module

    Returns:
        A Tracer instance for creating spans
    """
    return trace.get_tracer(name)


def shutdown_tracing() -> None:
    """
    Gracefully shutdown tracing.

    This should be called when your application is shutting down.
    It ensures all pending spans are exported before exit.

    Without this, spans created just before shutdown might be lost
    because the BatchSpanProcessor hasn't flushed them yet.
    """
    global _tracer_provider

    if _tracer_provider is not None:
        _tracer_provider.shutdown()
        _tracer_provider = None
        logger.info("Tracing shutdown complete")
