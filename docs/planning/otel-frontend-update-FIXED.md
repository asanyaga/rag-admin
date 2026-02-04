# OpenTelemetry Frontend Proxy Implementation - REVISED

## Changes from Original Plan

### Critical Fixes Applied:

1. **Proper HTTP client lifecycle management** - Use FastAPI app state instead of global variables
2. **Configuration via environment variables** - Collector URL and timeouts configurable
3. **Improved error handling** - Return 202 Accepted on collector failure (telemetry should never break the app)
4. **Better header forwarding** - Case-insensitive header handling
5. **Shorter timeouts** - 2-3 second timeouts appropriate for telemetry
6. **Operational logging** - Log collector errors for ops awareness
7. **Proper lifespan integration** - Shows how to integrate with existing app lifecycle

---

## Implementation

### File: `app/api/routes/otel_proxy.py`

```python
"""
OpenTelemetry proxy endpoints.

Forwards frontend telemetry to the local OTel collector,
avoiding browser permission prompts and keeping the collector private.
"""

import httpx
import logging
from fastapi import APIRouter, Request, Response, status
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["telemetry"])


class TelemetrySettings(BaseSettings):
    """Telemetry proxy configuration."""

    otel_collector_url: str = "http://localhost:4318"
    otel_connect_timeout: float = 2.0
    otel_request_timeout: float = 3.0

    class Config:
        env_prefix = "OTEL_"


settings = TelemetrySettings()


def get_http_client(request: Request) -> httpx.AsyncClient:
    """
    Get or create HTTP client from app state.

    Uses app state to avoid race conditions with global variables.
    """
    if not hasattr(request.app.state, "otel_http_client"):
        request.app.state.otel_http_client = httpx.AsyncClient(
            base_url=settings.otel_collector_url,
            timeout=httpx.Timeout(
                connect=settings.otel_connect_timeout,
                read=settings.otel_request_timeout,
                write=settings.otel_request_timeout,
                pool=1.0,
            ),
        )
    return request.app.state.otel_http_client


async def proxy_to_collector(request: Request, path: str) -> Response:
    """
    Forward request to OTel collector and return response.

    Handles both JSON and Protobuf content types.
    Returns 202 Accepted on collector failure to prevent breaking the frontend.
    """
    client = get_http_client(request)

    # Read raw body (works for both JSON and protobuf)
    body = await request.body()

    # Forward relevant headers (case-insensitive)
    headers = {}
    for header_name in ["content-type", "content-encoding", "accept-encoding"]:
        if header_value := request.headers.get(header_name):
            headers[header_name] = header_value

    try:
        response = await client.post(
            path,
            content=body,
            headers=headers,
        )

        # Only return safe response headers
        response_headers = {}
        for header in ["content-type", "content-length"]:
            if header in response.headers:
                response_headers[header] = response.headers[header]

        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=response_headers,
        )

    except (httpx.ConnectError, httpx.TimeoutException, httpx.RequestError) as e:
        # Log for ops awareness but return success to avoid breaking frontend
        # Telemetry should NEVER cause the application to fail
        logger.warning(
            f"OTel collector unavailable for {path}: {type(e).__name__}: {e}",
            extra={"path": path, "error_type": type(e).__name__}
        )
        return Response(
            status_code=status.HTTP_202_ACCEPTED,
            content=b'{"status": "accepted"}',
            headers={"content-type": "application/json"},
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


async def close_http_client(app):
    """Close HTTP client on application shutdown."""
    if hasattr(app.state, "otel_http_client"):
        await app.state.otel_http_client.aclose()
        logger.info("OTel HTTP client closed")
```

### File: `app/main.py` - Integration

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.api.routes import otel_proxy

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Application starting up")

    yield

    # Shutdown
    logger.info("Application shutting down")
    await otel_proxy.close_http_client(app)

# Create or update FastAPI app
app = FastAPI(lifespan=lifespan)

# Include the telemetry proxy router
app.include_router(otel_proxy.router)
```

### Environment Variables

Add to `.env` or deployment configuration:

```bash
# Optional - defaults shown
OTEL_COLLECTOR_URL=http://localhost:4318
OTEL_CONNECT_TIMEOUT=2.0
OTEL_REQUEST_TIMEOUT=3.0
```

### Frontend Configuration

```typescript
// config/telemetry.ts
export const getTelemetryConfig = () => {
  const isDev = import.meta.env.DEV;

  return {
    traces: isDev
      ? 'http://localhost:4318/v1/traces'
      : '/api/v1/traces',
    metrics: isDev
      ? 'http://localhost:4318/v1/metrics'
      : '/api/v1/metrics',
    logs: isDev
      ? 'http://localhost:4318/v1/logs'
      : '/api/v1/logs',
  };
};
```

---

## Key Improvements Summary

| Issue | Original | Fixed |
|-------|----------|-------|
| HTTP client lifecycle | Global variable with race condition | App state management |
| Configuration | Hardcoded URLs | Environment variables via Pydantic |
| Error responses | 503/504 errors | 202 Accepted (fail silently) |
| Timeouts | 10 seconds (too long) | 2-3 seconds (appropriate) |
| Header handling | Case-sensitive | Case-insensitive with .get() |
| Response headers | Returns all headers | Filters to safe headers only |
| Logging | None | Logs collector failures for ops |
| Error types | Only ConnectError, TimeoutException | Added RequestError catch-all |

---

## Testing Checklist

- [ ] Verify no browser permission prompt in production
- [ ] Verify traces appear in SigNoz from frontend
- [ ] Test with collector stopped - app should continue working
- [ ] Check logs for collector warnings when collector is down
- [ ] Test with both JSON and Protobuf content types
- [ ] Load test to verify connection pooling works
- [ ] Verify environment variables override defaults

---

## Why These Changes Matter

1. **App State vs Global**: Prevents race conditions and follows FastAPI best practices
2. **202 vs 503/504**: Telemetry should be invisible to users - never cause errors
3. **Shorter timeouts**: Frontend shouldn't wait 10s for telemetry to timeout
4. **Configuration**: Different environments need different settings (dev/staging/prod)
5. **Logging**: Ops need to know when collector is down without user-facing errors
6. **Header filtering**: Don't leak internal collector headers to frontend
