import { useNavigate } from 'react-router-dom'
import { ChevronDown, FolderKanban, Plus } from 'lucide-react'
import { useProject } from '@/contexts/ProjectContext'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'

export function ProjectSwitcher() {
  const { currentProject, projects, setCurrentProject } = useProject()
  const navigate = useNavigate()

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" className="w-full justify-start">
          <FolderKanban className="mr-2 h-4 w-4" />
          <span className="truncate">
            {currentProject?.name || 'Select Project'}
          </span>
          <ChevronDown className="ml-auto h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-56">
        <DropdownMenuLabel>Projects</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {projects.map((project) => (
          <DropdownMenuItem
            key={project.id}
            onClick={() => setCurrentProject(project)}
            className={project.id === currentProject?.id ? 'bg-accent' : ''}
          >
            <FolderKanban className="mr-2 h-4 w-4" />
            {project.name}
          </DropdownMenuItem>
        ))}
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={() => navigate('/projects')}>
          <Plus className="mr-2 h-4 w-4" />
          Manage Projects
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
