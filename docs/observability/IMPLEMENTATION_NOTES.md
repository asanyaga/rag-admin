# Observability Implementation Notes

This document captures key learnings from implementing distributed tracing in RAG Admin.

## The Problem

**Symptom**: FastAPI instrumentation wasn't working. No HTTP request spans appeared in SigNoz.

**Root Cause**: `FastAPIInstrumentor.instrument_app(app)` wasn't adding middleware correctly.

## The Solution

Use `OpenTelemetryMiddleware` directly instead of the FastAPI-specific instrumentor:

```python
from opentelemetry import trace
from opentelemetry.instrumentation.asgi import OpenTelemetryMiddleware

# AFTER creating app, BEFORE adding other middleware
if settings.OTEL_ENABLED:
    app.add_middleware(
        OpenTelemetryMiddleware,
        tracer_provider=trace.get_tracer_provider()
    )
```

### Why This Works

- **`OpenTelemetryMiddleware`** is the low-level ASGI middleware that actually does the tracing
- **`FastAPIInstrumentor`** is a high-level wrapper that's supposed to add this middleware automatically
- For unknown reasons, `FastAPIInstrumentor.instrument_app()` wasn't adding the middleware in our setup
- Using the middleware directly bypasses the instrumentor and works reliably

## Implementation Pattern

### Module-Level Initialization (backend/app/main.py)

```python
# 1. Setup tracing BEFORE app creation
from app.observability.tracing import setup_tracing, instrument_httpx

setup_tracing(...)
instrument_httpx()

# 2. Create app
app = FastAPI(...)

# 3. Add OpenTelemetry middleware IMMEDIATELY
if settings.OTEL_ENABLED:
    from opentelemetry import trace
    from opentelemetry.instrumentation.asgi import OpenTelemetryMiddleware

    app.add_middleware(
        OpenTelemetryMiddleware,
        tracer_provider=trace.get_tracer_provider()
    )

# 4. Add other middleware (CORS, Session, etc.)
app.add_middleware(CORSMiddleware, ...)
app.add_middleware(SessionMiddleware, ...)

# 5. In startup event: non-middleware instrumentation
@app.on_event("startup")
async def startup():
    instrument_sqlalchemy(engine.sync_engine)
```

### Key Points

1. **Timing is critical**: Middleware must be added before uvicorn starts
2. **Order matters**: OpenTelemetry middleware should be outermost (added first)
3. **Direct middleware**: Use `OpenTelemetryMiddleware` directly, not `FastAPIInstrumentor`
4. **SQLAlchemy in startup**: Engine instrumentation can happen in startup event

## Diagnostic Process

### 1. Check Middleware Stack

```python
# In main.py during initialization
print(f"Middleware: {[m.cls.__name__ for m in app.user_middleware]}")
```

Expected output should include `OpenTelemetryMiddleware`.

### 2. Run Diagnostic Script

```bash
docker exec rag-admin-backend-local python /app/diagnose_instrumentation.py
```

Should show:
- ✓ TracerProvider initialized
- ✓ Span processors configured
- ✓ OpenTelemetry middleware present
- ✓ Manual span creation

### 3. Check Backend Logs

```bash
docker logs rag-admin-backend-local | grep -i "otel\|trace"
```

Should see tracing initialization without errors.

### 4. Generate Traffic and Check SigNoz

```bash
curl http://localhost:8000/health
sleep 10  # Wait for batch export
# Check http://localhost:8080 for traces
```

## Troubleshooting

### Middleware Not Added

**Symptom**: Diagnostic shows no OpenTelemetry middleware

**Fix**: Ensure `app.add_middleware(OpenTelemetryMiddleware, ...)` is called at module level

### Traces Not Appearing in SigNoz

**Check 1**: Is collector reachable?
```bash
docker exec rag-admin-backend-local curl -v http://signoz-otel-collector:4317
```

**Check 2**: Is backend on signoz-net network?
```bash
docker inspect rag-admin-backend-local | grep Networks -A 10
```

**Check 3**: Are spans being created?
```bash
docker exec rag-admin-backend-local python /app/diagnose_instrumentation.py
```

### Collector Connection Errors

**Symptom**: `StatusCode.UNAVAILABLE` errors in logs

**Causes**:
- SigNoz not running: `cd ~/signoz/deploy/docker && docker compose ps`
- Network issue: Check both services are on `signoz-net`
- Transient error: If traces still appear in SigNoz, these can be ignored

## Performance Notes

### Overhead

With `BatchSpanProcessor`:
- **Latency**: < 1-2ms per request
- **Memory**: ~50-100MB for span queue
- **CPU**: Minimal (background thread)

### Optimization

For high-traffic endpoints:
```python
# Exclude health checks from tracing
app.add_middleware(
    OpenTelemetryMiddleware,
    excluded_urls="/health,/metrics",  # Don't trace these
    tracer_provider=trace.get_tracer_provider()
)
```

## Next Steps

Once HTTP tracing is working:

1. **Add manual spans** to business logic (see `backend/app/routers/auth.py`)
2. **Re-enable logging** with trace correlation
3. **Re-enable metrics** for request counts and latency
4. **Configure sampling** for production (10% of traces)
5. **Set up alerts** in SigNoz for errors and high latency

## References

- [OpenTelemetry Python ASGI Instrumentation](https://github.com/open-telemetry/opentelemetry-python-contrib/tree/main/instrumentation/opentelemetry-instrumentation-asgi)
- [FastAPI Instrumentation](https://github.com/open-telemetry/opentelemetry-python-contrib/tree/main/instrumentation/opentelemetry-instrumentation-fastapi)
- [Manual Span Guide](./manual-spans.md)
- [Testing Guide](./TESTING.md)
- [Deep Dive](./deep-dive.md)
