import { useState } from 'react'
import { AxiosError } from 'axios'
import { Project, ProjectCreate } from '@/types/project'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { toast } from 'sonner'

interface ProjectCreateDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSubmit: (data: ProjectCreate) => Promise<Project>
}

export function ProjectCreateDialog({
  open,
  onOpenChange,
  onSubmit,
}: ProjectCreateDialogProps) {
  const [isLoading, setIsLoading] = useState(false)
  const [formData, setFormData] = useState<ProjectCreate>({
    name: '',
    description: '',
    tags: [],
  })
  const [tagsInput, setTagsInput] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!formData.name.trim()) {
      toast.error('Project name is required')
      return
    }

    if (formData.name.length > 255) {
      toast.error('Project name must be 255 characters or less')
      return
    }

    if (formData.description && formData.description.length > 500) {
      toast.error('Description must be 500 characters or less')
      return
    }

    setIsLoading(true)
    try {
      // Parse tags from comma-separated input
      const tags = tagsInput
        .split(',')
        .map((tag) => tag.trim())
        .filter((tag) => tag.length > 0)

      await onSubmit({ ...formData, tags })

      // Reset form
      setFormData({ name: '', description: '', tags: [] })
      setTagsInput('')
      onOpenChange(false)
      toast.success('Project created successfully')
    } catch (error) {
      // Handle Axios errors with proper error message extraction
      if (error instanceof AxiosError && error.response) {
        const status = error.response.status
        const detail = error.response.data?.detail

        if (status === 409) {
          // Conflict error - duplicate project name
          toast.error(
            detail || `A project with the name "${formData.name}" already exists. Please choose a different name.`
          )
        } else {
          // Other API errors
          toast.error(detail || error.message || 'Failed to create project')
        }
      } else if (error instanceof Error) {
        toast.error(error.message || 'Failed to create project')
      } else {
        toast.error('Failed to create project')
      }
    } finally {
      setIsLoading(false)
    }
  }

  const handleClose = () => {
    if (!isLoading) {
      setFormData({ name: '', description: '', tags: [] })
      setTagsInput('')
      onOpenChange(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent>
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Create New Project</DialogTitle>
            <DialogDescription>
              Add a new project to organize your documents and workflows.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="name">
                Name <span className="text-destructive">*</span>
              </Label>
              <Input
                id="name"
                placeholder="My Project"
                value={formData.name}
                onChange={(e) =>
                  setFormData({ ...formData, name: e.target.value })
                }
                maxLength={255}
                required
                disabled={isLoading}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                placeholder="Project description..."
                value={formData.description}
                onChange={(e) =>
                  setFormData({ ...formData, description: e.target.value })
                }
                maxLength={500}
                rows={3}
                disabled={isLoading}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="tags">Tags</Label>
              <Input
                id="tags"
                placeholder="tag1, tag2, tag3"
                value={tagsInput}
                onChange={(e) => setTagsInput(e.target.value)}
                disabled={isLoading}
              />
              <p className="text-xs text-muted-foreground">
                Separate tags with commas
              </p>
            </div>
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={handleClose}
              disabled={isLoading}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isLoading}>
              {isLoading ? 'Creating...' : 'Create Project'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
