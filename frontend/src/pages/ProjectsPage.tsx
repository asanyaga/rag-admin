import { useState } from 'react'
import { useProjects } from '@/hooks/useProjects'
import { Project } from '@/types/project'
import { Button } from '@/components/ui/button'
import { ProjectCard } from '@/components/projects/ProjectCard'
import { ProjectCreateDialog } from '@/components/projects/ProjectCreateDialog'
import { ProjectEditDialog } from '@/components/projects/ProjectEditDialog'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Skeleton } from '@/components/ui/skeleton'
import { Plus, Archive } from 'lucide-react'
import { toast } from 'sonner'

export default function ProjectsPage() {
  const {
    projects,
    isLoading,
    error,
    includeArchived,
    setIncludeArchived,
    createProject,
    updateProject,
    archiveProject,
    unarchiveProject,
    deleteProject,
  } = useProjects()

  const [createDialogOpen, setCreateDialogOpen] = useState(false)
  const [editDialogOpen, setEditDialogOpen] = useState(false)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [selectedProject, setSelectedProject] = useState<Project | null>(null)

  const handleEdit = (project: Project) => {
    setSelectedProject(project)
    setEditDialogOpen(true)
  }

  const handleArchive = async (project: Project) => {
    try {
      await archiveProject(project.id)
      toast.success('Project archived successfully')
    } catch (error) {
      // Error already handled by the hook
    }
  }

  const handleUnarchive = async (project: Project) => {
    try {
      await unarchiveProject(project.id)
      toast.success('Project unarchived successfully')
    } catch (error) {
      // Error already handled by the hook
    }
  }

  const handleDeleteClick = (project: Project) => {
    setSelectedProject(project)
    setDeleteDialogOpen(true)
  }

  const handleDeleteConfirm = async () => {
    if (!selectedProject) return

    try {
      await deleteProject(selectedProject.id)
      setDeleteDialogOpen(false)
      setSelectedProject(null)
      toast.success('Project deleted successfully')
    } catch (error) {
      // Error already handled by the hook
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Projects</h1>
          <p className="text-muted-foreground mt-1">
            Organize your documents and workflows
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant={includeArchived ? 'default' : 'outline'}
            size="sm"
            onClick={() => setIncludeArchived(!includeArchived)}
          >
            <Archive className="h-4 w-4 mr-2" />
            {includeArchived ? 'Hide Archived' : 'Show Archived'}
          </Button>
          <Button onClick={() => setCreateDialogOpen(true)}>
            <Plus className="h-4 w-4 mr-2" />
            New Project
          </Button>
        </div>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {isLoading ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-48 rounded-lg" />
          ))}
        </div>
      ) : projects.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <Archive className="h-12 w-12 text-muted-foreground mb-4" />
          <h3 className="text-lg font-semibold mb-2">
            {includeArchived ? 'No projects found' : 'No active projects'}
          </h3>
          <p className="text-muted-foreground mb-4 max-w-sm">
            {includeArchived
              ? 'Create your first project to get started.'
              : 'Create a new project or show archived projects.'}
          </p>
          {!includeArchived && (
            <Button onClick={() => setCreateDialogOpen(true)}>
              <Plus className="h-4 w-4 mr-2" />
              Create Your First Project
            </Button>
          )}
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {projects.map((project) => (
            <ProjectCard
              key={project.id}
              project={project}
              onEdit={handleEdit}
              onArchive={handleArchive}
              onUnarchive={handleUnarchive}
              onDelete={handleDeleteClick}
            />
          ))}
        </div>
      )}

      <ProjectCreateDialog
        open={createDialogOpen}
        onOpenChange={setCreateDialogOpen}
        onSubmit={createProject}
      />

      <ProjectEditDialog
        project={selectedProject}
        open={editDialogOpen}
        onOpenChange={setEditDialogOpen}
        onSubmit={updateProject}
      />

      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Project</DialogTitle>
            <DialogDescription>
              Are you sure you want to permanently delete "{selectedProject?.name}"? This
              action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDeleteDialogOpen(false)}
            >
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleDeleteConfirm}>
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
