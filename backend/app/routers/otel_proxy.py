"""
OpenTelemetry proxy endpoints.

Forwards frontend telemetry to the local OTel collector,
avoiding browser permission prompts and keeping the collector private.
"""

import httpx
import logging
from fastapi import APIRouter, Request, Response, status

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["telemetry"])


def get_http_client(request: Request) -> httpx.AsyncClient:
    """
    Get or create HTTP client from app state.

    Uses app state to avoid race conditions with global variables.
    """
    if not hasattr(request.app.state, "otel_http_client"):
        from app.config import settings

        request.app.state.otel_http_client = httpx.AsyncClient(
            base_url=settings.OTEL_COLLECTOR_URL,
            timeout=httpx.Timeout(
                connect=settings.OTEL_CONNECT_TIMEOUT,
                read=settings.OTEL_REQUEST_TIMEOUT,
                write=settings.OTEL_REQUEST_TIMEOUT,
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
            extra={"path": path, "error_type": type(e).__name__},
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
