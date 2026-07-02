# Design: Rename `BlockRole.PARAGRAPH` → `BlockRole.TEXT`

**Date:** 2026-07-02  
**Status:** Approved  
**Scope:** Single PR — enum rename + Alembic data migration + full code/test sweep  
**No prod data** — no backward-compat alias required

---

## 1. Problem

`BlockRole.PARAGRAPH` is the CDM's catch-all "generic text block" role, but the name is misleading. Every parser maps their native "text" type to it:

| Parser | Native type → CDM role |
|---|---|
| fitz (PyMuPDF) | `btype == 0` → `PARAGRAPH` |
| LlamaParse | `"text"` → `PARAGRAPH` |
| Docling | `"text"`, `"paragraph"` → `PARAGRAPH` |
| LandingAI | fallback default → `PARAGRAPH` |
| SimpleText | every line → `PARAGRAPH` |

A block with `role=PARAGRAPH` is frequently a single word, a label, or an empty string. The name implies multi-sentence prose — a semantic claim the CDM cannot make and parsers do not support.

`TEXT` is the accurate label: it means "a block of extracted text whose internal structure we do not know."

---

## 2. Decision

Rename the enum member and its serialized string value:

```python
# before
PARAGRAPH = "paragraph"

# after
TEXT = "text"
```

No backward-compat alias. No staged migration. Single PR.

---

## 3. Database Migration

`"paragraph"` is stored as a plain string in three JSONB/JSON columns. No typed Postgres `ENUM` is involved, so no `ALTER TYPE` is needed — only targeted `UPDATE` statements via `op.execute()` in a new Alembic migration.

| Table | Column | JSON path |
|---|---|---|
| `parsed_documents` | `content` (JSONB) | `blocks[*].role` |
| `chunks` | `chunk_metadata` (JSON) | `block_roles[*]` |
| `indexes` | `config` (JSON) | `blockRoleFilter[*]` |

Classification tables (`classification_runs`, `classification_regions`) do **not** store block roles independently — roles are derived live by deserializing `parsed_documents.content` at query time. No migration needed there.

### Migration SQL (upgrade)

```sql
-- parsed_documents: rewrite role in each block
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
WHERE content->'blocks' @> '[{"role": "paragraph"}]';

-- chunks: rewrite role values in block_roles array
UPDATE chunks
SET chunk_metadata = jsonb_set(
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
WHERE chunk_metadata::jsonb @> '{"block_roles": ["paragraph"]}';

-- indexes: rewrite role values in blockRoleFilter array
UPDATE indexes
SET config = jsonb_set(
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
WHERE config::jsonb->'blockRoleFilter' IS NOT NULL
  AND config::jsonb @> '{"blockRoleFilter": ["paragraph"]}';
```

The downgrade reverses each substitution (`"text"` → `"paragraph"`).

---

## 4. Code Sweep

### Backend (~60 files)

**Rule:** If it is a `BlockRole.*` enum member reference → update. If it is a `_ROLE_MAP` key or `native_type` string (parser vocabulary) → leave alone.

**`backend/app/cdm/models.py`**
```python
PARAGRAPH = "paragraph"  →  TEXT = "text"
```

**Adapter `_ROLE_MAP` right-hand sides** (`docling.py`, `llamaparse.py`):
```python
# before
"text":      BlockRole.PARAGRAPH,
"paragraph": BlockRole.PARAGRAPH,   # docling only

# after
"text":      BlockRole.TEXT,
"paragraph": BlockRole.TEXT,        # key stays — docling's own label
```

**`fitz_tool.py`** — inline Block constructor:
```python
# before
Block(role=BlockRole.PARAGRAPH, native_type="text", ...)
# after
Block(role=BlockRole.TEXT, native_type="text", ...)
# native_type="text" unchanged — that's what fitz calls it
```

**`landing_ai.py`** — fallback return in `_detect_text_role`:
```python
return BlockRole.PARAGRAPH  →  return BlockRole.TEXT
```

**`simple_text.py`** — two inline Block constructors.

**All other backend files** — sweep `BlockRole.PARAGRAPH` → `BlockRole.TEXT`.

### Frontend (2 files)

**`frontend/src/types/index.ts`**:
```typescript
// BlockRole union type
| 'paragraph'  →  | 'text'

// BLOCK_ROLE_OPTIONS array
'paragraph'  →  'text'
```

**`frontend/src/components/parse-runs/DocumentPdfViewer.tsx`**:
```typescript
// color map key
paragraph: 'rgb(107,114,128)'  →  text: 'rgb(107,114,128)'
```

---

## 5. Test Sweep

No new tests. Existing suite covers the rename fully.

- All `BlockRole.PARAGRAPH` → `BlockRole.TEXT`
- Role-value string literals `"paragraph"` → `"text"` in fixtures (`role="paragraph"`, `block_role_filter=["paragraph"]`, assertions on `block_roles`)
- `native_type="paragraph"` in test fixtures **stays** — it's docling adapter source vocabulary

Key test: `test_models.py:17` asserts `BlockRole.PARAGRAPH.value == "paragraph"` → becomes `BlockRole.TEXT.value == "text"`.

---

## 6. What Does NOT Change

- `native_type` strings throughout — `"text"`, `"paragraph"` as parser-native labels are untouched
- `_ROLE_MAP` keys in adapter files
- The docling adapter's `"paragraph"` key (Docling's own element label)
- Color, display logic, chunking logic — only the string value and enum name change
