import apiClient from './client'
import type {
  ExtractionEvalRun,
  ExtractionEvalResult,
  CreateExtractionEvalRunRequest,
} from '@/types/extractionEval'

export async function createExtractionEvalRun(
  projectId: string,
  data: CreateExtractionEvalRunRequest
): Promise<ExtractionEvalRun> {
  const response = await apiClient.post<ExtractionEvalRun>(
    `/projects/${projectId}/extraction-eval-runs`,
    data
  )
  return response.data
}

export async function listExtractionEvalRuns(
  projectId: string,
  groundTruthSetId?: string
): Promise<ExtractionEvalRun[]> {
  const params = groundTruthSetId ? { groundTruthSetId } : undefined
  const response = await apiClient.get<ExtractionEvalRun[]>(
    `/projects/${projectId}/extraction-eval-runs`,
    { params }
  )
  return response.data
}

export async function getExtractionEvalRun(
  runId: string
): Promise<ExtractionEvalRun> {
  const response = await apiClient.get<ExtractionEvalRun>(
    `/extraction-eval-runs/${runId}`
  )
  return response.data
}

export async function deleteExtractionEvalRun(
  runId: string
): Promise<void> {
  await apiClient.delete(`/extraction-eval-runs/${runId}`)
}

export async function getExtractionEvalRunResults(
  runId: string
): Promise<ExtractionEvalResult[]> {
  const response = await apiClient.get<ExtractionEvalResult[]>(
    `/extraction-eval-runs/${runId}/results`
  )
  return response.data
}

export async function getExtractionEvalResult(
  resultId: string
): Promise<ExtractionEvalResult> {
  const response = await apiClient.get<ExtractionEvalResult>(
    `/extraction-eval-results/${resultId}`
  )
  return response.data
}
