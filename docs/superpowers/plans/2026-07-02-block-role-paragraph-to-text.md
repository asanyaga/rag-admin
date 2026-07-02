# BlockRole.PARAGRAPH → BlockRole.TEXT Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename `BlockRole.PARAGRAPH = "paragraph"` to `BlockRole.TEXT = "text"` across the entire codebase, including a data migration for existing JSONB/JSON columns.

**Architecture:** Single-PR rename — no backward-compat alias needed (no prod data). Change the enum member name and serialized value in `models.py`, sweep all code/test references, and write an Alembic data migration that rewrites `"paragraph"` → `"text"` strings in the three JSON columns that store block roles.

**Tech Stack:** Python 3.12, Alembic, PostgreSQL JSONB, React/TypeScript

## Global Constraints

- No new tests — existing suite is the verification harness; update it, don't extend it
- `native_type` strings (`"text"`, `"paragraph"`) are parser vocabulary — never change them
- `_ROLE_MAP` keys in adapter files are parser vocabulary — never change them; only update right-hand side enum references
- Commit message style: `type(scope): description` (e.g. `refactor(cdm): rename BlockRole.PARAGRAPH to TEXT`)
- Branch off `main`; link PR to the GitHub issue created in Task 1

---

## File Map

**Modified — backend:**
- `backend/app/cdm/models.py` — enum member rename
- `backend/app/cdm/adapters/docling.py` — `_ROLE_MAP` right-hand sides
- `backend/app/cdm/adapters/llamaparse.py` — `_ROLE_MAP` right-hand side
- `backend/app/cdm/adapters/landing_ai.py` — fallback return + docstring
- `backend/app/cdm/adapters/simple_text.py` — two `Block(role=...)` constructors
- `backend/app/cdm/adapters/custom_pipeline/tools/fitz_tool.py` — `Block(role=...)` constructor
- `backend/app/cdm/adapters/custom_pipeline/merger.py` — comment only
- `backend/app/services/block_chunking_service.py` — comment only
- All test files referencing `BlockRole.PARAGRAPH` or `"paragraph"` as a role value (listed per task below)

**Modified — frontend:**
- `frontend/src/types/index.ts` — `BlockRole` union type + `BLOCK_ROLE_OPTIONS`
- `frontend/src/components/parse-runs/DocumentPdfViewer.tsx` — color map key

**Created — migration:**
- `backend/alembic/versions/<hash>_rename_block_role_paragraph_to_text.py`

---

## Task 1: Setup — GitHub issue and feature branch

**Files:** none

- [ ] **Step 1: Create GitHub issue**

```bash
gh issue create \
  --title "refactor(cdm): rename BlockRole.PARAGRAPH to BlockRole.TEXT" \
  --body "## Summary
Rename the CDM block role from \`PARAGRAPH = \"paragraph\"\` to \`TEXT = \"text\"\` for semantic accuracy. Parsers emit this role for single words, labels, and empty strings — the name \"paragraph\" falsely implies multi-sentence prose.

## Acceptance Criteria
- [ ] \`BlockRole.TEXT = \"text\"\` exists; \`BlockRole.PARAGRAPH\` does not
- [ ] Alembic migration rewrites \`\"paragraph\"\` → \`\"text\"\` in \`parsed_documents.content\`, \`chunks.chunk_metadata\`, \`indexes.config\`
- [ ] All adapters produce \`BlockRole.TEXT\` for generic text blocks
- [ ] All tests pass with no \`PARAGRAPH\` references remaining in app code
- [ ] Frontend \`BlockRole\` type and color map updated

## References
- Spec: \`docs/superpowers/specs/2026-07-02-block-role-paragraph-to-text-design.md\`
- Plan: \`docs/superpowers/plans/2026-07-02-block-role-paragraph-to-text.md\`"
```

Note the issue number printed — you'll need it for the PR.

- [ ] **Step 2: Create feature branch**

```bash
git checkout -b refactor/block-role-paragraph-to-text
```

---

## Task 2: Alembic data migration

**Files:**
- Create: `backend/alembic/versions/<hash>_rename_block_role_paragraph_to_text.py`

**Interfaces:**
- Produces: Alembic migration that rewrites `"paragraph"` → `"text"` in `parsed_documents.content[blocks][*].role`, `chunks.chunk_metadata[block_roles][*]`, `indexes.config[blockRoleFilter][*]`

- [ ] **Step 1: Generate the migration file**

```bash
cd backend && alembic revision -m "rename_block_role_paragraph_to_text"
```

Alembic prints the new file path, e.g.:
```
Generating .../alembic/versions/abc123_rename_block_role_paragraph_to_text.py
```

- [ ] **Step 2: Write the migration**

Open the generated file and replace its entire contents with:

```python
"""rename block role paragraph to text

Revision ID: <keep the auto-generated value>
Revises: <keep the auto-generated value>
Create Date: <keep the auto-generated value>

"""
from typing import Sequence, Union

from alembic import op


revision: str = "<keep>"
down_revision: Union[str, None] = "<keep>"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # parsed_documents: rewrite role field on each block in the blocks array
    op.execute("""
        UPDATE parsed_documents
        SET content = jsonb_set(
            content,
            '{blocks}',
            (
                SELECT jsonb_agg(
                    CASE
                        WHEN elem->>'role' = 'paragraph'
                        THEN jsonb_set(elem, '{role}', '"text"')
                        ELSE elem
                    END
                )
                FROM jsonb_array_elements(content->'blocks') AS elem
            )
        )
        WHERE EXISTS (
            SELECT 1
            FROM jsonb_array_elements(content->'blocks') AS elem
            WHERE elem->>'role' = 'paragraph'
        )
    """)

    # chunks: rewrite role values in block_roles array
    op.execute("""
        UPDATE chunks
        SET chunk_metadata = (
            jsonb_set(
                chunk_metadata::jsonb,
                '{block_roles}',
                (
                    SELECT jsonb_agg(
                        CASE
                            WHEN elem::text = '"paragraph"' THEN '"text"'::jsonb
                            ELSE elem
                        END
                    )
                    FROM jsonb_array_elements(chunk_metadata::jsonb->'block_roles') AS elem
                )
            )
        )::json
        WHERE chunk_metadata::jsonb ? 'block_roles'
          AND EXISTS (
            SELECT 1
            FROM jsonb_array_elements(chunk_metadata::jsonb->'block_roles') AS elem
            WHERE elem::text = '"paragraph"'
          )
    """)

    # indexes: rewrite role values in blockRoleFilter array
    op.execute("""
        UPDATE indexes
        SET config = (
            jsonb_set(
                config::jsonb,
                '{blockRoleFilter}',
                (
                    SELECT jsonb_agg(
                        CASE
                            WHEN elem::text = '"paragraph"' THEN '"text"'::jsonb
                            ELSE elem
                        END
                    )
                    FROM jsonb_array_elements(config::jsonb->'blockRoleFilter') AS elem
                )
            )
        )::json
        WHERE config::jsonb ? 'blockRoleFilter'
          AND config::jsonb->'blockRoleFilter' IS NOT NULL
          AND EXISTS (
            SELECT 1
            FROM jsonb_array_elements(config::jsonb->'blockRoleFilter') AS elem
            WHERE elem::text = '"paragraph"'
          )
    """)


def downgrade() -> None:
    # parsed_documents: revert text → paragraph
    op.execute("""
        UPDATE parsed_documents
        SET content = jsonb_set(
            content,
            '{blocks}',
            (
                SELECT jsonb_agg(
                    CASE
                        WHEN elem->>'role' = 'text'
                        THEN jsonb_set(elem, '{role}', '"paragraph"')
                        ELSE elem
                    END
                )
                FROM jsonb_array_elements(content->'blocks') AS elem
            )
        )
        WHERE EXISTS (
            SELECT 1
            FROM jsonb_array_elements(content->'blocks') AS elem
            WHERE elem->>'role' = 'text'
        )
    """)

    # chunks: revert text → paragraph
    op.execute("""
        UPDATE chunks
        SET chunk_metadata = (
            jsonb_set(
                chunk_metadata::jsonb,
                '{block_roles}',
                (
                    SELECT jsonb_agg(
                        CASE
                            WHEN elem::text = '"text"' THEN '"paragraph"'::jsonb
                            ELSE elem
                        END
                    )
                    FROM jsonb_array_elements(chunk_metadata::jsonb->'block_roles') AS elem
                )
            )
        )::json
        WHERE chunk_metadata::jsonb ? 'block_roles'
          AND EXISTS (
            SELECT 1
            FROM jsonb_array_elements(chunk_metadata::jsonb->'block_roles') AS elem
            WHERE elem::text = '"text"'
          )
    """)

    # indexes: revert text → paragraph
    op.execute("""
        UPDATE indexes
        SET config = (
            jsonb_set(
                config::jsonb,
                '{blockRoleFilter}',
                (
                    SELECT jsonb_agg(
                        CASE
                            WHEN elem::text = '"text"' THEN '"paragraph"'::jsonb
                            ELSE elem
                        END
                    )
                    FROM jsonb_array_elements(config::jsonb->'blockRoleFilter') AS elem
                )
            )
        )::json
        WHERE config::jsonb ? 'blockRoleFilter'
          AND config::jsonb->'blockRoleFilter' IS NOT NULL
          AND EXISTS (
            SELECT 1
            FROM jsonb_array_elements(config::jsonb->'blockRoleFilter') AS elem
            WHERE elem::text = '"text"'
          )
    """)
```

- [ ] **Step 3: Verify the migration runs**

```bash
cd backend && alembic upgrade head
```

Expected: no errors, migration applies cleanly.

- [ ] **Step 4: Commit**

```bash
git add backend/alembic/versions/
git commit -m "feat(cdm): alembic migration — rename block role paragraph to text in JSONB columns"
```

---

## Task 3: Backend enum rename and full code sweep

**Files:**
- Modify: `backend/app/cdm/models.py`
- Modify: `backend/app/cdm/adapters/docling.py`
- Modify: `backend/app/cdm/adapters/llamaparse.py`
- Modify: `backend/app/cdm/adapters/landing_ai.py`
- Modify: `backend/app/cdm/adapters/simple_text.py`
- Modify: `backend/app/cdm/adapters/custom_pipeline/tools/fitz_tool.py`
- Modify: `backend/app/cdm/adapters/custom_pipeline/merger.py`
- Modify: `backend/app/services/block_chunking_service.py`
- Modify: all backend test files listed below

**Rule — applies to every file in this task:**
- `BlockRole.PARAGRAPH` → `BlockRole.TEXT` everywhere
- String literals `"paragraph"` used as a CDM role value → `"text"` (in `role=`, `"role": "paragraph"`, `block_role_filter`, `block_roles`, `drop` config lists)
- `native_type="paragraph"` — leave alone (parser vocabulary)
- `_ROLE_MAP` keys (left-hand side) — leave alone (parser vocabulary)

- [ ] **Step 1: Rename the enum member in models.py**

In `backend/app/cdm/models.py`, change:
```python
PARAGRAPH  = "paragraph"
```
to:
```python
TEXT       = "text"
```

- [ ] **Step 2: Update adapter files**

**`backend/app/cdm/adapters/docling.py`** — update two map entries:
```python
_ROLE_MAP: Dict[str, BlockRole] = {
    "title":               BlockRole.TITLE,
    "section_header":      BlockRole.HEADING,
    "text":                BlockRole.TEXT,       # was PARAGRAPH
    "paragraph":           BlockRole.TEXT,       # was PARAGRAPH; key stays
    ...
}
```

**`backend/app/cdm/adapters/llamaparse.py`** — update one map entry:
```python
_ROLE_MAP: Dict[str, BlockRole] = {
    "heading": BlockRole.HEADING,
    "text":    BlockRole.TEXT,    # was PARAGRAPH
    ...
}
```

**`backend/app/cdm/adapters/landing_ai.py`** — update the fallback return and docstring:
```python
def _detect_text_role(markdown: str) -> BlockRole:
    """Map a text chunk's markdown to TITLE, HEADING, or TEXT."""  # was PARAGRAPH
    first = _first_content_line(markdown)
    m = _HEADING_RE.match(first)
    if not m:
        return BlockRole.TEXT   # was PARAGRAPH
    return BlockRole.TITLE if len(m.group(1)) == 1 else BlockRole.HEADING
```

**`backend/app/cdm/adapters/simple_text.py`** — update both Block constructors:
```python
# boundary-based block (line ~36)
block = Block(
    id=block_id,
    role=BlockRole.TEXT,     # was PARAGRAPH
    native_type="text",
    ...
)

# fallback single-block (line ~52)
blocks = [Block(
    id=block_id,
    role=BlockRole.TEXT,     # was PARAGRAPH
    native_type="text",
    ...
)]
```

**`backend/app/cdm/adapters/custom_pipeline/tools/fitz_tool.py`** — update Block constructor (~line 108):
```python
block = Block(
    id=prov_id,
    role=BlockRole.TEXT,     # was PARAGRAPH
    native_type="text",
    ...
)
```

**`backend/app/cdm/adapters/custom_pipeline/merger.py`** — update comment:
```python
# Before: "A fitz PARAGRAPH block that overlaps..."
# After:  "A fitz TEXT block that overlaps..."
```

**`backend/app/services/block_chunking_service.py`** — update comment (~line 13):
```python
#    - Other content roles (TEXT/LIST/CAPTION/CODE/FORMULA): append to   # was PARAGRAPH/LIST/...
```

- [ ] **Step 3: Update backend test files**

Apply the rule at the top of this task to every file below. For each file, the change is mechanical: `BlockRole.PARAGRAPH` → `BlockRole.TEXT`, and `"paragraph"` → `"text"` where it is a role value (not a `native_type`).

**`backend/tests/cdm/test_models.py`** — also update the value assertion:
```python
assert BlockRole.TEXT.value == "text"   # was PARAGRAPH.value == "paragraph"
```

**`backend/tests/cdm/adapters/test_docling_adapter.py`** — update parametrize tuples:
```python
("text",      BlockRole.TEXT),   # was PARAGRAPH
("paragraph", BlockRole.TEXT),   # was PARAGRAPH; key string stays
```

**`backend/tests/cdm/adapters/test_llamaparse_adapter.py`**:
```python
("text", BlockRole.TEXT),        # was PARAGRAPH

# and assertion:
assert body.role.value == "text"  # was "paragraph"
```

**`backend/tests/cdm/test_landing_ai_adapter.py`** — update all `BlockRole.PARAGRAPH` references and role value assertions:
```python
assert _detect_text_role("Hello world.") == BlockRole.TEXT    # was PARAGRAPH
assert _detect_text_role("...") == BlockRole.TEXT             # all fallback cases
assert doc.blocks[0].role == BlockRole.TEXT
assert by_id["c-para"].role == BlockRole.TEXT
assert BlockRole.TEXT in roles
```

**`backend/tests/cdm/adapters/test_simple_text_adapter.py`**:
```python
assert all(b.role == BlockRole.TEXT for b in doc.blocks)   # was PARAGRAPH
```

**`backend/tests/cdm/adapters/custom_pipeline/test_fitz_tool.py`**:
```python
paras = [b for b in result.blocks if b.role == BlockRole.TEXT]   # was PARAGRAPH
para  = next(b for b in result.blocks if b.role == BlockRole.TEXT)
```

**`backend/tests/cdm/adapters/custom_pipeline/test_tools_base.py`**:
```python
block = Block(id="fitz:0:0", role=BlockRole.TEXT, ...)   # was PARAGRAPH
```

**`backend/tests/cdm/adapters/custom_pipeline/test_merger.py`**:
```python
Block(id="fitz:0:0", role=BlockRole.TEXT, ...),   # both blocks
Block(id="fitz:0:1", role=BlockRole.TEXT, ...),
```

**`backend/tests/cdm/adapters/custom_pipeline/test_adapter.py`**:
```python
Block(id="doc1:0:0", role=BlockRole.TEXT, ...),
Block(id="doc1:1:0", role=BlockRole.TEXT, ...),
```

**`backend/tests/cdm/test_workloads.py`**:
```python
role=BlockRole.TEXT,
native_type="paragraph",   # ← leave alone (native type string)
```

**`backend/tests/cdm/test_models.py`** (covered above in Step 3 opener).

**`backend/tests/repositories/test_parsed_document_round_trip.py`**:
```python
role=BlockRole.TEXT,   # was PARAGRAPH
```

**`backend/tests/services/test_block_chunking_service.py`** — update all `BlockRole.PARAGRAPH` and `"paragraph"` role-value strings:
```python
_block("b2", BlockRole.TEXT, ...)
_block("p1", BlockRole.TEXT, ...)
# ...all _block() calls that use PARAGRAPH

# filter lists:
config=_config(block_role_filter=["header", "text"])   # was "paragraph"

# assertions on block_roles metadata:
assert chunks[0].metadata["block_roles"] == ["heading", "text", "text"]  # was "paragraph"
assert meta["block_roles"] == ["heading", "text", "text"]
```

**`backend/tests/services/test_chunking_dispatcher.py`**:
```python
role=BlockRole.TEXT,   # was PARAGRAPH
assert chunks[0].metadata["block_roles"] == ["heading", "text"]   # was "paragraph"
```

**`backend/tests/services/test_index_processing_cdm.py`**:
```python
role=BlockRole.TEXT,   # was PARAGRAPH
```

**`backend/tests/services/test_extraction_service.py`**:
```python
Block(id="b1", role=BlockRole.TEXT, ...)   # was PARAGRAPH
```

**`backend/tests/services/test_query_citation.py`**:
```python
# ~line 88 — Block constructor
id="b2", role=BlockRole.TEXT, native_type="p", page_index=2,   # was PARAGRAPH

# ~line 115 — assertion on block_roles list
assert cit.block_roles == ["heading", "text"]   # was "paragraph"

# ~line 163 — raw dict
"block_roles": ["text"],   # was "paragraph"
```

**`backend/tests/services/classification/test_service.py`**:
```python
Block(id=f"b{i}", role=BlockRole.TEXT, ...)   # was PARAGRAPH
```

**`backend/tests/services/classification/test_serializer.py`**:
```python
role=BlockRole.TEXT,
native_type="paragraph",   # ← leave alone (native type string)
```

**`backend/tests/services/classification/test_assembler.py`**:
```python
role=BlockRole.TEXT,
native_type="paragraph",   # ← leave alone
```

**`backend/tests/services/classification/test_llm_classifier.py`**:
```python
Block(id=f"b{i}", role=BlockRole.TEXT, ...)   # was PARAGRAPH
```

**`backend/tests/services/parsing/test_custom_pipeline_runner.py`**:
```python
assert any(b.role == BlockRole.TEXT for b in doc.blocks)   # was PARAGRAPH
```

**`backend/tests/adapters/extraction/test_pipeline.py`**:
```python
Block(id=f"b{i}", role=BlockRole.TEXT, ...)   # was PARAGRAPH

# block_filter drop config — this IS a role value, not a native_type:
preprocess=[{"stage": "block_filter", "config": {"drop": ["text"]}}]   # was "paragraph"
```

**`backend/tests/adapters/extraction/test_llm_context.py`**:
```python
role=BlockRole.TEXT,
native_type="paragraph",   # ← leave alone
```

**`backend/tests/adapters/extraction/preprocess/test_block_filter.py`**:
```python
Block(id="p", role=BlockRole.TEXT, ...)   # was PARAGRAPH
```

**`backend/tests/adapters/extraction/chunking/test_token_budget.py`**:
```python
Block(id=f"b{i}", role=BlockRole.TEXT, ...)   # was PARAGRAPH
```

**`backend/tests/routers/test_classification_router.py`** — raw dict fixtures and assertions:
```python
{"id": "b-1", "role": "text", "native_type": "paragraph", "text": "Foo", ...},  # role → "text"; native_type stays
{"id": "b-2", "role": "text", "native_type": "paragraph", "text": "Bar", ...},

assert data[0]["role"] == "text"   # was "paragraph"
```

**`backend/tests/repositories/test_classification_run_repository.py`** — raw dict fixtures:
```python
{"id": "b-2", "role": "text", "native_type": "paragraph", ...},   # role → "text"
{"id": "b-3", "role": "text", "native_type": "paragraph", ...},
```

**`backend/tests/schemas/test_index_config_schema.py`** — filter list:
```python
"blockRoleFilter": ["text"],         # was "paragraph"
assert cfg.block_role_filter == ["text"]   # was "paragraph"
```

- [ ] **Step 4: Run the full backend test suite**

```bash
cd backend && uv run python -m pytest -o "addopts="
```

Expected: all tests pass. If any test fails with `AttributeError: PARAGRAPH`, you missed a reference — search for it:

```bash
grep -r "BlockRole\.PARAGRAPH\|\"role\".*paragraph\|role.*=.*paragraph" backend/ --include="*.py"
```

- [ ] **Step 5: Commit**

```bash
git add backend/
git commit -m "refactor(cdm): rename BlockRole.PARAGRAPH to BlockRole.TEXT"
```

---

## Task 4: Frontend sweep

**Files:**
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/components/parse-runs/DocumentPdfViewer.tsx`
- Modify: `frontend/src/components/parse-runs/ParsedDocumentPane.test.tsx`
- Modify: `frontend/src/components/parse-runs/DocumentPdfViewer.test.tsx`
- Modify: `frontend/src/hooks/useClassificationRuns.test.ts`
- Modify: `frontend/src/pages/IndexDetailPage.test.tsx`
- Modify: `frontend/src/components/indexes/BlockConfigPanel.test.tsx`

**Interfaces:**
- Consumes: backend API now returns `"text"` as role value for generic text blocks (from Task 3)

- [ ] **Step 1: Update types/index.ts**

In `frontend/src/types/index.ts`, make two changes:

```typescript
// BlockRole union type — change 'paragraph' to 'text'
export type BlockRole =
  | 'title'
  | 'heading'
  | 'text'         // was 'paragraph'
  | 'list'
  | 'table'
  | 'figure'
  | 'caption'
  | 'header'
  | 'footer'
  | 'marginalia'
  | 'code'
  | 'formula'
  | 'link'
  | 'other'

// BLOCK_ROLE_OPTIONS array
export const BLOCK_ROLE_OPTIONS: BlockRole[] = [
  'title', 'heading', 'text', 'list', 'table', 'figure',   // was 'paragraph'
  'caption', 'code', 'formula', 'link', 'other',
]
```

- [ ] **Step 2: Update DocumentPdfViewer.tsx color map**

In `frontend/src/components/parse-runs/DocumentPdfViewer.tsx`, change the color map key:

```typescript
// was:  paragraph: 'rgb(107,114,128)',
text: 'rgb(107,114,128)',
```

- [ ] **Step 3: Update frontend test files**

Apply the rule: `'paragraph'` → `'text'` where it is a role value.

**`frontend/src/components/parse-runs/ParsedDocumentPane.test.tsx`**:
```typescript
{ id: 'b1', page_index: 0, role: 'text', text: 'Block one' },   // was 'paragraph'
expect(screen.getAllByText('text').length).toBeGreaterThan(0)      // was 'paragraph'
// second occurrence:
blocks: [{ id: 'b1', page_index: 0, role: 'text', text: 'Block one' }],  // was 'paragraph'
```

**`frontend/src/components/parse-runs/DocumentPdfViewer.test.tsx`**:
```typescript
role: 'text',   // was 'paragraph'
```

**`frontend/src/hooks/useClassificationRuns.test.ts`**:
```typescript
{ blockId: 'b-1', pageIndex: 0, role: 'text', ... },   // was 'paragraph'
{ blockId: 'b-2', pageIndex: 1, role: 'text', ... },   // was 'paragraph'
```

**`frontend/src/pages/IndexDetailPage.test.tsx`**:
```typescript
blockRoleFilter: ['text', 'heading'],                  // was ['paragraph', 'heading']
expect(screen.getByText('text, heading')).toBeInTheDocument()   // was 'paragraph, heading'
```

**`frontend/src/components/indexes/BlockConfigPanel.test.tsx`**:
```typescript
config={{ ...baseConfig, blockRoleFilter: ['table', 'text'] }}   // was 'paragraph'
expect(screen.getByRole('button', { name: /^text$/i }))          // was /^paragraph$/i
```

- [ ] **Step 4: Run frontend tests and lint**

```bash
cd frontend && npx vitest run && npm run lint
```

Expected: all tests pass, no lint errors. If any test fails with a `'paragraph'` reference, search:

```bash
grep -r "paragraph" frontend/src --include="*.ts" --include="*.tsx"
```

Any remaining `'paragraph'` hits that are role values (not comments or unrelated UI copy like "Attach paragraphs and tables…") need updating.

- [ ] **Step 5: Build to verify no type errors**

```bash
cd frontend && npm run build
```

Expected: clean build with no TypeScript errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/
git commit -m "refactor(cdm): update frontend BlockRole type paragraph → text"
```

---

## Task 5: PR

- [ ] **Step 1: Push branch**

```bash
git push -u origin refactor/block-role-paragraph-to-text
```

- [ ] **Step 2: Create PR**

```bash
gh pr create \
  --title "refactor(cdm): rename BlockRole.PARAGRAPH to BlockRole.TEXT" \
  --body "Closes #<issue-number>

## Summary
- Renames \`BlockRole.PARAGRAPH = \"paragraph\"\` → \`BlockRole.TEXT = \"text\"\` in the CDM enum
- Alembic data migration rewrites \`\"paragraph\"\` → \`\"text\"\` in \`parsed_documents.content\`, \`chunks.chunk_metadata\`, \`indexes.config\`
- Full sweep of ~45 backend files and 5 frontend files
- No new tests — existing suite updated

## Why
\`PARAGRAPH\` is a misnomer. Every parser maps their native \"text\" type to this role, and the content is often a single word or label, not a paragraph. \`TEXT\` is accurate and matches parser vocabulary (LlamaParse: \`\"text\"\`, fitz: \`native_type=\"text\"\`, Docling: \`\"text\"\`).

## Notes for reviewer
- \`native_type\` strings (\`\"paragraph\"\`, \`\"text\"\`) are parser vocabulary and are intentionally unchanged
- \`_ROLE_MAP\` keys in adapter files are parser vocabulary and intentionally unchanged
- No prod data exists; migration handles dev data only

## Test plan
- [ ] \`cd backend && uv run python -m pytest -o \"addopts=\"\` — all pass
- [ ] \`cd frontend && npx vitest run && npm run lint && npm run build\` — all pass
- [ ] \`alembic upgrade head\` applies cleanly
- [ ] \`alembic downgrade -1\` reverses cleanly"
```
