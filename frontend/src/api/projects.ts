import apiClient from './client'
import { Project, ProjectCreate, ProjectUpdate } from '@/types/project'

export async function createProject(data: ProjectCreate): Promise<Project> {
  const response = await apiClient.post<Project>('/projects', data)
  return response.data
}

export async function getProjects(includeArchived = false): Promise<Project[]> {
  const response = await apiClient.get<Project[]>('/projects', {
    params: { include_archived: includeArchived },
  })
  return response.data
}

export async function getProject(id: string): Promise<Project> {
  const response = await apiClient.get<Project>(`/projects/${id}`)
  return response.data
}

export async function updateProject(
  id: string,
  data: ProjectUpdate
): Promise<Project> {
  const response = await apiClient.patch<Project>(`/projects/${id}`, data)
  return response.data
}

export async function archiveProject(id: string): Promise<Project> {
  const response = await apiClient.post<Project>(`/projects/${id}/archive`)
  return response.data
}

export async function unarchiveProject(id: string): Promise<Project> {
  const response = await apiClient.post<Project>(`/projects/${id}/unarchive`)
  return response.data
}

export async function deleteProject(id: string): Promise<void> {
  await apiClient.delete(`/projects/${id}`)
}
