// @vitest-environment node
import { describe, it, expect } from 'vitest'
import { getRunColor, BASELINE_COLOR } from './runColors'

describe('getRunColor', () => {
  it('returns a color set for index 0', () => {
    const color = getRunColor(0)
    expect(color.card).toBeTruthy()
    expect(color.headerTop).toBeTruthy()
    expect(color.cellBg).toBeTruthy()
    expect(color.groupBorder).toBeTruthy()
  })

  it('wraps around for indices beyond palette length', () => {
    const color0 = getRunColor(0)
    const color6 = getRunColor(6)
    expect(color0.card).toBe(color6.card)
  })

  it('returns distinct colors for indices 0-5', () => {
    const cards = Array.from({ length: 6 }, (_, i) => getRunColor(i).card)
    const unique = new Set(cards)
    expect(unique.size).toBe(6)
  })

  it('exports BASELINE_COLOR with all required fields', () => {
    expect(BASELINE_COLOR.card).toBeTruthy()
    expect(BASELINE_COLOR.headerTop).toBeTruthy()
    expect(BASELINE_COLOR.cellBg).toBeTruthy()
    expect(BASELINE_COLOR.groupBorder).toBeTruthy()
  })
})
