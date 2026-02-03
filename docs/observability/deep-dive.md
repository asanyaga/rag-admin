# OpenTelemetry Deep Dive

This document provides in-depth educational content about how observability works in RAG Admin.

---

## Table of Contents

- [Core Concepts](#core-concepts)
- [Architecture](#architecture)
- [Distributed Tracing Explained](#distributed-tracing-explained)
- [Auto-Instrumentation Deep Dive](#auto-instrumentation-deep-dive)
- [Context Propagation](#context-propagation)
- [Structured Logging](#structured-logging)
- [Metrics](#metrics)
- [Best Practices](#best-practices)
- [Common Pitfalls](#common-pitfalls)

---

## Core Concepts

### What is Observability?

Observability is the ability to understand the internal state of your system by examining its outputs. It consists of three pillars:

1. **Traces**: The journey of a single request through your system
2. **Logs**: Discrete events that happened
3. **Metrics**: Aggregate measurements over time

### Why OpenTelemetry?

OpenTelemetry is:
- **Vendor-neutral**: Works with any observability backend (SigNoz, Jaeger, Datadog, etc.)
- **Standardized**: Consistent APIs across languages
- **Comprehensive**: Covers traces, logs, and metrics
- **Active**: Major contributors from Google, Microsoft, Amazon, Splunk, etc.

---

## Architecture

### The OpenTelemetry Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                        Your Application                          │
│                                                                   │
│  ┌──────────────────┐         ┌──────────────────┐             │
│  │ Auto-Instrument  │         │ Manual Spans     │             │
│  │ - FastAPI        │         │ - Business logic │             │
│  │ - SQLAlchemy     │         │ - Custom metrics │             │
│  │ - httpx          │         └────────┬─────────┘             │
│  └────────┬─────────┘                  │                       │
│           │                            │                       │
│           ▼                            ▼                       │
│      ┌─────────────────────────────────────────┐              │
│      │        TracerProvider / MeterProvider    │              │
│      │  - Resource (service.name, version)     │              │
│      │  - Processors (batch, filter)           │              │
│      └──────────────────┬──────────────────────┘              │
│                         │                                       │
└─────────────────────────┼───────────────────────────────────────┘
                          │
                          ▼
             ┌────────────────────────┐
             │   OTLP Exporter        │
             │   (gRPC port 4317)     │
             └───────────┬────────────┘
                         │
                         ▼
             ┌────────────────────────┐
             │  OTel Collector        │
             │  - Receives telemetry  │
             │  - Transforms          │
             │  - Routes to backends  │
             └───────────┬────────────┘
                         │
                         ▼
             ┌────────────────────────┐
             │   SigNoz / ClickHouse  │
             │   - Stores telemetry   │
             │   - Powers UI/queries  │
             └────────────────────────┘
```

### Key Components

#### TracerProvider

The central component that:
- Creates `Tracer` instances for your modules
- Manages span lifecycle
- Routes completed spans to processors
- Attaches resource information to all spans

Think of it as a factory: you ask for a `Tracer`, and it gives you one configured with your service name and exporters.

#### SpanProcessor

Sits between span creation and export. Types:

**BatchSpanProcessor** (recommended for production):
```python
# Batches spans for efficiency
# Default settings:
span_processor = BatchSpanProcessor(
    exporter,
    max_queue_size=2048,        # Spans buffered in memory
    schedule_delay_millis=5000,  # Export every 5 seconds
    max_export_batch_size=512,   # Spans per batch
    export_timeout_millis=30000  # Timeout for export
)
```

Benefits:
- Reduces network overhead (batch vs single span)
- Non-blocking (your code doesn't wait for export)
- Handles retries if collector is down

**SimpleSpanProcessor** (useful for debugging):
```python
# Exports immediately, blocks until complete
# Only use for debugging - will slow down your app!
span_processor = SimpleSpanProcessor(exporter)
```

#### Resource

Describes **what** is generating telemetry:

```python
resource = Resource.create(
    attributes={
        SERVICE_NAME: "rag-admin-backend",
        SERVICE_VERSION: "0.1.0",
        "deployment.environment": "production",
        "host.name": socket.gethostname(),
    }
)
```

These attributes appear on **every span**, making it easy to filter:
- "Show me all traces from rag-admin-backend"
- "Show me production traces only"
- "Show me traces from host-03"

---

## Distributed Tracing Explained

### What is a Trace?

A **trace** represents the complete journey of a request through your system.

Example: User signs in

```
Trace ID: a1b2c3d4e5f6...

Span 1: POST /api/v1/auth/signin (450ms total)
  │
  ├─ Span 2: SELECT * FROM users WHERE email = ? (50ms)
  │
  ├─ Span 3: verify_password (350ms)
  │   └─ Span 4: bcrypt.verify (349ms)
  │
  └─ Span 5: INSERT INTO refresh_tokens (50ms)
```

Each span has:
- **Span ID**: Unique identifier for this operation
- **Trace ID**: Links all spans in this request
- **Parent Span ID**: Creates the tree structure
- **Start/End Time**: Duration of operation
- **Attributes**: Key-value metadata
- **Status**: OK, ERROR, UNSET
- **Events**: Timestamped log entries within the span
- **Links**: Connections to other traces (advanced)

### How Spans are Created

#### Auto-Instrumentation (FastAPI)

When a request arrives:

```python
# FastAPI instrumentor adds middleware that does:
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

async def middleware(request, call_next):
    # Start a span for the HTTP request
    with tracer.start_as_current_span(
        f"{request.method} {request.url.path}",
        kind=SpanKind.SERVER
    ) as span:
        # Set attributes from the request
        span.set_attribute("http.method", request.method)
        span.set_attribute("http.url", str(request.url))
        span.set_attribute("http.scheme", request.url.scheme)

        # Process the request
        response = await call_next(request)

        # Set attributes from the response
        span.set_attribute("http.status_code", response.status_code)

        # Automatically set span status based on HTTP status
        if response.status_code >= 400:
            span.set_status(Status(StatusCode.ERROR))

        return response
```

#### Manual Instrumentation

For custom business logic:

```python
from app.observability import get_tracer

tracer = get_tracer(__name__)

def authenticate_user(email: str, password: str):
    # Create a span for this operation
    with tracer.start_as_current_span("authenticate_user") as span:
        # Add context
        span.set_attribute("auth.email", email)
        span.set_attribute("auth.method", "email_password")

        # Your logic
        user = get_user_by_email(email)
        if not user:
            span.set_status(Status(StatusCode.ERROR, "User not found"))
            span.set_attribute("auth.success", False)
            raise UserNotFoundError()

        # Nested span for expensive operation
        with tracer.start_as_current_span("verify_password") as pwd_span:
            pwd_span.set_attribute("crypto.algorithm", "bcrypt")
            is_valid = bcrypt.verify(password, user.hashed_password)
            pwd_span.set_attribute("auth.password_valid", is_valid)

        if not is_valid:
            span.set_status(Status(StatusCode.ERROR, "Invalid password"))
            span.set_attribute("auth.success", False)
            raise InvalidPasswordError()

        span.set_attribute("auth.success", True)
        span.set_attribute("user.id", user.id)
        return user
```

This creates a span hierarchy:

```
POST /api/v1/auth/signin
└── authenticate_user
    ├── SELECT * FROM users... (auto from SQLAlchemy)
    └── verify_password
```

---

## Auto-Instrumentation Deep Dive

### How FastAPI Instrumentation Works

The `FastAPIInstrumentor` wraps your FastAPI app with OpenTelemetry middleware:

```python
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

# This is what happens internally:
FastAPIInstrumentor.instrument_app(app)

# Equivalent to:
app.add_middleware(
    OpenTelemetryMiddleware,
    excluded_urls=...,
    tracer_provider=trace.get_tracer_provider()
)
```

The middleware:
1. Intercepts every incoming request
2. Extracts trace context from headers (if present)
3. Starts a new span (or continues existing trace)
4. Calls your route handler
5. Captures response details
6. Ends the span
7. Exports to collector (batched)

### Why Module-Level Instrumentation?

**CRITICAL**: FastAPI builds its middleware stack when uvicorn starts. The startup event fires **after** the stack is built.

```python
# ❌ BROKEN: Startup event is too late
app = FastAPI()

@app.on_event("startup")
def startup():
    FastAPIInstrumentor.instrument_app(app)  # TOO LATE!

# Middleware stack already built, instrumentation bypassed


# ✅ CORRECT: Module-level instrumentation
app = FastAPI()
FastAPIInstrumentor.instrument_app(app)  # Before uvicorn starts

# Middleware stack includes OpenTelemetry
```

### SQLAlchemy Instrumentation

Unlike FastAPI (middleware-based), SQLAlchemy uses event listeners:

```python
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

# Instruments the engine with event hooks
SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)

# Now every query triggers:
@event.listens_for(Engine, "before_cursor_execute")
def receive_before_cursor_execute(conn, cursor, statement, params, ...):
    # Start a span for this query
    tracer = trace.get_tracer(__name__)
    span = tracer.start_span(
        "db.query",
        kind=SpanKind.CLIENT
    )
    span.set_attribute("db.statement", statement)
    span.set_attribute("db.system", "postgresql")
    # Store span in context for after_cursor_execute

@event.listens_for(Engine, "after_cursor_execute")
def receive_after_cursor_execute(conn, cursor, statement, params, ...):
    # End the span
    span.end()
```

### httpx Instrumentation

Instruments the httpx client globally:

```python
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

HTTPXClientInstrumentor().instrument()

# Now every httpx request automatically:
# 1. Creates a span
# 2. Adds traceparent header (propagates trace context)
# 3. Records duration, status, URL
```

This is crucial for **distributed tracing across services**.

---

## Context Propagation

### The Problem

How do you link spans across different services?

```
Frontend ──► Backend ──► Auth Service
            How does Auth Service know it's part of the same trace?
```

### The Solution: W3C Trace Context

OpenTelemetry uses the W3C standard `traceparent` header:

```
traceparent: 00-{trace-id}-{parent-span-id}-{flags}
```

Example:
```
traceparent: 00-a1b2c3d4e5f6...789-0123456789abcdef-01
             │  └──────────┬───────┘ └───────┬──────┘ │
             │        Trace ID          Span ID    Sampled
          Version
```

### How It Works

**Request flow:**

1. **Frontend** makes request to backend:
   ```http
   POST /api/v1/auth/signin HTTP/1.1
   Host: backend.example.com
   traceparent: 00-a1b2c3d4...-0123456789abcdef-01
   ```

2. **Backend** extracts trace context:
   ```python
   # FastAPI instrumentor does this automatically:
   from opentelemetry.propagate import extract

   context = extract(request.headers)
   # Context now contains trace_id and parent_span_id
   ```

3. **Backend** creates child span:
   ```python
   with tracer.start_as_current_span("process_signin", context=context):
       # This span has:
       # - Same trace_id as frontend (a1b2c3d4...)
       # - Parent is frontend's span (0123456789abcdef)
       # - New span_id (generated)
   ```

4. **Backend** calls external API:
   ```python
   # httpx instrumentor injects trace context
   response = httpx.post(
       "https://oauth.google.com/token",
       # Automatically adds header:
       # traceparent: 00-a1b2c3d4...-{backend-span-id}-01
   )
   ```

5. **Result**: Single trace spans multiple services:
   ```
   Trace ID: a1b2c3d4...

   Frontend: Click sign-in button (800ms)
   └── Backend: POST /api/v1/auth/signin (750ms)
       └── Google OAuth: POST /token (600ms)
   ```

---

## Structured Logging

### Why Structured Logging?

Traditional logs are unstructured text:

```
2024-01-29 10:15:32 INFO User test@example.com logged in successfully
```

Problems:
- Hard to query: "Show me all failed login attempts"
- No correlation: Which request caused this log?
- Lost context: What was the user_id? What was the IP?

Structured logs are JSON with fields:

```json
{
  "timestamp": "2024-01-29T10:15:32.123456Z",
  "level": "INFO",
  "message": "User login successful",
  "logger": "app.services.auth",
  "trace_id": "a1b2c3d4e5f6...",
  "span_id": "0123456789abcdef",
  "user_email": "test@example.com",
  "user_id": "123",
  "ip_address": "192.168.1.1"
}
```

Benefits:
- **Query**: `WHERE user_email = 'test@example.com' AND level = 'ERROR'`
- **Correlate**: Click `trace_id` to see full request journey
- **Analyze**: Count logins per hour, error rate by endpoint

### Trace Correlation in Practice

Every log automatically includes `trace_id` and `span_id`:

```python
import logging
logger = logging.getLogger(__name__)

# In your request handler:
logger.info("User login successful", extra={"user_email": email})

# Output includes trace context automatically:
# {
#   "trace_id": "a1b2c3d4...",  ← Added by TraceContextFilter
#   "span_id": "0123456...",     ← Added by TraceContextFilter
#   "user_email": "test@...",    ← From your extra={}
#   ...
# }
```

In SigNoz:
1. View a trace
2. See a span for "process_signin"
3. Click "Logs" tab
4. See all logs with matching `trace_id`

---

## Metrics

### Types of Metrics

#### Counter
Monotonically increasing value (or resets to 0):

```python
# Count total HTTP requests
http_requests_total.add(1, {"method": "POST", "route": "/signin"})

# Good for: Totals, rates
# Query: rate(http_requests_total[5m])  # Requests per second
```

#### Histogram
Distribution of values:

```python
# Record request duration
http_request_duration.record(0.450, {"method": "POST", "route": "/signin"})

# Internally creates buckets:
# < 0.1s: 1000 requests
# < 0.5s: 5000 requests
# < 1.0s: 6000 requests

# Good for: Latency, size distributions
# Query: histogram_quantile(0.99, http_request_duration)  # p99 latency
```

#### Gauge
Current value (can go up or down):

```python
# Track active connections
active_connections.set(42)

# Good for: Resource usage, queue depth
# Query: active_connections  # Current value
```

### Cardinality Warning

Labels create unique time series:

```python
# ✅ GOOD: Bounded cardinality (~50 time series)
counter.add(1, {
    "method": "POST",      # 7 values (GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS)
    "route": "/signin",    # ~10 routes in your app
    "status": "200"        # ~10 status codes
})
# Total: 7 × 10 × 10 = 700 time series

# ❌ BAD: Unbounded cardinality (millions of time series!)
counter.add(1, {
    "user_id": "12345",    # Every user creates a new time series
    "request_id": "abc",   # Every request creates a new time series
})
# Total: millions of users × millions of requests = 💥 memory explosion
```

High cardinality = metrics backend runs out of memory.

**Rule of thumb**: If a label has >100 possible values, it's probably too high cardinality.

---

## Best Practices

### Span Naming

**Good**:
- `GET /api/v1/users`  (HTTP requests)
- `SELECT users`  (Database operations)
- `authenticate_user`  (Business logic)
- `send_email`  (External calls)

**Bad**:
- `GET /api/v1/users/12345`  (includes variable, high cardinality)
- `process`  (too vague)
- `function_1`  (not descriptive)

### Span Attributes

Use semantic conventions where possible: https://opentelemetry.io/docs/specs/semconv/

**HTTP**:
```python
span.set_attribute("http.method", "POST")
span.set_attribute("http.route", "/api/v1/users")
span.set_attribute("http.status_code", 200)
span.set_attribute("http.url", "https://example.com/api/v1/users")
```

**Database**:
```python
span.set_attribute("db.system", "postgresql")
span.set_attribute("db.name", "ragadmin")
span.set_attribute("db.operation", "SELECT")
span.set_attribute("db.statement", "SELECT * FROM users WHERE id = ?")
```

**Custom**:
```python
span.set_attribute("user.id", "12345")
span.set_attribute("auth.method", "email_password")
span.set_attribute("business.transaction_amount", 99.99)
```

### Error Handling

Always record errors in spans:

```python
try:
    result = risky_operation()
except Exception as e:
    # Record the exception
    span.record_exception(e)

    # Set span status to ERROR
    span.set_status(Status(StatusCode.ERROR, str(e)))

    # Re-raise to propagate
    raise
```

### Sampling

For high-traffic applications, sample traces:

```python
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

# Sample 10% of traces
sampler = TraceIdRatioBased(0.1)

provider = TracerProvider(
    resource=resource,
    sampler=sampler
)
```

When to use:
- **1.0 (100%)**: Development, low traffic (<100 req/s)
- **0.1 (10%)**: Production, medium traffic (100-1000 req/s)
- **0.01 (1%)**: High traffic (>1000 req/s)

---

## Common Pitfalls

### 1. Forgetting to End Spans

```python
# ❌ BAD: Manual span that might not end
span = tracer.start_span("operation")
result = do_something()
span.end()  # What if do_something() raises exception?

# ✅ GOOD: Use context manager
with tracer.start_as_current_span("operation"):
    result = do_something()
# Span ends automatically, even on exception
```

### 2. High Cardinality Attributes

```python
# ❌ BAD: Every user creates unique span name
with tracer.start_as_current_span(f"process_user_{user_id}"):
    ...

# ✅ GOOD: Use attributes for variable data
with tracer.start_as_current_span("process_user") as span:
    span.set_attribute("user.id", user_id)
```

### 3. Blocking on Export

```python
# ❌ BAD: Every span blocks until exported
processor = SimpleSpanProcessor(exporter)

# ✅ GOOD: Batch exports in background
processor = BatchSpanProcessor(exporter)
```

### 4. Not Propagating Context

```python
# ❌ BAD: Starts a new trace instead of continuing
async def background_task():
    with tracer.start_as_current_span("background"):
        ...  # This is a root span, disconnected from parent

# ✅ GOOD: Pass context to background task
from opentelemetry import context

async def api_handler():
    ctx = context.get_current()
    asyncio.create_task(background_task(ctx))

async def background_task(ctx):
    with tracer.start_as_current_span("background", context=ctx):
        ...  # This is a child of the original request span
```

### 5. Over-Instrumenting

```python
# ❌ BAD: Too many tiny spans
with tracer.start_as_current_span("validate_email"):  # 0.001ms
    if "@" not in email:
        raise ValueError()

with tracer.start_as_current_span("check_length"):  # 0.001ms
    if len(email) < 3:
        raise ValueError()

# ✅ GOOD: One span for the whole operation
with tracer.start_as_current_span("validate_input"):  # 0.002ms
    validate_email(email)
    validate_password(password)
```

Only create spans for operations that:
- Take >10ms
- Are interesting for debugging (DB queries, external calls)
- Represent logical units (authenticate_user, process_payment)

---

## Further Reading

- [OpenTelemetry Python Documentation](https://opentelemetry.io/docs/instrumentation/python/)
- [W3C Trace Context Specification](https://www.w3.org/TR/trace-context/)
- [Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/)
- [SigNoz Documentation](https://signoz.io/docs/)
