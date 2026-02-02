# Session Log

Track learning, context, and summaries for each work session. Complements `/tasks` for work item tracking.

---

## Template

```markdown
## YYYY-MM-DD: [Brief Title]

**Goal:** What you wanted to accomplish
**Outcome:** What actually happened
**Learned:** Key concepts, patterns, or design decisions
**Tasks:** #1, #3 (reference completed task IDs)
**Next:** What to do in the next session
**Total cost:**Total cost for the session
**Total duration (API):** Total duration (API)
**Total duration (wall):** Total duration (wall)
**Total code changes:**    Total code changes
**Usage by model:**
        **model-name:**  input tokens, output token, cache read, cache write ($cost)
```

---

## Sessions

### 2026-02-02: Observability Migration to Official SigNoz + Telemetry Troubleshooting

**Goal:**
1. Migrate from custom observability stack to official SigNoz deployment
2. Verify telemetry is flowing from backend to SigNoz locally

**Outcome:**
- ✅ **Migration Complete**: Successfully implemented migration plan from custom `docker-compose.observability.yml` to official SigNoz standalone deployment
  - Created `.github/workflows/deploy-signoz.yml` for independent SigNoz deployment
  - Updated `docker-compose.prod.yml` and `docker-compose.local.yml` with multi-network architecture (app-network + signoz-net)
  - Backend now connects to both networks for application services and observability
  - Added automatic TLS detection in `backend/app/observability/tracing.py` (line 204)
  - Comprehensive documentation updates across `docs/observability/`, `docs/deployment/`, and `README.md`
  - Created `MIGRATION_SUMMARY.md` with complete migration guide
  - Created `scripts/verify-observability.sh` for automated verification

- ⚠️ **Telemetry Issue Discovered**: Manual OTLP export works, but FastAPI auto-instrumentation does NOT create spans
  - ✅ OTLP export pipeline verified working (test-service appeared in SigNoz)
  - ✅ SigNoz collector receiving traces on port 4317
  - ✅ Backend connected to both `app-network` and `signoz-net`
  - ✅ TCP connectivity from backend to collector works
  - ✅ TracerProvider set globally
  - ❌ FastAPI auto-instrumentation not creating spans for `rag-admin-backend` service

**Learned:**
1. **Multi-Network Architecture**: Backend can connect to multiple Docker networks simultaneously, enabling clean separation between app services and observability infrastructure
2. **OTLP Pipeline Verification**: Manual span creation/export is the best way to isolate infrastructure issues from instrumentation issues
3. **FastAPI Instrumentation Challenge**: The OpenTelemetry FastAPI instrumentation is complex and has timing/ordering requirements that aren't well documented

**FastAPI Instrumentation Attempts** (all failed to create spans):
1. ❌ **Standard `FastAPIInstrumentor.instrument_app(app)`**: Called in startup event, logged "enabled" but `is_instrumented_by_opentelemetry` returned False
2. ❌ **With error handling and verification**: Added try/catch and verification check, no errors thrown but still not instrumented
3. ❌ **Direct middleware addition**: Used `app.add_middleware(OpenTelemetryMiddleware)` instead of instrumentor
4. ❌ **Explicit tracer provider**: Passed `tracer_provider=trace.get_tracer_provider()` to middleware

**Root Cause Hypothesis**:
- FastAPI instrumentation requires middleware to be added BEFORE app starts serving requests
- Calling instrumentation in `@app.on_event("startup")` may be too late
- The instrumentor's `is_instrumented_by_opentelemetry` property suggests instrumentation isn't being applied despite no errors

**Infrastructure Status**:
- ✅ SigNoz running and healthy (4 containers)
- ✅ Collector listening on 0.0.0.0:4317 (gRPC)
- ✅ Network topology correct
- ✅ Manual traces working (test-service visible)
- ❌ FastAPI auto-instrumentation not working (rag-admin-backend not visible)

**Tasks:** N/A (tracking in separate observability-refactor task file)
**Next:**
1. Try instrumenting FastAPI at module level instead of in startup event
2. Consider alternative instrumentation approaches (manual span creation in middleware)
3. Check OpenTelemetry version compatibility
4. Review FastAPI instrumentor source code for timing requirements

### 2026-02-02: Workflow System Setup

**Goal:** Implement lightweight workflow recommendations for learning + traceability
**Outcome:** Created session log, updated docs/workflow/README.md and claude.md
**Learned:** Dual tracking (tasks for work items, session log for context/learning) provides better traceability than either alone
**Tasks:** N/A (planning session)
**Next:** Test the workflow with an Explore or Implement session
