import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, Trash2, Loader2, FlaskConical } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { CreateExperimentDialog } from './CreateExperimentDialog'
import type { Experiment, CreateExperimentRequest } from '@/types/experiment'

interface ExperimentsTabProps {
  experiments: Experiment[]
  isLoading: boolean
  onCreate: (data: CreateExperimentRequest) => Promise<Experiment>
  onDelete: (id: string) => Promise<void>
}

export function ExperimentsTab({
  experiments,
  isLoading,
  onCreate,
  onDelete,
}: ExperimentsTabProps) {
  const navigate = useNavigate()
  const [dialogOpen, setDialogOpen] = useState(false)

  const handleCreate = async (data: CreateExperimentRequest) => {
    const experiment = await onCreate(data)
    navigate(`/evaluation/experiments/${experiment.id}`)
  }

  const formatMetric = (val: number | undefined | null) =>
    val != null ? (val * 100).toFixed(1) + '%' : '—'

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-end">
        <Button size="sm" onClick={() => setDialogOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          New Experiment
        </Button>
      </div>

      {experiments.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">
          <FlaskConical className="mx-auto h-8 w-8 mb-3 opacity-50" />
          <p>No experiments yet.</p>
          <p className="text-sm mt-1">
            Create an experiment to group related eval runs and track hypotheses.
          </p>
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Runs</TableHead>
              <TableHead className="text-right">Baseline F1</TableHead>
              <TableHead>Created</TableHead>
              <TableHead className="w-10" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {experiments.map((exp) => (
              <TableRow
                key={exp.id}
                className="cursor-pointer"
                onClick={() => navigate(`/evaluation/experiments/${exp.id}`)}
              >
                <TableCell>
                  <div>
                    <p className="font-medium">{exp.name}</p>
                    {exp.description && (
                      <p className="text-xs text-muted-foreground line-clamp-1">
                        {exp.description}
                      </p>
                    )}
                  </div>
                </TableCell>
                <TableCell>
                  <Badge
                    variant={exp.status === 'active' ? 'blue' : 'secondary'}
                  >
                    {exp.status}
                  </Badge>
                </TableCell>
                <TableCell className="text-right font-mono text-sm">
                  {exp.runCount}
                </TableCell>
                <TableCell className="text-right font-mono text-sm">
                  {formatMetric(exp.baselineRun?.metrics?.avgF1)}
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  {new Date(exp.createdAt).toLocaleDateString()}
                </TableCell>
                <TableCell onClick={(e) => e.stopPropagation()}>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => onDelete(exp.id)}
                  >
                    <Trash2 className="h-4 w-4 text-muted-foreground" />
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      <CreateExperimentDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        onCreate={handleCreate}
      />
    </div>
  )
}
