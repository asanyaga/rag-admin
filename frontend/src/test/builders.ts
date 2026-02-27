/**
 * Test data builders for creating mock objects in tests.
 */
import type { Experiment, ExperimentDetail } from '@/types/experiment'
import type { EvalRun, EvalRunMetrics } from '@/types/eval-run'

export function buildEvalRunMetrics(
  overrides?: Partial<EvalRunMetrics>
): EvalRunMetrics {
  return {
    avgPrecision: 0.8,
    avgRecall: 0.7,
    avgF1: 0.75,
    queriesBelowThreshold: 1,
    avgFaithfulness: null,
    avgRelevance: null,
    ...overrides,
  }
}

export function buildEvalRun(overrides?: Partial<EvalRun>): EvalRun {
  return {
    id: 'run-1',
    name: 'Test Run',
    goldenSetId: 'gs-1',
    goldenSetName: 'Test GS',
    indexId: 'idx-1',
    indexName: 'Test Index',
    config: { searchType: 'semantic', topK: 5, similarityThreshold: 0 },
    status: 'completed',
    metrics: buildEvalRunMetrics(),
    errorMessage: null,
    createdBy: 'user-1',
    createdAt: '2026-01-01T00:00:00Z',
    mode: 'retrieval_only',
    generationModel: null,
    judgeModel: null,
    itemsCompleted: 5,
    failedItemCount: 0,
    experimentId: undefined,
    experimentName: undefined,
    variantLabel: undefined,
    ...overrides,
  }
}

export function buildExperiment(
  overrides?: Partial<Experiment>
): Experiment {
  return {
    id: 'exp-1',
    name: 'Test Experiment',
    description: 'A test experiment',
    status: 'active',
    notes: null,
    baselineRunId: null,
    baselineRun: null,
    runCount: 0,
    createdBy: 'user-1',
    createdAt: '2026-01-01T00:00:00Z',
    updatedAt: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

export function buildExperimentDetail(
  overrides?: Partial<ExperimentDetail>
): ExperimentDetail {
  return {
    ...buildExperiment(),
    runs: [],
    variableDiff: { varying: {}, constant: {} },
    ...overrides,
  }
}
