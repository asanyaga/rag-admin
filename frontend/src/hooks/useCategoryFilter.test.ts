import { renderHook, act } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { useCategoryFilter } from './useCategoryFilter'
import type { ClassificationRun } from '@/types/classification'

function run(overrides: Partial<ClassificationRun>): ClassificationRun {
  return {
    id: 'r1', parseRunId: 'p1', documentId: 'd1', labelsRequested: ['fin', 'legal'],
    classifierType: 'llm', classifierConfig: {}, status: 'completed',
    error: null, inputTokens: 0, outputTokens: 0, durationMs: 0,
    // The document list endpoint returns runs WITHOUT regions — categories must
    // come from labelsRequested, not regions.
    createdAt: '', regions: [],
    ...overrides,
  } as ClassificationRun
}

describe('useCategoryFilter', () => {
  it('picks the latest completed run matching the parse and exposes its categories', () => {
    const runs = [
      run({ id: 'old', parseRunId: 'p1', status: 'completed' }),
      run({ id: 'wrongparse', parseRunId: 'pX', status: 'completed' }),
      run({ id: 'notdone', parseRunId: 'p1', status: 'running' }),
    ]
    const { result } = renderHook(() => useCategoryFilter(runs, 'p1'))
    expect(result.current.eligibleRun?.id).toBe('old')
    expect(result.current.availableCategories).toEqual(['fin', 'legal'])
    expect(result.current.granularity).toBe('page')
  })

  it('returns null stage when nothing selected, and composes a stage when selected', () => {
    const runs = [run({ id: 'r1', parseRunId: 'p1' })]
    const { result } = renderHook(() => useCategoryFilter(runs, 'p1'))
    expect(result.current.toPreprocessStage()).toBeNull()
    act(() => result.current.setSelectedCategories(['fin']))
    expect(result.current.toPreprocessStage()).toEqual({
      stage: 'category_filter',
      config: { classificationRunId: 'r1', categories: ['fin'], granularity: 'page' },
    })
  })

  it('has no eligible run when parseRunId is null', () => {
    const runs = [run({ id: 'r1', parseRunId: 'p1' })]
    const { result } = renderHook(() => useCategoryFilter(runs, null))
    expect(result.current.eligibleRun).toBeNull()
    expect(result.current.toPreprocessStage()).toBeNull()
  })
})
