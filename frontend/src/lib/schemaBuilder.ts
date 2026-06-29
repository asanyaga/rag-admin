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

// Root keywords the builder handles natively — not stored as extra props
const NATIVE_ROOT_KEYWORDS = new Set(['type', 'properties', 'required'])

// Composition keywords the builder cannot render — trigger the warning banner
const COMPOSITION_KEYWORDS = new Set(['$ref', 'allOf', 'anyOf', 'oneOf', 'if', 'then', 'else', 'not'])

export function extractExtraRootProps(schema: Record<string, unknown>): Record<string, unknown> {
  const extra: Record<string, unknown> = {}
  for (const [k, v] of Object.entries(schema)) {
    if (!NATIVE_ROOT_KEYWORDS.has(k)) extra[k] = v
  }
  return extra
}

export function hasUnknownKeywords(schema: Record<string, unknown>): boolean {
  return Object.keys(schema).some(k => COMPOSITION_KEYWORDS.has(k))
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
