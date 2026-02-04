"""
Tracing Response Middleware

Injects OpenTelemetry trace context into HTTP response headers for
frontend-to-backend trace correlation.

This middleware adds W3C Trace Context headers (traceparent, tracestate) and
Server-Timing header to responses, enabling frontend applications to:
1. Extract trace IDs for error logging and debugging
2. Link frontend spans to backend spans in distributed traces
3. View trace context in browser DevTools Network tab
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from opentelemetry import trace
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator


class TracingResponseMiddleware(BaseHTTPMiddleware):
    """
    Middleware to inject OpenTelemetry trace context into response headers.

    Adds the following headers to responses:
    - Server-Timing: Contains traceparent in format compatible with browser DevTools
    - traceparent: W3C Trace Context header for propagation
    - tracestate: W3C Trace Context state (if present)

    The frontend can extract these headers to:
    - Create child spans that continue the distributed trace
    - Log trace IDs with errors for correlation
    - Display trace information in UI for debugging
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        """Process request and inject trace headers into response."""

        # Skip health/monitoring endpoints to avoid any trace context processing
        if request.url.path in ["/health", "/metrics", "/readiness"]:
            return await call_next(request)

        response = await call_next(request)

        # Get the current span context
        current_span = trace.get_current_span()

        # Only add headers if we have an active recording span
        if current_span and current_span.is_recording():
            span_context = current_span.get_span_context()

            # Format trace and span IDs as hex strings
            trace_id = format(span_context.trace_id, '032x')
            span_id = format(span_context.span_id, '016x')

            # Add Server-Timing header for browser DevTools
            # This makes traces visible in the Performance/Network tabs
            response.headers["Server-Timing"] = (
                f'traceparent;desc="00-{trace_id}-{span_id}-01"'
            )

            # Add W3C Trace Context headers for programmatic access
            # Frontend can extract these to create child spans
            carrier = {}
            TraceContextTextMapPropagator().inject(carrier)

            if "traceparent" in carrier:
                response.headers["traceparent"] = carrier["traceparent"]
            if "tracestate" in carrier:
                response.headers["tracestate"] = carrier["tracestate"]

        return response
