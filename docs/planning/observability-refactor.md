# Observability Refactor Tasks

Tasks for fixing and improving the observability setup after migration to official SigNoz.

---

## Current Status

**Infrastructure**: ✅ Complete
- Official SigNoz running and healthy
- Multi-network architecture (app-network + signoz-net) implemented
- Backend connected to both networks
- OTLP export pipeline verified working (manual test-service traces appearing)

**Instrumentation**: ❌ Broken
- FastAPI auto-instrumentation not creating spans
- `rag-admin-backend` service not appearing in SigNoz
- All requests going untraced despite instrumentation code running without errors

---

## Priority 1: Fix FastAPI Instrumentation

### Task 1: Try Module-Level Instrumentation
**Status**: TODO
**Priority**: HIGH

Instead of instrumenting in `@app.on_event("startup")`, try instrumenting at module import time in `backend/app/main.py`.

**Approach**:
```python
# At the end of backend/app/main.py, AFTER app is created but BEFORE uvicorn starts
from app.observability.tracing import setup_tracing, instrument_fastapi
from app.config import settings

# Initialize tracing immediately
setup_tracing(
    service_name=settings.OTEL_SERVICE_NAME,
    service_version="0.1.0",
    otlp_endpoint=settings.OTEL_EXPORTER_ENDPOINT,
    enabled=settings.OTEL_ENABLED
)

# Instrument FastAPI immediately
instrument_fastapi(app)
```

**Why this might work**: Middleware must be added before uvicorn starts processing requests. The startup event fires after uvicorn is already listening.

---

### Task 2: Investigate OpenTelemetry Version Compatibility
**Status**: TODO
**Priority**: MEDIUM

Check if there's a version mismatch between OpenTelemetry packages.

**Steps**:
1. Check installed versions:
   ```bash
   docker exec rag-admin-backend-local pip list | grep opentelemetry
   ```

2. Verify compatibility matrix:
   - opentelemetry-api
   - opentelemetry-sdk
   - opentelemetry-instrumentation-fastapi
   - opentelemetry-exporter-otlp-proto-grpc

3. Check for known issues in GitHub repos:
   - https://github.com/open-telemetry/opentelemetry-python
   - https://github.com/open-telemetry/opentelemetry-python-contrib

---

### Task 3: Review FastAPI Instrumentor Source Code
**Status**: TODO
**Priority**: MEDIUM

Understand exactly what `FastAPIInstrumentor.instrument_app()` does and why it might be failing silently.

**Key questions**:
- Does `instrument_app()` have prerequisites?
- What does `is_instrumented_by_opentelemetry` actually check?
- Are there any silent failure modes?

**Links**:
- [FastAPIInstrumentor source](https://github.com/open-telemetry/opentelemetry-python-contrib/blob/main/instrumentation/opentelemetry-instrumentation-fastapi/src/opentelemetry/instrumentation/fastapi/__init__.py)

---

### Task 4: Implement Manual Span Creation as Fallback
**Status**: TODO
**Priority**: LOW

If auto-instrumentation continues to fail, implement manual instrumentation using a custom middleware.

**Approach**:
```python
from starlette.middleware.base import BaseHTTPMiddleware
from opentelemetry import trace

class ManualTracingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        tracer = trace.get_tracer(__name__)

        with tracer.start_as_current_span(
            f"{request.method} {request.url.path}",
            kind=trace.SpanKind.SERVER
        ) as span:
            span.set_attribute("http.method", request.method)
            span.set_attribute("http.url", str(request.url))

            response = await call_next(request)

            span.set_attribute("http.status_code", response.status_code)
            return response
```

**Trade-offs**:
- ✅ Pro: Full control, guaranteed to work
- ❌ Con: Miss out on automatic SQLAlchemy, httpx instrumentation context propagation
- ❌ Con: More maintenance burden

---

## Priority 2: Diagnostic Tools

### Task 5: Create Comprehensive Diagnostic Script
**Status**: TODO
**Priority**: MEDIUM

Build on `diagnose_instrumentation.py` to create a comprehensive diagnostic that checks:

1. Tracer provider configuration
2. Span processor chain
3. OTLP exporter configuration
4. Middleware stack inspection
5. Manual span creation test
6. Span export test
7. Collector connectivity test

**Output**: Clear report showing exactly where the pipeline is breaking.

---

### Task 6: Add Instrumentation Verification to Startup
**Status**: TODO
**Priority**: LOW

Add automatic verification during app startup that instrumentation is working:

```python
@app.on_event("startup")
async def verify_instrumentation():
    # Create a test span
    tracer = trace.get_tracer("startup_verification")
    with tracer.start_as_current_span("startup-verification-span") as span:
        span.set_attribute("test", True)

    # Force flush
    provider = trace.get_tracer_provider()
    if hasattr(provider, 'force_flush'):
        provider.force_flush(timeout_millis=5000)

    # Log success/failure
    logger.info("Instrumentation verification complete")
```

---

## Priority 3: Documentation

### Task 7: Document Instrumentation Issue
**Status**: TODO
**Priority**: LOW

Add troubleshooting section to `docs/observability/README.md`:

**Section**: "Known Issues"
- FastAPI instrumentation not working
- Symptoms
- Workarounds tried
- Current status

---

## Context for Next Session

**What works**:
- SigNoz infrastructure fully operational
- OTLP export pipeline working (proven with `test-service`)
- TracerProvider configuration correct
- Network connectivity correct

**What doesn't work**:
- FastAPI auto-instrumentation
- `rag-admin-backend` service not appearing in SigNoz UI
- No HTTP request spans being created

**Files modified today**:
- `backend/app/observability/tracing.py` - Multiple instrumentation approaches tried
- `backend/app/observability/__init__.py` - Comments updated
- `docker-compose.prod.yml` - Multi-network setup
- `docker-compose.local.yml` - Multi-network setup
- All documentation files

**Key diagnostic files created**:
- `test_otlp_export.py` - Proves OTLP pipeline works
- `test-telemetry.sh` - User-friendly telemetry test
- `scripts/verify-observability.sh` - Infrastructure verification
- `diagnose_instrumentation.py` - Instrumentation state check (not yet run)

**Recommended starting point**: Task 1 (module-level instrumentation) - most likely to succeed.
