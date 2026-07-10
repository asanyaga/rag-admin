import { describe, it, expect } from 'vitest'
import { regionsToBlocks, regionColors, OBSERVATION_COLORS } from './probeOverlay'
import type { RegionFinding } from '@/types/probeReport'

const region: RegionFinding = {
  id: 'p0:img0', page_index: 0, kind: 'image',
  bbox: { x0: 0.1, y0: 0.1, x1: 0.9, y1: 0.5 }, signals: [],
  observation: { label: 'text_image', confidence: 0.88 },
}

describe('probeOverlay', () => {
  it('maps a region to a synthetic block preserving id/page/bbox', () => {
    const [b] = regionsToBlocks([region])
    expect(b.id).toBe('p0:img0')
    expect(b.page_index).toBe(0)
    expect(b.bbox).toEqual(region.bbox)
  })
  it('colors regions by observation label', () => {
    const colors = regionColors([region])
    expect(colors.get('p0:img0')).toBe(OBSERVATION_COLORS.text_image)
  })
})
