#!/bin/bash
# Test script to verify telemetry is flowing to SigNoz
# Usage: ./test-telemetry.sh

echo "====================================="
echo "Telemetry Test Script"
echo "====================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}Step 1: Generating test traffic...${NC}"
echo "Sending 20 requests to various endpoints..."

for i in {1..20}; do
    curl -s http://localhost:8000/health > /dev/null
    curl -s http://localhost:8000/docs > /dev/null
    echo -n "."
done
echo ""
echo -e "${GREEN}✓${NC} 20 requests sent"
echo ""

echo -e "${BLUE}Step 2: Waiting for batch export...${NC}"
echo "OpenTelemetry batches spans and exports them every 5 seconds."
echo "Waiting 15 seconds to ensure export happens..."
sleep 15
echo -e "${GREEN}✓${NC} Export window complete"
echo ""

echo -e "${BLUE}Step 3: Checking SigNoz UI${NC}"
echo ""
echo "Open SigNoz UI in your browser:"
echo -e "  ${YELLOW}http://localhost:8080${NC}"
echo ""
echo "Then navigate to:"
echo "  1. Click '${YELLOW}Traces${NC}' in the left sidebar"
echo "  2. In the filters, set: ${YELLOW}service = rag-admin-backend${NC}"
echo "  3. Set time range to: ${YELLOW}Last 15 minutes${NC}"
echo ""
echo "You should see traces for:"
echo "  - GET /health"
echo "  - GET /docs"
echo "  - GET /openapi.json"
echo ""

echo -e "${BLUE}Step 4: Verify trace details${NC}"
echo ""
echo "Click on any trace to see:"
echo "  • ${YELLOW}Span name:${NC} HTTP GET /health"
echo "  • ${YELLOW}Duration:${NC} A few milliseconds"
echo "  • ${YELLOW}Attributes:${NC} http.method, http.route, http.status_code, etc."
echo ""

echo -e "${BLUE}Step 5: Check service list${NC}"
echo ""
echo "In SigNoz UI:"
echo "  1. Click '${YELLOW}Services${NC}' in the left sidebar"
echo "  2. Look for: ${YELLOW}rag-admin-backend${NC}"
echo "  3. You should see request rate, error rate, and latency metrics"
echo ""

echo "====================================="
echo "Troubleshooting"
echo "====================================="
echo ""
echo "If you DON'T see traces:"
echo ""
echo "1. Check backend logs:"
echo "   docker logs rag-admin-backend-local | grep -i error"
echo ""
echo "2. Check collector logs:"
echo "   docker logs signoz-otel-collector --tail 50"
echo ""
echo "3. Verify network connectivity:"
echo "   docker exec rag-admin-backend-local python -c 'import socket; s=socket.socket(); s.connect((\"signoz-otel-collector\", 4317)); print(\"Connected\")'"
echo ""
echo "4. Check backend observability settings:"
echo "   docker exec rag-admin-backend-local env | grep OTEL"
echo ""
echo "5. Run full verification:"
echo "   ./scripts/verify-observability.sh"
echo ""
