import { useNavigate } from 'react-router-dom'
import type { AgentRunListItem } from '@/types/agent'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Eye, Trash2 } from 'lucide-react'

const statusConfig: Record<
  string,
  { label: string; variant: 'default' | 'secondary' | 'destructive' }
> = {
  pending: { label: 'Pending', variant: 'secondary' },
  running: { label: 'Running', variant: 'secondary' },
  waiting_for_input: { label: 'Needs Input', variant: 'default' },
  completed: { label: 'Completed', variant: 'default' },
  failed: { label: 'Failed', variant: 'destructive' },
}

interface AgentRunListProps {
  runs: AgentRunListItem[]
  isLoading: boolean
  onDelete: (runId: string) => Promise<void>
}

export function AgentRunList({ runs, isLoading, onDelete }: AgentRunListProps) {
  const navigate = useNavigate()

  if (isLoading) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
      </div>
    )
  }

  if (runs.length === 0) {
    return (
      <div className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
        No runs yet. Use the form above to start one.
      </div>
    )
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Status</TableHead>
          <TableHead>Current Node</TableHead>
          <TableHead>Started</TableHead>
          <TableHead className="w-20" />
        </TableRow>
      </TableHeader>
      <TableBody>
        {runs.map((run) => {
          const config = statusConfig[run.status] ?? statusConfig.pending
          return (
            <TableRow
              key={run.id}
              className="cursor-pointer"
              onClick={() => navigate(`/agent/runs/${run.id}`)}
            >
              <TableCell>
                <Badge variant={config.variant}>{config.label}</Badge>
              </TableCell>
              <TableCell className="text-sm font-mono text-muted-foreground">
                {run.currentNode ?? '—'}
              </TableCell>
              <TableCell className="text-sm text-muted-foreground">
                {new Date(run.createdAt).toLocaleString()}
              </TableCell>
              <TableCell>
                <div className="flex items-center gap-1">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 w-7 p-0"
                    onClick={(e) => {
                      e.stopPropagation()
                      navigate(`/agent/runs/${run.id}`)
                    }}
                    title="View run"
                  >
                    <Eye className="h-3.5 w-3.5" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 w-7 p-0 text-muted-foreground hover:text-red-600"
                    onClick={(e) => {
                      e.stopPropagation()
                      onDelete(run.id)
                    }}
                    title="Delete run"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </TableCell>
            </TableRow>
          )
        })}
      </TableBody>
    </Table>
  )
}
