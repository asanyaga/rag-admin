# CDM Index — Unit 1: Backend Foundation (reads + ORM column)

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Spec:** [`docs/superpowers/specs/2026-04-29-cdm-index-parser-config-selector.md`](../specs/2026-04-29-cdm-index-parser-config-selector.md)
**Issue:** [#46](https://github.com/asanyaga/rag-admin/issues/46)

**Goal:** Lay the data and read-API foundation for the parsed-document refactor without touching the index-create write path or the wizard. After this unit:

- `index_documents` has a `parsed_document_id` FK column (**nullable**, populated by backfill where possible — see the Cascade-Delete Deferral note below).
- `GET /projects/{projectId}/parse-runs/configs` lists the parse-config families available in the project.
- `GET /projects/{projectId}/parsed-documents` lists parsed-documents with family + representation filters and a `latest_per_source` toggle.
- All existing flows (index create, add documents, processing, preview) continue to work unchanged.

**Architecture:** Pure-additive backend slice. Migration adds the FK column and backfills from the existing `parse_run_id`. Two new project-scoped GET routers expose the read APIs the wizard rebuild (Unit 4) will consume. Existing `IndexDocument` ORM gets one new field; nothing in the write path changes.

**Tech Stack:** Python 3.12 · FastAPI async · SQLAlchemy 2.0 async · Alembic · Pydantic v2 · pytest

---

## Cascade-delete deferral

Per the breakdown discussion, this unit **does not delete legacy `index_documents` rows or legacy indexes**. The `parsed_document_id` column is added as **NULL-allowed**, backfilled from `parse_run_id` where possible, and left nullable for now. Legacy raw_text rows (with `parse_run_id IS NULL`) and rows whose `parse_run_id` does not resolve to a `ParsedDocument` will retain `parsed_document_id = NULL` until **Unit 6 (cleanup)** lands after Units 2–5 ship and the new flow is validated end-to-end.

Implications carried forward:
- Units 2–5 must tolerate `parsed_document_id IS NULL` on read paths (display "—" or hide the row in the new UI; existing UI continues to read `document_id` + `parse_run_id`).
- Unit 6 will: (a) cascade-delete the remaining NULL-bearing indexes, (b) `ALTER COLUMN parsed_document_id SET NOT NULL`, (c) optionally drop `document_id` / `parse_run_id` columns.

---

## Phase 0 — Repo cleanup (perform before issue creation)

The current branch (`feature/cdm-index-slice-2-markdown-chunking`) holds an in-progress slice-2 plus uncommitted artifacts that span both slice-2 and the new feature. Cleanly separating them is a prerequisite for this unit.

### Categorization

| Path | Belongs to | Action |
|------|-----------|--------|
| `backend/app/schemas/index.py` | slice-2 | commit on slice-2 branch |
| `backend/tests/schemas/test_index_config_schema.py` | slice-2 | commit on slice-2 branch |
| `frontend/src/components/indexes/IndexCreateDialog.tsx` | slice-2 | commit on slice-2 branch |
| `frontend/src/pages/CreateIndexPage.tsx` | slice-2 | commit on slice-2 branch |
| `docs/superpowers/plans/2026-04-29-cdm-index-slice-2-markdown-chunking.md` | slice-2 | commit on slice-2 branch |
| `.claude/settings.json` | settings chore | commit on slice-2 branch |
| `.claude/settings.local.json` | local-only | leave uncommitted |
| `docs/superpowers/specs/2026-04-28-cdm-index-slice-5-ui-polish.md` (modified) | new feature | revert on slice-2; re-apply on new branch |
| `docs/superpowers/specs/2026-04-29-cdm-index-parser-config-selector.md` (untracked) | new feature | move out, restore on new branch |
| `docs/superpowers/plans/2026-04-29-cdm-index-parser-config-selector.md` (untracked) | superseded | move out; **delete** (this plan supersedes it) |
| `docs/superpowers/plans/2026-04-29-preview-chunks-cdm-refactor.md` (untracked) | superseded | move out; **delete** (Unit 2 plan will supersede) |

### Cleanup steps

- [ ] **0.1 — Snapshot new-feature artifacts to a holding directory.**
  ```bash
  mkdir -p /tmp/cdm-parsed-doc-handoff
  mv /home/asa/rag-admin/docs/superpowers/specs/2026-04-29-cdm-index-parser-config-selector.md \
     /tmp/cdm-parsed-doc-handoff/spec.md
  mv /home/asa/rag-admin/docs/superpowers/plans/2026-04-29-cdm-index-parser-config-selector.md \
     /tmp/cdm-parsed-doc-handoff/superseded-plan-1.md
  mv /home/asa/rag-admin/docs/superpowers/plans/2026-04-29-preview-chunks-cdm-refactor.md \
     /tmp/cdm-parsed-doc-handoff/superseded-plan-2.md
  git -C /home/asa/rag-admin diff docs/superpowers/specs/2026-04-28-cdm-index-slice-5-ui-polish.md \
     > /tmp/cdm-parsed-doc-handoff/slice-5-trim.diff
  ```

- [ ] **0.2 — Revert the slice-5 spec edit on the slice-2 branch.** The trim depends on the new spec existing; it lands with the new feature, not slice-2.
  ```bash
  git -C /home/asa/rag-admin checkout HEAD -- docs/superpowers/specs/2026-04-28-cdm-index-slice-5-ui-polish.md
  ```

- [ ] **0.3 — Verify slice-2 working tree contains only slice-2 finishers.** `git status` should list only the rows marked "slice-2" or "settings chore" in the table above. If any new-feature artifacts remain, re-run 0.1.

- [ ] **0.4 — Run slice-2 verification:**
  ```bash
  uv run --directory /home/asa/rag-admin/backend python -m pytest -o "addopts="
  npm --prefix /home/asa/rag-admin/frontend run lint
  npm --prefix /home/asa/rag-admin/frontend run build
  ```

- [ ] **0.5 — Commit slice-2 finishers in logical groups, then push the branch.** Suggested grouping:
  - `chore(claude): permit npm test from settings` — `.claude/settings.json`
  - `feat(schemas): drop premature parser requirement on IndexConfig` — `backend/app/schemas/index.py` + the matching test
  - `feat(frontend): error-detail extractor for create-index toasts` — `IndexCreateDialog.tsx` + `CreateIndexPage.tsx` (error helper) + the page parity work
  - `docs: slice-2 markdown chunking implementation plan` — the slice-2 plan file

- [ ] **0.6 — Open the slice-2 PR.** Note in the description that preview is intentionally disabled for `full_markdown` (commit `2a0cfa1`) and will be restored by Unit 2 of the parsed-document refactor (link to spec). Do **not** wait for merge before continuing — Unit 1 work proceeds on the new branch in parallel.

- [ ] **0.7 — Branch off main for the new feature.**
  ```bash
  git -C /home/asa/rag-admin fetch origin
  git -C /home/asa/rag-admin checkout main
  git -C /home/asa/rag-admin pull --ff-only origin main
  git -C /home/asa/rag-admin checkout -b feature/cdm-index-parsed-doc-selector
  ```

- [ ] **0.8 — Restore the new-feature spec onto the new branch.**
  ```bash
  cp /tmp/cdm-parsed-doc-handoff/spec.md \
     /home/asa/rag-admin/docs/superpowers/specs/2026-04-29-cdm-index-parser-config-selector.md
  git -C /home/asa/rag-admin apply /tmp/cdm-parsed-doc-handoff/slice-5-trim.diff
  rm /tmp/cdm-parsed-doc-handoff/superseded-plan-1.md /tmp/cdm-parsed-doc-handoff/superseded-plan-2.md
  ```
  The two superseded plan files are dropped — this plan replaces them.

- [ ] **0.9 — Commit the spec + this plan as the first commit of the new branch.**
  ```
  docs(spec): parsed-document refactor for CDM index creation
  ```
  Includes: the new spec, the slice-5 spec trim (now coherent), and this plan file.

After 0.9, the new branch contains spec + plan, the slice-2 PR is open with the preview band-aid annotated, and the working tree is clean for Unit 1 implementation.

---

## Pre-implementation gate

- [ ] **Step P1 — Create GitHub issue and confirm with user.**

```bash
gh issue create \
  --title "feat(index): backend foundation for parsed-document selector (Unit 1)" \
  --body "$(cat <<'EOF'
## Summary
First unit of the CDM-index parsed-document refactor. Pure-additive backend
foundation: adds `index_documents.parsed_document_id` FK (nullable; backfilled
from `parse_run_id`) and exposes two project-scoped GET endpoints used by the
wizard rebuild in later units.

## Acceptance criteria
- [ ] `index_documents.parsed_document_id` column exists, FK to `parsed_documents` with `ON DELETE CASCADE`, nullable.
- [ ] Backfill populates `parsed_document_id` for every row whose `parse_run_id` resolves to a `parsed_document`. Rows that don't resolve remain NULL (deferred cleanup).
- [ ] `GET /projects/{projectId}/parse-runs/configs` returns distinct `(parser, parse_config_hash)` families with `parsed_document_count`, `has_full_markdown`, `latest_parsed_at`.
- [ ] `GET /projects/{projectId}/parsed-documents` supports `parser`, `parse_config_hash`, `representation`, `latest_per_source` query params; sorted newest-first; project-scoped authorization enforced.
- [ ] All existing index-create / processing / preview flows continue to pass their tests.
- [ ] No legacy data is deleted in this unit (cascade-delete + NOT NULL deferred to a final cleanup unit).

## Spec
docs/superpowers/specs/2026-04-29-cdm-index-parser-config-selector.md

## Plan
docs/superpowers/plans/2026-04-30-cdm-index-parsed-doc-unit-1-foundation.md
EOF
)" \
  --label "feature,backend"
```

After creating, confirm issue number with the user and update this file with `**Issue:** #<n>` before continuing.

---

## File map

| Action | Path | What changes |
|--------|------|--------------|
| **Create** | `backend/alembic/versions/<rev>_add_parsed_document_id_to_index_documents.py` | New migration: add FK column + backfill |
| Modify | `backend/app/models/index_document.py` | Add `parsed_document_id` field + relationship to `ParsedDocument` |
| Modify | `backend/app/repositories/parse_run_repository.py` | Add `list_distinct_configs_for_project(project_id)` |
| Modify | `backend/app/repositories/parsed_document_repository.py` | Add `list_for_project(project_id, *, parser, parse_config_hash, representation, latest_per_source)` |
| **Create** | `backend/app/schemas/parsed_document.py` (or extend existing) | `ParseConfigOption`, `ParsedDocumentListItem` |
| **Create** | `backend/app/routers/parse_run_configs.py` | `GET /projects/{project_id}/parse-runs/configs` |
| **Create** | `backend/app/routers/parsed_documents.py` | `GET /projects/{project_id}/parsed-documents` |
| Modify | `backend/app/main.py` | Register new routers |
| **Create** | `backend/tests/migrations/test_parsed_document_id_backfill.py` | Migration backfill test |
| **Create** | `backend/tests/repositories/test_parse_run_repository_configs.py` | Distinct-configs query test |
| **Create** | `backend/tests/repositories/test_parsed_document_repository_listing.py` | Listing + filter + latest_per_source tests |
| **Create** | `backend/tests/routers/test_parse_run_configs_router.py` | `/parse-runs/configs` endpoint tests |
| **Create** | `backend/tests/routers/test_parsed_documents_router.py` | `/parsed-documents` endpoint tests |

No frontend changes in this unit.

---

## Implementation tasks (TDD)

### Task 1 — ORM column + Alembic migration

- [ ] **1.1 Write migration test (red).** `backend/tests/migrations/test_parsed_document_id_backfill.py` — pytest fixture spins up an Alembic stamp at the previous revision, seeds `index_documents` rows with various `(parse_run_id, parsed_document)` shapes (resolvable, unresolvable, NULL), upgrades to the new revision, asserts:
  - Resolvable rows now have `parsed_document_id` populated correctly.
  - Unresolvable rows have `parsed_document_id IS NULL`.
  - The FK constraint is in place with `ON DELETE CASCADE`.
  - Column allows NULL (no NOT NULL constraint yet).

- [ ] **1.2 Generate the Alembic migration (green).** Use `alembic revision --autogenerate` after adding the field to the ORM (Task 1.4) — but the file will need manual edits for the backfill UPDATE. Migration body:
  ```python
  def upgrade() -> None:
      op.add_column(
          "index_documents",
          sa.Column(
              "parsed_document_id",
              postgresql.UUID(as_uuid=True),
              sa.ForeignKey("parsed_documents.id", ondelete="CASCADE"),
              nullable=True,
          ),
      )
      op.create_index(
          "ix_index_documents_parsed_document_id",
          "index_documents",
          ["parsed_document_id"],
      )
      op.execute("""
          UPDATE index_documents id
          SET parsed_document_id = pd.id
          FROM parsed_documents pd
          WHERE pd.parse_run_id = id.parse_run_id
            AND id.parse_run_id IS NOT NULL
      """)

  def downgrade() -> None:
      op.drop_index("ix_index_documents_parsed_document_id", table_name="index_documents")
      op.drop_column("index_documents", "parsed_document_id")
  ```

- [ ] **1.3 Run migration test — verify green.**
  ```bash
  uv run --directory /home/asa/rag-admin/backend python -m pytest tests/migrations/test_parsed_document_id_backfill.py -o "addopts="
  ```

- [ ] **1.4 Add field to `IndexDocument` ORM.**
  ```python
  parsed_document_id: Mapped[UUID | None] = mapped_column(
      PGUUID(as_uuid=True),
      ForeignKey("parsed_documents.id", ondelete="CASCADE"),
      nullable=True,
  )
  parsed_document: Mapped["ParsedDocument | None"] = relationship(
      "ParsedDocument", foreign_keys=[parsed_document_id]
  )
  ```
  Add `sa.Index('ix_index_documents_parsed_document_id', 'parsed_document_id')` to `__table_args__`.

- [ ] **1.5 Apply migration to local dev DB and spot-check.**
  ```bash
  docker compose -f /home/asa/rag-admin/docker-compose.local.yml exec backend alembic upgrade head
  docker compose -f /home/asa/rag-admin/docker-compose.local.yml exec postgres \
      psql -U postgres -d rag_admin -c \
      "SELECT count(*) total, count(parsed_document_id) backfilled FROM index_documents"
  ```

### Task 2 — `ParseRun` repository: distinct configs

- [ ] **2.1 Write repository tests (red).** `backend/tests/repositories/test_parse_run_repository_configs.py`:
  - `test_list_distinct_configs_for_project_groups_by_parser_and_hash`
  - `test_list_distinct_configs_excludes_other_projects`
  - `test_list_distinct_configs_excludes_failed_runs`
  - `test_list_distinct_configs_returns_parsed_document_count`
  - `test_list_distinct_configs_has_full_markdown_when_at_least_one_populated`
  - `test_list_distinct_configs_returns_latest_parsed_at`
  - `test_list_distinct_configs_empty_when_no_runs`

- [ ] **2.2 Implement `ParseRunRepository.list_distinct_configs_for_project(project_id)` (green).**
  Returns rows shaped:
  ```python
  @dataclass(frozen=True)
  class ParseConfigOptionRow:
      parser: str
      parse_config_hash: str
      config: dict
      parsed_document_count: int
      has_full_markdown: bool
      latest_parsed_at: datetime
  ```
  Query joins `parsed_documents → parse_runs → source_documents → documents`, filters `parse_runs.status = 'succeeded'` and `documents.project_id = :project_id`, groups by `(parser, config_hash)`, aggregates `count(*)`, `bool_or(parsed_documents.full_markdown IS NOT NULL)`, `max(parse_runs.finished_at)`. The `config` dict is fetched via a representative row (e.g. the latest run's `config_json`).

- [ ] **2.3 Run repository tests — verify green.**

### Task 3 — `ParsedDocument` repository: project-scoped listing

- [ ] **3.1 Write repository tests (red).** `backend/tests/repositories/test_parsed_document_repository_listing.py`:
  - `test_list_for_project_returns_only_project_parsed_docs`
  - `test_list_for_project_filters_by_parser_and_hash`
  - `test_list_for_project_filters_by_representation_full_markdown`
  - `test_list_for_project_filters_by_representation_full_text`
  - `test_list_for_project_filters_by_representation_block`
  - `test_list_for_project_latest_per_source_true_returns_one_per_source`
  - `test_list_for_project_latest_per_source_false_returns_all_runs`
  - `test_list_for_project_excludes_failed_run_parsed_docs`
  - `test_list_for_project_sorted_newest_first`

- [ ] **3.2 Implement `ParsedDocumentRepository.list_for_project(...)` (green).**
  Signature:
  ```python
  async def list_for_project(
      self,
      project_id: UUID,
      *,
      parser: str | None = None,
      parse_config_hash: str | None = None,
      representation: Literal["full_text", "full_markdown", "block"] | None = None,
      latest_per_source: bool = True,
  ) -> list[ParsedDocumentListRow]: ...
  ```
  Joins `parsed_documents → parse_runs → source_documents → documents`. Filters `parse_runs.status = 'succeeded'`. Representation filter:
  - `full_markdown` → `parsed_documents.full_markdown IS NOT NULL`
  - `full_text` → `parsed_documents.full_text IS NOT NULL` (always true under invariants but enforced in query)
  - `block` → no filter (every parsed-doc has ≥1 block by invariant; revisit if invariant changes)

  `latest_per_source=true` is implemented via a window function `ROW_NUMBER() OVER (PARTITION BY source_document_id ORDER BY parse_runs.finished_at DESC)` and a `WHERE rn = 1` outer wrapper.

- [ ] **3.3 Run repository tests — verify green.**

### Task 4 — Pydantic schemas

- [ ] **4.1 Add schemas.** `backend/app/schemas/parsed_document.py` (extend existing if `ParsedDocumentResponse` lives there; otherwise create):
  ```python
  class ParseConfigOption(BaseModel):
      parser: str
      parse_config_hash: str = Field(..., alias="parseConfigHash")
      config: dict[str, Any]
      parsed_document_count: int = Field(..., alias="parsedDocumentCount")
      has_full_markdown: bool = Field(..., alias="hasFullMarkdown")
      latest_parsed_at: datetime = Field(..., alias="latestParsedAt")

      model_config = ConfigDict(populate_by_name=True)


  class ParsedDocumentListItem(BaseModel):
      id: UUID
      parse_run_id: UUID = Field(..., alias="parseRunId")
      parser: str
      parse_config_hash: str = Field(..., alias="parseConfigHash")
      source_document_id: UUID = Field(..., alias="sourceDocumentId")
      source_filename: str | None = Field(None, alias="sourceFilename")
      has_full_markdown: bool = Field(..., alias="hasFullMarkdown")
      block_count: int = Field(..., alias="blockCount")
      parsed_at: datetime = Field(..., alias="parsedAt")

      model_config = ConfigDict(populate_by_name=True)
  ```

### Task 5 — Router: `/parse-runs/configs`

- [ ] **5.1 Write router tests (red).** `backend/tests/routers/test_parse_run_configs_router.py`:
  - `test_get_parse_run_configs_returns_options_for_project`
  - `test_get_parse_run_configs_requires_authentication`
  - `test_get_parse_run_configs_rejects_other_users_project`
  - `test_get_parse_run_configs_returns_empty_list`

- [ ] **5.2 Create router (green).** `backend/app/routers/parse_run_configs.py`:
  ```python
  router = APIRouter(prefix="/projects/{project_id}/parse-runs", tags=["parse-runs"])

  @router.get("/configs", response_model=list[ParseConfigOption])
  async def list_parse_run_configs(
      project_id: UUID,
      current_user: User = Depends(get_current_active_user),
      db: AsyncSession = Depends(get_db),
      project_repo: ProjectRepository = Depends(get_project_repo),
  ):
      await verify_project_access(project_id, current_user, project_repo)
      rows = await ParseRunRepository(db).list_distinct_configs_for_project(project_id)
      return [ParseConfigOption(...) for row in rows]
  ```

- [ ] **5.3 Register the router in `app/main.py`.**

- [ ] **5.4 Run router tests — verify green.**

### Task 6 — Router: `/parsed-documents`

- [ ] **6.1 Write router tests (red).** `backend/tests/routers/test_parsed_documents_router.py`:
  - `test_get_parsed_documents_no_filter_returns_project_set`
  - `test_get_parsed_documents_filters_by_family`
  - `test_get_parsed_documents_representation_full_markdown`
  - `test_get_parsed_documents_latest_per_source_default_true`
  - `test_get_parsed_documents_latest_per_source_explicit_false`
  - `test_get_parsed_documents_rejects_unauthorized_user`
  - `test_get_parsed_documents_validates_query_params` — e.g. `parser` set without `parse_config_hash` should 422

- [ ] **6.2 Create router (green).** `backend/app/routers/parsed_documents.py`:
  ```python
  router = APIRouter(prefix="/projects/{project_id}/parsed-documents", tags=["parsed-documents"])

  @router.get("", response_model=list[ParsedDocumentListItem])
  async def list_parsed_documents(
      project_id: UUID,
      parser: str | None = Query(None),
      parse_config_hash: str | None = Query(None, alias="parseConfigHash"),
      representation: Literal["full_text", "full_markdown", "block"] | None = Query(None),
      latest_per_source: bool = Query(True, alias="latestPerSource"),
      current_user: User = Depends(get_current_active_user),
      db: AsyncSession = Depends(get_db),
      project_repo: ProjectRepository = Depends(get_project_repo),
  ):
      await verify_project_access(project_id, current_user, project_repo)
      if (parser is None) != (parse_config_hash is None):
          raise HTTPException(422, "parser and parse_config_hash must be supplied together")
      rows = await ParsedDocumentRepository(db).list_for_project(
          project_id,
          parser=parser,
          parse_config_hash=parse_config_hash,
          representation=representation,
          latest_per_source=latest_per_source,
      )
      return [ParsedDocumentListItem(...) for row in rows]
  ```

- [ ] **6.3 Register the router in `app/main.py`.**

- [ ] **6.4 Run router tests — verify green.**

### Task 7 — Verification

- [ ] **7.1 Full backend test suite passes.**
  ```bash
  uv run --directory /home/asa/rag-admin/backend python -m pytest -o "addopts="
  ```

- [ ] **7.2 Manual smoke against the local stack.**
  ```bash
  docker compose -f /home/asa/rag-admin/docker-compose.local.yml up -d --build backend
  ```
  Get a valid JWT for an existing project, then:
  ```bash
  curl -H "Authorization: Bearer $TOKEN" \
       "http://localhost/api/v1/projects/$PROJECT_ID/parse-runs/configs" | jq

  curl -H "Authorization: Bearer $TOKEN" \
       "http://localhost/api/v1/projects/$PROJECT_ID/parsed-documents?parser=llamaparse&parseConfigHash=$HASH&representation=full_markdown&latestPerSource=true" | jq
  ```
  Expectations:
  - `/configs` returns at least one `ParseConfigOption` per family seen during slice-2 testing.
  - `/parsed-documents` returns one row per source document by default; toggle `latestPerSource=false` and verify multiple rows per source when re-runs exist.
  - Unauthenticated request → 401.
  - Different user's project → 403/404.

- [ ] **7.3 Confirm existing flows unaffected.**
  - Open Create Index wizard for raw_text. Create + auto-process. Verify success.
  - Open Create Index for full_markdown (using the existing slice-2 wizard before Unit 4 lands). Create + auto-process. Verify rows in `index_documents` have `parsed_document_id` populated by the migration backfill.

- [ ] **7.4 Verify cascade FK behavior.** In a scratch psql session: delete a parsed-doc row directly and confirm dependent `index_documents` rows are removed. (Do not run on shared data.)

---

## Manual verification checklist (to attach to the PR)

- [ ] Migration runs cleanly on a freshly-cloned local DB.
- [ ] Backfill populated `parsed_document_id` for all rows where `parse_run_id` resolves to a `ParsedDocument`.
- [ ] Legacy raw_text `index_documents` rows remain (with `parsed_document_id IS NULL`) — **not deleted** in this unit.
- [ ] `GET /parse-runs/configs` returns expected families.
- [ ] `GET /parsed-documents` filters and `latest_per_source` toggle behave per spec.
- [ ] Existing `Create Index` flow (slice-2 wizard) still works for raw_text and full_markdown.

---

## Out of scope (next units)

- **Unit 2:** Source-resolution seam refactor + chunk preview fix (un-bandaid `2a0cfa1`).
- **Unit 3:** `IndexCreate.parsed_document_ids` shape, `IndexConfig` validators, drop `raw_text`, route renames.
- **Unit 4:** Wizard rebuild — family selector + parsed-doc picker.
- **Unit 5:** Index detail "Parsed Documents" tab.
- **Unit 6 (cleanup):** Cascade-delete legacy NULL-bearing indexes; `ALTER COLUMN parsed_document_id SET NOT NULL`; optional drop of `document_id` / `parse_run_id` columns.
