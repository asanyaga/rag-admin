# OpenTelemetry Frontend Proxy Implementation

## Handoff Document for Claude Code

**Project:** RAG Admin Application  
**Goal:** Enable frontend observability (traces, metrics, logs) without exposing the OTel collector or triggering browser permission prompts

---

## Current Situation Analysis

### The Problem

When users visit `ragadmin.adilitech.com`, Chrome displays a permission prompt:

> "ragadmin.adilitech.com wants to look for and connect to any device on your local network"

**Root cause:** The frontend OpenTelemetry SDK is configured to send traces to `http://localhost:4318/v1/traces`. In production, `localhost` resolves to the visitor's machine, not the server. This triggers Chrome's Local Network Access permission because the browser detects a request to a local/private IP range.

### Impact

| Issue | Severity |
|-------|----------|
| Every visitor sees an alarming permission prompt | High |
| Users who click "Block" (most will) send no telemetry | High |
| Users who click "Allow" still fail — no collector on their machine | High |
| Damages trust and professional appearance of the application | High |
| Zero frontend telemetry is actually being collected | Critical |

### Current Architecture (Broken)

```
┌─────────────────┐     ❌ localhost:4318      ┌─────────────────┐
│                 │ ─────────────────────────► │                 │
│  User Browser   │   (resolves to user's PC)  │  SigNoz/OTel    │
│  (frontend JS)  │                            │  Collector      │
│                 │                            │  (on server)    │
└─────────────────┘                            └─────────────────┘
        │
        ▼
   Permission prompt
   (always fails)
```

---

## Solution: Backend Proxy for OTLP Signals

Route all frontend telemetry through FastAPI endpoints that forward to the local collector.

### Target Architecture

```
┌─────────────────┐                           ┌─────────────────┐
│                 │   POST /api/v1/traces     │                 │
│  User Browser   │ ────────────────────────► │    FastAPI      │
│  (frontend JS)  │   POST /api/v1/metrics    │    Backend      │
│                 │   POST /api/v1/logs       │                 │
└─────────────────┘                           └────────┬────────┘
                                                       │
                                              localhost:4318
                                                       │
                                                       ▼
                                              ┌─────────────────┐
                                              │  SigNoz/OTel    │
                                              │  Collector      │
                                              └─────────────────┘
```

### Why This Works

1. Frontend sends telemetry to same origin (`ragadmin.adilitech.com/api/v1/traces`)
2. No cross-origin request, no local network access — no permission prompt
3. FastAPI forwards to collector on `localhost:4318` (server-side, this works)
4. Collector is never exposed to the internet (security win)

---

## OTLP Signal Types & Endpoints

OpenTelemetry uses three signal types, each with its own endpoint:

| Signal | OTLP Endpoint | Use Case |
|--------|---------------|----------|
| **Traces** | `/v1/traces` | Distributed tracing, request flows, user interactions |
| **Metrics** | `/v1/metrics` | Web Vitals (LCP, FCP, CLS, TTFB), custom counters |
| **Logs** | `/v1/logs` | Frontend errors, console captures, user events |

**Answer to your question:** Yes, Web Vitals and error logging will use different endpoints. Web Vitals are typically exported as metrics, and frontend errors as logs. The implementation below covers all three.

---

## Phase 1: Implementation (Immediate)

### FastAPI Proxy Endpoints

Create a new router file for OTLP proxy endpoints:

**File:** `app/api/routes/otel_proxy.py`

```python
"""
OpenTelemetry proxy endpoints.

Forwards frontend telemetry to the local OTel collector,
avoiding browser permission prompts and keeping the collector private.
"""

import httpx
from fastapi import APIRouter, Request, Response, status
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/v1", tags=["telemetry"])

# Collector base URL - localhost works server-side
OTEL_COLLECTOR_URL = "http://localhost:4318"

# Reusable async client (connection pooling)
_http_client: httpx.AsyncClient | None = None


async def get_http_client() -> httpx.AsyncClient:
    """Lazy-initialize HTTP client with connection pooling."""
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(
            base_url=OTEL_COLLECTOR_URL,
            timeout=10.0,
        )
    return _http_client


async def proxy_to_collector(request: Request, path: str) -> Response:
    """
    Forward request to OTel collector and return response.
    
    Handles both JSON and Protobuf content types.
    """
    client = await get_http_client()
    
    # Read raw body (works for both JSON and protobuf)
    body = await request.body()
    
    # Preserve content-type header (application/json or application/x-protobuf)
    headers = {}
    if "content-type" in request.headers:
        headers["content-type"] = request.headers["content-type"]
    
    try:
        response = await client.post(
            path,
            content=body,
            headers=headers,
        )
        
        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=dict(response.headers),
        )
        
    except httpx.ConnectError:
        # Collector not reachable - log but don't fail the user's experience
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"error": "Telemetry collector unavailable"},
        )
    except httpx.TimeoutException:
        return JSONResponse(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            content={"error": "Telemetry collector timeout"},
        )


@router.post("/traces")
async def proxy_traces(request: Request) -> Response:
    """Proxy trace data to OTel collector."""
    return await proxy_to_collector(request, "/v1/traces")


@router.post("/metrics")
async def proxy_metrics(request: Request) -> Response:
    """Proxy metrics (including Web Vitals) to OTel collector."""
    return await proxy_to_collector(request, "/v1/metrics")


@router.post("/logs")
async def proxy_logs(request: Request) -> Response:
    """Proxy logs (including frontend errors) to OTel collector."""
    return await proxy_to_collector(request, "/v1/logs")


# Cleanup on shutdown
async def close_http_client():
    """Close HTTP client on application shutdown."""
    global _http_client
    if _http_client:
        await _http_client.aclose()
        _http_client = None
```

**File:** `app/main.py` (add to existing)

```python
from app.api.routes import otel_proxy
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    # Cleanup
    await otel_proxy.close_http_client()

# Include the router
app.include_router(otel_proxy.router)
```

### Frontend Configuration Change

Update the frontend OTel initialization to use the proxy:

**Before:**
```javascript
const collectorUrl = 'http://localhost:4318/v1/traces';
```

**After:**
```javascript
// Use relative URL - works in all environments
const collectorUrl = '/api/v1/traces';

// Or with explicit origin for clarity
const collectorUrl = `${window.location.origin}/api/v1/traces`;
```

**Environment-aware configuration (recommended):**

```javascript
// config/telemetry.ts
export const getCollectorUrl = (signal: 'traces' | 'metrics' | 'logs') => {
  if (import.meta.env.DEV) {
    // Local development - direct to collector
    return `http://localhost:4318/v1/${signal}`;
  }
  // Production - use proxy
  return `/api/v1/${signal}`;
};
```

---

## Phase 2: Future Enhancements

### 2.1 Web Vitals Integration

Web Vitals should be exported as OTLP metrics. The frontend setup:

```javascript
// Install: npm install web-vitals @opentelemetry/api @opentelemetry/sdk-metrics

import { onCLS, onFCP, onLCP, onTTFB, onINP } from 'web-vitals';
import { MeterProvider } from '@opentelemetry/sdk-metrics';
import { OTLPMetricExporter } from '@opentelemetry/exporter-metrics-otlp-http';

const metricExporter = new OTLPMetricExporter({
  url: '/api/v1/metrics',  // Uses our proxy
});

// Record each vital as a metric
onLCP((metric) => {
  // Export as histogram or gauge
});
```

**Proxy endpoint needed:** `/api/v1/metrics` ✅ (included in Phase 1)

### 2.2 Frontend Error Logging

Capture and export frontend errors as OTLP logs:

```javascript
import { LoggerProvider } from '@opentelemetry/sdk-logs';
import { OTLPLogExporter } from '@opentelemetry/exporter-logs-otlp-http';

const logExporter = new OTLPLogExporter({
  url: '/api/v1/logs',  // Uses our proxy
});

// Global error handler
window.addEventListener('error', (event) => {
  logger.emit({
    severityText: 'ERROR',
    body: event.message,
    attributes: {
      'error.stack': event.error?.stack,
      'error.filename': event.filename,
      'error.lineno': event.lineno,
    },
  });
});

// Unhandled promise rejections
window.addEventListener('unhandledrejection', (event) => {
  logger.emit({
    severityText: 'ERROR',
    body: `Unhandled rejection: ${event.reason}`,
  });
});
```

**Proxy endpoint needed:** `/api/v1/logs` ✅ (included in Phase 1)

### 2.3 User Analytics Events

Custom events for analytics (page views, button clicks, feature usage):

```javascript
// As traces (spans)
tracer.startSpan('user.action', {
  attributes: {
    'action.type': 'button_click',
    'action.target': 'submit_document',
    'page.path': window.location.pathname,
  },
}).end();

// Or as logs
logger.emit({
  severityText: 'INFO',
  body: 'User action',
  attributes: {
    'event.name': 'document_uploaded',
    'document.type': 'pdf',
  },
});
```

### 2.4 Rate Limiting (Optional Enhancement)

If concerned about abuse, add rate limiting to proxy endpoints:

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/traces")
@limiter.limit("100/minute")
async def proxy_traces(request: Request) -> Response:
    return await proxy_to_collector(request, "/v1/traces")
```

### 2.5 Request Correlation

Link frontend spans to backend spans for full distributed tracing:

```javascript
// Frontend: Include trace context in API requests
fetch('/api/documents', {
  headers: {
    'traceparent': getTraceParent(),  // W3C Trace Context header
  },
});
```

```python
# Backend: Extract and continue trace context
from opentelemetry.propagate import extract

@router.get("/documents")
async def get_documents(request: Request):
    context = extract(request.headers)
    with tracer.start_as_current_span("get_documents", context=context):
        # This span is now linked to the frontend span
        ...
```

---

## Implementation Checklist for Claude Code

### Phase 1 Tasks (Do Now)

- [ ] Create `app/api/routes/otel_proxy.py` with the three proxy endpoints
- [ ] Add router to `app/main.py` 
- [ ] Add `httpx` to requirements/dependencies if not present
- [ ] Add lifespan handler for cleanup (or integrate with existing)
- [ ] Update frontend telemetry config to use `/api/v1/traces` instead of `localhost:4318`
- [ ] Test locally: verify traces appear in SigNoz
- [ ] Deploy and verify no more browser permission prompts

### Phase 2 Tasks (Next)

- [ ] Add Web Vitals collection to frontend using `/api/v1/metrics`
- [ ] Add global error handlers exporting to `/api/v1/logs`
- [ ] Add request correlation (traceparent header propagation)
- [ ] Consider rate limiting on proxy endpoints

### Testing Verification

1. **No permission prompt:** Load site in Chrome incognito, should see no prompt
2. **Traces flowing:** Check SigNoz for traces from frontend
3. **Error handling:** Stop collector, verify app still works (graceful degradation)
4. **Content types:** Test with both JSON and Protobuf exporters

---

## Files to Modify

| File | Action |
|------|--------|
| `app/api/routes/otel_proxy.py` | Create new |
| `app/main.py` | Add router include + lifespan cleanup |
| `requirements.txt` or `pyproject.toml` | Add `httpx` if missing |
| `frontend/src/config/telemetry.ts` (or equivalent) | Change collector URL |

---

## Security Considerations

1. **Collector not exposed:** The OTel collector stays on localhost, never internet-facing
2. **Same-origin requests:** No CORS complexity, uses existing auth cookies
3. **No sensitive data in telemetry:** Review what attributes are being sent
4. **Rate limiting:** Consider adding to prevent telemetry spam/abuse

---

## Configuration Reference

**Environment variables to consider:**

```bash
# Backend
OTEL_COLLECTOR_URL=http://localhost:4318  # Default, can override

# Frontend (build-time)
VITE_OTEL_PROXY_ENABLED=true
```

---

## Summary

This implementation solves the immediate browser permission issue while setting up a proper foundation for comprehensive frontend observability including traces, Web Vitals metrics, and error logging—all flowing through a secure backend proxy to your SigNoz collector.
