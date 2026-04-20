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

## Local Testing (Docker)

To test a feature branch locally while reusing the main branch's DB volumes and data:

```bash
# 1. Build the frontend first
cd frontend && npm run build

# 2. Copy files not tracked in git (needed once per worktree)
cp -r /c/Repos/rag-admin/caddy ./caddy
cp /c/Repos/rag-admin/.env.local ./.env.local
# Fix CRLF line endings on Windows (required for Docker)
sed -i 's/\r//' backend/entrypoint.sh

# 3. Start containers — -p rag-admin reuses volumes from the main branch stack
docker compose -f docker-compose.local.yml -p rag-admin up --build -d
```

Using `-p rag-admin` ensures Docker reuses the named volumes (`rag-admin_postgres_data_local`,
`rag-admin_document_storage_local`) that the main branch stack created, so existing data is
preserved. Alembic migrations run automatically on backend startup.

Access: http://localhost (or http://localhost:3000)

## Workflow

- Always work against a GitHub issue + spec + Plan
- Create PR linked to issue; wait for user to merge before cleanup

## Superpowers Workflow Customizations

### Pre-Implementation Gate (applies after any planning step)
After writing an implementation plan and before writing any code:
1. Create a GitHub issue with:
   - Title: one-line summary of the work
   - Body: acceptance criteria derived from the plan
   - Links to the relevant spec (`docs/specs/`) and plan
2. Confirm Github issue details with the user
3. Continue with implementation
4. Do not begin implementation until the issue exists.

### Systematic Debugging — Stop Rule
When running the systematic-debugging skill:
- If you cannot identify a root cause after **3 fix attempts** on a failing test, **STOP immediately**.
- Do not attempt a 4th fix.
- Report to the user:
  1. The failing test and what behaviour it asserts
  2. Each of the 3 approaches tried and why each did not resolve it
  3. Your recommended next step (rewrite the test, investigate upstream dependency, ask for clarification, etc.)
- **Wait for explicit user instruction before continuing.**

### Finishing a Development Branch — Issue Close Gate
After running the finishing-a-development-branch skill:
- Ask the user: *"Should I close GitHub issue #[number] for this branch?"*
- Close the issue **only on explicit consent**.
- Do not close automatically as part of the skill flow.