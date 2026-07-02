import { useMemo, useState } from 'react'
import type { ClassificationRun } from '@/types/classification'
import type { PreprocessStage } from '@/types/extraction'

export interface CategoryFilterState {
  eligibleRun: ClassificationRun | null
  availableCategories: string[]
  selectedCategories: string[]
  granularity: 'page' | 'block'
  setSelectedCategories: (c: string[]) => void
  setGranularity: (g: 'page' | 'block') => void
  toPreprocessStage: () => PreprocessStage | null
}

export function useCategoryFilter(
  runs: ClassificationRun[],
  parseRunId: string | null,
): CategoryFilterState {
  const [selectedCategories, setSelectedCategories] = useState<string[]>([])
  const [granularity, setGranularity] = useState<'page' | 'block'>('page')

  // runs arrive newest-first (see useDocumentClassificationRuns); take the first
  // completed run bound to this parse.
  const eligibleRun = useMemo<ClassificationRun | null>(() => {
    if (!parseRunId) return null
    return (
      runs.find((r) => r.status === 'completed' && r.parseRunId === parseRunId) ?? null
    )
  }, [runs, parseRunId])

  const availableCategories = useMemo<string[]>(() => {
    if (!eligibleRun) return []
    return Array.from(new Set(eligibleRun.regions.map((r) => r.label)))
  }, [eligibleRun])

  const toPreprocessStage = (): PreprocessStage | null => {
    if (!eligibleRun || selectedCategories.length === 0) return null
    return {
      stage: 'category_filter',
      config: {
        classificationRunId: eligibleRun.id,
        categories: selectedCategories,
        granularity,
      },
    }
  }

  return {
    eligibleRun,
    availableCategories,
    selectedCategories,
    granularity,
    setSelectedCategories,
    setGranularity,
    toPreprocessStage,
  }
}
