import { useState, useCallback, useEffect } from 'react'
import { Folder, FolderCreate, FolderUpdate } from '@/types/folder'
import * as foldersApi from '@/api/folders'

interface UseFoldersReturn {
  folders: Folder[]
  isLoading: boolean
  error: string | null
  fetchFolders: () => Promise<void>
  createFolder: (data: FolderCreate) => Promise<Folder>
  updateFolder: (folderId: string, data: FolderUpdate) => Promise<Folder>
  deleteFolder: (folderId: string) => Promise<void>
}

export function useFolders(projectId: string | null): UseFoldersReturn {
  const [folders, setFolders] = useState<Folder[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchFolders = useCallback(async () => {
    if (!projectId) {
      setFolders([])
      return
    }
    setIsLoading(true)
    setError(null)
    try {
      const data = await foldersApi.listFolders(projectId)
      setFolders(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch folders')
    } finally {
      setIsLoading(false)
    }
  }, [projectId])

  const createFolder = useCallback(
    async (data: FolderCreate): Promise<Folder> => {
      if (!projectId) throw new Error('No project selected')
      try {
        const folder = await foldersApi.createFolder(projectId, data)
        setFolders((prev) => [...prev, folder])
        return folder
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to create folder')
        throw err
      }
    },
    [projectId]
  )

  const updateFolder = useCallback(
    async (folderId: string, data: FolderUpdate): Promise<Folder> => {
      if (!projectId) throw new Error('No project selected')
      try {
        const updated = await foldersApi.updateFolder(projectId, folderId, data)
        setFolders((prev) =>
          prev.map((f) => (f.id === folderId ? updated : f))
        )
        return updated
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to update folder')
        throw err
      }
    },
    [projectId]
  )

  const deleteFolder = useCallback(
    async (folderId: string): Promise<void> => {
      if (!projectId) throw new Error('No project selected')
      try {
        await foldersApi.deleteFolder(projectId, folderId)
        setFolders((prev) => prev.filter((f) => f.id !== folderId))
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to delete folder')
        throw err
      }
    },
    [projectId]
  )

  useEffect(() => {
    if (projectId) {
      fetchFolders()
    }
  }, [projectId, fetchFolders])

  return {
    folders,
    isLoading,
    error,
    fetchFolders,
    createFolder,
    updateFolder,
    deleteFolder,
  }
}
