# Extraction Schema System Prompt

**Date:** 2026-06-23
**Status:** Approved

## Overview

Add a per-schema system prompt field to `ExtractionSchema`. When LLM extraction runs, this prompt overrides the hardcoded application default. Users view and edit it in the schema editor, where the hardcoded default text is shown as placeholder so they know exactly what they are overriding.

## Scope

- LLM extraction method only (`extractionMethod === 'llm'`). LlamaExtract is a third-party service and has no system prompt concept.
- Per-schema granularity (not per-project or per-run).
- The existing per-run `llmConfig.systemPrompt` field remains unchanged and continues to take highest priority.

## Data Model

Add one nullable column to `extraction_schemas`:

```sql
ALTER TABLE extraction_schemas ADD COLUMN system_prompt TEXT NULL;
```

Python model (`backend/app/models/extraction_schema.py`):

```python
system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
```

Pydantic schemas (`backend/app/schemas/extraction_result.py`):

- `ExtractionSchemaCreate` — `system_prompt: str | None = None` (alias `"systemPrompt"`)
- `ExtractionSchemaUpdate` — `system_prompt: str | None = None` (alias `"systemPrompt"`)
- `ExtractionSchemaResponse` — `system_prompt: str | None = None` (alias `"systemPrompt"`), populated in `from_orm_model`

Frontend types (`frontend/src/types/extraction.ts`):

- `ExtractionSchema` — `systemPrompt?: string`
- `ExtractionSchemaCreate` — `systemPrompt?: string`
- `ExtractionSchemaUpdate` — `systemPrompt?: string`

## Backend: Extraction Priority Chain

`LLMExtractor._build_messages` selects the system prompt using this priority:

1. **Per-run override** — `llm_config.system_prompt` (already supported via `PromptConfigEditor`)
2. **Schema default** — `config["schema_system_prompt"]` injected by the router
3. **Hardcoded fallback** — `DEFAULT_EXTRACTION_SYSTEM_PROMPT`

The extraction router (`backend/app/routers/extraction.py`) already fetches the full `ExtractionSchema` record before dispatching. It injects `schema.system_prompt` into the `config` dict as `"schema_system_prompt"` when the field is non-null.

## UI: Schema Editor

`ExtractionSchemaEditor` gets a new textarea below the JSON Schema field:

- **Label:** `System Prompt (LLM extraction)`
- **Description:** `Applies to LLM extraction only. Leave blank to use the application default.`
- **Placeholder:** The full `DEFAULT_EXTRACTION_SYSTEM_PROMPT` text, so users can read the default before deciding to override it.
- **Behaviour:** Pre-filled with `schema.systemPrompt` when editing an existing schema. Submitted as `systemPrompt: text || undefined` (empty string → omit field).

No changes to `ExtractionForm`, `PromptConfigEditor`, or `ExtractionHistory`.

## Error Handling

- Schema editor: no special validation — the system prompt is free text, any string is valid.
- Backend: `schema_system_prompt` in config is treated as a plain string; the extractor does not validate its content.

## Migration

A single Alembic migration adds the nullable column with no backfill needed (existing schemas default to `NULL`, which falls through to the hardcoded default — no behaviour change for existing data).

## Testing

- Backend unit test: `LLMExtractor._build_messages` with (a) no config, (b) `schema_system_prompt` in config, (c) both `schema_system_prompt` and `llm_config.system_prompt` — verifies the priority chain.
- Frontend: update `ExtractionSchemaEditor` tests to assert the system prompt field renders and submits correctly.
