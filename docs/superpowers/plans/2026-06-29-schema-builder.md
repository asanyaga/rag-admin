# Schema Builder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Builder/JSON toggle to `ExtractionSchemaEditor` so users can build extraction schemas visually or in raw JSON, with both views kept in sync.

**Architecture:** A typed `SchemaField[]` tree is the single source of truth. Two pure functions (`schemaToFields`, `fieldsToSchema`) convert between it and JSON Schema. `SchemaBuilder` owns this state, exposes `value`/`onChange` to its parent, and renders either a visual field list or a JSON textarea based on a tab toggle.

**Tech Stack:** React 18, TypeScript, shadcn/ui (Tabs, Checkbox, Select, Input, Textarea), Tailwind CSS, Vitest + Testing Library.

## Global Constraints

- No new npm packages — debounce via `useRef` + `setTimeout`
- All new components in `frontend/src/components/extraction/`
- Pure functions in `frontend/src/lib/schemaBuilder.ts`
- No backend changes — `schemaDefinition` shape on the wire is unchanged
- shadcn Checkbox, Tabs, Select, Input, Textarea, Button are all available
- Run tests with: `npx vitest run --reporter=verbose` from `frontend/`
- Run lint with: `npm run lint` from `frontend/`

---

## File Map

| File | Status | Responsibility |
|---|---|---|
| `frontend/src/lib/schemaBuilder.ts` | Create | Types + pure conversion functions |
| `frontend/src/lib/schemaBuilder.test.ts` | Create | Unit tests for pure functions |
| `frontend/src/components/extraction/SchemaBuilderJsonView.tsx` | Create | Controlled JSON textarea + parse error |
| `frontend/src/components/extraction/SchemaFieldEditor.tsx` | Create | Recursive field row component |
| `frontend/src/components/extraction/SchemaBuilder.tsx` | Create | Toggle container, owns field state |
| `frontend/src/components/extraction/SchemaBuilder.test.tsx` | Create | Component tests |
| `frontend/src/components/extraction/ExtractionSchemaEditor.tsx` | Modify | Swap textarea for `<SchemaBuilder />` |

---

### Task 1: Pure functions and types (`schemaBuilder.ts`)

**Files:**
- Create: `frontend/src/lib/schemaBuilder.ts`
- Test: `frontend/src/lib/schemaBuilder.test.ts`

**Interfaces:**
- Produces: `FieldType`, `SchemaField`, `schemaToFields`, `fieldsToSchema`, `hasUnknownKeywords`, `newBlankField`, `getDuplicateKeys`, `validateFields` — all exported, all used by later tasks

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/lib/schemaBuilder.test.ts`:

```ts
// @vitest-environment node
import { describe, it, expect } from 'vitest'
import {
  schemaToFields,
  fieldsToSchema,
  hasUnknownKeywords,
  validateFields,
  newBlankField,
  getDuplicateKeys,
} from './schemaBuilder'
import type { SchemaField } from './schemaBuilder'

describe('fieldsToSchema', () => {
  it('converts a required string field', () => {
    const fields: SchemaField[] = [
      { key: 'name', type: 'string', description: 'Full name', required: true, nullable: false },
    ]
    expect(fieldsToSchema(fields)).toEqual({
      type: 'object',
      properties: { name: { type: 'string', description: 'Full name' } },
      required: ['name'],
    })
  })

  it('omits required array when no fields are required', () => {
    const fields: SchemaField[] = [
      { key: 'opt', type: 'number', description: '', required: false, nullable: false },
    ]
    const schema = fieldsToSchema(fields) as Record<string, unknown>
    expect(schema.required).toBeUndefined()
  })

  it('omits description when empty', () => {
    const fields: SchemaField[] = [
      { key: 'x', type: 'string', description: '', required: false, nullable: false },
    ]
    const props = (fieldsToSchema(fields) as any).properties
    expect(props.x.description).toBeUndefined()
  })

  it('emits nullable as type array', () => {
    const fields: SchemaField[] = [
      { key: 'age', type: 'number', description: '', required: false, nullable: true },
    ]
    expect((fieldsToSchema(fields) as any).properties.age.type).toEqual(['number', 'null'])
  })

  it('includes enum values', () => {
    const fields: SchemaField[] = [
      { key: 'status', type: 'string', description: '', required: false, nullable: false, enumValues: ['active', 'inactive'] },
    ]
    expect((fieldsToSchema(fields) as any).properties.status.enum).toEqual(['active', 'inactive'])
  })

  it('converts nested object fields', () => {
    const fields: SchemaField[] = [{
      key: 'addr', type: 'object', description: '', required: false, nullable: false,
      properties: [
        { key: 'street', type: 'string', description: '', required: true, nullable: false },
      ],
    }]
    const addr = (fieldsToSchema(fields) as any).properties.addr
    expect(addr.type).toBe('object')
    expect(addr.properties.street).toBeDefined()
    expect(addr.required).toEqual(['street'])
  })

  it('converts array of primitives', () => {
    const fields: SchemaField[] = [{
      key: 'tags', type: 'array', description: '', required: false, nullable: false,
      items: { key: '', type: 'string', description: '', required: false, nullable: false },
    }]
    const tags = (fieldsToSchema(fields) as any).properties.tags
    expect(tags.type).toBe('array')
    expect(tags.items).toEqual({ type: 'string' })
  })

  it('converts array of objects', () => {
    const fields: SchemaField[] = [{
      key: 'rows', type: 'array', description: '', required: false, nullable: false,
      items: {
        key: '', type: 'object', description: '', required: false, nullable: false,
        properties: [
          { key: 'id', type: 'integer', description: '', required: true, nullable: false },
        ],
      },
    }]
    const rows = (fieldsToSchema(fields) as any).properties.rows
    expect(rows.items.type).toBe('object')
    expect(rows.items.properties.id).toBeDefined()
    expect(rows.items.required).toEqual(['id'])
  })

  it('skips fields with empty keys', () => {
    const fields: SchemaField[] = [
      { key: '', type: 'string', description: '', required: false, nullable: false },
      { key: 'ok', type: 'string', description: '', required: false, nullable: false },
    ]
    const schema = fieldsToSchema(fields) as any
    expect(Object.keys(schema.properties)).toEqual(['ok'])
  })
})

describe('schemaToFields', () => {
  it('parses a required string field', () => {
    const schema = {
      type: 'object',
      properties: { name: { type: 'string', description: 'Full name' } },
      required: ['name'],
    }
    const fields = schemaToFields(schema)
    expect(fields).toHaveLength(1)
    expect(fields[0]).toMatchObject({ key: 'name', type: 'string', description: 'Full name', required: true, nullable: false })
  })

  it('parses nullable type array', () => {
    const schema = { type: 'object', properties: { age: { type: ['number', 'null'] } } }
    const fields = schemaToFields(schema)
    expect(fields[0].type).toBe('number')
    expect(fields[0].nullable).toBe(true)
  })

  it('parses enum values', () => {
    const schema = { type: 'object', properties: { s: { type: 'string', enum: ['a', 'b'] } } }
    expect(schemaToFields(schema)[0].enumValues).toEqual(['a', 'b'])
  })

  it('parses nested object', () => {
    const schema = {
      type: 'object',
      properties: {
        addr: { type: 'object', properties: { city: { type: 'string' } }, required: ['city'] },
      },
    }
    const fields = schemaToFields(schema)
    expect(fields[0].type).toBe('object')
    expect(fields[0].properties).toHaveLength(1)
    expect(fields[0].properties![0]).toMatchObject({ key: 'city', required: true })
  })

  it('parses array of primitives', () => {
    const schema = { type: 'object', properties: { tags: { type: 'array', items: { type: 'string' } } } }
    const fields = schemaToFields(schema)
    expect(fields[0].type).toBe('array')
    expect(fields[0].items?.type).toBe('string')
  })

  it('parses array of objects', () => {
    const schema = {
      type: 'object',
      properties: {
        rows: { type: 'array', items: { type: 'object', properties: { id: { type: 'integer' } } } },
      },
    }
    const fields = schemaToFields(schema)
    expect(fields[0].items?.type).toBe('object')
    expect(fields[0].items?.properties).toHaveLength(1)
  })

  it('returns empty array for schema with no properties', () => {
    expect(schemaToFields({ type: 'object' })).toEqual([])
  })
})

describe('round-trip fidelity', () => {
  it('preserves structure through fieldsToSchema(schemaToFields(schema))', () => {
    const schema = {
      type: 'object',
      properties: {
        name: { type: 'string', description: 'Name' },
        age: { type: ['number', 'null'] },
        addr: {
          type: 'object',
          properties: { city: { type: 'string' } },
          required: ['city'],
        },
        tags: { type: 'array', items: { type: 'string' } },
      },
      required: ['name'],
    }
    expect(fieldsToSchema(schemaToFields(schema))).toEqual(schema)
  })
})

describe('hasUnknownKeywords', () => {
  it('returns false for standard keywords', () => {
    expect(hasUnknownKeywords({ type: 'object', properties: {}, required: [], description: 'x', enum: [], items: {} })).toBe(false)
  })

  it('returns true for $ref', () => {
    expect(hasUnknownKeywords({ type: 'object', $ref: '#/x' })).toBe(true)
  })
})

describe('validateFields', () => {
  it('returns null for valid fields', () => {
    const fields: SchemaField[] = [
      { key: 'name', type: 'string', description: '', required: false, nullable: false },
    ]
    expect(validateFields(fields)).toBeNull()
  })

  it('returns null for empty field list', () => {
    expect(validateFields([])).toBeNull()
  })

  it('returns error for empty key', () => {
    const fields: SchemaField[] = [
      { key: '', type: 'string', description: '', required: false, nullable: false },
    ]
    expect(validateFields(fields)).toBe('All fields must have a name')
  })

  it('returns error for duplicate keys', () => {
    const fields: SchemaField[] = [
      { key: 'x', type: 'string', description: '', required: false, nullable: false },
      { key: 'x', type: 'number', description: '', required: false, nullable: false },
    ]
    expect(validateFields(fields)).toBe('Field names must be unique')
  })

  it('validates nested fields recursively', () => {
    const fields: SchemaField[] = [{
      key: 'addr', type: 'object', description: '', required: false, nullable: false,
      properties: [
        { key: '', type: 'string', description: '', required: false, nullable: false },
      ],
    }]
    expect(validateFields(fields)).toBe('All fields must have a name')
  })
})

describe('getDuplicateKeys', () => {
  it('returns empty set for unique keys', () => {
    const fields: SchemaField[] = [
      { key: 'a', type: 'string', description: '', required: false, nullable: false },
      { key: 'b', type: 'string', description: '', required: false, nullable: false },
    ]
    expect(getDuplicateKeys(fields).size).toBe(0)
  })

  it('returns duplicate key', () => {
    const fields: SchemaField[] = [
      { key: 'x', type: 'string', description: '', required: false, nullable: false },
      { key: 'x', type: 'number', description: '', required: false, nullable: false },
    ]
    expect(getDuplicateKeys(fields)).toEqual(new Set(['x']))
  })
})

describe('newBlankField', () => {
  it('returns a field with empty key and string type', () => {
    const f = newBlankField()
    expect(f.key).toBe('')
    expect(f.type).toBe('string')
    expect(f.required).toBe(false)
    expect(f.nullable).toBe(false)
  })
})
```

- [ ] **Step 2: Run tests — expect all to fail**

```
cd frontend && npx vitest run src/lib/schemaBuilder.test.ts --reporter=verbose
```

Expected: all tests fail with "Cannot find module './schemaBuilder'"

- [ ] **Step 3: Implement `schemaBuilder.ts`**

Create `frontend/src/lib/schemaBuilder.ts`:

```ts
export type FieldType = 'string' | 'number' | 'integer' | 'boolean' | 'object' | 'array'

export interface SchemaField {
  key: string
  type: FieldType
  description: string
  required: boolean
  nullable: boolean
  enumValues?: string[]
  items?: SchemaField
  properties?: SchemaField[]
}

const KNOWN_KEYWORDS = new Set(['type', 'properties', 'required', 'description', 'enum', 'items'])

export function hasUnknownKeywords(schema: Record<string, unknown>): boolean {
  return Object.keys(schema).some(k => !KNOWN_KEYWORDS.has(k))
}

export function newBlankField(): SchemaField {
  return { key: '', type: 'string', description: '', required: false, nullable: false }
}

export function getDuplicateKeys(fields: SchemaField[]): Set<string> {
  const seen = new Set<string>()
  const dupes = new Set<string>()
  for (const f of fields) {
    if (f.key) {
      if (seen.has(f.key)) dupes.add(f.key)
      else seen.add(f.key)
    }
  }
  return dupes
}

export function validateFields(fields: SchemaField[]): string | null {
  for (const field of fields) {
    if (!field.key.trim()) return 'All fields must have a name'
    if (field.properties) {
      const err = validateFields(field.properties)
      if (err) return err
    }
    if (field.items?.properties) {
      const err = validateFields(field.items.properties)
      if (err) return err
    }
  }
  const keys = fields.filter(f => f.key).map(f => f.key)
  if (new Set(keys).size !== keys.length) return 'Field names must be unique'
  return null
}

export function fieldsToSchema(fields: SchemaField[]): Record<string, unknown> {
  const properties: Record<string, unknown> = {}
  const required: string[] = []
  for (const field of fields) {
    if (!field.key) continue
    if (field.required) required.push(field.key)
    properties[field.key] = fieldToJsonSchema(field)
  }
  const schema: Record<string, unknown> = { type: 'object', properties }
  if (required.length > 0) schema.required = required
  return schema
}

function fieldToJsonSchema(field: SchemaField): Record<string, unknown> {
  const def: Record<string, unknown> = {}
  def.type = field.nullable ? [field.type, 'null'] : field.type
  if (field.description) def.description = field.description
  if (
    (field.type === 'string' || field.type === 'number' || field.type === 'integer') &&
    field.enumValues?.length
  ) {
    def.enum = field.enumValues
  }
  if (field.type === 'object' && field.properties) {
    const nested = fieldsToSchema(field.properties)
    def.properties = nested.properties
    if (nested.required) def.required = nested.required
  }
  if (field.type === 'array' && field.items) {
    def.items = fieldToJsonSchema(field.items)
  }
  return def
}

export function schemaToFields(schema: Record<string, unknown>): SchemaField[] {
  const properties = schema.properties as Record<string, unknown> | undefined
  const required = (schema.required as string[] | undefined) ?? []
  if (!properties) return []
  return Object.entries(properties).map(([key, def]) =>
    jsonSchemaToField(key, def as Record<string, unknown>, required.includes(key))
  )
}

function jsonSchemaToField(
  key: string,
  def: Record<string, unknown>,
  required: boolean
): SchemaField {
  let type: FieldType = 'string'
  let nullable = false
  const rawType = def.type
  if (Array.isArray(rawType)) {
    const nonNull = (rawType as string[]).filter(t => t !== 'null')
    type = (nonNull[0] ?? 'string') as FieldType
    nullable = (rawType as string[]).includes('null')
  } else if (typeof rawType === 'string') {
    type = rawType as FieldType
  }
  const field: SchemaField = {
    key,
    type,
    description: (def.description as string) ?? '',
    required,
    nullable,
  }
  if (
    (type === 'string' || type === 'number' || type === 'integer') &&
    Array.isArray(def.enum)
  ) {
    field.enumValues = (def.enum as unknown[]).map(String)
  }
  if (type === 'object') {
    field.properties = schemaToFields({
      type: 'object',
      properties: def.properties,
      required: def.required,
    } as Record<string, unknown>)
  }
  if (type === 'array' && def.items) {
    field.items = jsonSchemaToField('', def.items as Record<string, unknown>, false)
  }
  return field
}
```

- [ ] **Step 4: Run tests — expect all to pass**

```
cd frontend && npx vitest run src/lib/schemaBuilder.test.ts --reporter=verbose
```

Expected: all tests pass

- [ ] **Step 5: Commit**

```
git add frontend/src/lib/schemaBuilder.ts frontend/src/lib/schemaBuilder.test.ts
git commit -m "feat(schema-builder): add schemaToFields/fieldsToSchema pure functions"
```

---

### Task 2: `SchemaBuilderJsonView` component

**Files:**
- Create: `frontend/src/components/extraction/SchemaBuilderJsonView.tsx`

**Interfaces:**
- Consumes: nothing from Task 1 directly (no SchemaField types)
- Produces: `SchemaBuilderJsonView({ value: string, onChange: (v: string) => void, parseError: string | null })` — used by `SchemaBuilder` in Task 4

- [ ] **Step 1: Create the component**

Create `frontend/src/components/extraction/SchemaBuilderJsonView.tsx`:

```tsx
import { Textarea } from '@/components/ui/textarea'

interface SchemaBuilderJsonViewProps {
  value: string
  onChange: (v: string) => void
  parseError: string | null
}

export function SchemaBuilderJsonView({ value, onChange, parseError }: SchemaBuilderJsonViewProps) {
  return (
    <div className="space-y-1">
      <Textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="font-mono text-sm min-h-[300px]"
        placeholder='{"type": "object", "properties": {...}}'
        spellCheck={false}
      />
      {parseError && (
        <p className="text-xs text-destructive">{parseError}</p>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Run lint to verify no type errors**

```
cd frontend && npm run lint -- --max-warnings 0 src/components/extraction/SchemaBuilderJsonView.tsx
```

Expected: no errors

- [ ] **Step 3: Commit**

```
git add frontend/src/components/extraction/SchemaBuilderJsonView.tsx
git commit -m "feat(schema-builder): add SchemaBuilderJsonView controlled textarea"
```

---

### Task 3: `SchemaFieldEditor` component

**Files:**
- Create: `frontend/src/components/extraction/SchemaFieldEditor.tsx`

**Interfaces:**
- Consumes: `SchemaField`, `FieldType`, `newBlankField`, `getDuplicateKeys` from `@/lib/schemaBuilder`
- Produces: `SchemaFieldEditor({ field, onChange, onDelete, depth?, duplicateKeys?, hideDelete? })` — used by `SchemaBuilder` in Task 4

- [ ] **Step 1: Create the component**

Create `frontend/src/components/extraction/SchemaFieldEditor.tsx`:

```tsx
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Plus, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { SchemaField, FieldType } from '@/lib/schemaBuilder'
import { newBlankField, getDuplicateKeys } from '@/lib/schemaBuilder'

interface SchemaFieldEditorProps {
  field: SchemaField
  onChange: (updated: SchemaField) => void
  onDelete: () => void
  depth?: number
  duplicateKeys?: Set<string>
  hideDelete?: boolean
}

export function SchemaFieldEditor({
  field,
  onChange,
  onDelete,
  depth = 0,
  duplicateKeys = new Set(),
  hideDelete = false,
}: SchemaFieldEditorProps) {
  const isDuplicate = field.key !== '' && duplicateKeys.has(field.key)

  const update = (patch: Partial<SchemaField>) => onChange({ ...field, ...patch })

  const handleTypeChange = (type: FieldType) => {
    const patch: Partial<SchemaField> = { type }
    if (type !== 'string' && type !== 'number' && type !== 'integer') patch.enumValues = undefined
    if (type !== 'object') patch.properties = undefined
    if (type !== 'array') patch.items = undefined
    if (type === 'object') patch.properties = field.properties ?? []
    if (type === 'array') patch.items = field.items ?? newBlankField()
    update(patch)
  }

  const addEnumValue = () => update({ enumValues: [...(field.enumValues ?? []), ''] })
  const updateEnumValue = (i: number, v: string) => {
    const enumValues = [...(field.enumValues ?? [])]
    enumValues[i] = v
    update({ enumValues })
  }
  const deleteEnumValue = (i: number) =>
    update({ enumValues: (field.enumValues ?? []).filter((_, idx) => idx !== i) })

  const addNestedField = () =>
    update({ properties: [...(field.properties ?? []), newBlankField()] })
  const updateNestedField = (i: number, updated: SchemaField) => {
    const properties = [...(field.properties ?? [])]
    properties[i] = updated
    update({ properties })
  }
  const deleteNestedField = (i: number) =>
    update({ properties: (field.properties ?? []).filter((_, idx) => idx !== i) })

  const nestedDuplicateKeys = getDuplicateKeys(field.properties ?? [])

  return (
    <div className={cn('space-y-2', depth > 0 && 'ml-4 pl-3 border-l border-border')}>
      <div className="flex items-start gap-2">
        <div className="flex-1 grid grid-cols-[1fr_auto_2fr] gap-2 items-center min-w-0">
          <Input
            value={field.key}
            onChange={(e) => update({ key: e.target.value })}
            placeholder="field_name"
            className={cn('font-mono text-sm h-8', isDuplicate && 'border-destructive')}
          />
          <Select value={field.type} onValueChange={handleTypeChange}>
            <SelectTrigger className="w-28 h-8 text-sm">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="string">string</SelectItem>
              <SelectItem value="number">number</SelectItem>
              <SelectItem value="integer">integer</SelectItem>
              <SelectItem value="boolean">boolean</SelectItem>
              <SelectItem value="object">object</SelectItem>
              <SelectItem value="array">array</SelectItem>
            </SelectContent>
          </Select>
          <Input
            value={field.description}
            onChange={(e) => update({ description: e.target.value })}
            placeholder="Description (guides extraction)"
            className="text-sm h-8"
          />
        </div>
        <div className="flex items-center gap-2 shrink-0 pt-0.5">
          <label className="flex items-center gap-1 text-xs text-muted-foreground cursor-pointer select-none">
            <Checkbox
              checked={field.required}
              onCheckedChange={(v) => update({ required: !!v })}
              className="h-3.5 w-3.5"
            />
            Req
          </label>
          <label className="flex items-center gap-1 text-xs text-muted-foreground cursor-pointer select-none">
            <Checkbox
              checked={field.nullable}
              onCheckedChange={(v) => update({ nullable: !!v })}
              className="h-3.5 w-3.5"
            />
            Null
          </label>
          {!hideDelete && (
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 text-muted-foreground hover:text-destructive"
              onClick={onDelete}
              type="button"
            >
              <X className="h-3.5 w-3.5" />
            </Button>
          )}
        </div>
      </div>

      {isDuplicate && (
        <p className="text-xs text-destructive">Duplicate field name</p>
      )}

      {(field.type === 'string' || field.type === 'number' || field.type === 'integer') && (
        <div className="ml-4 space-y-1.5">
          <p className="text-xs text-muted-foreground font-medium">Enum values</p>
          {(field.enumValues ?? []).map((val, i) => (
            <div key={i} className="flex items-center gap-2">
              <Input
                value={val}
                onChange={(e) => updateEnumValue(i, e.target.value)}
                placeholder="value"
                className="text-sm h-7 flex-1"
              />
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                onClick={() => deleteEnumValue(i)}
                type="button"
              >
                <X className="h-3 w-3" />
              </Button>
            </div>
          ))}
          <Button
            variant="ghost"
            size="sm"
            className="h-6 text-xs px-2"
            onClick={addEnumValue}
            type="button"
          >
            <Plus className="h-3 w-3 mr-1" />
            Add enum value
          </Button>
        </div>
      )}

      {field.type === 'object' && (
        <div className="space-y-2">
          {(field.properties ?? []).map((nested, i) => (
            <SchemaFieldEditor
              key={i}
              field={nested}
              onChange={(updated) => updateNestedField(i, updated)}
              onDelete={() => deleteNestedField(i)}
              depth={depth + 1}
              duplicateKeys={nestedDuplicateKeys}
            />
          ))}
          <div className={cn(depth > 0 && 'ml-4')}>
            <Button
              variant="ghost"
              size="sm"
              className="h-6 text-xs px-2"
              onClick={addNestedField}
              type="button"
            >
              <Plus className="h-3 w-3 mr-1" />
              Add field
            </Button>
          </div>
        </div>
      )}

      {field.type === 'array' && field.items && (
        <div className="ml-4 space-y-1.5">
          <p className="text-xs text-muted-foreground font-medium">Item type</p>
          <SchemaFieldEditor
            field={field.items}
            onChange={(updated) => update({ items: updated })}
            onDelete={() => {}}
            depth={depth + 1}
            hideDelete
          />
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Run lint**

```
cd frontend && npm run lint -- --max-warnings 0 src/components/extraction/SchemaFieldEditor.tsx
```

Expected: no errors

- [ ] **Step 3: Commit**

```
git add frontend/src/components/extraction/SchemaFieldEditor.tsx
git commit -m "feat(schema-builder): add recursive SchemaFieldEditor component"
```

---

### Task 4: `SchemaBuilder` toggle container + component tests

**Files:**
- Create: `frontend/src/components/extraction/SchemaBuilder.tsx`
- Create: `frontend/src/components/extraction/SchemaBuilder.test.tsx`

**Interfaces:**
- Consumes: `SchemaFieldEditor` (Task 3), `SchemaBuilderJsonView` (Task 2), all of `@/lib/schemaBuilder`
- Produces: `SchemaBuilder({ value: Record<string, unknown>, onChange: (v: Record<string, unknown>) => void, onValidChange?: (valid: boolean) => void })` — used by `ExtractionSchemaEditor` in Task 5

- [ ] **Step 1: Write failing component tests**

Create `frontend/src/components/extraction/SchemaBuilder.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { SchemaBuilder } from './SchemaBuilder'

const emptySchema = { type: 'object', properties: {} }

describe('SchemaBuilder', () => {
  it('renders builder tab and Add field button by default', () => {
    render(<SchemaBuilder value={emptySchema} onChange={vi.fn()} />)
    expect(screen.getByRole('tab', { name: /builder/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /add field/i })).toBeInTheDocument()
  })

  it('switches to JSON view on tab click', async () => {
    const user = userEvent.setup()
    render(<SchemaBuilder value={emptySchema} onChange={vi.fn()} />)
    await user.click(screen.getByRole('tab', { name: /json/i }))
    expect(screen.getByRole('textbox')).toBeInTheDocument()
  })

  it('calls onChange when a field is added', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(<SchemaBuilder value={emptySchema} onChange={onChange} />)
    await user.click(screen.getByRole('button', { name: /add field/i }))
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ type: 'object' }))
  })

  it('renders existing fields from value prop', () => {
    const schema = {
      type: 'object',
      properties: { invoice_number: { type: 'string', description: 'Invoice #' } },
    }
    render(<SchemaBuilder value={schema} onChange={vi.fn()} />)
    expect(screen.getByDisplayValue('invoice_number')).toBeInTheDocument()
  })

  it('JSON view shows serialized schema', async () => {
    const user = userEvent.setup()
    const schema = { type: 'object', properties: { x: { type: 'string' } } }
    render(<SchemaBuilder value={schema} onChange={vi.fn()} />)
    await user.click(screen.getByRole('tab', { name: /json/i }))
    const textarea = screen.getByRole('textbox')
    expect(textarea).toHaveValue(JSON.stringify(schema, null, 2))
  })

  it('shows parse error on invalid JSON', async () => {
    vi.useFakeTimers()
    const user = userEvent.setup({ advanceTimers: (ms) => vi.advanceTimersByTime(ms) })
    render(<SchemaBuilder value={emptySchema} onChange={vi.fn()} />)
    await user.click(screen.getByRole('tab', { name: /json/i }))
    const textarea = screen.getByRole('textbox')
    await user.clear(textarea)
    await user.type(textarea, '{bad json')
    act(() => { vi.advanceTimersByTime(400) })
    expect(screen.getByText(/invalid json/i)).toBeInTheDocument()
    vi.useRealTimers()
  })

  it('preserves builder fields when JSON becomes invalid', async () => {
    vi.useFakeTimers()
    const user = userEvent.setup({ advanceTimers: (ms) => vi.advanceTimersByTime(ms) })
    const schema = { type: 'object', properties: { name: { type: 'string', description: 'Full name' } } }
    render(<SchemaBuilder value={schema} onChange={vi.fn()} />)
    await user.click(screen.getByRole('tab', { name: /json/i }))
    const textarea = screen.getByRole('textbox')
    await user.clear(textarea)
    await user.type(textarea, 'not valid json')
    act(() => { vi.advanceTimersByTime(400) })
    await user.click(screen.getByRole('tab', { name: /builder/i }))
    expect(screen.getByDisplayValue('name')).toBeInTheDocument()
    vi.useRealTimers()
  })

  it('calls onValidChange(false) when a blank field is added', async () => {
    const user = userEvent.setup()
    const onValidChange = vi.fn()
    render(<SchemaBuilder value={emptySchema} onChange={vi.fn()} onValidChange={onValidChange} />)
    await user.click(screen.getByRole('button', { name: /add field/i }))
    expect(onValidChange).toHaveBeenLastCalledWith(false)
  })

  it('calls onValidChange(true) when all fields have keys', async () => {
    const user = userEvent.setup()
    const onValidChange = vi.fn()
    render(<SchemaBuilder value={emptySchema} onChange={vi.fn()} onValidChange={onValidChange} />)
    await user.click(screen.getByRole('button', { name: /add field/i }))
    const keyInput = screen.getByPlaceholderText('field_name')
    await user.type(keyInput, 'my_field')
    expect(onValidChange).toHaveBeenLastCalledWith(true)
  })
})
```

- [ ] **Step 2: Run tests — expect to fail**

```
cd frontend && npx vitest run src/components/extraction/SchemaBuilder.test.tsx --reporter=verbose
```

Expected: all fail with "Cannot find module './SchemaBuilder'"

- [ ] **Step 3: Create `SchemaBuilder.tsx`**

Create `frontend/src/components/extraction/SchemaBuilder.tsx`:

```tsx
import { useState, useRef, useCallback, useEffect } from 'react'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { Button } from '@/components/ui/button'
import { Plus, AlertCircle } from 'lucide-react'
import { SchemaBuilderJsonView } from './SchemaBuilderJsonView'
import { SchemaFieldEditor } from './SchemaFieldEditor'
import {
  type SchemaField,
  schemaToFields,
  fieldsToSchema,
  newBlankField,
  getDuplicateKeys,
  hasUnknownKeywords,
  validateFields,
} from '@/lib/schemaBuilder'

const DEBOUNCE_MS = 300

interface SchemaBuilderProps {
  value: Record<string, unknown>
  onChange: (v: Record<string, unknown>) => void
  onValidChange?: (valid: boolean) => void
}

export function SchemaBuilder({ value, onChange, onValidChange }: SchemaBuilderProps) {
  const [fields, setFields] = useState<SchemaField[]>(() => schemaToFields(value))
  const [jsonText, setJsonText] = useState(() => JSON.stringify(value, null, 2))
  const [parseError, setParseError] = useState<string | null>(null)
  const [unknownKeywords, setUnknownKeywords] = useState(() => hasUnknownKeywords(value))
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current) }
  }, [])

  const applyFields = useCallback(
    (next: SchemaField[]) => {
      setFields(next)
      const schema = fieldsToSchema(next)
      setJsonText(JSON.stringify(schema, null, 2))
      setUnknownKeywords(false)
      onChange(schema)
      onValidChange?.(validateFields(next) === null)
    },
    [onChange, onValidChange]
  )

  const handleJsonChange = (text: string) => {
    setJsonText(text)
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      try {
        const parsed = JSON.parse(text) as Record<string, unknown>
        const next = schemaToFields(parsed)
        setFields(next)
        setUnknownKeywords(hasUnknownKeywords(parsed))
        setParseError(null)
        onChange(parsed)
        onValidChange?.(validateFields(next) === null)
      } catch {
        setParseError('Invalid JSON')
        onValidChange?.(false)
      }
    }, DEBOUNCE_MS)
  }

  const addField = () => applyFields([...fields, newBlankField()])
  const updateField = (i: number, updated: SchemaField) => {
    const next = [...fields]
    next[i] = updated
    applyFields(next)
  }
  const deleteField = (i: number) => applyFields(fields.filter((_, idx) => idx !== i))

  const duplicateKeys = getDuplicateKeys(fields)

  return (
    <Tabs defaultValue="builder">
      <TabsList className="h-8">
        <TabsTrigger value="builder" className="text-xs px-3 h-7">Builder</TabsTrigger>
        <TabsTrigger value="json" className="text-xs px-3 h-7">JSON</TabsTrigger>
      </TabsList>

      <TabsContent value="builder" className="mt-3 space-y-2">
        {unknownKeywords && (
          <div className="flex items-center gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700 dark:border-amber-900/50 dark:bg-amber-900/20 dark:text-amber-400">
            <AlertCircle className="h-3.5 w-3.5 shrink-0" />
            Some schema keywords aren't editable in Builder view. They're preserved in JSON.
          </div>
        )}
        {fields.map((field, i) => (
          <SchemaFieldEditor
            key={i}
            field={field}
            onChange={(updated) => updateField(i, updated)}
            onDelete={() => deleteField(i)}
            duplicateKeys={duplicateKeys}
          />
        ))}
        <Button
          variant="outline"
          size="sm"
          className="h-7 text-xs"
          onClick={addField}
          type="button"
        >
          <Plus className="h-3 w-3 mr-1" />
          Add field
        </Button>
      </TabsContent>

      <TabsContent value="json" className="mt-3">
        <SchemaBuilderJsonView
          value={jsonText}
          onChange={handleJsonChange}
          parseError={parseError}
        />
      </TabsContent>
    </Tabs>
  )
}
```

- [ ] **Step 4: Run tests — expect to pass**

```
cd frontend && npx vitest run src/components/extraction/SchemaBuilder.test.tsx --reporter=verbose
```

Expected: all tests pass

- [ ] **Step 5: Commit**

```
git add frontend/src/components/extraction/SchemaBuilder.tsx frontend/src/components/extraction/SchemaBuilder.test.tsx
git commit -m "feat(schema-builder): add SchemaBuilder toggle container with builder/JSON views"
```

---

### Task 5: Wire `SchemaBuilder` into `ExtractionSchemaEditor`

**Files:**
- Modify: `frontend/src/components/extraction/ExtractionSchemaEditor.tsx`

**Interfaces:**
- Consumes: `SchemaBuilder` from `./SchemaBuilder`
- No new exports

- [ ] **Step 1: Replace the file**

Replace the full contents of `frontend/src/components/extraction/ExtractionSchemaEditor.tsx`:

```tsx
import { useState, useEffect, useRef } from 'react'
import type { ExtractionSchema, ExtractionSchemaCreate, ExtractionSchemaUpdate } from '@/types/extraction'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { SchemaBuilder } from './SchemaBuilder'

const EMPTY_SCHEMA: Record<string, unknown> = { type: 'object', properties: {} }

interface ExtractionSchemaEditorProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  schema?: ExtractionSchema | null
  onSave: (data: ExtractionSchemaCreate | ExtractionSchemaUpdate) => Promise<void>
}

export function ExtractionSchemaEditor({
  open,
  onOpenChange,
  schema,
  onSave,
}: ExtractionSchemaEditorProps) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [extractionTarget, setExtractionTarget] = useState('PER_DOC')
  const [isSchemaValid, setIsSchemaValid] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [schemaBuilderKey, setSchemaBuilderKey] = useState(0)
  const schemaDefinitionRef = useRef<Record<string, unknown>>(EMPTY_SCHEMA)

  const isEditing = !!schema

  useEffect(() => {
    if (schema) {
      setName(schema.name)
      setDescription(schema.description || '')
      schemaDefinitionRef.current = schema.schemaDefinition
      setExtractionTarget(schema.extractionTarget)
    } else {
      setName('')
      setDescription('')
      schemaDefinitionRef.current = EMPTY_SCHEMA
      setExtractionTarget('PER_DOC')
    }
    setIsSchemaValid(true)
    setError(null)
    setSchemaBuilderKey(k => k + 1)
  }, [schema, open])

  const handleSave = async () => {
    setError(null)

    if (!name.trim()) {
      setError('Name is required')
      return
    }

    const schemaDefinition = schemaDefinitionRef.current
    if (schemaDefinition.type !== 'object') {
      setError('Root schema type must be "object"')
      return
    }

    setIsSaving(true)
    try {
      if (isEditing) {
        await onSave({
          name: name.trim(),
          description: description.trim() || undefined,
          schemaDefinition,
          extractionTarget,
        } as ExtractionSchemaUpdate)
      } else {
        await onSave({
          name: name.trim(),
          description: description.trim() || undefined,
          schemaDefinition,
          extractionTarget,
        } as ExtractionSchemaCreate)
      }
      onOpenChange(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save schema')
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{isEditing ? 'Edit Schema' : 'Create Schema'}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label htmlFor="schema-name">Name</Label>
            <Input
              id="schema-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Invoice Fields"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="schema-description">Description</Label>
            <Input
              id="schema-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Optional description"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="extraction-target">Extraction Target</Label>
            <Select value={extractionTarget} onValueChange={setExtractionTarget}>
              <SelectTrigger id="extraction-target">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="PER_DOC">Per Document</SelectItem>
                <SelectItem value="PER_PAGE">Per Page</SelectItem>
                <SelectItem value="PER_TABLE_ROW">Per Table Row</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label>Schema Definition</Label>
            <SchemaBuilder
              key={schemaBuilderKey}
              value={schemaDefinitionRef.current}
              onChange={(v) => { schemaDefinitionRef.current = v }}
              onValidChange={setIsSchemaValid}
            />
          </div>

          {error && (
            <p className="text-sm text-destructive">{error}</p>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isSaving}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={isSaving || !isSchemaValid}>
            {isSaving ? 'Saving...' : isEditing ? 'Update' : 'Create'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
```

- [ ] **Step 2: Run the full test suite**

```
cd frontend && npx vitest run --reporter=verbose
```

Expected: all existing tests pass (no regressions), new tests pass

- [ ] **Step 3: Run lint**

```
cd frontend && npm run lint
```

Expected: no errors

- [ ] **Step 4: Run build to check type errors**

```
cd frontend && npm run build
```

Expected: successful build, no TypeScript errors

- [ ] **Step 5: Commit**

```
git add frontend/src/components/extraction/ExtractionSchemaEditor.tsx
git commit -m "feat(schema-builder): wire SchemaBuilder into ExtractionSchemaEditor"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Covered by |
|---|---|
| Builder / JSON toggle | Task 4 — `Tabs` in `SchemaBuilder` |
| Sync: JSON edit → builder | Task 4 — debounced `handleJsonChange` |
| Sync: builder edit → JSON | Task 4 — `applyFields` calls `fieldsToSchema` |
| All field types (string/number/integer/boolean/object/array) | Task 3 — type select, Task 1 — conversion functions |
| Nested objects | Task 1 + 3 — recursive `properties` |
| Arrays of primitives and objects | Task 1 + 3 — `items` as `SchemaField` |
| Enum values | Task 1 + 3 — `enumValues` add/remove |
| Nullable | Task 1 + 3 — checkbox → `[type, 'null']` |
| Required | Task 1 + 3 — checkbox → `required[]` |
| Invalid JSON → error + preserve fields | Task 4 — `parseError` state + `setFields` only on valid parse |
| Unknown keywords → warning banner | Task 4 — `unknownKeywords` state + amber banner |
| Duplicate key → inline error | Task 3 — `isDuplicate` from `getDuplicateKeys` |
| Empty key → save disabled | Task 4 — `onValidChange(false)`, Task 5 — `disabled={!isSchemaValid}` |
| Root type `object` check | Task 5 — preserved in `handleSave` |
| Unit tests for conversions | Task 1 |
| Component tests for SchemaBuilder | Task 4 |

**Placeholder scan:** No TBDs, TODOs, or incomplete steps found.

**Type consistency:** All types match across tasks — `SchemaField`, `FieldType`, `schemaToFields`, `fieldsToSchema`, `newBlankField`, `getDuplicateKeys`, `validateFields` defined in Task 1 and consumed consistently in Tasks 3, 4, 5.
