# RAG Admin

Web application for creating and managing RAG pipelines. Learning/portfolio project—prioritize clean architecture and readability.

## Stack

- **Backend:** Python 3.12, FastAPI (async), SQLAlchemy 2.0, PostgreSQL, Alembic
- **Frontend:** React 18, TypeScript, Vite
- **Auth:** JWT + HTTP-only refresh tokens, Google OAuth

## Structure

```
backend/app/    → routers/ → services/ → repositories/ → models/
frontend/src/   → pages/ → components/ → hooks/ → api/
docs/planning/  → PRD, TDD, API spec, database schema
```

## Commands

```bash
# Backend
cd backend && uvicorn app.main:app --reload
cd backend && pytest
cd backend && alembic upgrade head

# Frontend
cd frontend && npm run dev
```

## Patterns

- Data flow: router → service → repository → database
- Services raise exceptions; routers catch and return HTTP responses
- All database operations async
- Type hints on all functions
- Read the relevant spec in `docs/planning/` before implementing features

## Current Phase

Project scaffold → Authentication implementation
