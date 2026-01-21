#!/bin/bash
set -e

echo "==================================="
echo "RAG Admin - Project Setup"
echo "==================================="
echo ""

if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed!"
    echo ""
    echo "Please install Python 3.12 from:"
    echo "  - Official: https://www.python.org/downloads/"
    echo "  - Ubuntu/Debian: sudo apt install python3.12 python3.12-venv"
    echo "  - macOS: brew install python@3.12"
    echo "  - Windows: Download from python.org or use Microsoft Store"
    echo ""
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
echo "✓ Found Python $PYTHON_VERSION"

if ! command -v uv &> /dev/null; then
    echo "❌ uv is not installed!"
    echo ""
    echo "Please install uv from:"
    echo "  - Linux/macOS/WSL: curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo "  - Windows: powershell -c \"irm https://astral.sh/uv/install.ps1 | iex\""
    echo "  - Or visit: https://docs.astral.sh/uv/getting-started/installation/"
    echo ""
    echo "After installation, restart your terminal and run this script again."
    exit 1
fi

UV_VERSION=$(uv --version)
echo "✓ Found $UV_VERSION"

if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed!"
    echo "Please install Node.js 18+ from https://nodejs.org/"
    exit 1
fi

NODE_VERSION=$(node --version)
echo "✓ Found Node.js $NODE_VERSION"
echo ""

echo "Setting up backend..."
cd backend

echo "Installing Python dependencies with uv..."
uv sync --all-extras

if [ ! -f ".env" ]; then
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo "⚠️  Please edit backend/.env with your configuration"
fi

cd ..

echo ""
echo "Setting up frontend..."
cd frontend

echo "Installing Node.js dependencies..."
npm install

cd ..

echo ""
echo "==================================="
echo "✓ Setup complete!"
echo "==================================="
echo ""
echo "Next steps:"
echo "  1. Start PostgreSQL: docker compose up -d"
echo "  2. Edit backend/.env if needed"
echo "  3. Run migrations: cd backend && uv run alembic upgrade head"
echo "  4. Start dev servers: ./scripts/dev.sh"
echo ""
