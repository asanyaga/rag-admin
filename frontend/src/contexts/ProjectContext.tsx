import {
  createContext,
  ReactNode,
  useCallback,
  useEffect,
  useState,
  useContext,
} from 'react'
import { Project, ProjectCreate } from '@/types/project'
import * as projectsApi from '@/api/projects'
import { useAuth } from '@/hooks/useAuth'

interface ProjectContextType {
  currentProject: Project | null
  setCurrentProject: (project: Project) => void
  projects: Project[]
  isLoading: boolean
  fetchProjects: () => Promise<void>
  createProject: (data: ProjectCreate) => Promise<Project>
}

const ProjectContext = createContext<ProjectContextType | undefined>(undefined)

interface ProjectProviderProps {
  children: ReactNode
}

export function ProjectProvider({ children }: ProjectProviderProps) {
  const { user, isAuthenticated } = useAuth()
  const [currentProject, setCurrentProjectState] = useState<Project | null>(null)
  const [projects, setProjects] = useState<Project[]>([])
  const [isLoading, setIsLoading] = useState(true)

  // Fetch all projects
  const fetchProjects = useCallback(async () => {
    try {
      const fetchedProjects = await projectsApi.getProjects()
      console.log('[ProjectContext] Fetched projects:', fetchedProjects.map(p => ({ id: p.id, name: p.name, userId: p.userId })))
      setProjects(fetchedProjects)
    } catch (error) {
      console.error('[ProjectContext] Failed to fetch projects:', error)
    }
  }, [])

  // Set current project and persist to localStorage
  const setCurrentProject = useCallback((project: Project) => {
    setCurrentProjectState(project)
    localStorage.setItem('currentProjectId', project.id)
  }, [])

  // Fetch default project
  const fetchDefaultProject = useCallback(async () => {
    try {
      const defaultProject = await projectsApi.getDefaultProject()
      setCurrentProject(defaultProject)
    } catch (error) {
      console.error('Failed to fetch default project:', error)
    }
  }, [setCurrentProject])

  // Create a new project
  const createProject = useCallback(async (data: ProjectCreate): Promise<Project> => {
    const newProject = await projectsApi.createProject(data)
    setProjects((prev) => [newProject, ...prev])
    return newProject
  }, [])

  // Load current project when user authenticates
  useEffect(() => {
    const initProject = async () => {
      // Don't initialize if user is not authenticated
      if (!isAuthenticated || !user) {
        console.log('[ProjectContext] Not authenticated, clearing state')
        setIsLoading(false)
        setProjects([])
        setCurrentProjectState(null)
        return
      }

      console.log('[ProjectContext] Initializing for user:', user.id)

      setIsLoading(true)
      try {
        // Fetch all projects first
        await fetchProjects()

        // Try to load from localStorage
        const savedProjectId = localStorage.getItem('currentProjectId')

        if (savedProjectId) {
          // Try to fetch the saved project
          try {
            const project = await projectsApi.getProject(savedProjectId)
            setCurrentProjectState(project)
          } catch (error) {
            // If saved project not found, fall back to default
            await fetchDefaultProject()
          }
        } else {
          // No saved project, fetch default
          await fetchDefaultProject()
        }
      } catch (error) {
        console.error('Failed to initialize project context:', error)
      } finally {
        setIsLoading(false)
      }
    }

    initProject()
  }, [isAuthenticated, user?.id, fetchProjects, fetchDefaultProject])

  // Clear projects when user signs out
  useEffect(() => {
    if (!isAuthenticated) {
      console.log('[ProjectContext] User signed out, clearing projects and localStorage')
      setProjects([])
      setCurrentProjectState(null)
      localStorage.removeItem('currentProjectId')
    }
  }, [isAuthenticated])

  const value: ProjectContextType = {
    currentProject,
    setCurrentProject,
    projects,
    isLoading,
    fetchProjects,
    createProject,
  }

  return (
    <ProjectContext.Provider value={value}>
      {children}
    </ProjectContext.Provider>
  )
}

export function useProject() {
  const context = useContext(ProjectContext)
  if (!context) {
    throw new Error('useProject must be used within ProjectProvider')
  }
  return context
}
