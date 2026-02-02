# Observability Guide

This guide explains how to set up and use SigNoz observability with RAG Admin.

## Overview

### What is Observability?

Observability gives you visibility into your application's behavior through three pillars:

1. **Traces**: See the journey of each request through your system
   - Which endpoints were called?
   - How long did each operation take?
   - What was the sequence of events?

2. **Logs**: Structured JSON logs with trace correlation
   - What happened and when?
   - What were the request/response details?
   - Were there any errors or warnings?

3. **Metrics**: Application performance data
   - How many requests per second?
   - What's the latency distribution?
   - What's the error rate?

### Architecture

RAG Admin uses the **official SigNoz standalone deployment** for observability:

- **Phase 1 (Current)**: Both RAG Admin and SigNoz run on the same VPS
  - Backend connects to SigNoz via Docker network (`signoz-net`)
  - Simple deployment, zero internet traffic
  - Portable design for future migration

- **Phase 2 (Future)**: SigNoz can move to a separate machine
  - Just change `OTEL_EXPORTER_ENDPOINT` environment variable
  - Enable TLS for secure communication
  - No code changes required

### Components

- **SigNoz OTel Collector**: Receives telemetry from backend (port 4317)
- **ClickHouse**: Time-series database for storing telemetry
- **SigNoz Query Service**: Web UI for viewing traces, logs, and metrics
- **Zookeeper**: Coordination service for ClickHouse

---

## Prerequisites

### Install Official SigNoz

SigNoz is deployed **independently** from RAG Admin.

```bash
# Clone SigNoz repository
git clone https://github.com/SigNoz/signoz.git ~/signoz
cd ~/signoz/deploy/docker

# Deploy SigNoz
docker compose up -d

# Verify it's running (wait ~60 seconds for health checks)
docker compose ps
```

Expected output:
```
NAME                        STATUS
signoz-clickhouse           healthy
signoz-otel-collector       healthy
signoz-query-service        healthy
signoz-zookeeper-1          healthy
```

**Verify endpoints:**
```bash
# Collector gRPC endpoint
curl -v http://localhost:4317
# Expected: HTTP/2 connection

# SigNoz UI
curl http://localhost:8080/api/v1/health
# Expected: {"status":"ok"}
```

**Check Docker networks:**
```bash
docker network ls | grep signoz-net
# Expected: signoz-net
```

---

## Local Development Setup

### Option 1: Backend in Docker (Mirrors Production)

```bash
cd ~/rag-admin

# Ensure SigNoz is running
cd ~/signoz/deploy/docker && docker compose ps

# Start RAG Admin (backend connects to signoz-net)
cd ~/rag-admin
docker compose -f docker-compose.local.yml up -d

# Check backend connected to both networks
docker inspect rag-admin-backend-local | grep -A 10 Networks
# Should show: app-network and signoz-net
```

### Option 2: Backend Running Natively (Direct Development)

When running the backend natively with `uvicorn`, update `backend/.env`:

```bash
# backend/.env
OTEL_ENABLED=True
OTEL_EXPORTER_ENDPOINT=http://localhost:4317  # Note: localhost, not signoz-otel-collector
OTEL_SERVICE_NAME=rag-admin-backend
LOG_LEVEL=INFO
LOG_FORMAT=json
```

Then start:
```bash
cd backend
uv run uvicorn app.main:app --reload
```

### Verify Observability is Working

1. **Generate test traffic:**
   ```bash
   curl http://localhost:8000/health
   curl http://localhost:8000/api/v1/auth/health
   ```

2. **Check backend logs:**
   ```bash
   # Docker
   docker logs rag-admin-backend-local | grep "Observability"

   # Native
   # Check terminal output
   ```

   Expected: `Observability initialization complete`

3. **View traces in SigNoz UI:**
   - Open http://localhost:8080
   - Navigate to: **Traces** → Filter by service: `rag-admin-backend`
   - You should see recent traces (within 1-2 minutes)

---

## Production Deployment

### Step 1: Deploy SigNoz (First Time Only)

**Option A: Manual Deployment**
```bash
ssh user@yourserver.com

# Clone and deploy SigNoz
git clone https://github.com/SigNoz/signoz.git ~/signoz
cd ~/signoz/deploy/docker
docker compose up -d

# Verify
docker compose ps
```

**Option B: GitHub Actions**
1. Go to **Actions** → **Deploy SigNoz**
2. Click **Run workflow**
3. Enter your server hostname and path

### Step 2: Deploy RAG Admin

RAG Admin will automatically connect to SigNoz via the `signoz-net` network.

**Using GitHub Actions** (recommended):
```bash
# Push to main branch
git push origin main

# Or trigger manually from GitHub Actions UI
```

**Manual deployment:**
```bash
ssh user@yourserver.com
cd ~/rag-admin

# Pull latest
git pull origin main

# Ensure .env.prod has correct settings
cat .env.prod | grep OTEL
# OTEL_ENABLED=True
# OTEL_EXPORTER_ENDPOINT=http://signoz-otel-collector:4317

# Deploy
docker compose -f docker-compose.prod.yml up -d

# Verify backend is on both networks
docker inspect rag-admin-backend | jq '.[0].NetworkSettings.Networks | keys'
# Expected: ["app-network", "signoz-net"]
```

### Step 3: Verify Connectivity

```bash
# Test backend → collector connectivity
docker exec rag-admin-backend curl -v http://signoz-otel-collector:4317
# Expected: Successful gRPC connection

# Test backend → database connectivity
docker exec rag-admin-backend nc -zv postgres 5432
# Expected: Connection successful

# Check observability logs
docker logs rag-admin-backend 2>&1 | grep -A 5 "Initializing Observability"
# Expected: "Observability initialization complete"

# Generate test traffic
curl https://yourdomain.com/health

# Check SigNoz UI (see "Accessing SigNoz UI" section below)
```

---

## Accessing SigNoz UI

### Local Development
Simply open http://localhost:8080

### Production (SSH Tunnel)

**Option 1: One-time access**
```bash
# From your local machine
ssh -L 8080:localhost:8080 user@yourserver.com

# Keep terminal open, then visit: http://localhost:8080
```

**Option 2: Expose via Caddy (Advanced)**

Add to `caddy/Caddyfile` on production server:
```caddyfile
signoz.yourdomain.com {
    reverse_proxy signoz-query-service:3301

    # Optional: Add basic auth
    basicauth {
        admin $2a$14$... # Generate with: caddy hash-password
    }
}
```

Then access at: https://signoz.yourdomain.com

---

## Configuration Reference

### Environment Variables

Configure in `.env.prod` (production) or `backend/.env` (local):

| Variable | Description | Default | Options |
|----------|-------------|---------|---------|
| `OTEL_ENABLED` | Enable/disable observability | `True` | `True`, `False` |
| `OTEL_EXPORTER_ENDPOINT` | OTel Collector endpoint | `http://signoz-otel-collector:4317` | See below |
| `OTEL_SERVICE_NAME` | Service identifier in traces | `rag-admin-backend` | Any string |
| `LOG_LEVEL` | Minimum log level | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `LOG_FORMAT` | Log output format | `json` | `json`, `text` |

### OTEL_EXPORTER_ENDPOINT Options

| Scenario | Endpoint | TLS |
|----------|----------|-----|
| Same machine (Docker) | `http://signoz-otel-collector:4317` | No |
| Same machine (native dev) | `http://localhost:4317` | No |
| Different machine (internet) | `https://signoz.yourdomain.com:4317` | Yes (auto) |
| Different machine (VPN) | `http://10.0.1.5:4317` | No |

**Note:** TLS is automatically enabled when endpoint starts with `https://`. No code changes needed!

---

## Using SigNoz

### Viewing Traces

1. Open SigNoz UI: http://localhost:8080
2. Click **Traces** in the sidebar
3. Filter by service: `rag-admin-backend`
4. Click any trace to see the waterfall view:
   - Root span: HTTP request (e.g., `GET /api/v1/auth/health`)
   - Child spans: Database queries, external HTTP calls
   - Duration: How long each operation took

### Viewing Logs

1. Click **Logs** in the sidebar
2. Filter by `service = rag-admin-backend`
3. Click any log entry to see:
   - Full log message
   - Structured fields (user_id, request_id, etc.)
   - Related trace (click to jump)

### Trace-Log Correlation

Every log entry includes a `trace_id`. To find related logs:

1. In a trace, copy the `trace_id`
2. Go to **Logs**
3. Search for: `trace_id:<paste-id>`
4. See all logs from that request

### Viewing Metrics

1. Click **Metrics** or **Dashboards**
2. Available metrics:
   - `http_server_requests_total` - Request count by method, route, status
   - `http_server_request_duration_seconds` - Latency histogram

---

## Troubleshooting

### Backend can't reach collector

**Symptom:** Backend logs show connection errors to collector

**Check:**
```bash
# Is SigNoz running?
cd ~/signoz/deploy/docker && docker compose ps

# Is signoz-net network created?
docker network inspect signoz-net

# Is backend connected to signoz-net?
docker inspect rag-admin-backend | grep -A 10 Networks

# Can backend reach collector?
docker exec rag-admin-backend curl -v http://signoz-otel-collector:4317
```

**Fix:**
```bash
# Recreate backend to connect to network
cd ~/rag-admin
docker compose -f docker-compose.prod.yml up -d --force-recreate backend
```

### No traces appearing in SigNoz

**Wait 1-2 minutes** - traces are batched for efficiency.

**Then check:**
```bash
# 1. Is OTEL enabled?
docker exec rag-admin-backend env | grep OTEL
# Should show: OTEL_ENABLED=True

# 2. Check collector logs
docker logs signoz-otel-collector --tail 50

# 3. Generate test traffic
curl https://yourdomain.com/health

# 4. Check backend logs
docker logs rag-admin-backend | grep "Observability"
```

### No logs in SigNoz

1. Ensure `LOG_FORMAT=json` in your `.env`
2. Wait 1-2 minutes (logs are batched)
3. Check collector logs:
   ```bash
   docker logs signoz-otel-collector | grep error
   ```

### Network connectivity issues

**For same-machine setup:**
```bash
# Verify networks exist
docker network ls | grep -E "app-network|signoz-net"

# Verify backend is on both
docker inspect rag-admin-backend | jq '.[0].NetworkSettings.Networks | keys'
```

**For separate-machine setup (future):**
```bash
# Test from app server to SigNoz server
curl -v https://signoz.yourdomain.com:4317

# Check TLS is working
openssl s_client -connect signoz.yourdomain.com:4317
```

### SigNoz UI not loading

```bash
# Check query service
docker logs signoz-query-service --tail 50

# Check ClickHouse
docker logs signoz-clickhouse --tail 50

# Verify UI port is accessible
curl http://localhost:8080/api/v1/health
```

---

## Future: Moving to Separate Machine

When you're ready to move SigNoz to a cheaper cloud provider:

### Step 1: Deploy SigNoz to New Server

```bash
# On new server
ssh user@signoz-server.com
git clone https://github.com/SigNoz/signoz.git ~/signoz
cd ~/signoz/deploy/docker
docker compose up -d
```

### Step 2: Expose Collector Securely

**Option A: Caddy Reverse Proxy (Recommended)**

On SigNoz server, create `Caddyfile`:
```caddyfile
signoz-collector.yourdomain.com {
    reverse_proxy signoz-otel-collector:4317
}
```

**Option B: WireGuard VPN (Most Secure)**

Set up VPN between servers, use private IP:
```bash
OTEL_EXPORTER_ENDPOINT=http://10.0.1.5:4317
```

### Step 3: Update RAG Admin

On app server, update `.env.prod`:
```bash
# Change this line:
OTEL_EXPORTER_ENDPOINT=https://signoz-collector.yourdomain.com:4317
```

Redeploy:
```bash
cd ~/rag-admin
docker compose -f docker-compose.prod.yml up -d
```

**That's it!** Backend automatically uses TLS when endpoint starts with `https://`.

---

## Disabling Observability

To run without observability (e.g., for testing or cost reduction):

### Temporary (Degraded Mode)

```bash
# In .env.prod or backend/.env
OTEL_ENABLED=False

# Restart backend
docker compose -f docker-compose.prod.yml up -d
```

The backend will still try to connect to `signoz-net`, but won't send telemetry.

### Permanent (Remove Network)

Edit `docker-compose.prod.yml` and remove:
```yaml
networks:
  - signoz-net  # Remove this line
```

Also remove the network definition:
```yaml
signoz-net:  # Remove entire block
  external: true
  name: signoz-net
```

---

## Resource Usage

The official SigNoz stack uses:

| Service | Memory | CPU |
|---------|--------|-----|
| ClickHouse | ~1GB | 1 core |
| OTel Collector | ~200MB | 0.5 core |
| Query Service | ~512MB | 0.5 core |
| Zookeeper | ~128MB | 0.2 core |

**Total: ~2GB memory, ~2.2 CPU cores**

RAG Admin's backend adds minimal overhead (~10MB for OpenTelemetry SDK).

---

## Further Reading

- [SigNoz Official Documentation](https://signoz.io/docs/)
- [OpenTelemetry Python Docs](https://opentelemetry.io/docs/instrumentation/python/)
- [Multi-Network Architecture](../deployment/docker.md#multi-network-architecture)
