import { renderHook, act } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { useClassificationFilter } from './useClassificationFilter'
import type { ClassificationRun } from '@/types/classification'

function run(overrides: Partial<ClassificationRun>): ClassificationRun {
  return {
    id: 'r1', parseRunId: 'p1', documentId: 'd1', labelsRequested: ['fin', 'legal'],
    classifierType: 'llm', classifierConfig: {}, status: 'completed',
    error: null, inputTokens: 0, outputTokens: 0, durationMs: 0,
    createdAt: '', regions: [], ...overrides,
  } as ClassificationRun
}

describe('useClassificationFilter', () => {
  it('select mode with categories from labelsRequested when eligible run exists', () => {
    const { result } = renderHook(() => useClassificationFilter([run({})], 'p1'))
    expect(result.current.mode).toBe('select')
    expect(result.current.selectCategories).toEqual(['fin', 'legal'])
  })

  it('configure mode when no eligible run for the parse', () => {
    const { result } = renderHook(() => useClassificationFilter([run({ parseRunId: 'pX' })], 'p1'))
    expect(result.current.mode).toBe('configure')
    expect(result.current.eligibleRun).toBeNull()
  })

  it('tracks selected categories and granularity', () => {
    const { result } = renderHook(() => useClassificationFilter([run({})], 'p1'))
    act(() => result.current.setSelectedCategories(['fin']))
    act(() => result.current.setGranularity('block'))
    expect(result.current.selectedCategories).toEqual(['fin'])
    expect(result.current.granularity).toBe('block')
  })
})
