import { describe, it, expect } from 'vitest'
import { navigationItems } from './navigation'

describe('navigationItems', () => {
  it('places Probe between Source Documents and Parse', () => {
    const labels = navigationItems.map((i) => i.label)
    const sourceDocs = labels.indexOf('Source Documents')
    const probe = labels.indexOf('Probe')
    const parse = labels.indexOf('Parse')

    expect(probe).toBeGreaterThan(sourceDocs)
    expect(probe).toBeLessThan(parse)
  })
})
