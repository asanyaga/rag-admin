# Extraction LLM Prompt Visibility

**Date:** 2026-06-23
**Status:** Approved

## Overview

When running LLM extraction, users cannot currently see the default system prompt or user prompt template — both fields show "leave blank to use the default" placeholder text. This means users cannot read the defaults before deciding to override them, making prompt variation comparison difficult.

This feature makes both default prompts visible and editable per run. There is no persistence; schema-level or project-level default overrides are a later iteration.

## Scope

- LLM extraction method only. LlamaExtract has no prompt concept.
- Per-run only — no persistence, no model changes, no migration.
- Both the system prompt and user prompt template are pre-filled with their defaults.
- Users can edit either field and run extractions with different prompt variations; the extraction history already records each run's config, enabling comparison.

## Backend

Add one new endpoint:

```
GET /extractors/llm/defaults
```

Response:

```json
{
  "systemPrompt": "You are a structured data extraction assistant...",
  "userPromptTemplate": "Extract structured data from the following document..."
}
```

The response body is the two constants already defined in `backend/app/adapters/extraction/llm.py`:
- `DEFAULT_EXTRACTION_SYSTEM_PROMPT`
- `DEFAULT_USER_PROMPT_TEMPLATE`

No auth required beyond the standard project-member check (same as other extractor endpoints). No query parameters. Response is effectively static but served from the backend so the frontend never duplicates the strings.

## Frontend

**API layer** (`frontend/src/api/extraction.ts`): add `getLlmDefaults(): Promise<{ systemPrompt: string; userPromptTemplate: string }>` calling `GET /extractors/llm/defaults`.

**ExtractionForm** (`frontend/src/components/extraction/ExtractionForm.tsx`):

- On mount (or when `extractionMethod` switches to `'llm'`), call `getLlmDefaults()` and store the result in local state.
- Pre-fill `promptConfig.systemPrompt` with the fetched system prompt if it is currently unset.
- Pre-fill `userPromptTemplate` with the fetched user prompt template if it is currently unset.
- Both fields remain fully editable. The user can clear them or replace them for this run.
- If the fetch fails, fall back silently — fields remain blank and the existing "leave blank" behaviour applies.

No changes to `PromptConfigEditor`, `ExtractionHistory`, or any type definitions.

## Priority Chain (unchanged)

`LLMExtractor` already uses: per-run `llm_config.system_prompt` → `DEFAULT_EXTRACTION_SYSTEM_PROMPT`. With pre-filling, users will typically send explicit values in both fields rather than relying on the backend fallback, but the fallback remains in place for API callers that omit the fields.

## Error Handling

- Fetch failure: silent fallback, no visible error. The extraction can still run using backend defaults.
- Empty string submitted: the backend treats an empty `userPromptTemplate` as "use default", which is consistent with current behaviour.

## Testing

- Backend: unit test for the new endpoint — assert both strings match the constants.
- Frontend: update `ExtractionForm` tests to assert that when LLM method is selected, the system prompt and user prompt template fields are populated with the fetched defaults.
