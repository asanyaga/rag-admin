# CDM Viewer — Backend Spec

> **Status**: Spec for implementation.
> **Scope**: Read-only HTTP surface for browsing `ParseRun` + `ParsedDocument` records that were persisted by the CDM path in [cdm_persistence.md](cdm_persistence.md).
> **Out of scope**: Re-parse trigger (already wired via existing upload/re-parse path), PDF rendering, bbox overlays, UI.
> **Reference**: [cdm_v1.md §11.4](cdm_v1.md), [cdm_persistence.md](cdm_persistence.md).

---

## 1. Goals

1. Expose the two CDM records a viewer needs: the list of `ParseRun`s for a document, and the full `ParsedDocument` content for a run.
2. Do not duplicate the legacy `/parse-results` surface — this is the CDM-native path. Both coexist until the legacy adapter is retired.
3. Keep the wire shape a thin, obvious projection of the ORM rows. No invented fields.

Non-goals: pagination (page counts are small, O(10) runs per doc), filtering, mutation.

---

## 2. Endpoints

### 2.1 `GET /documents/{document_id}/parse-runs`

List all `ParseRun` rows associated with a document, newest first.

**Resolution:** `Document.source_document_id → ParseRun.source_document_id`. If the document has no `source_document_id` (legacy row pre-CDM), return `[]`.

**Response** (`200 OK`):

```json
[
  {
    "id": "uuid",
    "source_document_id": "uuid",
    "parser": "llamaparse",
    "parser_version": null,
    "representation_kind": "vector_light",
    "status": "succeeded",
    "started_at": "2026-04-24T10:00:00Z",
    "finished_at": "2026-04-24T10:00:12Z",
    "duration_ms": 12340,
    "input_tokens": 1200,
    "output_tokens": 450,
    "cost": {"credits": 1.2},
    "warnings": [],
    "failed_pages": [],
    "provider_refs": {"llamaparse_job_id": "..."},
    "error": null,
    "config": {"parser_mode": "parse_page_with_agent"},
    "created_at": "2026-04-24T10:00:00Z"
  }
]
```

**Errors:** `404` if document not found or not accessible to the current user.

### 2.2 `GET /parse-runs/{parse_run_id}/parsed-document`

Return the `ParsedDocument` content blob associated with a run.

**Response** (`200 OK`):

```json
{
  "parse_run_id": "uuid",
  "source_document_id": "uuid",
  "page_count": 3,
  "block_count": 47,
  "full_text": "…",
  "full_markdown": "…",
  "content": { "…raw ParsedDocument Pydantic JSON…" }
}
```

`content` is the full round-trippable CDM payload (pages, blocks, tables, bboxes). The top-level scalar fields (`page_count`, `full_text`, etc.) are duplicated for clients that only need summaries.

**Errors:**
- `404` if the run doesn't exist, or exists but has no `ParsedDocument` (e.g. status=`failed`).
- `403` if the user doesn't own any `Document` pointing at the run's `source_document_id`.

---

## 3. Authorization

Both endpoints require an authenticated user. A user can read a `ParseRun` / `ParsedDocument` iff they own a `Document` whose `source_document_id` matches the run's `source_document_id`. Cross-project reuse (same bytes, different project) is deferred — the auth check scopes to "any Document visible to this user".

Rationale: `source_documents` is content-addressed and project-agnostic, but access is gated through `documents`. This keeps us consistent with the existing `GET /documents/{id}` authorization model.

---

## 4. Schemas

Add to `backend/app/schemas/parse_run.py` (new file):

- `ParseRunResponse` — list item shape from §2.1.
- `ParsedDocumentResponse` — detail shape from §2.2.

Use camelCase aliases on response models (matches existing `DocumentResponse` convention — see [frontend/src/types/parsing.ts](../../frontend/src/types/parsing.ts) for consumer expectation).

---

## 5. Repository additions

Add to `ParseRunRepository`:

- `list_for_source_document(source_document_id: UUID) -> list[ParseRun]` — ordered by `created_at DESC`.

`ParsedDocumentRepository.get_by_run` already exists.

No changes to `SourceDocumentRepository`.

---

## 6. Router wiring

New router module `backend/app/routers/parse_runs.py` for the `/parse-runs/{id}/…` routes. The `/documents/{id}/parse-runs` route lives on the existing `documents.py` router next to `/documents/{id}/parse-results`.

Both routers share a small dependency `get_parse_run_service` in `app/dependencies/parsing.py` (or extend the existing `get_parsing_service`).

---

## 7. Testing

- `backend/tests/routers/test_parse_runs_router.py` — 404 for missing doc, empty list for pre-CDM doc, populated list for doc with ≥1 run, ordering is newest-first, 403 for cross-user access.
- `backend/tests/routers/test_parsed_document_router.py` — 200 for existing succeeded run, 404 for non-existent run, 404 for failed run (no ParsedDocument row), 403 for cross-user access.
- `backend/tests/repositories/test_parse_run_repository.py` — add a test for `list_for_source_document` ordering and empty case.

---

## 8. Acceptance Criteria

1. Both endpoints implemented, returning the shapes in §2.
2. Authorization enforces the user-owns-a-Document-pointing-at-this-source rule.
3. Tests in §7 pass. Existing backend tests continue to pass.
4. No schema migrations required (reads only against existing tables).
5. `/parse-results` legacy endpoints remain untouched.
