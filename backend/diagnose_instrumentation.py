#!/usr/bin/env python3
"""
OpenTelemetry Instrumentation Diagnostic Tool

This script verifies that distributed tracing is correctly configured.
Run inside the backend container to diagnose tracing issues.

Usage (from project root):
    docker exec rag-admin-backend-local python /app/diagnose_instrumentation.py
    docker exec rag-admin-backend python /app/diagnose_instrumentation.py

Or use the test script:
    ./scripts/test-tracing.sh
"""

import sys
import time
sys.path.insert(0, '/app')

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from app.main import app
from app.config import settings

def print_header(title):
    """Print a formatted section header."""
    print("\n" + "=" * 70)
    print(f" {title}")
    print("=" * 70)

def print_check(message, passed, details=None):
    """Print a check result with pass/fail indicator."""
    status = "✓" if passed else "✗"
    color = "\033[92m" if passed else "\033[91m"  # Green or Red
    reset = "\033[0m"
    print(f"{color}{status}{reset} {message}")
    if details:
        print(f"  → {details}")

def main():
    print_header("OpenTelemetry Instrumentation Diagnostic")

    # =========================================================================
    # 1. Configuration Check
    # =========================================================================
    print_header("1. Configuration")

    print_check(
        "OTEL_ENABLED",
        settings.OTEL_ENABLED,
        f"Value: {settings.OTEL_ENABLED}"
    )

    print_check(
        "OTEL_SERVICE_NAME",
        bool(settings.OTEL_SERVICE_NAME),
        f"Value: {settings.OTEL_SERVICE_NAME}"
    )

    print_check(
        "OTEL_EXPORTER_ENDPOINT",
        bool(settings.OTEL_EXPORTER_ENDPOINT),
        f"Value: {settings.OTEL_EXPORTER_ENDPOINT}"
    )

    if not settings.OTEL_ENABLED:
        print("\n⚠️  Tracing is DISABLED. Set OTEL_ENABLED=True to enable.")
        return

    # =========================================================================
    # 2. TracerProvider Check
    # =========================================================================
    print_header("2. TracerProvider")

    provider = trace.get_tracer_provider()
    is_tracer_provider = isinstance(provider, TracerProvider)

    print_check(
        "TracerProvider initialized",
        is_tracer_provider,
        f"Type: {type(provider).__name__}"
    )

    if not is_tracer_provider:
        print("  ✗ TracerProvider not configured correctly")
        print("  → Expected: TracerProvider")
        print(f"  → Got: {type(provider)}")
        return

    # Check resource attributes
    if hasattr(provider, '_resource'):
        resource = provider._resource
        attrs = dict(resource.attributes)
        print(f"  Resource attributes:")
        for key, value in attrs.items():
            print(f"    - {key}: {value}")

    # =========================================================================
    # 3. Span Processor Check
    # =========================================================================
    print_header("3. Span Processors")

    has_processors = False
    if hasattr(provider, '_active_span_processor'):
        processor = provider._active_span_processor
        print(f"  Processor type: {type(processor).__name__}")

        # Check if BatchSpanProcessor
        is_batch = isinstance(processor, BatchSpanProcessor)
        print_check(
            "Using BatchSpanProcessor (recommended)",
            is_batch,
            "Spans are batched for efficiency" if is_batch else "Consider using BatchSpanProcessor"
        )

        # Check sub-processors
        if hasattr(processor, '_span_processors'):
            processors = processor._span_processors
            print(f"  Sub-processors: {len(processors)}")
            for i, sp in enumerate(processors):
                print(f"    {i+1}. {type(sp).__name__}")
                if hasattr(sp, 'span_exporter'):
                    exporter = sp.span_exporter
                    print(f"       Exporter: {type(exporter).__name__}")
            has_processors = len(processors) > 0

    print_check(
        "Span processors configured",
        has_processors,
        "Spans will be exported" if has_processors else "No processors found - spans won't be exported"
    )

    # =========================================================================
    # 4. FastAPI Middleware Check
    # =========================================================================
    print_header("4. FastAPI Middleware")

    print(f"  Total middleware: {len(app.user_middleware)}")

    # List all middleware
    for i, middleware in enumerate(app.user_middleware):
        mw_cls = middleware.cls if hasattr(middleware, 'cls') else middleware
        mw_name = mw_cls.__name__ if hasattr(mw_cls, '__name__') else str(mw_cls)
        print(f"    {i+1}. {mw_name}")

    # Check for OpenTelemetry middleware
    otel_middleware_found = any(
        'OpenTelemetry' in str(m) or 'ServerRequestHook' in str(m)
        for m in app.user_middleware
    )

    print_check(
        "OpenTelemetry middleware present",
        otel_middleware_found,
        "HTTP requests will be traced" if otel_middleware_found else "FastAPI requests won't be traced!"
    )

    if not otel_middleware_found:
        print("\n  ⚠️  OpenTelemetry middleware not found!")
        print("  → Ensure FastAPIInstrumentor.instrument_app(app) is called")
        print("  → Must be called AFTER app creation but BEFORE app startup")

    # =========================================================================
    # 5. Instrumentation Status
    # =========================================================================
    print_header("5. Library Instrumentation")

    # Check FastAPI instrumentor
    instrumentor = FastAPIInstrumentor()
    is_instrumented = instrumentor.is_instrumented_by_opentelemetry

    print_check(
        "FastAPI instrumented",
        is_instrumented,
        "Auto-instrumentation active" if is_instrumented else "Not instrumented via FastAPIInstrumentor"
    )

    # =========================================================================
    # 6. Manual Span Creation Test
    # =========================================================================
    print_header("6. Manual Span Test")

    try:
        tracer = trace.get_tracer("diagnostic")

        with tracer.start_as_current_span("test-span") as span:
            span.set_attribute("test.key", "test.value")
            span.set_attribute("test.timestamp", time.time())

            # Create nested span
            with tracer.start_as_current_span("nested-span") as nested:
                nested.set_attribute("nested", True)

        print_check(
            "Manual span creation",
            True,
            "Spans can be created programmatically"
        )

        # Force flush to export
        if hasattr(provider, 'force_flush'):
            success = provider.force_flush(timeout_millis=5000)
            print_check(
                "Force flush",
                success,
                "Test spans exported to collector" if success else "Failed to export - check collector connectivity"
            )

    except Exception as e:
        print_check(
            "Manual span creation",
            False,
            f"Error: {str(e)}"
        )

    # =========================================================================
    # 7. Summary
    # =========================================================================
    print_header("Summary")

    all_checks = [
        ("Configuration", settings.OTEL_ENABLED),
        ("TracerProvider", is_tracer_provider),
        ("Span Processors", has_processors),
        ("FastAPI Middleware", otel_middleware_found),
    ]

    passed = sum(1 for _, check in all_checks if check)
    total = len(all_checks)

    print(f"\n  Checks passed: {passed}/{total}")

    if passed == total:
        print("\n  ✓ Tracing is correctly configured!")
        print("  → Generate test traffic: curl http://localhost:8000/health")
        print("  → Wait 5-10 seconds for batch export")
        print("  → Check SigNoz: http://localhost:8080")
    else:
        print("\n  ✗ Some checks failed. Review the output above.")
        print("  → See docs/observability/deep-dive.md for troubleshooting")

    print("\n" + "=" * 70 + "\n")

if __name__ == "__main__":
    main()
