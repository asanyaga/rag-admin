# Testing Observability

This guide helps you verify that distributed tracing is working correctly.

## Prerequisites

1. **SigNoz running**:
   ```bash
   cd ~/signoz/deploy/docker && docker compose ps
   # All services should be "healthy"
   ```

2. **Backend running**:
   ```bash
   docker compose -f docker-compose.local.yml ps
   # rag-admin-backend-local should be "healthy"
   ```

## Quick Test

Run the automated test script:

```bash
./scripts/test-tracing.sh
```

This script:
1. Checks prerequisites
2. Runs diagnostic to verify configuration
3. Generates test traffic
4. Provides verification steps

## Manual Testing

### Step 1: Run Diagnostic

```bash
docker exec rag-admin-backend-local python diagnose_instrumentation.py
```

Expected output:
```
✓ OTEL_ENABLED → Value: True
✓ TracerProvider initialized → Type: TracerProvider
✓ Span processors configured → Spans will be exported
✓ OpenTelemetry middleware present → HTTP requests will be traced
✓ FastAPI instrumented → Auto-instrumentation active
✓ Manual span creation → Spans can be created programmatically
✓ Force flush → Test spans exported to collector

Checks passed: 6/6
✓ Tracing is correctly configured!
```

If any checks fail, see [Troubleshooting](#troubleshooting) below.

### Step 2: Generate Traffic

```bash
# Health check endpoint
curl http://localhost:8000/health

# Root endpoint
curl http://localhost:8000/

# Auth endpoint (sign-in attempt - will fail without credentials)
curl -X POST http://localhost:8000/api/v1/auth/signin \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"wrong"}'
```

### Step 3: Wait for Export

Spans are batched and exported every 5 seconds. Wait 10 seconds to be safe:

```bash
sleep 10
```

### Step 4: Verify in SigNoz

1. Open SigNoz UI: http://localhost:8080

2. Navigate to **Traces** in the sidebar

3. Filter by service: `rag-admin-backend`

4. You should see recent traces (within last minute)

5. Click on a trace to see details

### Step 5: Inspect Span Hierarchy

A typical trace should look like:

```
GET /health (200 OK) - 5ms
└── (No child spans for health check)

POST /api/v1/auth/signin (401 Unauthorized) - 150ms
└── authenticate_user - 145ms
    ├── SELECT FROM users WHERE email = ? - 50ms
    └── (password verification would appear here if instrumented)
```

### Step 6: Check Span Attributes

Click on a span to see its attributes:

**HTTP Span (auto-instrumented)**:
- `http.method`: POST
- `http.route`: /api/v1/auth/signin
- `http.status_code`: 401
- `http.url`: http://localhost:8000/api/v1/auth/signin

**Manual Span (authenticate_user)**:
- `auth.email`: test@example.com
- `auth.method`: email_password
- `auth.success`: false
- `auth.error`: invalid_credentials
- `client.ip`: 172.x.x.x

**Database Span (auto-instrumented)**:
- `db.system`: postgresql
- `db.name`: ragadmin
- `db.statement`: SELECT * FROM users WHERE email = $1
- `db.operation`: SELECT

## What to Look For

### ✅ Success Indicators

- [x] Service `rag-admin-backend` appears in Services list
- [x] Traces appear within 10 seconds of request
- [x] HTTP spans show correct method, route, status code
- [x] Database spans show SQL queries (if endpoints hit database)
- [x] Manual spans appear with custom attributes
- [x] Span hierarchy is correct (parent → child relationship)
- [x] Timestamps and durations are reasonable

### ❌ Failure Indicators

- [ ] No service `rag-admin-backend` in Services list
  → Tracing not initialized or spans not exported

- [ ] No traces appear after 30+ seconds
  → Check collector connectivity, exporter configuration

- [ ] HTTP spans missing
  → FastAPI instrumentation not applied correctly

- [ ] No span attributes
  → Tracer provider not configured with resource

- [ ] Flat span hierarchy (all spans at root level)
  → Context propagation broken

## Performance Check

After verifying traces work, check for performance impact:

### Baseline (No Observability)

1. Disable tracing:
   ```bash
   # In .env.local
   OTEL_ENABLED=False
   ```

2. Restart backend:
   ```bash
   docker compose -f docker-compose.local.yml restart backend
   ```

3. Benchmark:
   ```bash
   ab -n 1000 -c 10 http://localhost:8000/health
   ```

4. Note the "Time per request" (mean)

### With Observability

1. Enable tracing:
   ```bash
   # In .env.local
   OTEL_ENABLED=True
   ```

2. Restart and benchmark again

3. Compare times

**Expected overhead**: < 5-10% latency increase

If overhead is > 20%, check:
- Are you using BatchSpanProcessor? (not SimpleSpanProcessor)
- Is collector reachable? (spans queue up if not)
- Are you creating too many manual spans?

## Troubleshooting

### No traces appearing

**Check 1**: Is OTEL enabled?
```bash
docker exec rag-admin-backend-local env | grep OTEL_ENABLED
# Should be: OTEL_ENABLED=True
```

**Check 2**: Is collector reachable?
```bash
docker exec rag-admin-backend-local curl -v http://signoz-otel-collector:4317
# Should connect (may see gRPC error, that's OK - just verifying connectivity)
```

**Check 3**: Are spans being created?
```bash
docker logs rag-admin-backend-local | grep -i "trace\|span\|otel"
# Should see initialization messages
```

**Check 4**: Collector receiving spans?
```bash
docker logs signoz-otel-collector | grep -i "trace\|span"
# Should see activity when requests are made
```

### Traces appear but no attributes

**Issue**: TracerProvider not configured with Resource

**Fix**: Check `backend/app/main.py`:
```python
# Should have:
setup_tracing(
    service_name=settings.OTEL_SERVICE_NAME,  # ← Must be set
    service_version="0.1.0",
    otlp_endpoint=settings.OTEL_EXPORTER_ENDPOINT,
    enabled=settings.OTEL_ENABLED,
)
```

### Middleware not found

**Issue**: FastAPI instrumentation applied too late

**Fix**: In `backend/app/main.py`:
```python
# ✅ Correct order:
app = FastAPI(...)
FastAPIInstrumentor.instrument_app(app)  # ← BEFORE startup event
app.add_middleware(...)

# ❌ Wrong order:
app = FastAPI(...)
app.add_middleware(...)  # ← Middleware stack built
FastAPIInstrumentor.instrument_app(app)  # ← Too late!
```

### Database spans missing

**Issue**: SQLAlchemy not instrumented

**Check**: `backend/app/main.py` startup event:
```python
@app.on_event("startup")
async def startup_event():
    from app.observability.tracing import instrument_sqlalchemy
    instrument_sqlalchemy(engine.sync_engine)  # ← Should be present
```

### Manual spans not appearing

**Issue 1**: Tracer not imported
```python
# Add to your module:
from app.observability import get_tracer
tracer = get_tracer(__name__)
```

**Issue 2**: Context not active
```python
# Must be inside a request context or parent span:
with tracer.start_as_current_span("name"):
    # This only works if there's an active context
```

**Issue 3**: TracerProvider not initialized
```python
# Check main.py has setup_tracing() at module level
```

## Advanced Testing

### Test Context Propagation

Send a request with a trace context header:

```bash
curl -H "traceparent: 00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01" \
     http://localhost:8000/health
```

In SigNoz, the trace ID should match: `0af7651916cd43dd8448eb211c80319c`

### Test Error Recording

Trigger an error:

```bash
curl -X POST http://localhost:8000/api/v1/auth/signin \
  -H "Content-Type: application/json" \
  -d '{"email":"nonexistent@example.com","password":"wrong"}'
```

In SigNoz:
- Span status should be "Error"
- Span should have `auth.error` attribute
- HTTP status_code should be 401

### Test Nested Spans

Sign up with valid data (creates nested spans):

```bash
curl -X POST http://localhost:8000/api/v1/auth/signup \
  -H "Content-Type: application/json" \
  -d '{
    "email":"testuser@example.com",
    "password":"SecurePassword123!",
    "name":"Test User"
  }'
```

Trace hierarchy should show:
```
POST /api/v1/auth/signup
└── (multiple database INSERT spans)
```

## Continuous Monitoring

For ongoing verification, check these periodically:

```bash
# Recent traces count (last 5 minutes)
# Via SigNoz UI: Services → rag-admin-backend → Request Rate

# Error rate
# Via SigNoz UI: Services → rag-admin-backend → Error Rate

# P99 latency
# Via SigNoz UI: Services → rag-admin-backend → P99 Latency
```

## Next Steps

Once tracing is verified:

1. **Re-enable logging and metrics** (currently disabled):
   - Uncomment logging setup in main.py
   - Uncomment metrics setup in main.py
   - Add MetricsMiddleware back

2. **Add more manual spans**:
   - Password verification in auth service
   - External API calls
   - Complex business logic

3. **Set up alerts** in SigNoz:
   - High error rate (> 5%)
   - High latency (P99 > 1s)
   - Service down

4. **Configure sampling** (for production):
   - Sample 10% of traces if traffic > 100 req/s
   - Always sample errors (tail-based sampling)

## Resources

- [Observability README](./README.md) - Setup and configuration
- [Deep Dive Guide](./deep-dive.md) - How tracing works
- [Manual Spans Guide](./manual-spans.md) - Adding custom instrumentation
- [SigNoz Documentation](https://signoz.io/docs/)
