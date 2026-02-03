"""
Observability Module
====================

Provides distributed tracing for the RAG Admin application using OpenTelemetry.

USAGE:
------
Tracing is initialized at module level in main.py:

    from app.observability.tracing import setup_tracing, instrument_httpx
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    # Initialize tracing before app creation
    setup_tracing(
        service_name=settings.OTEL_SERVICE_NAME,
        service_version="0.1.0",
        otlp_endpoint=settings.OTEL_EXPORTER_ENDPOINT,
        enabled=settings.OTEL_ENABLED,
    )

    # Create app
    app = FastAPI(...)

    # Instrument FastAPI immediately
    FastAPIInstrumentor.instrument_app(app)

    # Instrument other libraries
    instrument_httpx()

CREATING CUSTOM SPANS:
---------------------
For manual instrumentation of business logic:

    from app.observability import get_tracer

    tracer = get_tracer(__name__)

    def my_function():
        with tracer.start_as_current_span("operation_name") as span:
            span.set_attribute("key", "value")
            # Your code here

CONFIGURATION:
--------------
Settings in app/config.py:

    OTEL_ENABLED           - Master toggle (True/False)
    OTEL_EXPORTER_ENDPOINT - Collector address (http://collector:4317)
    OTEL_SERVICE_NAME      - Service identifier (rag-admin-backend)
"""

from app.observability.tracing import (
    setup_tracing,
    instrument_sqlalchemy,
    instrument_httpx,
    shutdown_tracing,
    get_tracer,
)

# Package version - used in trace resource attributes
__version__ = "0.1.0"

# Export functions for external use
__all__ = [
    # Tracing setup
    "setup_tracing",
    "instrument_sqlalchemy",
    "instrument_httpx",
    "shutdown_tracing",
    # Manual instrumentation
    "get_tracer",
]
