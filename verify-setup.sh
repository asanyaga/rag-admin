#!/bin/bash
# Deployment Verification Script
# Run this before deploying to verify all configuration files are present

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "================================================"
echo "RAG Admin - Deployment Configuration Verification"
echo "================================================"
echo ""

ERRORS=0
WARNINGS=0

# Function to check file exists
check_file() {
    local file=$1
    local type=${2:-"required"}

    if [ -f "$file" ]; then
        echo -e "${GREEN}✓${NC} Found: $file"
        return 0
    else
        if [ "$type" = "required" ]; then
            echo -e "${RED}✗${NC} Missing (REQUIRED): $file"
            ERRORS=$((ERRORS + 1))
        else
            echo -e "${YELLOW}⚠${NC} Missing (optional): $file"
            WARNINGS=$((WARNINGS + 1))
        fi
        return 1
    fi
}

# Function to check directory exists
check_dir() {
    local dir=$1

    if [ -d "$dir" ]; then
        echo -e "${GREEN}✓${NC} Found: $dir/"
        return 0
    else
        echo -e "${RED}✗${NC} Missing directory: $dir/"
        ERRORS=$((ERRORS + 1))
        return 1
    fi
}

echo "Checking Docker configuration files..."
echo "--------------------------------------"
check_file "docker-compose.prod.yml"
check_file "backend/Dockerfile"
check_file "backend/entrypoint.sh"
check_file "backend/.dockerignore"
check_file "frontend/.dockerignore"
check_file "caddy/Caddyfile"
check_file "docker/init-db.sql"

# Optional reference files (not used in production)
if [ -f "frontend/Dockerfile.nginx-reference" ]; then
    echo -e "${GREEN}✓${NC} Found: frontend/Dockerfile.nginx-reference (reference only, not used)"
fi
if [ -f "frontend/nginx.conf.reference" ]; then
    echo -e "${GREEN}✓${NC} Found: frontend/nginx.conf.reference (reference only, not used)"
fi
echo ""

echo "Checking scripts and configuration..."
echo "-------------------------------------"
check_file ".env.prod.example"
check_file "backup.sh"

if ! check_file ".env.prod" "optional"; then
    echo -e "  ${YELLOW}→${NC} Create .env.prod from .env.prod.example before deployment"
fi
echo ""

echo "Checking documentation..."
echo "-------------------------"
check_file "DEPLOYMENT.md" "optional"
check_file "DOCKER.md" "optional"
echo ""

echo "Checking directory structure..."
echo "-------------------------------"
check_dir "backend"
check_dir "frontend"
check_dir "caddy"
check_dir "docker"
check_dir "backend/app"
check_dir "frontend/src"

# Check for built frontend
if ! check_dir "frontend/dist"; then
    echo -e "  ${YELLOW}→${NC} Build frontend before deployment: cd frontend && npm run build"
fi
echo ""

echo "Checking file permissions..."
echo "---------------------------"
if [ -f "backend/entrypoint.sh" ]; then
    if [ -x "backend/entrypoint.sh" ]; then
        echo -e "${GREEN}✓${NC} backend/entrypoint.sh is executable"
    else
        echo -e "${YELLOW}⚠${NC} backend/entrypoint.sh is not executable (will be set in container)"
    fi
fi

if [ -f "backup.sh" ]; then
    if [ -x "backup.sh" ]; then
        echo -e "${GREEN}✓${NC} backup.sh is executable"
    else
        echo -e "${RED}✗${NC} backup.sh is not executable"
        echo -e "  ${YELLOW}→${NC} Run: chmod +x backup.sh"
        ERRORS=$((ERRORS + 1))
    fi
fi
echo ""

# Check for placeholder values in .env.prod if it exists
if [ -f ".env.prod" ]; then
    echo "Checking .env.prod configuration..."
    echo "-----------------------------------"

    if grep -q "CHANGE_THIS" .env.prod; then
        echo -e "${RED}✗${NC} .env.prod contains placeholder values (CHANGE_THIS)"
        echo -e "  ${YELLOW}→${NC} Generate secure values before deployment"
        ERRORS=$((ERRORS + 1))
    else
        echo -e "${GREEN}✓${NC} No placeholder values found in .env.prod"
    fi

    if grep -q "yourdomain.com" .env.prod; then
        echo -e "${YELLOW}⚠${NC} .env.prod contains 'yourdomain.com'"
        echo -e "  ${YELLOW}→${NC} Replace with your actual domain"
        WARNINGS=$((WARNINGS + 1))
    else
        echo -e "${GREEN}✓${NC} Domain configured in .env.prod"
    fi
    echo ""
fi

# Check Caddyfile for domain placeholder
if [ -f "caddy/Caddyfile" ]; then
    echo "Checking Caddyfile configuration..."
    echo "-----------------------------------"

    if grep -q "yourdomain.com" caddy/Caddyfile; then
        echo -e "${YELLOW}⚠${NC} Caddyfile contains 'yourdomain.com' placeholder"
        echo -e "  ${YELLOW}→${NC} Replace with your actual domain before deployment"
        WARNINGS=$((WARNINGS + 1))
    else
        echo -e "${GREEN}✓${NC} Domain configured in Caddyfile"
    fi
    echo ""
fi

# Check Docker is installed (if we're on the VPS)
echo "Checking system requirements..."
echo "-------------------------------"
if command -v docker &> /dev/null; then
    DOCKER_VERSION=$(docker --version | awk '{print $3}' | sed 's/,//')
    echo -e "${GREEN}✓${NC} Docker is installed (version $DOCKER_VERSION)"

    if command -v docker compose &> /dev/null; then
        echo -e "${GREEN}✓${NC} Docker Compose plugin is installed"
    else
        echo -e "${RED}✗${NC} Docker Compose plugin is not installed"
        echo -e "  ${YELLOW}→${NC} Install with: sudo apt-get install docker-compose-plugin"
        ERRORS=$((ERRORS + 1))
    fi
else
    echo -e "${YELLOW}⚠${NC} Docker is not installed (OK if checking locally)"
    echo -e "  ${YELLOW}→${NC} Install on VPS with: curl -fsSL https://get.docker.com | sh"
fi
echo ""

# Summary
echo "================================================"
echo "Verification Summary"
echo "================================================"

if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo -e "${GREEN}✓ All checks passed!${NC}"
    echo "You're ready to deploy."
    exit 0
elif [ $ERRORS -eq 0 ]; then
    echo -e "${YELLOW}⚠ $WARNINGS warning(s) found${NC}"
    echo "Review warnings before deployment."
    exit 0
else
    echo -e "${RED}✗ $ERRORS error(s) found${NC}"
    if [ $WARNINGS -gt 0 ]; then
        echo -e "${YELLOW}⚠ $WARNINGS warning(s) found${NC}"
    fi
    echo "Fix errors before deployment."
    exit 1
fi
