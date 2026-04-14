# Data Stores: Testing Notes

## Problem

The test suite uses SQLite in-memory (`sqlite+aiosqlite:///:memory:` in `backend/tests/conftest.py`) but the data stores feature uses PostgreSQL-specific SQL:

- **`gen_random_uuid()`** — SQLite has no equivalent server-side UUID function
- **`RETURNING *`** — SQLite added limited RETURNING support in 3.35.0 but behavior differs
- **`TIMESTAMPTZ`** — SQLite has no native timezone-aware datetime type
- **Raw DDL** — `CREATE TABLE`, `ALTER TABLE ADD COLUMN`, `DROP TABLE` via `text()` use PostgreSQL type names (`TEXT`, `INTEGER`, `NUMERIC`, `BOOLEAN`, `TIMESTAMPTZ`)
- **`gen_random_uuid()` as column default** — used in the `project_data_stores` migration and model `server_default`

## Current State

- `backend/tests/services/test_data_store_service.py` exists with tests that mock all dynamic table operations (raw SQL) and run metadata CRUD against SQLite. This approach works for service-level logic but doesn't test the actual SQL.
- The tests have NOT been run due to the SQLite incompatibility with the migration/model (the `gen_random_uuid()` server_default in `ProjectDataStore` causes errors when SQLite tries to create the table during test setup).

## Suggested Solutions

### Option A: PostgreSQL Test Database (Recommended)

Use a real PostgreSQL instance for tests. This gives full coverage including dynamic table operations.

1. Add `testcontainers` (Python package) to dev dependencies — it spins up a PostgreSQL Docker container per test session
2. Update `conftest.py` to use `postgresql+asyncpg://...` URL from testcontainers
3. Run the real Alembic migrations against it
4. Remove all mocks from data store tests — test the actual SQL

**Pros:** Tests match production exactly. Catches real SQL bugs.
**Cons:** Requires Docker. Slower test startup (~2-3s for container).

### Option B: Conditional Test Database

Keep SQLite for fast unit tests, add a separate PostgreSQL fixture for integration tests.

1. Add a `conftest.py` marker: `@pytest.mark.postgres` for tests needing PostgreSQL
2. Use an environment variable (`TEST_DATABASE_URL`) to opt into PostgreSQL
3. Skip postgres-marked tests when no PostgreSQL is available

**Pros:** Fast unit tests stay fast. Integration tests get real SQL coverage.
**Cons:** Two test paths to maintain.

### Option C: Fix SQLite Compatibility

Make the model/migration work with both SQLite and PostgreSQL.

1. Use conditional `server_default` (detect dialect)
2. Replace `gen_random_uuid()` with Python-side `default=uuid4` only (remove `server_default`)
3. Use dialect-specific type mapping in dynamic table DDL

**Pros:** No Docker needed. Tests run everywhere.
**Cons:** Production code gets polluted with test concerns. Dynamic table SQL would need a SQLite code path that doesn't exist in production.

## Recommendation

**Option A** is the cleanest path. The project already uses Docker for PostgreSQL in development. Adding `testcontainers` to the test setup ensures tests match production behavior without compromising the codebase.
