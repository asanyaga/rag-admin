/**
 * Card component for displaying an index
 */
import { IndexListItem } from '@/types/index'
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
import { IndexStatusBadge } from './IndexStatusBadge'
import {
  MoreVertical,
  Edit,
  Trash2,
  Play,
  RefreshCw,
  Eye,
  FileText,
  Layers,
} from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'

interface IndexCardProps {
  index: IndexListItem
  onView: (index: IndexListItem) => void
  onEdit: (index: IndexListItem) => void
  onDelete: (index: IndexListItem) => void
  onProcess: (index: IndexListItem) => void
  onRetry: (index: IndexListItem) => void
}

export function IndexCard({
  index,
  onView,
  onEdit,
  onDelete,
  onProcess,
  onRetry,
}: IndexCardProps) {
  const canProcess = index.status === 'created'
  const canRetry = index.status === 'failed'
  const canEdit = index.status === 'created'

  return (
    <Card className="hover:shadow-md transition-shadow">
      <CardHeader className="flex flex-row items-start justify-between space-y-0 pb-3">
        <div className="space-y-1 flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <CardTitle className="text-lg truncate">{index.name}</CardTitle>
            <IndexStatusBadge status={index.status} />
          </div>
          <CardDescription className="text-sm">
            Created{' '}
            {formatDistanceToNow(new Date(index.createdAt), { addSuffix: true })}
          </CardDescription>
        </div>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" className="h-8 w-8 shrink-0">
              <MoreVertical className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={() => onView(index)}>
              <Eye className="mr-2 h-4 w-4" />
              View Details
            </DropdownMenuItem>
            {canEdit && (
              <DropdownMenuItem onClick={() => onEdit(index)}>
                <Edit className="mr-2 h-4 w-4" />
                Edit
              </DropdownMenuItem>
            )}
            <DropdownMenuSeparator />
            {canProcess && (
              <DropdownMenuItem onClick={() => onProcess(index)}>
                <Play className="mr-2 h-4 w-4" />
                Start Processing
              </DropdownMenuItem>
            )}
            {canRetry && (
              <DropdownMenuItem onClick={() => onRetry(index)}>
                <RefreshCw className="mr-2 h-4 w-4" />
                Retry Processing
              </DropdownMenuItem>
            )}
            <DropdownMenuSeparator />
            <DropdownMenuItem
              onClick={() => onDelete(index)}
              className="text-destructive focus:text-destructive"
            >
              <Trash2 className="mr-2 h-4 w-4" />
              Delete
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </CardHeader>
      <CardContent>
        {index.description && (
          <p className="text-sm text-muted-foreground mb-3 line-clamp-2">
            {index.description}
          </p>
        )}
        <div className="flex items-center gap-4 text-sm text-muted-foreground">
          <span className="flex items-center gap-1">
            <FileText className="h-4 w-4" />
            {index.documentCount} docs
          </span>
          <span className="flex items-center gap-1">
            <Layers className="h-4 w-4" />
            {index.chunkCount} chunks
          </span>
        </div>
        {index.embeddingModel && (
          <div className="mt-2 text-xs text-muted-foreground">
            {index.chunkingStrategy} • {index.embeddingModel}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
