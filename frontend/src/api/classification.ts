// frontend/src/api/classification.ts
import apiClient from './client'
import type { AnnotatedBlock, ClassificationRun, ClassificationRunCreateRequest } from '@/types/classification'

export async function createClassificationRun(
  documentId: string,
  data: ClassificationRunCreateRequest,
): Promise<ClassificationRun> {
  const response = await apiClient.post<ClassificationRun>(
    `/documents/${documentId}/classification-runs`,
    {
      parse_run_id: data.parseRunId,
      labels: data.labels,
      classifier_type: data.classifierType,
      classifier_config: data.classifierConfig,
    },
  )
  return response.data
}

export async function listDocumentClassificationRuns(
  documentId: string,
): Promise<ClassificationRun[]> {
  const response = await apiClient.get<ClassificationRun[]>(
    `/documents/${documentId}/classification-runs`,
  )
  return response.data
}

export async function listAllClassificationRuns(
  projectId: string,
): Promise<ClassificationRun[]> {
  const response = await apiClient.get<ClassificationRun[]>(
    `/classification-runs?project_id=${projectId}`,
  )
  return response.data
}

export async function getClassificationRun(runId: string): Promise<ClassificationRun> {
  const response = await apiClient.get<ClassificationRun>(`/classification-runs/${runId}`)
  return response.data
}

export async function deleteClassificationRun(runId: string): Promise<void> {
  await apiClient.delete(`/classification-runs/${runId}`)
}

export async function getClassificationRunBlocks(runId: string): Promise<AnnotatedBlock[]> {
  const response = await apiClient.get<AnnotatedBlock[]>(`/classification-runs/${runId}/blocks`)
  return response.data
}

export async function getClassificationSystemPromptConfig(): Promise<{
  instruction: string
  requiredFormat: string
}> {
  const response = await apiClient.get<{ instruction: string; required_format: string }>(
    '/classification-runs/system-prompt-config',
  )
  return {
    instruction: response.data.instruction,
    requiredFormat: response.data.required_format,
  }
}
