export type Granularity = 'page' | 'block'

export type ClassificationFilterIntent =
  | { mode: 'none' }
  | { mode: 'select'; classificationRunId: string; categories: string[]; granularity: Granularity }
  | {
      mode: 'configure'
      classify: { labels: string[]; classifierType: string; classifierConfig: Record<string, unknown> }
      categories: string[]
      granularity: Granularity
    }

export interface FilterInputs {
  eligibleRunId: string | null
  selectedCategories: string[]
  granularity: Granularity
  classify: { labels: string[]; classifierType: string; classifierConfig: Record<string, unknown> } | null
}

export function buildFilterIntent(inputs: FilterInputs): ClassificationFilterIntent {
  const { eligibleRunId, selectedCategories, granularity, classify } = inputs
  if (selectedCategories.length === 0) return { mode: 'none' }
  if (eligibleRunId) {
    return { mode: 'select', classificationRunId: eligibleRunId, categories: selectedCategories, granularity }
  }
  if (classify && classify.labels.length > 0) {
    return { mode: 'configure', classify, categories: selectedCategories, granularity }
  }
  return { mode: 'none' }
}
