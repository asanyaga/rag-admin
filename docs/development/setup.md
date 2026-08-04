# Development Setup

Detailed setup, tooling, and troubleshooting for running RAG Admin locally. For a fast path, see the [Quickstart in the README](../../README.md#quickstart-self-host). This guide covers the full details for each prerequisite and common problems.

## Prerequisites

Install the following before you begin.

### 1. Python 3.12

**Ubuntu/Debian**
```bash
sudo apt update
sudo apt install python3.12 python3.12-venv python3-pip
```

**macOS**
```bash
brew install python@3.12
```

**Windows**
- Download from [python.org](https://www.python.org/downloads/), or install via the Microsoft Store.
- Make sure to check **"Add Python to PATH"** during installation.

Verify:
```bash
python3 --version  # Should show Python 3.12.x
```

### 2. uv (Python package manager)

**Linux/macOS/WSL**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows (PowerShell)**
```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Restart your terminal after installation, then verify:
```bash
uv --version
```

More options: https://docs.astral.sh/uv/getting-started/installation/

### 3. Node.js 18+

Install Node.js 18 or newer (22 LTS recommended) from [nodejs.org](https://nodejs.org/) or via a version manager such as `nvm`/`fnm`.

Verify:
```bash
node --version  # v18.x or higher
```

### 4. Docker & Docker Compose

**Ubuntu/Debian**
```bash
sudo apt install docker.io docker-compose
sudo systemctl start docker
sudo usermod -aG docker $USER  # Log out and back in after this
```

**macOS / Windows**
- Install [Docker Desktop](https://www.docker.com/products/docker-desktop/).

Verify:
```bash
docker --version
docker compose version
```

## First-time setup

From the repository root:

```bash
./scripts/setup.sh
```

The setup script will:
- Check for Python, uv, and Node.js
- Install Python dependencies with uv (creates `.venv` automatically)
- Install Node.js dependencies
- Create the `.env` file from the template

### Configure environment

Edit `backend/.env` with your settings:

```bash
# Database (default works with docker-compose.yml)
DATABASE_URL=postgresql+asyncpg://ragadmin:ragadmin_dev@localhost:5432/ragadmin

# JWT — IMPORTANT: change in production!
JWT_SECRET_KEY=your-secure-random-key-here

# Google OAuth (optional, for Google sign-in)
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret

# Observability (optional)
OTEL_ENABLED=True
OTEL_EXPORTER_ENDPOINT=http://localhost:4317
```

### Start the database and run migrations

```bash
docker compose up -d          # start PostgreSQL (ParadeDB)
docker compose ps             # verify it's running

cd backend
uv run alembic upgrade head   # apply migrations
cd ..
```

### Start the development servers

```bash
./scripts/dev.sh
```

This starts:
- **Backend:** http://localhost:8000
- **Frontend:** http://localhost:5173
- **API docs:** http://localhost:8000/docs
- **SigNoz UI:** http://localhost:8080 (if installed — see below)

## Observability (optional)

For local development with full observability (traces, logs, metrics), run SigNoz alongside the app. The application works fine without it.

```bash
# Clone SigNoz
git clone https://github.com/SigNoz/signoz.git ~/signoz
cd ~/signoz/deploy/docker

# Deploy
docker compose up -d
docker compose ps
```

SigNoz UI: http://localhost:8080

See [docs/observability/](../observability/) for more.

## Command reference

### Backend

```bash
cd backend

# Start server
uv run uvicorn app.main:app --reload

# Run tests (addopts is cleared so coverage/strict-markers config doesn't interfere)
uv run python -m pytest -o "addopts="

# Run tests with coverage
uv run pytest --cov=app --cov-report=html

# Create a migration
uv run alembic revision --autogenerate -m "description"

# Apply / roll back migrations
uv run alembic upgrade head
uv run alembic downgrade -1

# Dependencies
uv add <package-name>            # add a dependency
uv add --dev <package-name>      # add a dev dependency
uv sync                          # sync from lockfile
uv add --upgrade <package-name>  # upgrade a package
```

### Frontend

```bash
cd frontend

npm run dev      # start dev server
npm run build    # build for production
npm run lint     # lint
npm run format   # format
npx vitest run   # run tests
```

### Database

```bash
docker compose up -d                 # start PostgreSQL
docker compose down                  # stop PostgreSQL
docker compose logs -f postgres      # view logs

# Reset database (WARNING: deletes all data)
docker compose down -v
docker compose up -d
```

## Troubleshooting

### Port already in use

If ports 8000 or 5173 are in use:

```bash
lsof -i :8000   # or :5173 — find the process
kill -9 <PID>   # stop it
```

### Database connection error

1. Ensure PostgreSQL is running: `docker compose ps`
2. Check `DATABASE_URL` in `backend/.env`
3. Verify credentials match `docker-compose.yml`

### Python dependency issues

```bash
cd backend
rm -rf .venv uv.lock
uv sync --all-extras
```

### Frontend dependency issues

```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
```
