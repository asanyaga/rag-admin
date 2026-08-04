# RAG Admin

**An open workbench for building, running, and evaluating RAG and document-AI pipelines.**

RAG Admin is a self-hostable platform for turning documents into reliable AI. Ingest your documents, parse them into a canonical model, build searchable indexes, compose agents that reason over them, and — most importantly — measure quality with golden sets, experiments, and end-to-end evaluations. Everything runs on your own infrastructure with Docker.

<!-- TODO: add product screenshot at docs/assets/overview.png and reference it here -->

![License: MIT](https://img.shields.io/badge/license-MIT-blue) ![Backend: FastAPI](https://img.shields.io/badge/backend-FastAPI-009688) ![Frontend: React](https://img.shields.io/badge/frontend-React-61dafb)

---

## What it does

RAG Admin covers the full lifecycle of a document-AI pipeline, from raw files to measured quality.

- **Ingest & parse** — Organize work into projects and data stores, upload documents, and parse them into a **canonical document model (CDM)** for consistent downstream processing.
- **Index & retrieve** — Build indexes and run hybrid search over **ParadeDB** (`pgvector` for semantic + `pg_search` for full-text), with a playground and probe for exploring retrieval.
- **Agents** — Compose agents in the UI, run them against your data, and inspect each run's trace step by step.
- **Extract & classify** — Run structured extraction and classification over your documents, and drill into per-run results.
- **Evaluate** — Define golden sets, run experiments, and score **retrieval, extraction, parser, and answer** quality. Compare runs side by side to see what actually improved.
- **Observe** — Full OpenTelemetry traces, logs, and metrics, viewable in **SigNoz**.

## Tech stack

- **Backend:** Python 3.12, FastAPI (async), SQLAlchemy 2.0, ParadeDB (PostgreSQL + `pgvector` + `pg_search`), Alembic, OpenTelemetry
- **Frontend:** React 18, TypeScript, Vite, shadcn/ui, Tailwind CSS
- **Auth:** JWT + HTTP-only refresh tokens, Google OAuth
- **Observability:** OpenTelemetry → SigNoz
- **Delivery:** Docker, Caddy reverse proxy with automatic HTTPS

## Quickstart (self-host)

You'll need **Python 3.12**, **[uv](https://docs.astral.sh/uv/)**, **Node.js 18+**, and **Docker**. See the [development setup guide](docs/development/setup.md) for detailed, per-OS install steps and troubleshooting.

```bash
# 1. Install dependencies and create your .env
./scripts/setup.sh

# 2. Configure secrets in backend/.env (JWT_SECRET_KEY, optional Google OAuth)

# 3. Start PostgreSQL and apply migrations
docker compose up -d
cd backend && uv run alembic upgrade head && cd ..

# 4. Start the dev servers
./scripts/dev.sh
```

Then open:
- **Frontend:** http://localhost:5173
- **Backend API:** http://localhost:8000
- **API docs:** http://localhost:8000/docs

For the full command reference (tests, migrations, dependency management) and troubleshooting, see the [development setup guide](docs/development/setup.md).

## Architecture

RAG Admin ships as a small set of Docker containers:

- **ParadeDB** — PostgreSQL with `pgvector` and `pg_search` extensions
- **FastAPI backend** — the API and pipeline services
- **Caddy** — reverse proxy serving the built frontend with automatic HTTPS (Let's Encrypt)

Production deployments sit behind a standalone edge proxy and include automated daily backups with 7-day retention.

- 📖 [docs/architecture/](docs/architecture/) — system and deployment architecture
- 🚀 [docs/deployment/](docs/deployment/) — production deployment guide, checklist, Docker, and CI/CD
- 📊 [docs/observability/](docs/observability/) — tracing, logs, and metrics

## Development

RAG Admin follows a clean, layered architecture.

**Backend** — `router → service → repository → database`
- Services raise exceptions; routers catch them and return HTTP responses
- All database operations are async, with type hints throughout
- Read the relevant spec in `docs/planning/` or `docs/specs/` before implementing a feature

**Frontend** — `page → component → hook → api`
- One hook per feature, one page per route, feature-scoped components
- API calls go through a centralized client; TypeScript strict mode is enabled
- shadcn/ui + Tailwind for all UI; use the `@/` path alias for imports from `src/`

### Project structure

```
rag-admin/
├── backend/
│   └── app/
│       ├── routers/        # API routes
│       ├── services/       # Business logic
│       ├── repositories/   # Database operations
│       ├── models/         # SQLAlchemy models
│       ├── schemas/        # Pydantic schemas
│       ├── cdm/            # Canonical document model
│       ├── adapters/       # External integrations
│       ├── observability/  # OpenTelemetry setup
│       └── ...             # dependencies, middleware, ports, probe, utils
├── frontend/
│   └── src/
│       ├── pages/          # Page components (one per route)
│       ├── components/     # Reusable, feature-scoped components
│       ├── hooks/          # Custom hooks (one per feature)
│       ├── api/            # API client
│       ├── contexts/       # React contexts
│       └── ...             # config, constants, lib, types, utils
├── docs/                   # Architecture, deployment, planning, specs
└── scripts/                # setup.sh, dev.sh, and dev tooling
```

See the [development setup guide](docs/development/setup.md) for the full command reference.

## Contributing

Contributions are welcome. When working in the codebase:
- Keep the layering and separation of concerns intact
- Use type hints and TypeScript types throughout
- Add tests for new features
- Write clear commit messages

## License

Released under the [MIT License](LICENSE).
