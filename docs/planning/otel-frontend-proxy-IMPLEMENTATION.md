# OpenTelemetry Frontend Proxy - Implementation Complete

## Summary

Successfully implemented the OpenTelemetry frontend proxy to eliminate browser permission prompts when collecting frontend telemetry.

## What Was Changed

### Backend Changes

1. **Created `/backend/app/routers/otel_proxy.py`**
   - Three proxy endpoints: `/api/v1/traces`, `/api/v1/metrics`, `/api/v1/logs`
   - Uses FastAPI app state for HTTP client management (no race conditions)
   - Returns 202 Accepted on collector failure (telemetry never breaks the app)
   - Proper timeout configuration (2s connect, 3s request)
   - Case-insensitive header forwarding
   - Comprehensive error logging for ops awareness

2. **Updated `/backend/app/config.py`**
   - Added `OTEL_COLLECTOR_URL` (default: `http://localhost:4318`)
   - Added `OTEL_CONNECT_TIMEOUT` (default: 2.0 seconds)
   - Added `OTEL_REQUEST_TIMEOUT` (default: 3.0 seconds)

3. **Updated `/backend/app/main.py`**
   - Migrated from `@app.on_event("startup/shutdown")` to `lifespan` context manager
   - Imported and included `otel_proxy` router
   - Added HTTP client cleanup on shutdown

### Frontend Changes

1. **Updated `/frontend/src/lib/tracing.ts`**
   - Changed collector URL logic to use `/api/v1/traces` in production
   - Keeps `http://localhost:4318/v1/traces` for local development
   - Environment-aware configuration using `import.meta.env.DEV`

## Environment Variables (Optional)

Add to `.env` if you need to override defaults:

```bash
# Backend proxy settings (optional - defaults shown)
OTEL_COLLECTOR_URL=http://localhost:4318
OTEL_CONNECT_TIMEOUT=2.0
OTEL_REQUEST_TIMEOUT=3.0
```

Frontend environment variables remain the same:
```bash
# Frontend settings (optional)
VITE_OTEL_ENABLED=true
VITE_OTEL_COLLECTOR_URL=  # Leave empty to use automatic detection
```

## Testing Instructions

### 1. Local Development Testing

```bash
# Terminal 1: Start backend
cd backend
source .venv/bin/activate  # or your virtualenv
uvicorn app.main:app --reload --port 8000

# Terminal 2: Start frontend
cd frontend
npm run dev

# Terminal 3: Test the proxy endpoint
curl -X POST http://localhost:8000/api/v1/traces \
  -H "Content-Type: application/json" \
  -d '{"test": "data"}'
```

### 2. Verify No Permission Prompt

1. Build and deploy to production (or test in production mode locally)
2. Open browser in incognito mode
3. Visit your application
4. **Expected:** No permission prompt appears
5. **Check DevTools Network tab:** Traces should POST to `/api/v1/traces` (same origin)

### 3. Verify Traces Flowing

1. Open SigNoz dashboard
2. Navigate to Traces view
3. Look for traces from `rag-admin-frontend` service
4. Should see traces for:
   - Document load
   - User interactions (clicks)
   - API requests (with trace context propagation)

### 4. Test Graceful Degradation

```bash
# Stop the OTel collector temporarily
docker stop signoz-otel-collector

# Visit the application
# Expected behavior:
# - App works normally
# - No errors shown to users
# - Backend logs show warnings: "OTel collector unavailable"

# Restart collector
docker start signoz-otel-collector

# Traces should start flowing again
```

## Architecture

```
┌─────────────────┐                           ┌─────────────────┐
│                 │   POST /api/v1/traces     │                 │
│  User Browser   │ ────────────────────────► │    FastAPI      │
│  (frontend JS)  │   (same origin - no       │    Backend      │
│                 │    permission prompt)     │                 │
└─────────────────┘                           └────────┬────────┘
                                                       │
                                              localhost:4318
                                              (HTTP endpoint)
                                                       │
                                                       ▼
                                              ┌─────────────────┐
                                              │  SigNoz/OTel    │
                                              │  Collector      │
                                              │  (port 4318)    │
                                              └─────────────────┘

Note: Backend traces use gRPC endpoint (port 4317)
      Frontend traces use HTTP proxy → HTTP endpoint (port 4318)
```

## Key Benefits

1. ✅ No browser permission prompts
2. ✅ Collector stays private (not exposed to internet)
3. ✅ Graceful degradation if collector is down
4. ✅ Same-origin requests (no CORS complexity)
5. ✅ Ready for future Web Vitals and error logging
6. ✅ Fast timeouts (won't slow down frontend)
7. ✅ Production-ready error handling

## Future Enhancements (Phase 2)

When ready, you can add:

1. **Web Vitals collection** - Already have `/api/v1/metrics` endpoint
2. **Frontend error logging** - Already have `/api/v1/logs` endpoint
3. **Rate limiting** - Use `slowapi` to prevent abuse
4. **Enhanced request correlation** - Already supported via traceparent headers

## Troubleshooting

### Backend logs show "OTel collector unavailable"

**Cause:** Collector is not reachable at `localhost:4318`

**Solution:**
- Check if collector is running: `docker ps | grep otel-collector`
- Verify collector port mapping includes 4318 (HTTP endpoint)
- Check `OTEL_COLLECTOR_URL` in `.env`

### Frontend not sending traces

**Cause:** Frontend might still be using old localhost URL

**Solution:**
- Clear browser cache
- Rebuild frontend: `npm run build`
- Check DevTools Network tab for POST requests to `/api/v1/traces`
- Verify `VITE_OTEL_ENABLED` is not set to `false`

### 502 Bad Gateway on /api/v1/traces

**Cause:** Backend can't reach the collector

**Solution:**
- If using Docker, verify network connectivity
- Check collector URL in backend logs
- Try `curl http://localhost:4318/v1/traces` from backend container/host

## Files Modified

| File | Change |
|------|--------|
| `backend/app/routers/otel_proxy.py` | ✅ Created - New proxy router |
| `backend/app/config.py` | ✅ Added telemetry proxy settings |
| `backend/app/main.py` | ✅ Added router + lifespan manager |
| `frontend/src/lib/tracing.ts` | ✅ Updated collector URL logic |

## Next Steps

1. ✅ Implementation complete
2. Test locally with the instructions above
3. Deploy to staging/production
4. Monitor backend logs for any collector warnings
5. Verify traces appear in SigNoz
6. Consider adding Web Vitals and error logging (Phase 2)
