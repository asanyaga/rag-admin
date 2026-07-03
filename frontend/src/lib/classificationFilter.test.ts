import { describe, expect, it } from 'vitest'
import { buildFilterIntent } from './classificationFilter'

const base = { eligibleRunId: null, selectedCategories: [], granularity: 'page' as const, classify: null }

describe('buildFilterIntent', () => {
  it('select mode when an eligible run and categories are chosen', () => {
    expect(buildFilterIntent({ ...base, eligibleRunId: 'r1', selectedCategories: ['fin'] })).toEqual({
      mode: 'select', classificationRunId: 'r1', categories: ['fin'], granularity: 'page',
    })
  })

  it('configure mode when no run but classify labels + filter categories set', () => {
    const classify = { labels: ['fin', 'legal'], classifierType: 'llm', classifierConfig: { a: 1 } }
    expect(buildFilterIntent({ ...base, classify, selectedCategories: ['fin'] })).toEqual({
      mode: 'configure', classify, categories: ['fin'], granularity: 'page',
    })
  })

  it('none when nothing selected', () => {
    expect(buildFilterIntent(base)).toEqual({ mode: 'none' })
    expect(buildFilterIntent({ ...base, eligibleRunId: 'r1' })).toEqual({ mode: 'none' })
    expect(buildFilterIntent({ ...base, classify: { labels: [], classifierType: 'llm', classifierConfig: {} } }))
      .toEqual({ mode: 'none' })
  })
})
