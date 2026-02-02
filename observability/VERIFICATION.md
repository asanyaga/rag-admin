# Phase 1 Observability Verification Guide

This guide walks you through verifying that all observability components work correctly.

## Prerequisites

- Docker and Docker Compose installed
- Backend dependencies installed (`uv sync` in backend directory)

## Step 1: Start the Observability Stack

Start SigNoz (ClickHouse, OTel Collector, Query Service):

```bash
# From the project root directory
docker compose -f docker-compose.observability.yml up -d
```

Wait for services to be healthy (about 30-60 seconds):

```bash
# Check service status
docker compose -f docker-compose.observability.yml ps
```

Expected output:
```
NAME                      STATUS
rag-admin-clickhouse      healthy
rag-admin-otel-collector  healthy
rag-admin-signoz          healthy
```

## Step 2: Access SigNoz UI

Open your browser and navigate to:

**http://localhost:3301**

You should see the SigNoz dashboard. If this is your first time, you may be prompted to create an account.

## Step 3: Start the Backend

For local development (without full Docker stack):

```bash
# Terminal 1: Start PostgreSQL
docker compose up -d postgres

# Terminal 2: Start the backend
cd backend
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

You should see startup logs in JSON format with observability initialization messages.

## Step 4: Generate Test Traffic

Run the verification script:

```bash
cd backend
uv run python -m observability.verify
```

Or manually with curl:

```bash
# Health check
curl http://localhost:8000/health

# Root endpoint
curl http://localhost:8000/

# API endpoint (will return error without auth, but still creates trace)
curl http://localhost:8000/api/v1/users/me
```

## Step 5: Verify in SigNoz

### 5.1 Check Traces

1. In SigNoz, click **"Traces"** in the left sidebar
2. You should see traces for the requests you made
3. Click on a trace to see the waterfall view:
   - Root span: HTTP request (e.g., `GET /health`)
   - Child spans: Database queries (if any)

**What to look for:**
- [ ] Traces appear within 1-2 minutes of making requests
- [ ] Service name shows "rag-admin-backend"
- [ ] HTTP method and route are correct
- [ ] Duration is recorded

### 5.2 Check Logs

1. Click **"Logs"** in the left sidebar
2. Filter by service: `service = rag-admin-backend`
3. You should see JSON-formatted logs

**What to look for:**
- [ ] Logs appear with JSON format
- [ ] Each log has `trace_id` field
- [ ] Each log has `service` field
- [ ] Log levels (INFO, WARNING, ERROR) are correct

### 5.3 Check Trace-Log Correlation

1. In a log entry, find the `trace_id` field
2. Copy the trace_id value
3. Go to Traces and search for that trace_id
4. You should find the corresponding trace

**What to look for:**
- [ ] Clicking trace_id in logs navigates to the trace
- [ ] The trace timestamp matches the log timestamp

### 5.4 Check Metrics

1. Click **"Metrics"** or **"Dashboards"** in the left sidebar
2. Search for metrics:
   - `http_server_requests_total`
   - `http_server_request_duration_seconds`

**What to look for:**
- [ ] Metrics appear (may take up to 60 seconds due to export interval)
- [ ] Labels include method, route, status_code
- [ ] Values increase as you make more requests

## Troubleshooting

### No traces appearing

1. Check the OTel Collector is running:
   ```bash
   docker logs rag-admin-otel-collector
   ```

2. Check the backend can reach the collector:
   ```bash
   # From inside the backend container or with correct network
   curl http://localhost:4317
   ```

3. Verify OTEL_ENABLED is True in your environment

### No logs appearing

1. Check LOG_FORMAT is set to "json"
2. Verify logs are going to stdout:
   ```bash
   docker logs <backend-container>
   ```

### Metrics not showing

1. Metrics are exported every 60 seconds by default
2. Wait at least 2 minutes after making requests
3. Check the collector logs for export errors

## Expected Results Summary

| Component | Status | Notes |
|-----------|--------|-------|
| Traces | ✓ | HTTP requests create spans |
| Child Spans | ✓ | SQLAlchemy queries appear as children |
| Logs | ✓ | JSON format with trace_id |
| Log Correlation | ✓ | trace_id links logs to traces |
| Metrics | ✓ | Request count and duration recorded |

## Next Steps

Once verification passes:
- Phase 2: Add custom business metrics and frontend error capture
- Phase 3: Set up alerting and dashboards
