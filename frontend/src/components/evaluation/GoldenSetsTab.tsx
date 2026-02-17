import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, ChevronRight, Trash2, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { EvalStatusBadge } from './EvalStatusBadge'
import { CreateGoldenSetDialog } from './CreateGoldenSetDialog'
import type { GoldenSet, GoldenSetCreate } from '@/types/golden-set'

interface GoldenSetsTabProps {
  goldenSets: GoldenSet[]
  isLoading: boolean
  onCreate: (data: GoldenSetCreate) => Promise<GoldenSet>
  onDelete: (id: string) => Promise<void>
}

export function GoldenSetsTab({
  goldenSets,
  isLoading,
  onCreate,
  onDelete,
}: GoldenSetsTabProps) {
  const navigate = useNavigate()
  const [dialogOpen, setDialogOpen] = useState(false)

  const handleCreate = async (data: GoldenSetCreate, method: 'manual' | 'auto-generate') => {
    const gs = await onCreate(data)
    setDialogOpen(false)
    if (method === 'auto-generate') {
      navigate(`/evaluation/golden-sets/${gs.id}/generate`)
    } else {
      navigate(`/evaluation/golden-sets/${gs.id}`)
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button size="sm" onClick={() => setDialogOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          New Golden Set
        </Button>
      </div>

      {goldenSets.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">
          <p>No golden sets yet.</p>
          <p className="text-sm mt-1">
            Create a golden set to define ground-truth queries and expected sources.
          </p>
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead className="text-right">Queries</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="w-10" />
              <TableHead className="w-10" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {goldenSets.map((gs) => (
              <TableRow
                key={gs.id}
                className="cursor-pointer"
                onClick={() => navigate(`/evaluation/golden-sets/${gs.id}`)}
              >
                <TableCell>
                  <div>
                    <p className="font-medium">{gs.name}</p>
                    {gs.documentCount > 0 && (
                      <p className="text-xs text-muted-foreground">
                        {gs.documentCount} document{gs.documentCount !== 1 ? 's' : ''}
                      </p>
                    )}
                  </div>
                </TableCell>
                <TableCell className="text-right font-mono text-sm">
                  {gs.queryCount}
                </TableCell>
                <TableCell>
                  <EvalStatusBadge status={gs.generationStatus ?? gs.status} />
                </TableCell>
                <TableCell onClick={(e) => e.stopPropagation()}>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => onDelete(gs.id)}
                  >
                    <Trash2 className="h-4 w-4 text-muted-foreground" />
                  </Button>
                </TableCell>
                <TableCell>
                  <ChevronRight className="h-4 w-4 text-muted-foreground" />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      <CreateGoldenSetDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        onCreate={handleCreate}
      />
    </div>
  )
}
