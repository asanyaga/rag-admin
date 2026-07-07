import apiClient from './client'
import type {
  ParserEvalCase, ParserEvalCaseDetail, ParserEvalRun, ParserEvalResult,
  CreateCaseRequest, CreateRunRequest, BootstrapTableRequest,
} from '@/types/parserEval'

export async function listCases(projectId: string): Promise<ParserEvalCase[]> {
  const r = await apiClient.get<ParserEvalCase[]>(`/projects/${projectId}/parser-eval/cases`)
  return r.data
}

export async function createCase(projectId: string, data: CreateCaseRequest): Promise<ParserEvalCase> {
  const r = await apiClient.post<ParserEvalCase>(`/projects/${projectId}/parser-eval/cases`, data)
  return r.data
}

export async function bootstrapTableCase(
  projectId: string, data: BootstrapTableRequest,
): Promise<ParserEvalCaseDetail> {
  const r = await apiClient.post<ParserEvalCaseDetail>(
    `/projects/${projectId}/parser-eval/cases/bootstrap-table`, data)
  return r.data
}

export async function getCase(projectId: string, caseId: string): Promise<ParserEvalCaseDetail> {
  const r = await apiClient.get<ParserEvalCaseDetail>(
    `/projects/${projectId}/parser-eval/cases/${caseId}`)
  return r.data
}

export async function updateCaseReview(
  projectId: string, caseId: string, reviewStatus: 'draft' | 'verified',
): Promise<ParserEvalCaseDetail> {
  const r = await apiClient.patch<ParserEvalCaseDetail>(
    `/projects/${projectId}/parser-eval/cases/${caseId}`, { reviewStatus })
  return r.data
}

export async function deleteCase(projectId: string, caseId: string): Promise<void> {
  await apiClient.delete(`/projects/${projectId}/parser-eval/cases/${caseId}`)
}

export async function listRuns(projectId: string): Promise<ParserEvalRun[]> {
  const r = await apiClient.get<ParserEvalRun[]>(`/projects/${projectId}/parser-eval/runs`)
  return r.data
}

export async function createRun(projectId: string, data: CreateRunRequest): Promise<ParserEvalRun> {
  const r = await apiClient.post<ParserEvalRun>(`/projects/${projectId}/parser-eval/runs`, data)
  return r.data
}

export async function getRun(projectId: string, runId: string): Promise<ParserEvalRun> {
  const r = await apiClient.get<ParserEvalRun>(`/projects/${projectId}/parser-eval/runs/${runId}`)
  return r.data
}

export async function getRunResults(projectId: string, runId: string): Promise<ParserEvalResult[]> {
  const r = await apiClient.get<ParserEvalResult[]>(`/projects/${projectId}/parser-eval/runs/${runId}/results`)
  return r.data
}
