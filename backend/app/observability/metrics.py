"""
Metrics Collection with OpenTelemetry
=====================================

This module configures application metrics that answer questions about
aggregate behavior:
- "How many requests per second?"
- "What's the 95th percentile latency?"
- "How many errors in the last hour?"

METRICS vs TRACES vs LOGS:
-------------------------

| Telemetry | Question Answered      | Example                           |
|-----------|------------------------|-----------------------------------|
| Traces    | "What happened to      | Request abc123 took 450ms,        |
|           |  THIS request?"        | 350ms was password verification   |
| Logs      | "What events occurred?"| "User login failed: invalid pass" |
| Metrics   | "What's the overall    | "5% of logins fail, p99 latency   |
|           |  system behavior?"     |  is 800ms, 100 req/sec"           |

KEY CONCEPTS:
-------------

1. METER: A named collection of instruments (like a namespace)
   meter = provider.get_meter("http.server")

2. INSTRUMENTS: The actual metric types
   - Counter: Monotonically increasing (requests_total)
   - Histogram: Distribution of values (request_duration)
   - Gauge: Current value (active_connections) - not used here

3. ATTRIBUTES/LABELS: Dimensions to slice data
   counter.add(1, {"method": "POST", "route": "/signin", "status": "200"})

4. METRIC READER: Periodically collects and exports metrics
   - Default: every 60 seconds
   - Aggregates data points between exports

CARDINALITY WARNING:
-------------------
Labels create unique time series. Be careful with high-cardinality labels!

GOOD: method, route, status_code (bounded, known values)
BAD:  user_id, request_id, timestamp (unbounded, millions of values)

High cardinality = memory explosion in your metrics backend!

Example:
  http_requests_total{method="POST", route="/signin"} → ~50 combinations
  http_requests_total{user_id="..."} → millions of combinations! 💥
"""

import logging
from typing import Optional

from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider, Counter, Histogram
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter

logger = logging.getLogger(__name__)

# Module-level state
_meter_provider: Optional[MeterProvider] = None
_http_request_counter: Optional[Counter] = None
_http_request_duration: Optional[Histogram] = None


def setup_metrics(
    service_name: str,
    service_version: str,
    otlp_endpoint: str,
    enabled: bool = True,
    export_interval_millis: int = 60000,
) -> Optional[MeterProvider]:
    """
    Initialize metrics collection for the application.

    This function sets up:
    1. MeterProvider (creates and manages meters)
    2. OTLPMetricExporter (sends to collector)
    3. PeriodicExportingMetricReader (batches exports)
    4. Basic HTTP metrics (counter + histogram)

    Args:
        service_name: Identifies this service in metrics
        service_version: Version for correlation with deployments
        otlp_endpoint: Where to send metrics (e.g., "http://collector:4317")
        enabled: Set to False to disable metrics collection
        export_interval_millis: How often to export (default: 60 seconds)

    Returns:
        The configured MeterProvider, or None if disabled

    Example:
        >>> setup_metrics(
        ...     service_name="rag-admin-backend",
        ...     service_version="0.1.0",
        ...     otlp_endpoint="http://signoz-otel-collector:4317"
        ... )
    """
    global _meter_provider, _http_request_counter, _http_request_duration

    if not enabled:
        logger.info("Metrics collection is disabled via configuration")
        return None

    if _meter_provider is not None:
        logger.warning("Metrics already initialized, skipping")
        return _meter_provider

    logger.info(f"Initializing metrics for service: {service_name}")

    # -------------------------------------------------------------------------
    # Step 1: Create Resource (same as tracing)
    # -------------------------------------------------------------------------
    # The Resource identifies what is generating the metrics.
    # Using the same resource as tracing ensures consistency.

    resource = Resource.create(
        attributes={
            SERVICE_NAME: service_name,
            SERVICE_VERSION: service_version,
        }
    )

    # -------------------------------------------------------------------------
    # Step 2: Create OTLP Metric Exporter
    # -------------------------------------------------------------------------
    # The exporter sends metrics to the OTel Collector.
    # It uses gRPC for efficient binary transfer.

    otlp_exporter = OTLPMetricExporter(
        endpoint=otlp_endpoint,
        insecure=True,  # Set to False and configure TLS in production
    )

    # -------------------------------------------------------------------------
    # Step 3: Create Periodic Metric Reader
    # -------------------------------------------------------------------------
    # The reader collects metrics at regular intervals and sends them.
    #
    # Why periodic instead of immediate?
    # - Reduces network overhead (batch vs single metric)
    # - Allows aggregation (sum values over the interval)
    # - Matches how metrics backends expect data (time-series points)
    #
    # export_interval_millis: How often to export (default 60s)
    # - Lower = more real-time, but more network overhead
    # - Higher = less overhead, but delayed visibility

    metric_reader = PeriodicExportingMetricReader(
        exporter=otlp_exporter,
        export_interval_millis=export_interval_millis,
    )

    # -------------------------------------------------------------------------
    # Step 4: Create MeterProvider
    # -------------------------------------------------------------------------
    # The MeterProvider is the central registry for metrics.
    # It creates Meters (namespaces) which create Instruments (actual metrics).

    _meter_provider = MeterProvider(
        resource=resource,
        metric_readers=[metric_reader],
    )

    # Register as the global MeterProvider
    metrics.set_meter_provider(_meter_provider)

    # -------------------------------------------------------------------------
    # Step 5: Create HTTP Metrics
    # -------------------------------------------------------------------------
    # We pre-create the common HTTP metrics here so they're available
    # immediately when requests come in.

    _create_http_metrics()

    logger.info("Metrics initialized successfully")
    return _meter_provider


def _create_http_metrics() -> None:
    """
    Create standard HTTP server metrics.

    These metrics follow OpenTelemetry semantic conventions for HTTP servers.
    They provide insight into:
    - Request volume (how busy is the server?)
    - Error rates (what percentage of requests fail?)
    - Latency distribution (how fast are we responding?)

    Metrics created:
    ----------------

    1. http_server_requests_total (Counter)
       Counts every HTTP request. Labels allow slicing by:
       - method: GET, POST, PUT, DELETE, etc.
       - route: The URL pattern (e.g., /api/v1/users/{id})
       - status_code: 200, 404, 500, etc.

       Example queries:
       - Total requests: sum(http_server_requests_total)
       - Error rate: sum(status_code=~"5..") / sum(total)
       - Requests by endpoint: group by route

    2. http_server_request_duration_seconds (Histogram)
       Records the duration of each request. Histograms provide:
       - Count: How many requests
       - Sum: Total time spent
       - Buckets: Distribution (how many < 100ms, < 500ms, etc.)

       Example queries:
       - p50 latency: histogram_quantile(0.5, ...)
       - p99 latency: histogram_quantile(0.99, ...)
       - Average: sum / count
    """
    global _http_request_counter, _http_request_duration

    # Get a meter (namespace for HTTP metrics)
    # The name helps organize metrics in the backend
    meter = metrics.get_meter("http.server")

    # -------------------------------------------------------------------------
    # Counter: http_server_requests_total
    # -------------------------------------------------------------------------
    # A counter only goes up (or resets to 0 on restart).
    # Perfect for counting discrete events like requests.
    #
    # The name follows Prometheus naming conventions:
    # - snake_case
    # - suffix _total for counters
    # - descriptive name

    _http_request_counter = meter.create_counter(
        name="http_server_requests_total",
        description="Total number of HTTP requests received",
        unit="requests",
    )

    # -------------------------------------------------------------------------
    # Histogram: http_server_request_duration_seconds
    # -------------------------------------------------------------------------
    # A histogram records the distribution of values.
    # For latency, this lets us compute percentiles (p50, p95, p99).
    #
    # The unit "s" (seconds) is standard for durations.
    # OpenTelemetry will create buckets automatically, or you can customize.
    #
    # Default buckets (in seconds):
    # [0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0]

    _http_request_duration = meter.create_histogram(
        name="http_server_request_duration_seconds",
        description="Duration of HTTP requests in seconds",
        unit="s",
    )

    logger.debug("HTTP metrics instruments created")


def record_http_request(
    method: str,
    route: str,
    status_code: int,
    duration_seconds: float,
) -> None:
    """
    Record metrics for an HTTP request.

    Call this at the end of each request to record:
    - Increment the request counter
    - Record the duration in the histogram

    This is typically called from middleware that wraps all requests.

    Args:
        method: HTTP method (GET, POST, etc.)
        route: URL route pattern (e.g., /api/v1/users/{id})
        status_code: HTTP response status code
        duration_seconds: How long the request took (in seconds)

    Example:
        >>> import time
        >>> start = time.perf_counter()
        >>> # ... handle request ...
        >>> duration = time.perf_counter() - start
        >>> record_http_request(
        ...     method="POST",
        ...     route="/api/v1/auth/signin",
        ...     status_code=200,
        ...     duration_seconds=duration
        ... )

    IMPORTANT - Attribute Cardinality:
    ---------------------------------
    We use route (the pattern) not path (the actual URL) because:

    GOOD: route="/api/v1/users/{id}"
          Creates ONE time series for all user requests

    BAD:  path="/api/v1/users/123", "/api/v1/users/456", ...
          Creates THOUSANDS of time series (one per user!)

    High cardinality = memory problems in your metrics backend.
    """
    # Define attributes (labels) for this data point
    # These let you filter and group in queries
    attributes = {
        "http.request.method": method,
        "http.route": route,
        "http.response.status_code": str(status_code),
    }

    # Record the request count
    if _http_request_counter is not None:
        _http_request_counter.add(1, attributes)

    # Record the duration
    if _http_request_duration is not None:
        _http_request_duration.record(duration_seconds, attributes)


def get_meter(name: str):
    """
    Get a meter for creating custom metrics.

    Use this to create application-specific metrics beyond HTTP.

    Example - Business metrics:
    ```python
    from app.observability.metrics import get_meter

    meter = get_meter("auth")

    # Counter for auth events
    signups_counter = meter.create_counter(
        name="auth_signups_total",
        description="Total user signups",
    )

    # Record a signup
    signups_counter.add(1, {"provider": "email"})
    ```

    Example - Performance metrics:
    ```python
    meter = get_meter("database")

    query_duration = meter.create_histogram(
        name="db_query_duration_seconds",
        description="Database query duration",
        unit="s",
    )

    # Record query time
    query_duration.record(0.045, {"operation": "SELECT", "table": "users"})
    ```

    Args:
        name: Meter name (namespace for your metrics)

    Returns:
        A Meter instance for creating instruments
    """
    return metrics.get_meter(name)


def shutdown_metrics() -> None:
    """
    Gracefully shutdown metrics collection.

    This ensures all pending metrics are exported before the application exits.
    Without this, the last export interval's data might be lost.

    Call this during application shutdown.
    """
    global _meter_provider

    if _meter_provider is not None:
        _meter_provider.shutdown()
        _meter_provider = None
        logger.info("Metrics shutdown complete")
