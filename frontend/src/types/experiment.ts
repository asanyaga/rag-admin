/**
 * Experiment feature types
 */
import type { EvalRun } from './eval-run'

export type ExperimentStatus = 'active' | 'concluded'

export interface Experiment {
  id: string
  name: string
  description: string | null
  status: ExperimentStatus
  notes: string | null
  baselineRunId: string | null
  baselineRun: EvalRun | null
  runCount: number
  createdBy: string
  createdAt: string
  updatedAt: string
}

export interface VariableDiff {
  varying: Record<string, string[]>
  constant: Record<string, string>
}

export interface ExperimentDetail extends Experiment {
  runs: EvalRun[]
  variableDiff: VariableDiff
}

export interface CreateExperimentRequest {
  name: string
  description?: string
}

export interface UpdateExperimentRequest {
  name?: string
  description?: string
  notes?: string
  status?: ExperimentStatus
  baselineRunId?: string
}

export interface RunMeta {
  id: string
  name: string
  variantLabel: string | null
  avgF1: number | null
}

export interface PerRunMetrics {
  precision: number
  recall: number
  f1: number
  deltaF1: number | null
}

export interface ComparisonRow {
  queryId: string
  queryText: string
  results: Record<string, PerRunMetrics>
}

export interface ExperimentComparison {
  experimentId: string
  experimentName: string
  baselineRunId: string | null
  runs: RunMeta[]
  rows: ComparisonRow[]
}
