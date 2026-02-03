import { Project } from '@/types/project'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Button } from '@/components/ui/button'
import { MoreVertical, Edit, Archive, ArchiveRestore, Trash2 } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'

interface ProjectCardProps {
  project: Project
  onEdit: (project: Project) => void
  onArchive: (project: Project) => void
  onUnarchive: (project: Project) => void
  onDelete: (project: Project) => void
}

export function ProjectCard({
  project,
  onEdit,
  onArchive,
  onUnarchive,
  onDelete,
}: ProjectCardProps) {
  return (
    <Card className={project.isArchived ? 'opacity-60' : ''}>
      <CardHeader className="flex flex-row items-start justify-between space-y-0 pb-4">
        <div className="space-y-1 flex-1">
          <div className="flex items-center gap-2">
            <CardTitle className="text-xl">{project.name}</CardTitle>
            {project.isArchived && (
              <span className="text-xs bg-muted text-muted-foreground px-2 py-1 rounded">
                Archived
              </span>
            )}
          </div>
          <CardDescription className="text-sm text-muted-foreground">
            Created {formatDistanceToNow(new Date(project.createdAt), { addSuffix: true })}
          </CardDescription>
        </div>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" className="h-8 w-8">
              <MoreVertical className="h-4 w-4" />
              <span className="sr-only">Open menu</span>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={() => onEdit(project)}>
              <Edit className="mr-2 h-4 w-4" />
              Edit
            </DropdownMenuItem>
            {project.isArchived ? (
              <DropdownMenuItem onClick={() => onUnarchive(project)}>
                <ArchiveRestore className="mr-2 h-4 w-4" />
                Unarchive
              </DropdownMenuItem>
            ) : (
              <DropdownMenuItem onClick={() => onArchive(project)}>
                <Archive className="mr-2 h-4 w-4" />
                Archive
              </DropdownMenuItem>
            )}
            {project.isArchived && (
              <>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  onClick={() => onDelete(project)}
                  className="text-destructive focus:text-destructive"
                >
                  <Trash2 className="mr-2 h-4 w-4" />
                  Delete
                </DropdownMenuItem>
              </>
            )}
          </DropdownMenuContent>
        </DropdownMenu>
      </CardHeader>
      <CardContent>
        {project.description && (
          <p className="text-sm text-muted-foreground mb-3">{project.description}</p>
        )}
        {project.tags.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {project.tags.map((tag) => (
              <span
                key={tag}
                className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-primary/10 text-primary"
              >
                {tag}
              </span>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
