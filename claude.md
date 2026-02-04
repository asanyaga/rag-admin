# RAG Admin

Web application for creating and managing RAG pipelines. Learning/portfolio project—prioritize clean architecture and readability.

## Stack

- **Backend:** Python 3.12, FastAPI (async), SQLAlchemy 2.0, Paradedb, Alembic,Otel, Signoz
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
cd frontend && npm run lint  # Run ESLint checks
```

## Quality Checks

**After making frontend code changes:**
1. Run `cd frontend && npm run lint` to verify no TypeScript/ESLint errors
2. Common issues to watch for:
   - Avoid `any` types - use proper interfaces or unions like `Record<string, unknown>`
   - Remove unnecessary semicolons (especially in statement expressions)
   - Ensure all functions have explicit return types

## Patterns

- Data flow: router → service → repository → database
- Services raise exceptions; routers catch and return HTTP responses
- All database operations async
- Type hints on all functions
- Read the relevant spec in `docs/planning/` before implementing features

## UI/Design Direction

### Component Library
- **shadcn/ui** with Tailwind CSS

## Current Focus

Project scaffold → Authentication implementation

## Working with Me

- **Learning preference:** Explain *why* (reasoning, patterns, trade-offs) not basic concepts
- **Session tracking:** Use `/tasks` for work items + `docs/session-log.md` for context
- **Before implementing:** Read relevant PRD in `docs/planning/`, plan first
- **End of session:** Ask for "Session wrap-up" to capture learning and update docs
