#!/bin/bash
# Test script to verify distributed tracing is working
#
# Usage:
#   ./scripts/test-tracing.sh

set -e

echo "======================================================================"
echo " OpenTelemetry Tracing Test"
echo "======================================================================"
echo ""

# Check if backend is running
echo "1. Checking if backend is running..."
if curl -s -f http://localhost:8000/health > /dev/null 2>&1; then
    echo "   ✓ Backend is running"
else
    echo "   ✗ Backend is not running!"
    echo "   → Start with: docker compose -f docker-compose.local.yml up -d"
    exit 1
fi

# Check if SigNoz is running
echo ""
echo "2. Checking if SigNoz is running..."
if curl -s -f http://localhost:8080/api/v1/health > /dev/null 2>&1; then
    echo "   ✓ SigNoz is running"
else
    echo "   ✗ SigNoz is not running!"
    echo "   → Start with: cd ~/signoz/deploy/docker && docker compose up -d"
    exit 1
fi

# Run diagnostic script
echo ""
echo "3. Running instrumentation diagnostic..."
echo "======================================================================"
docker exec rag-admin-backend-local python /app/diagnose_instrumentation.py
echo "======================================================================"

# Generate test traffic
echo ""
echo "4. Generating test traffic..."

# Health check
echo "   - GET /health"
curl -s http://localhost:8000/health > /dev/null

# Auth health
echo "   - GET /api/v1/auth/health (if exists)"
curl -s http://localhost:8000/api/v1/auth/health > /dev/null 2>&1 || true

# Root endpoint
echo "   - GET /"
curl -s http://localhost:8000/ > /dev/null

echo "   ✓ Test traffic sent"

# Wait for batch export
echo ""
echo "5. Waiting for spans to be exported (10 seconds)..."
for i in {10..1}; do
    echo -ne "   $i...\r"
    sleep 1
done
echo "   ✓ Export window complete"

# Instructions for verification
echo ""
echo "======================================================================"
echo " Verification Steps"
echo "======================================================================"
echo ""
echo "1. Open SigNoz UI: http://localhost:8080"
echo ""
echo "2. Navigate to: Traces → Services"
echo "   → Look for service: rag-admin-backend"
echo ""
echo "3. Click on a recent trace"
echo "   → You should see spans for:"
echo "     - HTTP requests (GET /health, etc.)"
echo "     - Database queries (if any)"
echo "     - Manual spans (authenticate_user, etc.)"
echo ""
echo "4. Check span hierarchy:"
echo "   HTTP Request (parent)"
echo "   └── Business Logic (child)"
echo "       └── Database Query (grandchild)"
echo ""
echo "======================================================================"
echo " Trace Attributes to Look For"
echo "======================================================================"
echo ""
echo "HTTP Spans should have:"
echo "  - http.method (GET, POST, etc.)"
echo "  - http.route (/health, /api/v1/auth/signin)"
echo "  - http.status_code (200, 404, etc.)"
echo ""
echo "Database Spans should have:"
echo "  - db.system (postgresql)"
echo "  - db.statement (SQL query)"
echo ""
echo "Manual Spans (auth.py) should have:"
echo "  - auth.email"
echo "  - auth.method"
echo "  - auth.success"
echo ""
echo "======================================================================"
echo ""
echo "If traces don't appear, check:"
echo "  1. Backend logs: docker logs rag-admin-backend-local"
echo "  2. Collector logs: docker logs signoz-otel-collector"
echo "  3. Diagnostic output above"
echo ""
echo "For troubleshooting: docs/observability/README.md#troubleshooting"
echo ""
