"""
Observability Module
====================

This module provides comprehensive observability for the RAG Admin application,
implementing the three pillars of observability:

1. TRACING  - See the journey of each request (tracing.py)
2. LOGGING  - Structured logs with trace correlation (logging.py) - coming next
3. METRICS  - Counters, gauges, histograms (metrics.py) - coming next

QUICK START:
------------
In your main.py, initialize observability on startup:

    from app.observability import setup_observability, shutdown_observability

    @app.on_event("startup")
    async def startup():
        setup_observability(app)

    @app.on_event("shutdown")
    async def shutdown():
        shutdown_observability()

WHAT HAPPENS DURING SETUP:
--------------------------

    setup_observability(app)
            │
            ├──► setup_tracing()
            │    Creates TracerProvider, configures OTLP exporter,
            │    enables auto-instrumentation for FastAPI, SQLAlchemy, httpx
            │
            ├──► setup_logging()  (Task 4)
            │    Configures structured JSON logging with trace_id injection
            │
            └──► setup_metrics()  (Task 5)
                 Creates MeterProvider, configures basic HTTP metrics

CONFIGURATION:
--------------
All settings come from app/config.py:

    OTEL_ENABLED          - Master toggle (True/False)
    OTEL_EXPORTER_ENDPOINT - Collector address (http://collector:4317)
    OTEL_SERVICE_NAME     - Service identifier (rag-admin-backend)
    LOG_LEVEL             - Minimum log level (INFO)
    LOG_FORMAT            - Output format (json/text)

DISABLING OBSERVABILITY:
------------------------
Set OTEL_ENABLED=False in your environment to completely disable
all observability. This is useful for:
    - Local development without Docker
    - Running tests
    - Debugging without telemetry overhead
"""

import logging
from typing import TYPE_CHECKING

from app.config import settings
from app.observability.tracing import (
    setup_tracing,
    instrument_fastapi,
    instrument_httpx,
    shutdown_tracing,
    get_tracer,
)
from app.observability.log_config import setup_logging, get_logger
from app.observability.metrics import (
    setup_metrics,
    record_http_request,
    get_meter,
    shutdown_metrics,
)
from app.observability.middleware import MetricsMiddleware

# TYPE_CHECKING prevents circular imports - FastAPI is only imported for type hints
if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)

# Package version - used in trace resource attributes
__version__ = "0.1.0"


def setup_observability(app: "FastAPI") -> None:
    """
    Initialize all observability components.

    This is the main entry point for setting up observability.
    Call this once during application startup, BEFORE handling any requests.

    The order of initialization matters:
    1. Tracing first (other components may create spans)
    2. Logging second (needs trace context for correlation)
    3. Metrics third (independent but follows same pattern)
    4. Instrument FastAPI last (after providers are ready)

    Args:
        app: The FastAPI application instance

    Example:
        >>> from fastapi import FastAPI
        >>> from app.observability import setup_observability
        >>>
        >>> app = FastAPI()
        >>>
        >>> @app.on_event("startup")
        >>> async def startup():
        >>>     setup_observability(app)
    """
    # Check if observability is enabled
    if not settings.OTEL_ENABLED:
        logger.info(
            "Observability is DISABLED. Set OTEL_ENABLED=True to enable. "
            "Telemetry will not be collected."
        )
        return

    logger.info("=" * 60)
    logger.info("Initializing Observability Stack")
    logger.info("=" * 60)
    logger.info(f"  Service Name: {settings.OTEL_SERVICE_NAME}")
    logger.info(f"  Exporter Endpoint: {settings.OTEL_EXPORTER_ENDPOINT}")
    logger.info(f"  Log Level: {settings.LOG_LEVEL}")
    logger.info(f"  Log Format: {settings.LOG_FORMAT}")
    logger.info("=" * 60)

    # -------------------------------------------------------------------------
    # Step 1: Initialize Tracing
    # -------------------------------------------------------------------------
    # Tracing must be set up first because:
    #   - The TracerProvider must exist before any spans are created
    #   - Logging setup needs trace context to inject trace_id
    #   - Auto-instrumentors need the provider to be registered

    setup_tracing(
        service_name=settings.OTEL_SERVICE_NAME,
        service_version=__version__,
        otlp_endpoint=settings.OTEL_EXPORTER_ENDPOINT,
        enabled=settings.OTEL_ENABLED,
    )

    # -------------------------------------------------------------------------
    # Step 2: Initialize Structured Logging
    # -------------------------------------------------------------------------
    # Structured logging outputs JSON with trace correlation.
    # Every log entry includes trace_id and span_id, allowing you to:
    #   - Click a log entry in SigNoz and see the full trace
    #   - Search for all logs related to a specific request
    #   - Correlate errors with the requests that caused them

    setup_logging(
        service_name=settings.OTEL_SERVICE_NAME,
        level=settings.LOG_LEVEL,
        log_format=settings.LOG_FORMAT,
    )

    # -------------------------------------------------------------------------
    # Step 3: Initialize Metrics
    # -------------------------------------------------------------------------
    # Metrics answer questions about aggregate behavior:
    #   - How many requests per second?
    #   - What's the p99 latency?
    #   - What's the error rate?
    #
    # We create two standard HTTP metrics:
    #   - http_server_requests_total (counter)
    #   - http_server_request_duration_seconds (histogram)

    setup_metrics(
        service_name=settings.OTEL_SERVICE_NAME,
        service_version=__version__,
        otlp_endpoint=settings.OTEL_EXPORTER_ENDPOINT,
        enabled=settings.OTEL_ENABLED,
    )

    # -------------------------------------------------------------------------
    # Step 4: Auto-instrument libraries
    # -------------------------------------------------------------------------
    # Now that the TracerProvider is set up, we can instrument libraries.
    # The order here doesn't matter since they're independent.

    # Instrument FastAPI for HTTP request tracing
    # NOTE: We call instrument_app() here, but middleware is only added if
    # instrumentation hasn't been applied yet. For proper tracing, FastAPI
    # should ideally be instrumented before first request, but calling it
    # in startup event still works for most cases.
    instrument_fastapi(app)

    # Instrument httpx for outgoing HTTP request tracing
    # (Used by Google OAuth, external API calls, etc.)
    instrument_httpx()

    # Note: SQLAlchemy instrumentation happens in database.py
    # because we need access to the engine instance.
    # See: app/database.py

    logger.info("Observability initialization complete")


def shutdown_observability() -> None:
    """
    Gracefully shutdown all observability components.

    Call this during application shutdown to ensure:
    - All pending spans are exported
    - All pending metrics are flushed
    - Connections are properly closed

    Without this, telemetry created just before shutdown might be lost.

    Example:
        >>> @app.on_event("shutdown")
        >>> async def shutdown():
        >>>     shutdown_observability()
    """
    logger.info("Shutting down observability...")

    # Shutdown in reverse order of initialization
    # (metrics first, then tracing, since metrics might create spans)
    shutdown_metrics()
    shutdown_tracing()

    logger.info("Observability shutdown complete")


# Export commonly used items for convenience
__all__ = [
    # Main setup functions
    "setup_observability",
    "shutdown_observability",
    # Tracing
    "get_tracer",
    # Logging
    "get_logger",
    # Metrics
    "get_meter",
    "record_http_request",
    # Middleware
    "MetricsMiddleware",
]
