import { useState, useCallback, useEffect } from 'react'
import { Project, ProjectCreate, ProjectUpdate } from '@/types/project'
import * as projectsApi from '@/api/projects'

interface UseProjectsReturn {
  projects: Project[]
  isLoading: boolean
  error: string | null
  includeArchived: boolean
  setIncludeArchived: (value: boolean) => void
  fetchProjects: () => Promise<void>
  createProject: (data: ProjectCreate) => Promise<Project>
  updateProject: (id: string, data: ProjectUpdate) => Promise<Project>
  archiveProject: (id: string) => Promise<Project>
  unarchiveProject: (id: string) => Promise<Project>
  deleteProject: (id: string) => Promise<void>
}

export function useProjects(autoFetch = true): UseProjectsReturn {
  const [projects, setProjects] = useState<Project[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [includeArchived, setIncludeArchived] = useState(false)

  const fetchProjects = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const data = await projectsApi.getProjects(includeArchived)
      setProjects(data)
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch projects'
      setError(errorMessage)
      console.error('Error fetching projects:', err)
    } finally {
      setIsLoading(false)
    }
  }, [includeArchived])

  const createProject = useCallback(
    async (data: ProjectCreate): Promise<Project> => {
      try {
        const newProject = await projectsApi.createProject(data)
        setProjects((prev) => [newProject, ...prev])
        return newProject
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Failed to create project'
        setError(errorMessage)
        throw err
      }
    },
    []
  )

  const updateProject = useCallback(
    async (id: string, data: ProjectUpdate): Promise<Project> => {
      try {
        const updatedProject = await projectsApi.updateProject(id, data)
        setProjects((prev) =>
          prev.map((p) => (p.id === id ? updatedProject : p))
        )
        return updatedProject
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Failed to update project'
        setError(errorMessage)
        throw err
      }
    },
    []
  )

  const archiveProject = useCallback(
    async (id: string): Promise<Project> => {
      try {
        const archivedProject = await projectsApi.archiveProject(id)
        setProjects((prev) =>
          prev.map((p) => (p.id === id ? archivedProject : p))
        )
        return archivedProject
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Failed to archive project'
        setError(errorMessage)
        throw err
      }
    },
    []
  )

  const unarchiveProject = useCallback(
    async (id: string): Promise<Project> => {
      try {
        const unarchivedProject = await projectsApi.unarchiveProject(id)
        setProjects((prev) =>
          prev.map((p) => (p.id === id ? unarchivedProject : p))
        )
        return unarchivedProject
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : 'Failed to unarchive project'
        setError(errorMessage)
        throw err
      }
    },
    []
  )

  const deleteProject = useCallback(async (id: string): Promise<void> => {
    try {
      await projectsApi.deleteProject(id)
      setProjects((prev) => prev.filter((p) => p.id !== id))
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to delete project'
      setError(errorMessage)
      throw err
    }
  }, [])

  // Auto-fetch on mount and when includeArchived changes
  useEffect(() => {
    if (autoFetch) {
      fetchProjects()
    }
  }, [autoFetch, fetchProjects])

  return {
    projects,
    isLoading,
    error,
    includeArchived,
    setIncludeArchived,
    fetchProjects,
    createProject,
    updateProject,
    archiveProject,
    unarchiveProject,
    deleteProject,
  }
}
