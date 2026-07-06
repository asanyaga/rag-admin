import { describe, it, expect } from 'vitest'
import { stableStringify } from './stableStringify'

describe('stableStringify', () => {
  it('is independent of key order at every level', () => {
    expect(stableStringify({ a: 1, b: 2 })).toBe(stableStringify({ b: 2, a: 1 }))
    expect(stableStringify({ x: { b: 2, a: 1 } })).toBe(stableStringify({ x: { a: 1, b: 2 } }))
  })

  it('preserves array order (order is significant)', () => {
    expect(stableStringify([1, 2])).not.toBe(stableStringify([2, 1]))
  })

  it('distinguishes nested differences', () => {
    expect(stableStringify({ tools: [{ id: 'fitz' }] }))
      .not.toBe(stableStringify({ tools: [{ id: 'pdfplumber' }] }))
  })

  it('handles primitives and null', () => {
    expect(stableStringify(null)).toBe('null')
    expect(stableStringify(3)).toBe('3')
    expect(stableStringify('x')).toBe('"x"')
  })
})
