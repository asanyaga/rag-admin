/**
 * Eval Runs API client functions
 */
import apiClient from './client'
import type {
  EvalRun,
  CreateEvalRunRequest,
  EvalRunResult,
  EvalRunProgress,
  RunComparison,
  LlmModelOption,
} from '@/types/eval-run'

export async function listEvalRuns(projectId: string): Promise<EvalRun[]> {
  const response = await apiClient.get<EvalRun[]>(
    `/projects/${projectId}/eval-runs`
  )
  return response.data
}

export async function getEvalRun(
  projectId: string,
  runId: string
): Promise<EvalRun> {
  const response = await apiClient.get<EvalRun>(
    `/projects/${projectId}/eval-runs/${runId}`
  )
  return response.data
}

export async function createEvalRun(
  projectId: string,
  data: CreateEvalRunRequest
): Promise<EvalRun> {
  const response = await apiClient.post<EvalRun>(
    `/projects/${projectId}/eval-runs`,
    data
  )
  return response.data
}

export async function deleteEvalRun(
  projectId: string,
  runId: string
): Promise<void> {
  await apiClient.delete(`/projects/${projectId}/eval-runs/${runId}`)
}

export async function getEvalRunResults(
  projectId: string,
  runId: string,
  filter?: string
): Promise<EvalRunResult[]> {
  const params = filter && filter !== 'all' ? { filter } : undefined
  const response = await apiClient.get<EvalRunResult[]>(
    `/projects/${projectId}/eval-runs/${runId}/results`,
    { params }
  )
  return response.data
}

export async function getEvalRunProgress(
  projectId: string,
  runId: string
): Promise<EvalRunProgress> {
  const response = await apiClient.get<EvalRunProgress>(
    `/projects/${projectId}/eval-runs/${runId}/progress`
  )
  return response.data
}

export async function fetchLlmModels(): Promise<LlmModelOption[]> {
  const response = await apiClient.get<{ models: LlmModelOption[] }>(
    '/settings/llm-models'
  )
  return response.data.models
}

export async function getEvalRunConfig(
  projectId: string,
  runId: string
): Promise<Record<string, unknown>> {
  const response = await apiClient.get<Record<string, unknown>>(
    `/projects/${projectId}/eval-runs/${runId}/config`
  )
  return response.data
}

export async function compareRuns(
  projectId: string,
  runId1: string,
  runId2: string
): Promise<RunComparison> {
  const response = await apiClient.get<RunComparison>(
    `/projects/${projectId}/eval-runs/compare`,
    { params: { runIds: `${runId1},${runId2}` } }
  )
  return response.data
}
