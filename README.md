# RAG Admin

Web application for creating and managing RAG pipelines. Learning/portfolio project—prioritize clean architecture and readability.

## Stack

- **Backend:** Python 3.12, FastAPI (async), SQLAlchemy 2.0, PostgreSQL, Alembic
- **Frontend:** React 18, TypeScript, Vite
- **Auth:** JWT + HTTP-only refresh tokens, Google OAuth

## Project Structure

```
rag-admin/
├── backend/
│   ├── app/
│   │   ├── models/         # SQLAlchemy models
│   │   ├── schemas/        # Pydantic schemas
│   │   ├── routers/        # API routes
│   │   ├── services/       # Business logic
│   │   ├── repositories/   # Database operations
│   │   ├── dependencies/   # FastAPI dependencies
│   │   └── utils/          # Utility functions
│   ├── tests/              # Backend tests
│   └── alembic/            # Database migrations
├── frontend/
│   └── src/
│       ├── api/            # API client
│       ├── contexts/       # React contexts
│       ├── hooks/          # Custom hooks
│       ├── pages/          # Page components
│       ├── components/     # Reusable components
│       └── types/          # TypeScript types
└── scripts/                # Development scripts
```

## Prerequisites

Before you begin, ensure you have the following installed:

### 1. Python 3.12

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install python3.12 python3.12-venv python3-pip
```

**macOS:**
```bash
brew install python@3.12
```

**Windows:**
- Download from [python.org](https://www.python.org/downloads/)
- Or install via Microsoft Store
- Make sure to check "Add Python to PATH" during installation

**Verify installation:**
```bash
python3 --version  # Should show Python 3.12.x
```

### 2. uv (Python Package Manager)

**Linux/macOS/WSL:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows:**
```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

After installation, restart your terminal.

**Verify installation:**
```bash
uv --version  # Should show uv version
```

For more installation options, visit: https://docs.astral.sh/uv/getting-started/installation/

### 3. Node.js 18+

You have Node.js 22+ installed.

**Verify installation:**
```bash
node --version  # Should show v18.x or higher
```

### 4. Docker & Docker Compose

**Ubuntu/Debian:**
```bash
sudo apt install docker.io docker-compose
sudo systemctl start docker
sudo usermod -aG docker $USER  # Log out and back in after this
```

**macOS:**
- Download and install [Docker Desktop for Mac](https://www.docker.com/products/docker-desktop/)

**Windows:**
- Download and install [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/)

**Verify installation:**
```bash
docker --version
docker compose version
```

## Quick Start

### 1. Clone and Setup

```bash
# Navigate to the project directory
cd rag-admin

# Run the setup script
./scripts/setup.sh
```

The setup script will:
- Check for Python, uv, and Node.js
- Install Python dependencies using uv (creates `.venv` automatically)
- Install Node.js dependencies
- Create `.env` file from template

### 2. (Optional) Install SigNoz for Observability

For local development with full observability (traces, logs, metrics):

```bash
# Clone SigNoz repository
git clone https://github.com/SigNoz/signoz.git ~/signoz
cd ~/signoz/deploy/docker

# Deploy SigNoz
docker compose up -d

# Verify it's running
docker compose ps
```

SigNoz UI: http://localhost:8080

**Note:** This is optional. The application works fine without observability.

### 3. Configure Environment

Edit `backend/.env` with your settings:

```bash
# Database (default works with docker-compose.yml)
DATABASE_URL=postgresql+asyncpg://ragadmin:ragadmin_dev@localhost:5432/ragadmin

# JWT - IMPORTANT: Change in production!
JWT_SECRET_KEY=your-secure-random-key-here

# Google OAuth (optional, for Google sign-in)
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret

# Observability (optional)
OTEL_ENABLED=True
OTEL_EXPORTER_ENDPOINT=http://localhost:4317
```

### 4. Start PostgreSQL

```bash
docker compose up -d
```

Verify it's running:
```bash
docker compose ps
```

### 4. Run Database Migrations

```bash
cd backend
uv run alembic upgrade head
cd ..
```

### 5. Start Development Servers

```bash
./scripts/dev.sh
```

This will start:
- **Backend:** http://localhost:8000
- **Frontend:** http://localhost:5173
- **API Docs:** http://localhost:8000/docs
- **SigNoz UI:** http://localhost:8080 (if installed)

## Development Commands

### Backend

```bash
cd backend

# Start server
uv run uvicorn app.main:app --reload

# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=app --cov-report=html

# Create migration
uv run alembic revision --autogenerate -m "description"

# Run migrations
uv run alembic upgrade head

# Rollback migration
uv run alembic downgrade -1

# Add a new dependency
uv add <package-name>

# Add a development dependency
uv add --dev <package-name>

# Update dependencies
uv sync

# Update a specific package
uv add --upgrade <package-name>
```

### Frontend

```bash
cd frontend

# Start dev server
npm run dev

# Build for production
npm run build

# Lint code
npm run lint

# Format code
npm run format
```

### Database

```bash
# Start PostgreSQL
docker compose up -d

# Stop PostgreSQL
docker compose down

# View logs
docker compose logs -f postgres

# Reset database (WARNING: deletes all data)
docker compose down -v
docker compose up -d
```

## Development Patterns

### Backend

- **Data flow:** router → service → repository → database
- Services raise exceptions; routers catch and return HTTP responses
- All database operations are async
- Type hints on all functions
- Read the relevant spec in `docs/planning/` before implementing features

### Frontend

- Component-based architecture
- Use custom hooks for shared logic
- API calls through centralized `apiClient`
- TypeScript strict mode enabled
- Use path alias `@/` for imports from `src/`

## Current Phase

✅ **Project Scaffold** (Complete)
✅ **Authentication Implementation** (Complete)
✅ **Docker Deployment** (Complete)
🔄 **CI/CD Pipeline** (Next)

## Deployment

### Production Deployment

For deploying to a VPS with Docker:

- 📖 **[docs/deployment/](docs/deployment/)** - Complete deployment guide
- 📋 **[docs/deployment/checklist.md](docs/deployment/checklist.md)** - Deployment checklist
- 🐳 **[docs/deployment/docker.md](docs/deployment/docker.md)** - Docker architecture and configuration
- 🔄 **[docs/deployment/ci-cd.md](docs/deployment/ci-cd.md)** - GitHub Actions CI/CD setup

Quick start:
```bash
# 1. Build frontend
cd frontend && npm run build

# 2. Transfer to VPS
scp -r dist user@vps:~/rag-admin/frontend/

# 3. Deploy
ssh user@vps
cd ~/rag-admin
docker compose -f docker-compose.prod.yml up -d
```

### Automated Deployment (CI/CD)

Set up GitHub Actions for automated testing and deployment:

- See **[docs/deployment/ci-cd.md](docs/deployment/ci-cd.md)** for complete CI/CD setup
- Automated testing on every push
- Automated deployment to production on merge to main
- Daily health checks and backups

### Architecture

- **3 containers**: PostgreSQL (ParadeDB), FastAPI Backend, Caddy (reverse proxy + static files)
- **Automatic HTTPS**: Let's Encrypt via Caddy
- **Database**: PostgreSQL with pgvector and pg_search extensions
- **Backups**: Automated daily backups with 7-day retention

See [docs/architecture/](docs/architecture/) for deployment architecture details.

## Troubleshooting

### Port Already in Use

If ports 8000 or 5173 are in use:

```bash
# Find process using port
lsof -i :8000  # or :5173

# Kill process
kill -9 <PID>
```

### Database Connection Error

1. Ensure PostgreSQL is running: `docker compose ps`
2. Check DATABASE_URL in `backend/.env`
3. Verify credentials match `docker-compose.yml`

### Python Dependency Issues

```bash
# Remove and reinstall dependencies
cd backend
rm -rf .venv uv.lock
uv sync --all-extras
```

### Frontend Dependencies Issues

```bash
# Clear and reinstall
cd frontend
rm -rf node_modules package-lock.json
npm install
```

## Contributing

This is a learning/portfolio project. Focus on:
- Clean, readable code
- Proper layering and separation of concerns
- Comprehensive type hints and types
- Clear commit messages
- Tests for new features

## License

MIT
