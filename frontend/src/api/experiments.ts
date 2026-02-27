/**
 * Experiments API client functions
 */
import apiClient from './client'
import type {
  Experiment,
  ExperimentDetail,
  CreateExperimentRequest,
  UpdateExperimentRequest,
} from '@/types/experiment'

export async function listExperiments(projectId: string): Promise<Experiment[]> {
  const response = await apiClient.get<Experiment[]>(
    `/projects/${projectId}/experiments`
  )
  return response.data
}

export async function createExperiment(
  projectId: string,
  data: CreateExperimentRequest
): Promise<Experiment> {
  const response = await apiClient.post<Experiment>(
    `/projects/${projectId}/experiments`,
    data
  )
  return response.data
}

export async function getExperiment(
  projectId: string,
  experimentId: string
): Promise<ExperimentDetail> {
  const response = await apiClient.get<ExperimentDetail>(
    `/projects/${projectId}/experiments/${experimentId}`
  )
  return response.data
}

export async function updateExperiment(
  projectId: string,
  experimentId: string,
  data: UpdateExperimentRequest
): Promise<Experiment> {
  const response = await apiClient.patch<Experiment>(
    `/projects/${projectId}/experiments/${experimentId}`,
    data
  )
  return response.data
}

export async function deleteExperiment(
  projectId: string,
  experimentId: string
): Promise<void> {
  await apiClient.delete(`/projects/${projectId}/experiments/${experimentId}`)
}
