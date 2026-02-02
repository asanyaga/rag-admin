# Observability PRD & TRD: RAG Admin Application

## Document Overview

This document contains both the **Product Requirements Document (PRD)** and **Technical Requirements Document (TRD)** for implementing observability across the RAG Admin application stack.

---

# Part 1: Product Requirements Document (PRD)

## 1.1 Executive Summary

**Goal:** Implement comprehensive observability (structured logging, distributed tracing, and metrics) across the RAG Admin application to enable debugging, performance monitoring, proactive alerting, and operational visibility.

**Approach:** Phased implementation using OpenTelemetry (OTel) standards with SigNoz as the observability backend, deployed alongside the existing application stack.

## 1.2 Problem Statement

| Problem | Impact |
|---------|--------|
| No visibility into production errors | Difficult to debug issues when users report problems |
| No performance metrics | Can't identify slow endpoints or bottlenecks |
| No proactive monitoring | Issues discovered only when users complain |
| No structured logging | Hard to search and correlate log events |

## 1.3 Success Criteria

| Metric | Target |
|--------|--------|
| Mean Time to Detection (MTTD) | < 5 minutes for critical errors |
| Mean Time to Resolution (MTTR) | 50% improvement from baseline |
| Trace coverage | 100% of HTTP requests traced |
| Log correlation | 100% of logs include trace_id |
| Alert false positive rate | < 10% |

## 1.4 User Stories

**As a developer, I want to:**
- See the full journey of a request through the system so I can identify bottlenecks
- Search logs by error type, user, or time range so I can debug issues quickly
- View dashboards showing request rates and error rates so I understand system health
- Receive alerts when error rates spike so I can respond proactively

**As a team member, I want to:**
- Access observability dashboards with my own credentials
- Understand what happened during an incident by viewing correlated logs and traces

## 1.5 Scope

### In Scope (This Project)
- Backend structured logging with trace correlation
- Distributed tracing for all HTTP requests and database queries
- Application metrics (request rate, latency, errors)
- Business metrics (auth events, user activity)
- Basic frontend error capture
- Alerting for critical conditions
- Team access via secured UI

### Out of Scope (Future)
- Full Real User Monitoring (RUM) with Web Vitals
- Synthetic monitoring / uptime checks
- Log analytics and anomaly detection
- Multi-region deployment considerations

## 1.6 Phased Delivery Plan

| Phase | Duration | Deliverables |
|-------|----------|--------------|
| **Phase 1: Foundation** | Days 1-3 | Basic tracing, logging, metrics working end-to-end |
| **Phase 2: Enhancement** | Days 4-7 | Custom instrumentation, business metrics, frontend errors |
| **Phase 3: Production-Ready** | Days 8-14 | Alerting, retention, security, dashboards |
| **Phase 4: Advanced** | Future | Full frontend RUM, synthetic monitoring |

---

# Part 2: Technical Requirements Document (TRD)

## 2.1 OpenTelemetry Concepts (Educational Reference)

### The Three Pillars of Observability

```
┌─────────────────────────────────────────────────────────────────┐
│                    OBSERVABILITY                                 │
├─────────────────┬─────────────────┬─────────────────────────────┤
│     LOGS        │    METRICS      │         TRACES              │
│                 │                 │                             │
│  "What happened"│ "How much/many" │  "The request journey"      │
│                 │                 │                             │
│  • Timestamps   │  • Counters     │  • Spans (units of work)    │
│  • Log levels   │  • Gauges       │  • Parent-child relations   │
│  • Messages     │  • Histograms   │  • Timing data              │
│  • Context      │  • Labels       │  • Attributes               │
└─────────────────┴─────────────────┴─────────────────────────────┘
```

### Key OTel Terminology

| Term | Definition | Example |
|------|------------|---------|
| **Trace** | Complete journey of a request | User login from click to response |
| **Span** | Single unit of work within a trace | "Query user from database" |
| **Trace ID** | Unique ID linking all spans in a request | `a1b2c3d4e5f6...` |
| **Span ID** | Unique ID for one span | `7890abcd...` |
| **Attributes** | Key-value metadata on spans | `user.email: "test@example.com"` |
| **Resource** | Describes the service | `service.name: "rag-admin-backend"` |
| **Exporter** | Sends telemetry to a backend | OTLP exporter to SigNoz |

### Trace Anatomy

```
Trace ID: abc123...
│
├── Span: HTTP POST /api/v1/auth/signin (500ms)
│   ├── Attributes: http.method=POST, http.route=/api/v1/auth/signin
│   │
│   ├── Span: authenticate_user (450ms)
│   │   ├── Attributes: user.email=test@example.com
│   │   │
│   │   ├── Span: SELECT user FROM users (50ms)
│   │   │   └── Attributes: db.system=postgresql, db.operation=SELECT
│   │   │
│   │   ├── Span: verify_password (300ms)
│   │   │   └── Attributes: auth.method=bcrypt
│   │   │
│   │   └── Span: INSERT refresh_token (80ms)
│   │       └── Attributes: db.system=postgresql, db.operation=INSERT
│   │
│   └── Span: serialize_response (20ms)
```

### Structured Log Example

```json
{
  "timestamp": "2024-01-29T10:15:32.123Z",
  "level": "info",
  "message": "User authentication successful",
  "service": "rag-admin-backend",
  "trace_id": "abc123...",
  "span_id": "def456...",
  "user_email": "test@example.com",
  "auth_method": "password",
  "response_time_ms": 500,
  "endpoint": "/api/v1/auth/signin"
}
```

**Why this matters:** With trace_id in logs, you can click a log entry in SigNoz and immediately see the full trace showing exactly what happened during that request.

## 2.2 Stack Selection

### Options Evaluated

| Stack | Components | RAM Usage | Pros | Cons |
|-------|------------|-----------|------|------|
| **Grafana LGTM** | Loki + Tempo + Prometheus + Grafana | ~1.3GB | Industry standard, flexible | 5 services, complex config |
| **Classic** | ELK + Jaeger + Prometheus | ~2GB+ | Mature, great Jaeger UI | Resource heavy, no correlation |
| **SigNoz** | All-in-one + ClickHouse | ~1.2-1.6GB | OTel-native, unified UI, simple | Smaller community |

### Recommendation: SigNoz

**Why SigNoz fits your requirements:**

1. **OTel-Native:** Built on OpenTelemetry from the ground up. Your instrumentation code is 100% standard and transferable to any OTel-compatible backend.

2. **Learning-Friendly:** Single unified UI means you learn observability concepts, not tool-specific quirks. See logs, traces, and metrics in one place with built-in correlation.

3. **Resource-Efficient:** At ~1.2-1.6GB, fits comfortably on your 4-8GB VPS alongside the application.

4. **Alerting Built-in:** No need to add AlertManager separately.

5. **Growth Path:** When you outgrow SigNoz, your OTel instrumentation works unchanged with Grafana, Datadog, or any other backend.

## 2.3 Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Your VPS (4-8GB RAM)                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────┐     ┌─────────────────┐     ┌─────────────────────┐   │
│  │ Browser │────▶│      Caddy      │────▶│  FastAPI Backend    │   │
│  │(React)  │     │ (reverse proxy) │     │  (OTel instrumented)│   │
│  └────┬────┘     └─────────────────┘     └──────────┬──────────┘   │
│       │                                             │              │
│       │ JS errors                                   │ OTLP        │
│       │                                             ▼              │
│       │          ┌─────────────────────────────────────────────┐   │
│       └─────────▶│           SigNoz OTel Collector             │   │
│                  │  (receives logs, traces, metrics via OTLP)  │   │
│                  └──────────────────┬──────────────────────────┘   │
│                                     │                              │
│                                     ▼                              │
│                  ┌─────────────────────────────────────────────┐   │
│                  │              ClickHouse                      │   │
│                  │     (stores all observability data)          │   │
│                  └──────────────────┬──────────────────────────┘   │
│                                     │                              │
│                                     ▼                              │
│                  ┌─────────────────────────────────────────────┐   │
│                  │         SigNoz Query Service                 │   │
│                  │    (API + Web UI on port 3301)               │   │
│                  └─────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────┐                                               │
│  │   PostgreSQL    │ ◀── SQLAlchemy queries traced automatically  │
│  └─────────────────┘                                               │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## 2.4 Resource Budget

| Component | Min RAM | Recommended | Max RAM |
|-----------|---------|-------------|---------|
| **Application** ||||
| PostgreSQL | 256MB | 512MB | 1GB |
| FastAPI Backend | 128MB | 256MB | 512MB |
| Caddy | 32MB | 64MB | 128MB |
| **Observability** ||||
| SigNoz Query Service | 256MB | 512MB | 768MB |
| SigNoz OTel Collector | 128MB | 256MB | 512MB |
| ClickHouse | 512MB | 768MB | 1GB |
| **System** ||||
| OS + buffers | 512MB | 1GB | 1.5GB |
| **Total** | ~1.8GB | ~3.4GB | ~5.4GB |

**Verdict:** 8GB is comfortable. 4GB is tight but workable with memory limits.

## 2.5 Data Retention Policy

| Data Type | Retention | Rationale |
|-----------|-----------|-----------|
| **Traces** | 3 days | High cardinality, large volume; old traces rarely useful |
| **Logs** | 7 days | Useful for debugging recent issues |
| **Metrics** | 30 days | Lower volume, good for trend analysis |

---

# Part 3: Implementation Plan

## Phase 1: Foundation (Days 1-3)

**Goal:** Minimal viable observability - all three pillars working with auto-instrumentation.

### What You'll Learn
- How OTel auto-instrumentation works (zero-code tracing)
- What spans and traces look like in practice
- How structured logs connect to traces via trace_id
- Basic metric types (counters, histograms)

### Step 1.1: Add SigNoz to Docker Compose

**Create:** `docker-compose.observability.yml`

Services to add:
- `clickhouse` - Time-series database for storing telemetry
- `signoz-otel-collector` - Receives telemetry via OTLP protocol
- `signoz-query-service` - API and Web UI

### Step 1.2: Backend OTel Dependencies

**Modify:** `backend/pyproject.toml`

```toml
# Add to dependencies:
opentelemetry-api = "^1.20.0"
opentelemetry-sdk = "^1.20.0"
opentelemetry-instrumentation-fastapi = "^0.41b0"
opentelemetry-instrumentation-sqlalchemy = "^0.41b0"
opentelemetry-instrumentation-httpx = "^0.41b0"
opentelemetry-exporter-otlp = "^1.20.0"
python-json-logger = "^2.0.7"
```

### Step 1.3: Create Observability Module

**Create:** `backend/app/observability/` directory with:

| File | Purpose |
|------|---------|
| `__init__.py` | Module initialization, main setup function |
| `tracing.py` | TracerProvider, OTLP exporter, auto-instrumentors |
| `logging.py` | JSON formatter, trace context injection |
| `metrics.py` | MeterProvider, basic HTTP metrics |

### Step 1.4: Initialize on Startup

**Modify:** `backend/app/main.py`

```python
# Add to app startup:
from app.observability import setup_observability

@app.on_event("startup")
async def startup_event():
    setup_observability()  # Initialize OTel before handling requests
    # ... existing startup code
```

### Step 1.5: Configuration

**Modify:** `backend/app/config.py`

```python
# Add settings:
OTEL_ENABLED: bool = True
OTEL_EXPORTER_ENDPOINT: str = "http://signoz-otel-collector:4317"
OTEL_SERVICE_NAME: str = "rag-admin-backend"
LOG_LEVEL: str = "INFO"
LOG_FORMAT: str = "json"  # or "text" for local dev
```

### Step 1.6: Trace Propagation

**Modify:** `caddy/Caddyfile`

```
# Add to reverse_proxy block:
header_up traceparent {header.traceparent}
header_up tracestate {header.tracestate}
```

### Phase 1 Verification
- [ ] SigNoz UI accessible at `http://localhost:3301`
- [ ] Make API request → trace appears in SigNoz
- [ ] Trace shows FastAPI span + SQLAlchemy child spans
- [ ] Logs in Docker have JSON format with trace_id
- [ ] Basic request metrics visible in SigNoz

---

## Phase 2: Enhancement (Days 4-7)

**Goal:** Custom instrumentation, business metrics, basic frontend error capture.

### What You'll Learn
- How to create custom spans for business logic
- How to add meaningful attributes to spans
- How to define business-relevant metrics
- Basics of frontend error tracking

### Step 2.1: Custom Spans for Auth Flows

**Modify:** `backend/app/services/auth_service.py`

Add custom spans for:
- `sign_up` operation (with user email, provider)
- `sign_in` operation (with success/failure, duration)
- `password_verification` (timing-sensitive)
- `token_refresh` (security-relevant)

### Step 2.2: Business Metrics

**Create:** `backend/app/observability/business_metrics.py`

```python
# Counters:
auth_signups_total         # labels: provider
auth_signins_total         # labels: provider, success
auth_failures_total        # labels: reason

# Histograms:
auth_signin_duration_seconds
db_query_duration_seconds  # labels: operation, table

# Gauges:
active_sessions_count
```

### Step 2.3: Exception Tracking

**Create:** `backend/app/middleware/exception_handler.py`

- Catch unhandled exceptions
- Record exception in current span (sets span status to ERROR)
- Log structured error with stack trace
- Increment error counter metric

### Step 2.4: Frontend Error Capture

**Create:** `frontend/src/observability/errorReporter.ts`

- Global `window.onerror` handler
- Global `window.onunhandledrejection` handler
- Batch errors and send to backend

**Create:** `frontend/src/observability/ErrorBoundary.tsx`

- React error boundary component
- Catches render errors
- Reports to backend with component stack

**Create:** `backend/app/routers/errors.py`

- `POST /api/v1/errors` endpoint
- Receives frontend errors
- Logs with trace correlation when available

### Phase 2 Verification
- [ ] Custom auth spans appear in traces with attributes
- [ ] Business metrics queryable (e.g., `auth_signins_total`)
- [ ] Frontend JS error → appears in backend logs
- [ ] Exception stack traces visible in span events

---

## Phase 3: Production-Ready (Days 8-14)

**Goal:** Alerting, retention, security, and dashboards.

### What You'll Learn
- How to set up meaningful alerts
- Avoiding alert fatigue
- Data lifecycle management
- Securing observability endpoints

### Step 3.1: Alerting Rules

**Create:** `observability/alerts/rules.yaml`

**Critical Alerts (immediate notification):**
1. Service down - backend health check fails for 2 minutes
2. Error rate spike - >5% 5xx responses in 5 minutes
3. Database connection failures

**Warning Alerts (review during business hours):**
4. High latency - p95 > 2 seconds for 10 minutes
5. Auth failure spike - >10 failures/minute
6. Disk space low on observability volume

### Step 3.2: Notification Channels

Configure in SigNoz UI:
- Email (primary)
- Slack webhook (optional)

### Step 3.3: Retention Configuration

Configure ClickHouse TTL:
```sql
-- Traces: 3 days
-- Logs: 7 days
-- Metrics: 30 days with downsampling after 7 days
```

### Step 3.4: Secure Access

**Modify:** `caddy/Caddyfile`

Add subdomain for SigNoz with basic auth:
```
signoz.yourdomain.com {
    basicauth {
        admin $2a$14$...
        dev1 $2a$14$...
    }
    reverse_proxy signoz-query-service:3301
}
```

### Step 3.5: Dashboards

Create in SigNoz:
1. **Service Overview** - Request rate, error rate, latency percentiles
2. **Authentication** - Sign-ups, sign-ins, failures by reason
3. **Infrastructure** - Database connections, response times by endpoint

### Phase 3 Verification
- [ ] Trigger test alert → notification received
- [ ] Data older than retention period is deleted
- [ ] Team can access SigNoz via secured subdomain
- [ ] Dashboards show real-time data

---

## Phase 4: Advanced (Future)

**Goal:** Full frontend RUM, synthetic monitoring.

### Future Enhancements
- Full OpenTelemetry browser SDK with Web Vitals (LCP, FID, CLS)
- User session tracking and replay
- Synthetic monitoring (scheduled health checks)
- Log anomaly detection
- SLO tracking and error budgets

---

# Part 4: Files to Create/Modify

## New Files

| Path | Purpose |
|------|---------|
| `docker-compose.observability.yml` | SigNoz stack definition |
| `backend/app/observability/__init__.py` | OTel setup orchestration |
| `backend/app/observability/tracing.py` | Tracer configuration |
| `backend/app/observability/logging.py` | Structured JSON logging |
| `backend/app/observability/metrics.py` | Metrics configuration |
| `backend/app/observability/business_metrics.py` | App-specific metrics |
| `backend/app/middleware/request_context.py` | Request ID middleware |
| `backend/app/middleware/exception_handler.py` | Global exception handler |
| `backend/app/routers/errors.py` | Frontend error endpoint |
| `frontend/src/observability/errorReporter.ts` | JS error capture |
| `frontend/src/observability/ErrorBoundary.tsx` | React error boundary |
| `observability/alerts/rules.yaml` | Alert definitions |

## Files to Modify

| Path | Changes |
|------|---------|
| `backend/pyproject.toml` | Add OTel dependencies |
| `backend/app/main.py` | Initialize observability on startup |
| `backend/app/config.py` | Add OTel settings |
| `backend/app/services/auth_service.py` | Add custom spans |
| `frontend/src/App.tsx` | Wrap with ErrorBoundary |
| `frontend/src/lib/api-client.ts` | Add error reporting |
| `caddy/Caddyfile` | Trace headers + SigNoz proxy |
| `docker-compose.prod.yml` | Reference observability compose |
| `.env.prod.example` | Document OTel env vars |

---

# Part 5: Verification Plan

## End-to-End Test Scenarios

### Scenario 1: Trace Visibility
1. Start all services with `docker compose up`
2. Open SigNoz at `http://localhost:3301`
3. Make a sign-in request via the frontend
4. Verify trace appears showing: HTTP request → auth service → database queries

### Scenario 2: Log Correlation
1. Make a failing sign-in request (wrong password)
2. Find the error log in SigNoz Logs
3. Click the trace_id → verify it links to the full trace

### Scenario 3: Metrics
1. Make 10 successful and 5 failed requests
2. Query `auth_signins_total` in SigNoz
3. Verify counts match with proper labels

### Scenario 4: Alerting
1. Stop the backend container
2. Verify "service down" alert fires within 2 minutes
3. Restart backend, verify alert resolves

### Scenario 5: Frontend Errors
1. Trigger a JS error (e.g., access undefined property)
2. Verify error appears in backend logs
3. Verify error includes stack trace and user context

---

# Appendix: Quick Reference

## OTel Environment Variables

```bash
OTEL_SERVICE_NAME=rag-admin-backend
OTEL_EXPORTER_OTLP_ENDPOINT=http://signoz-otel-collector:4317
OTEL_TRACES_EXPORTER=otlp
OTEL_METRICS_EXPORTER=otlp
OTEL_LOGS_EXPORTER=otlp
OTEL_PYTHON_LOG_CORRELATION=true
```

## Useful SigNoz Queries

```sql
-- Find slow requests
SELECT * FROM signoz_traces WHERE duration_nano > 1000000000

-- Error rate by endpoint
SELECT http_route, count(*) as errors
FROM signoz_traces
WHERE status_code = 'ERROR'
GROUP BY http_route

-- Auth failures by reason
SELECT attributes['failure_reason'], count(*)
FROM signoz_logs
WHERE message LIKE '%authentication failed%'
GROUP BY attributes['failure_reason']
```

## Resource Monitoring Commands

```bash
# Check container memory usage
docker stats --no-stream

# ClickHouse disk usage
docker exec clickhouse du -sh /var/lib/clickhouse/

# Collector queue depth
curl http://localhost:8888/metrics | grep otelcol_processor
```
