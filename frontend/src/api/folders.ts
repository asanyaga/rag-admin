import apiClient from './client'
import { Folder, FolderCreate, FolderUpdate } from '@/types/folder'

export async function listFolders(projectId: string): Promise<Folder[]> {
  const response = await apiClient.get<Folder[]>(
    `/projects/${projectId}/folders`
  )
  return response.data
}

export async function createFolder(
  projectId: string,
  data: FolderCreate
): Promise<Folder> {
  const response = await apiClient.post<Folder>(
    `/projects/${projectId}/folders`,
    data
  )
  return response.data
}

export async function updateFolder(
  projectId: string,
  folderId: string,
  data: FolderUpdate
): Promise<Folder> {
  const response = await apiClient.patch<Folder>(
    `/projects/${projectId}/folders/${folderId}`,
    data
  )
  return response.data
}

export async function deleteFolder(
  projectId: string,
  folderId: string
): Promise<void> {
  await apiClient.delete(`/projects/${projectId}/folders/${folderId}`)
}
