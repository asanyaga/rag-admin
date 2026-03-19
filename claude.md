# RAG Admin

Web application for managing RAG pipelines for AI Agents. Prioritize clean architecture and readability.

## Stack

- **Backend:** Python 3.12, FastAPI (async), SQLAlchemy 2.0, ParadeDB, Alembic, OpenTelemetry, SigNoz
- **Frontend:** React 18, TypeScript, Vite, shadcn/ui, Tailwind CSS
- **Auth:** JWT + HTTP-only refresh tokens

## Structure

```
backend/app/    → routers/ → services/ → repositories/ → models/
frontend/src/   → pages/ → components/ → hooks/ → api/
docs/planning/  → PRD, specs, wireframes
docs/specs/     → detailed feature specs
```

## Commands

```bash
# Backend
cd backend && uvicorn app.main:app --reload
cd backend && uv run python -m pytest -o "addopts="
cd backend && alembic upgrade head

# Frontend
cd frontend && npm run dev
cd frontend && npm run lint
cd frontend && npm run build
cd frontend && npx vitest run

# Packages
cd backend && uv add <package>
cd frontend && npm install <package>
```

## Patterns

- Data flow: router → service → repository → database
- Services raise exceptions; routers catch and return HTTP responses
- All database operations async with type hints
- Frontend: one hook per feature, one page per route, feature-scoped components
- shadcn/ui with Tailwind CSS for all UI
- Read relevant spec in `docs/` before implementing features

## Workflow

- Always work against a GitHub issue + spec
- Create feature branch from main (e.g., `feat/issue-42-short-description`)
- Write tests alongside implementation
- Run change-verifier agent after changes
- Create PR linked to issue; wait for user to merge before cleanup
