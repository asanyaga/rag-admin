"""
Observability Middleware
========================

This module provides middleware for collecting HTTP metrics on every request.

WHY MIDDLEWARE?
--------------
Middleware wraps every request, making it the perfect place to:
- Record metrics (request count, duration)
- Add common context to logs
- Handle cross-cutting concerns

The middleware runs AROUND your route handlers:

    Request arrives
         │
         ▼
    ┌─────────────────────────────────────┐
    │  MetricsMiddleware.dispatch()       │
    │  1. Record start time               │
    │  2. Call next handler ──────────────┼──► Your route handler runs
    │  3. Record end time                 │◄── Response returned
    │  4. Record metrics                  │
    │  5. Return response                 │
    └─────────────────────────────────────┘
         │
         ▼
    Response sent to client

WHAT WE RECORD:
--------------
For every HTTP request:
- Counter: http_server_requests_total (incremented by 1)
- Histogram: http_server_request_duration_seconds (response time)

Both metrics include labels:
- method: GET, POST, PUT, DELETE, etc.
- route: URL pattern (e.g., /api/v1/users/{id})
- status_code: 200, 404, 500, etc.
"""

import time
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Match

from app.observability.metrics import record_http_request


class MetricsMiddleware(BaseHTTPMiddleware):
    """
    Middleware that records HTTP metrics for every request.

    This middleware:
    1. Captures the start time before handling
    2. Calls the next handler in the chain
    3. Records metrics after the response is generated

    Usage:
        app.add_middleware(MetricsMiddleware)

    Metrics recorded:
    - http_server_requests_total: Counter of all requests
    - http_server_request_duration_seconds: Histogram of request durations
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Response]
    ) -> Response:
        """
        Process a request and record metrics.

        Args:
            request: The incoming HTTP request
            call_next: Function to call the next handler

        Returns:
            The HTTP response
        """
        # Record the start time with high precision
        # perf_counter() is the most accurate timer for measuring durations
        start_time = time.perf_counter()

        # Call the next handler (this runs your route function)
        # Any exception here will propagate up (we don't catch it)
        response = await call_next(request)

        # Calculate how long the request took
        duration = time.perf_counter() - start_time

        # Get the route pattern (not the actual path)
        # This is important for cardinality - see explanation below
        route = self._get_route_pattern(request)

        # Record metrics
        record_http_request(
            method=request.method,
            route=route,
            status_code=response.status_code,
            duration_seconds=duration,
        )

        return response

    def _get_route_pattern(self, request: Request) -> str:
        """
        Extract the route PATTERN from a request, not the actual path.

        WHY PATTERN INSTEAD OF PATH?
        ---------------------------
        Using the actual path creates high cardinality:
          /api/v1/users/123 → one time series
          /api/v1/users/456 → another time series
          /api/v1/users/789 → yet another time series
          ... millions of time series!

        Using the pattern keeps cardinality low:
          /api/v1/users/{user_id} → ONE time series for all user requests

        HOW IT WORKS:
        ------------
        FastAPI/Starlette stores route information on the request.
        We iterate through the app's routes to find which one matched,
        then use its path pattern.

        Args:
            request: The HTTP request

        Returns:
            The route pattern (e.g., "/api/v1/users/{user_id}")
            Falls back to request.url.path if no route matches
        """
        # Try to get the matched route from the request scope
        # Starlette stores routing information in request.scope
        app = request.app

        # Iterate through routes to find the matching one
        for route in app.routes:
            # Check if this route matches the request
            match, _ = route.matches(request.scope)
            if match == Match.FULL:
                # Return the route's path pattern
                return route.path

        # Fallback: if no route matched, use the actual path
        # This happens for 404s or unregistered paths
        return request.url.path
