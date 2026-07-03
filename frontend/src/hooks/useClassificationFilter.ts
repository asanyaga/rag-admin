import { useMemo, useState } from 'react'
import type { ClassificationRun } from '@/types/classification'
import type { Granularity } from '@/lib/classificationFilter'

export interface ClassificationFilterState {
  mode: 'select' | 'configure'
  eligibleRun: ClassificationRun | null
  selectCategories: string[]
  selectedCategories: string[]
  granularity: Granularity
  setSelectedCategories: (c: string[]) => void
  setGranularity: (g: Granularity) => void
}

export function useClassificationFilter(
  runs: ClassificationRun[],
  parseRunId: string | null,
): ClassificationFilterState {
  const [selectedCategories, setSelectedCategories] = useState<string[]>([])
  const [granularity, setGranularity] = useState<Granularity>('page')

  // Eligible = completed run bound to the SAME parse the extraction will use.
  const eligibleRun = useMemo<ClassificationRun | null>(() => {
    if (!parseRunId) return null
    return runs.find((r) => r.status === 'completed' && r.parseRunId === parseRunId) ?? null
  }, [runs, parseRunId])

  // Categories come from labelsRequested — the list endpoint does not populate regions.
  const selectCategories = useMemo<string[]>(
    () => (eligibleRun ? Array.from(new Set(eligibleRun.labelsRequested)) : []),
    [eligibleRun],
  )

  return {
    mode: eligibleRun ? 'select' : 'configure',
    eligibleRun,
    selectCategories,
    selectedCategories,
    granularity,
    setSelectedCategories,
    setGranularity,
  }
}
