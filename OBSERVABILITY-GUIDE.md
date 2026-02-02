# Observability Guide

This guide explains how to run the RAG Admin app with SigNoz observability locally and in production.

## Overview

The observability stack provides:
- **Traces**: See the journey of each request through the system
- **Logs**: Structured JSON logs with trace correlation
- **Metrics**: Request counts and latency histograms

Components:
- **ClickHouse**: Time-series database for storing telemetry
- **OTel Collector**: Receives telemetry from the backend
- **SigNoz Query Service**: Web UI for viewing traces, logs, and metrics

---

## Local Development (WSL)

### Prerequisites

- Docker and Docker Compose installed
- Python 3.12 with `uv` package manager
- Node.js 18+

### Step 1: Start the Observability Stack

```bash
# From project root
docker compose -f docker-compose.observability.yml up -d
```

Wait for services to be healthy (~30-60 seconds):

```bash
docker compose -f docker-compose.observability.yml ps
```

Expected output:
```
NAME                       STATUS
rag-admin-clickhouse       healthy
rag-admin-otel-collector   healthy
rag-admin-signoz           healthy
```

### Step 2: Start PostgreSQL

```bash
docker compose up -d
```

### Step 3: Start the Backend

```bash
cd backend
uv run uvicorn app.main:app --reload
```

You should see startup logs showing observability initialization:
```
Initializing Observability Stack
Service Name: rag-admin-backend
Exporter Endpoint: http://localhost:4317
```

### Step 4: Start the Frontend (separate terminal)

```bash
cd frontend
npm run dev
```

### Step 5: Access the App

| Service | URL |
|---------|-----|
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |
| SigNoz UI | http://localhost:3301 |

### Stopping Services

```bash
# Stop observability stack
docker compose -f docker-compose.observability.yml down

# Stop PostgreSQL
docker compose down

# Stop backend/frontend: Ctrl+C in their terminals
```

---

## Production Deployment

### Automatic (GitHub Actions)

The deploy workflow automatically includes the observability stack. Push to `main` or trigger manually.

### Manual Deployment

SSH into your server and run:

```bash
cd ~/rag-admin

# Pull latest changes
git pull origin main

# Start all services including observability
docker compose -f docker-compose.prod.yml -f docker-compose.observability.yml up -d

# Check status
docker compose -f docker-compose.prod.yml -f docker-compose.observability.yml ps
```

---

## Viewing Logs

### Option 1: SigNoz UI (Recommended)

**Local:**
1. Open http://localhost:3301
2. Click "Logs" in the sidebar
3. Filter by `service = rag-admin-backend`
4. Click any log entry to see the full trace

**Production (via SSH tunnel):**
```bash
# From your local machine
ssh -L 3301:localhost:3301 user@yourserver.com

# Then open http://localhost:3301 in your browser
```

### Option 2: Docker Logs

**View backend logs:**
```bash
docker logs rag-admin-backend --tail=100 -f
```

**View all logs:**
```bash
# Local
docker compose -f docker-compose.observability.yml logs -f

# Production
docker compose -f docker-compose.prod.yml -f docker-compose.observability.yml logs -f
```

**View specific service:**
```bash
# Production backend
docker compose -f docker-compose.prod.yml -f docker-compose.observability.yml logs backend -f

# OTel Collector
docker compose -f docker-compose.observability.yml logs signoz-otel-collector -f
```

---

## Viewing Traces

1. Open SigNoz UI (http://localhost:3301)
2. Click "Traces" in the sidebar
3. You'll see all HTTP requests to your backend
4. Click a trace to see the waterfall view:
   - Root span: HTTP request (e.g., `GET /health`)
   - Child spans: Database queries, external HTTP calls

### Trace-Log Correlation

Every log entry includes a `trace_id`. To find related logs:
1. In a trace, copy the trace ID
2. Go to Logs
3. Search for that trace ID
4. See all logs from that request

---

## Viewing Metrics

1. Open SigNoz UI (http://localhost:3301)
2. Click "Metrics" or "Dashboards"
3. Available metrics:
   - `http_server_requests_total` - Request count by method, route, status
   - `http_server_request_duration_seconds` - Latency histogram

---

## Configuration

Settings in `backend/.env` (local) or `.env.prod` (production):

| Setting | Description | Default |
|---------|-------------|---------|
| `OTEL_ENABLED` | Enable/disable observability | `True` |
| `OTEL_EXPORTER_ENDPOINT` | OTel Collector address | `http://signoz-otel-collector:4317` |
| `OTEL_SERVICE_NAME` | Service name in traces | `rag-admin-backend` |
| `LOG_LEVEL` | Minimum log level | `INFO` |
| `LOG_FORMAT` | `json` or `text` | `json` |

**Local development endpoint:** `http://localhost:4317`
**Production endpoint:** `http://signoz-otel-collector:4317` (Docker network)

---

## Troubleshooting

### No traces appearing

1. Check OTel Collector is running:
   ```bash
   docker logs rag-admin-otel-collector
   ```

2. Verify `OTEL_ENABLED=True` in your `.env`

3. Check the backend can reach the collector:
   ```bash
   curl http://localhost:4317
   ```

### No logs in SigNoz

1. Ensure `LOG_FORMAT=json` in your `.env`
2. Wait 1-2 minutes (logs are batched)
3. Check collector logs for errors

### Metrics not showing

1. Metrics are exported every 60 seconds
2. Wait at least 2 minutes after making requests
3. Make several requests to generate data

### SigNoz UI not loading

1. Check Query Service is healthy:
   ```bash
   docker logs rag-admin-signoz
   ```

2. Check ClickHouse is healthy:
   ```bash
   docker logs rag-admin-clickhouse
   ```

---

## Resource Usage

The observability stack uses these resources:

| Service | Memory Limit | Memory Reserved |
|---------|--------------|-----------------|
| ClickHouse | 1GB | 512MB |
| OTel Collector | 512MB | 256MB |
| SigNoz Query Service | 768MB | 512MB |

**Total: ~2.3GB memory limit**

For low-resource environments, you can disable observability by setting `OTEL_ENABLED=False`.

---

## Disabling Observability

To run without observability (e.g., for testing):

**Local:**
```bash
# In backend/.env
OTEL_ENABLED=False

# Then just start PostgreSQL and backend
docker compose up -d
cd backend && uv run uvicorn app.main:app --reload
```

**Production:**
```bash
# Use only prod compose (no observability)
docker compose -f docker-compose.prod.yml up -d
```
