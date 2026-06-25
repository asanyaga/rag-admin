import { describe, it, expect } from 'vitest'
import { buildCsvString } from './exportCsv'

describe('buildCsvString', () => {
  it('emits header + single row for a flat object', () => {
    expect(buildCsvString({ name: 'Alice', age: 30 })).toBe('name,age\nAlice,30')
  })

  it('emits header + one row per array element', () => {
    const data = { items: [{ sku: 'A', qty: 2 }, { sku: 'B', qty: 1 }] }
    expect(buildCsvString(data)).toBe('sku,qty\nA,2\nB,1')
  })

  it('appends flat sibling fields as extra columns on every array row', () => {
    const data = {
      title: 'Invoice',
      items: [{ sku: 'A', qty: 2 }, { sku: 'B', qty: 1 }],
    }
    expect(buildCsvString(data)).toBe('sku,qty,title\nA,2,Invoice\nB,1,Invoice')
  })

  it('picks the array with the most elements when multiple exist', () => {
    const data = {
      items: [{ sku: 'A' }, { sku: 'B' }, { sku: 'C' }],
      tags: [{ name: 'x' }],
    }
    const lines = buildCsvString(data).split('\n')
    expect(lines).toHaveLength(4) // header + 3 rows
    expect(lines[0]).toBe('sku')
  })

  it('collects all columns from all rows when array items have different keys', () => {
    const data = {
      items: [{ sku: 'A', qty: 2 }, { sku: 'B', note: 'special' }],
    }
    expect(buildCsvString(data)).toBe('sku,qty,note\nA,2,\nB,,special')
  })

  it('wraps cells containing commas in double-quotes', () => {
    expect(buildCsvString({ name: 'Smith, John' })).toBe('name\n"Smith, John"')
  })

  it('escapes embedded double-quotes per RFC 4180', () => {
    expect(buildCsvString({ note: 'He said "hello"' })).toBe('note\n"He said ""hello"""')
  })

  it('wraps cells containing newlines in double-quotes', () => {
    expect(buildCsvString({ text: 'line1\nline2' })).toBe('text\n"line1\nline2"')
  })

  it('serializes nested objects as RFC 4180-quoted JSON strings', () => {
    // JSON.stringify produces double-quotes around keys, triggering quoting
    expect(buildCsvString({ meta: { x: 1 }, name: 'Alice' }))
      .toBe('meta,name\n"{""x"":1}",Alice')
  })

  it('emits empty string for null and undefined values', () => {
    expect(buildCsvString({ a: null, b: 'x' })).toBe('a,b\n,x')
  })

  it('falls back to a data column containing full JSON for an empty object', () => {
    expect(buildCsvString({})).toBe('data\n{}')
  })
})
