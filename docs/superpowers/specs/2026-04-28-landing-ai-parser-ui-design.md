# Landing AI Parser UI — Design

> **Status**: Approved.
> **Date**: 2026-04-28

---

## 1. Goals

1. Add Landing AI as a selectable parser in the document upload and re-parse flows.
2. Introduce a `PARSER_REGISTRY` constant so adding future parsers requires only a new config component + one registry entry.
3. Fix two backend router gates that currently exclude `landing_ai` from the CDM path.

---

## 2. Scope

### In scope
- Refactor `ParseMethodSelector` to drive parser options from a registry.
- Extract LlamaParse config into `LlamaParseConfig.tsx`.
- Create `LandingAIConfig.tsx` with a model dropdown.
- Backend: extend CDM gate condition and re-parse validation to accept `"landing_ai"`.
- Backend: inject `parser` key into `parse_cfg` so the CDM dispatch picks the right runner.

### Out of scope
- Generic schema-driven config rendering (YAGNI — revisit when 4+ parsers exist with real configs).
- Exposing `poll_timeout_s` / `poll_interval_s` in the UI.
- Any changes to the `simple` parser flow.

---

## 3. File Changes

| File | Action |
|---|---|
| `frontend/src/components/documents/ParseMethodSelector.tsx` | Refactor — registry + conditional render |
| `frontend/src/components/documents/parser-configs/LlamaParseConfig.tsx` | Create — extracted from current ParseMethodSelector |
| `frontend/src/components/documents/parser-configs/LandingAIConfig.tsx` | Create — model dropdown |
| `frontend/src/types/parsing.ts` | Update — add `model?: string` to `ParseConfig` |
| `backend/app/routers/documents.py` | Update — CDM gate + `parse_cfg["parser"]` injection |
| `backend/app/routers/parse_results.py` | Update — CDM gate + validation + `parse_cfg["parser"]` injection |

---

## 4. Frontend Design

### 4.1 `PARSER_REGISTRY`

Lives at the top of `ParseMethodSelector.tsx`. Each entry describes a parser the user can select.

```ts
interface ParserMeta {
  label: string
  description: string
  defaultConfig: ParseConfig
}

const PARSER_REGISTRY: Record<string, ParserMeta> = {
  simple: {
    label: 'Simple (local)',
    description: 'Basic text extraction. Works on clean text-based PDFs.',
    defaultConfig: {},
  },
  llamaparse: {
    label: 'LlamaParse',
    description: 'Intelligent parsing. Handles complex layouts, tables, scanned documents.',
    defaultConfig: { tier: 'agentic', expand: ['markdown', 'text', 'items'] },
  },
  landing_ai: {
    label: 'Landing AI',
    description: 'Vision-based parsing. Best for images, shelf photos, and complex visual layouts.',
    defaultConfig: { model: 'dpt-2-latest' },
  },
}
```

When the user switches parser type, `onParserTypeChange` fires and `onConfigChange` fires with the incoming parser's `defaultConfig`. This resets config to a clean state — stale LlamaParse fields do not bleed into a LandingAI submission.

### 4.2 `ParseMethodSelector` structure

```tsx
<div>
  {/* Parser select driven by Object.entries(PARSER_REGISTRY) */}
  <Select value={parserType} onValueChange={handleParserChange}>
    ...
  </Select>
  <p>{PARSER_REGISTRY[parserType]?.description}</p>

  {parserType === 'llamaparse' && <LlamaParseConfig config={config} onChange={onConfigChange} disabled={disabled} />}
  {parserType === 'landing_ai' && <LandingAIConfig config={config} onChange={onConfigChange} disabled={disabled} />}
</div>
```

### 4.3 `LlamaParseConfig`

Extracted verbatim from the current inline block in `ParseMethodSelector`. No behaviour change — tier dropdown + output checkboxes (text always checked, markdown + items toggleable, markdown/items disabled on fast tier).

### 4.4 `LandingAIConfig`

Single model dropdown. One option now; dropdown is present to accommodate future models without a UI change.

```
Model
[ dpt-2-latest ▼ ]
<p>Vision-based document parsing model.</p>
```

Config shape: `{ model: string }`. Default: `{ model: 'dpt-2-latest' }`.

### 4.5 `ParseConfig` type update

```ts
export type ParseConfig = {
  tier?: string
  expand?: string[]
  model?: string
  [key: string]: unknown
}
```

---

## 5. Data Flow

What the frontend sends for each parser:

| Field | `simple` | `llamaparse` | `landing_ai` |
|---|---|---|---|
| `parser_type` (form field) | `"simple"` | `"llamaparse"` | `"landing_ai"` |
| `parse_config` (JSON string) | `null` | `{"tier":"agentic","expand":["markdown","text","items"]}` | `{"model":"dpt-2-latest"}` |

---

## 6. Backend Changes

### 6.1 CDM gate — both routers

**Before:**
```python
use_cdm = settings.USE_CDM_PARSER and parser_type == "llamaparse"
```

**After:**
```python
use_cdm = settings.USE_CDM_PARSER and parser_type in ("llamaparse", "landing_ai")
```

Applies to:
- `backend/app/routers/documents.py` (upload route, line ~107; bulk upload route, line ~234)
- `backend/app/routers/parse_results.py` (re-parse route, line ~96)

### 6.2 Parser key injection — both routers

After stripping `representation_kind` from config, inject the parser key so the CDM dispatch table picks the correct runner:

```python
parse_cfg = {k: v for k, v in (config_dict or {}).items() if k != "representation_kind"}
parse_cfg["parser"] = parser_type  # e.g. "landing_ai" → LandingAI runner
```

This keeps the frontend config clean — no `parser` key the UI needs to manage.

### 6.3 Re-parse validation fix

`parse_results.py` validates the parser type via `get_parser()` (the legacy registry). `landing_ai` is not in that registry so it would be rejected before reaching the CDM path. Allow CDM parser types through:

```python
parser = get_parser(body.parser_type)
if parser is None and body.parser_type not in ("simple", "llamaparse", "landing_ai"):
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Unknown parser type: {body.parser_type}",
    )
```

---

## 7. Extending for Future Parsers

To add a new parser (e.g. `unstructured_api`):

1. Create `frontend/src/components/documents/parser-configs/UnstructuredApiConfig.tsx`
2. Add an entry to `PARSER_REGISTRY` in `ParseMethodSelector.tsx`
3. Add `{parserType === 'unstructured_api' && <UnstructuredApiConfig ... />}` in `ParseMethodSelector`
4. Extend the backend CDM gate tuple and `get_parser()` validation list

No other files need to change.
