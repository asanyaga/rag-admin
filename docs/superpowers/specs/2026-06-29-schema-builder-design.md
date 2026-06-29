# Schema Builder for Extraction — Design Spec

**Date:** 2026-06-29
**Status:** Approved

---

## Overview

Add a visual schema builder to the `ExtractionSchemaEditor` dialog. Users toggle between a **Builder** view (visual field editor) and a **JSON** view (raw textarea). Both views stay in sync via a single canonical data model — a typed field tree.

No backend changes are required. The `schemaDefinition` shape stored in the database is unchanged.

---

## Data Model

The canonical state is a `SchemaField[]` tree:

```ts
type FieldType = 'string' | 'number' | 'integer' | 'boolean' | 'object' | 'array'

interface SchemaField {
  key: string            // JSON property name
  type: FieldType
  description: string    // critical for LLM guidance
  required: boolean
  nullable: boolean      // adds null to type union
  enumValues?: string[]  // for string / number / integer types
  items?: SchemaField    // for array type — can itself be type: 'object' with properties
  properties?: SchemaField[]  // for object type (nested fields)
}
```

Two pure conversion utilities power sync:

- **`schemaToFields(json: Record<string, unknown>): SchemaField[]`** — parses a JSON Schema object into the field tree
- **`fieldsToSchema(fields: SchemaField[]): Record<string, unknown>`** — serializes the field tree back to JSON Schema

Arrays of objects are supported: when `type = array`, `items` is a full `SchemaField` which may itself have `type = 'object'` with nested `properties`.

Unknown JSON Schema keywords (`$ref`, `allOf`, etc.) are preserved verbatim in the JSON output but not rendered in the builder. A warning banner notes this when detected.

---

## Component Architecture

All new components live in `frontend/src/components/extraction/`.

### `SchemaBuilder`

Top-level toggle container. Owns:
- `fields: SchemaField[]` — canonical state
- `activeView: 'builder' | 'json'`
- `jsonText: string` — the JSON string representation

Sync logic:
- **JSON edit → builder:** debounce-parse JSON → if valid, update `fields`; if invalid, show parse error but preserve last valid `fields`
- **Builder edit → JSON:** `fieldsToSchema(fields)` → update `jsonText`

Exposes: `value: Record<string, unknown>` + `onChange: (v: Record<string, unknown>) => void` — same interface as the current textarea, so `ExtractionSchemaEditor` only needs to swap the textarea for `<SchemaBuilder />`.

### `SchemaFieldEditor`

Renders one field row. Controls:
- Key (text input)
- Type (select: string / number / integer / boolean / object / array)
- Description (text input)
- Required toggle
- Nullable toggle
- Enum values list (visible when type is string / number / integer) — inline add/remove
- For `object`: indented nested `SchemaFieldEditor` list + "Add field" button
- For `array`: single "Item type" sub-row (a `SchemaFieldEditor` for `items`) — if item type is `object`, its properties expand inline

Recursively embeds itself for nested object properties and array item schemas.

### `SchemaBuilderJsonView`

The existing JSON textarea, now a controlled component accepting `value: string` and `onChange: (v: string) => void`. Monospace font, full width. Displays an inline parse error below when JSON is invalid.

---

## Integration

`ExtractionSchemaEditor` replaces the current `<Textarea>` schema section with:

```tsx
<SchemaBuilder
  value={parsedSchema}
  onChange={setParsedSchema}
/>
```

The name, description, and extraction target fields above it are unchanged.

---

## Builder UX

**Field row layout:** key · type · description · required · nullable · delete (×)

**Type-specific expansions (shown inline below the row):**
- `string / number / integer`: enum value list with add/remove
- `object`: indented nested field list + "Add field" button
- `array`: single item-schema row; if item type is `object`, expands to its properties

**Tab toggle** (`Builder | JSON`) lives above both views. Switching is instant — no async, no data loss.

**Add field** button at the bottom of each property level adds a new blank field.

---

## Validation & Error Handling

| Scenario | Behaviour |
|---|---|
| Invalid JSON in JSON view | Inline error below textarea; last valid field tree preserved |
| Unknown JSON Schema keywords | Preserved in JSON output; warning banner in builder view |
| Duplicate field key | Inline error on the key input |
| Empty field key | Blocked — save disabled until resolved |
| Root type not `object` | Existing check in `handleSave` unchanged |

---

## Testing

**Unit tests** (`schemaToFields` / `fieldsToSchema`):
- All field types (string, number, integer, boolean, object, array)
- Nested objects
- Arrays of primitives and arrays of objects
- Enum values
- Nullable fields
- Round-trip fidelity: `fieldsToSchema(schemaToFields(json))` ≅ `json`

**Component tests** (`SchemaBuilder`):
- JSON → builder sync (valid JSON updates field list)
- Builder → JSON sync (field edit updates textarea)
- Invalid JSON preserves last valid builder state
- Toggle switching renders correct view

---

## Out of Scope

- `$ref`, `anyOf`, `allOf`, `oneOf`, `if/then/else` — not rendered in builder (preserved in JSON)
- Drag-to-reorder fields
- Import schema from an existing extraction result
