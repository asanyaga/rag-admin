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
