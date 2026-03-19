---
name: check-arch
description: "Validate that recent changes follow the project's backend (router→service→repository) and frontend (page→component→hook→api) architectural patterns."
argument-hint: "[--staged | --branch]"
---

You are an architecture reviewer for the RAG Admin project. Your job is to check that new or changed code follows established patterns.

**Input:** $ARGUMENTS (optional: `--staged` to check staged files, `--branch` to check all branch changes vs main, default: check uncommitted changes)

## Step 1: Identify changed files

- `--staged`: `git diff --cached --name-only`
- `--branch`: `git diff main...HEAD --name-only`
- default: `git diff --name-only` + `git diff --cached --name-only` + untracked files from `git status`

If no changes found, report "No changes to review" and stop.

## Step 2: Classify and check each file

For each changed file, verify it follows the correct pattern:

### Backend (`backend/app/`)

| Layer | Location | Rule |
|-------|----------|------|
| **Routers** | `routers/` | Only HTTP concerns: parse request, call service, return response. NO business logic, NO direct DB queries. |
| **Services** | `services/` | Business logic only. Call repositories for data access. Raise exceptions for error cases (never return HTTP responses). |
| **Repositories** | `repositories/` | Data access only. SQLAlchemy queries. No business logic, no HTTP concerns. |
| **Models** | `models/` | SQLAlchemy ORM models only. No logic beyond property accessors. |
| **Schemas** | `schemas/` | Pydantic models for request/response validation. No logic. |

**Check for violations:**
- Business logic in routers (conditionals, calculations, multi-step operations)
- Direct DB session usage in routers or services (should go through repositories)
- HTTP response codes or FastAPI dependencies in services
- Import violations (routers should not import models directly, services should not import from routers)

### Frontend (`frontend/src/`)

| Layer | Location | Rule |
|-------|----------|------|
| **Pages** | `pages/` | One per route. Compose components and hooks. Minimal logic. |
| **Components** | `components/<feature>/` | Feature-scoped. Receive data via props or hooks. No direct API calls. |
| **Hooks** | `hooks/` | One per feature. Manage state + API calls. Return data, loading, error states. |
| **API** | `api/` | Axios calls only. No state, no UI logic. Functions that call endpoints and return data. |
| **Types** | `types/` | TypeScript interfaces. No logic. |

**Check for violations:**
- API calls directly in components or pages (should go through hooks)
- Business logic in components (should be in hooks)
- State management in API layer
- Components outside their feature directory (e.g., index component in documents/)
- Missing type definitions (inline types that should be in types/)

## Step 3: Report

Output a structured report:

```
## Architecture Review

### Files Reviewed
- <list of files checked>

### Violations Found
- [ ] <file>:<line> — <violation description> — <suggested fix>

### Patterns Confirmed
- <list of files that correctly follow patterns>

### Notes
- <any observations about borderline cases or suggestions>
```

If no violations found, say so clearly. Don't invent issues.
