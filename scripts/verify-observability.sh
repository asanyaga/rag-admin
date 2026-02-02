#!/bin/bash
# Verify observability setup after migration
# Usage: ./scripts/verify-observability.sh

set -e

echo "=========================================="
echo "Observability Migration Verification"
echo "=========================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

success() {
    echo -e "${GREEN}✓${NC} $1"
}

warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

error() {
    echo -e "${RED}✗${NC} $1"
}

# Check 1: SigNoz is running
echo "1. Checking if SigNoz is running..."
if docker ps --format '{{.Names}}' | grep -q "signoz"; then
    success "SigNoz containers are running"
    docker ps --format 'table {{.Names}}\t{{.Status}}' | grep signoz
else
    error "SigNoz is not running"
    echo "   Install with: git clone https://github.com/SigNoz/signoz.git ~/signoz"
    echo "   Then: cd ~/signoz/deploy/docker && docker compose up -d"
    exit 1
fi
echo ""

# Check 2: signoz-net network exists
echo "2. Checking if signoz-net network exists..."
if docker network inspect signoz-net > /dev/null 2>&1; then
    success "signoz-net network exists"
else
    error "signoz-net network not found"
    echo "   This should be created by SigNoz deployment"
    exit 1
fi
echo ""

# Check 3: RAG Admin backend is running
echo "3. Checking if RAG Admin backend is running..."
if docker ps --format '{{.Names}}' | grep -q "rag-admin-backend"; then
    BACKEND_CONTAINER=$(docker ps --format '{{.Names}}' | grep rag-admin-backend | head -1)
    success "Backend container found: $BACKEND_CONTAINER"
else
    warning "Backend container not found (not deployed yet?)"
    echo "   Deploy with: docker compose -f docker-compose.prod.yml up -d"
    echo "   Or local: docker compose -f docker-compose.local.yml up -d"
    exit 0
fi
echo ""

# Check 4: Backend is on both networks
echo "4. Checking if backend is connected to both networks..."
BACKEND_CONTAINER=$(docker ps --format '{{.Names}}' | grep rag-admin-backend | head -1)
NETWORKS=$(docker inspect $BACKEND_CONTAINER | grep -o '"Name": "[^"]*network[^"]*"' | cut -d'"' -f4 | sort)

if echo "$NETWORKS" | grep -q "app-network"; then
    success "Backend connected to app-network"
else
    error "Backend NOT connected to app-network"
fi

if echo "$NETWORKS" | grep -q "signoz-net"; then
    success "Backend connected to signoz-net"
else
    error "Backend NOT connected to signoz-net"
    echo "   Redeploy backend: docker compose up -d --force-recreate backend"
fi
echo ""

# Check 5: Backend can reach collector
echo "5. Checking if backend can reach OTel Collector..."
if docker exec $BACKEND_CONTAINER curl -s --max-time 5 http://signoz-otel-collector:4317 > /dev/null 2>&1; then
    success "Backend can reach signoz-otel-collector:4317"
elif docker exec $BACKEND_CONTAINER nc -z signoz-otel-collector 4317 2>/dev/null; then
    success "Backend can reach signoz-otel-collector:4317 (via netcat)"
else
    error "Backend CANNOT reach signoz-otel-collector:4317"
    echo "   Check: docker exec $BACKEND_CONTAINER ping signoz-otel-collector"
fi
echo ""

# Check 6: Backend can reach database
echo "6. Checking if backend can reach PostgreSQL..."
if docker exec $BACKEND_CONTAINER nc -z postgres 5432 2>/dev/null; then
    success "Backend can reach postgres:5432"
else
    error "Backend CANNOT reach postgres:5432"
fi
echo ""

# Check 7: Check observability environment variables
echo "7. Checking observability environment variables..."
OTEL_ENABLED=$(docker exec $BACKEND_CONTAINER env | grep "OTEL_ENABLED=" | cut -d'=' -f2)
OTEL_ENDPOINT=$(docker exec $BACKEND_CONTAINER env | grep "OTEL_EXPORTER_ENDPOINT=" | cut -d'=' -f2)

if [ "$OTEL_ENABLED" = "True" ]; then
    success "OTEL_ENABLED=True"
else
    warning "OTEL_ENABLED=$OTEL_ENABLED (telemetry disabled)"
fi

if [ -n "$OTEL_ENDPOINT" ]; then
    success "OTEL_EXPORTER_ENDPOINT=$OTEL_ENDPOINT"
else
    error "OTEL_EXPORTER_ENDPOINT not set"
fi
echo ""

# Check 8: Check backend logs for observability initialization
echo "8. Checking backend logs for observability initialization..."
if docker logs $BACKEND_CONTAINER 2>&1 | grep -q "Observability initialization complete"; then
    success "Backend initialized observability successfully"
elif docker logs $BACKEND_CONTAINER 2>&1 | grep -q "Observability is disabled"; then
    warning "Observability is disabled (OTEL_ENABLED=False)"
else
    warning "Cannot confirm observability initialization (check logs manually)"
fi
echo ""

# Check 9: SigNoz UI is accessible
echo "9. Checking if SigNoz UI is accessible..."
if curl -sf http://localhost:8080/api/v1/health > /dev/null 2>&1; then
    success "SigNoz UI is accessible at http://localhost:8080"
elif curl -sf http://localhost:3301/api/v1/health > /dev/null 2>&1; then
    success "SigNoz UI is accessible at http://localhost:3301"
else
    warning "Cannot reach SigNoz UI (may need SSH tunnel for remote)"
    echo "   For remote access: ssh -L 8080:localhost:8080 user@yourserver"
fi
echo ""

# Summary
echo "=========================================="
echo "Verification Summary"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Generate test traffic: curl http://localhost:8000/health"
echo "2. Check SigNoz UI: http://localhost:8080"
echo "3. Navigate to: Traces → Filter by service: rag-admin-backend"
echo "4. You should see traces within 1-2 minutes"
echo ""
echo "For troubleshooting, see: docs/observability/README.md"
echo ""
