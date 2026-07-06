import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { EvalStatusBadge } from '@/components/evaluation/EvalStatusBadge'
import { useParserEvalRuns } from '@/hooks/useParserEval'
import type { CreateRunRequest } from '@/types/parserEval'
import { NewRunDialog } from './NewRunDialog'

export function ParserEvalRunsTab({ projectId }: { projectId: string }) {
  const { runs, isLoading, createRun } = useParserEvalRuns(projectId)
  const [dialogOpen, setDialogOpen] = useState(false)
  const navigate = useNavigate()

  const handleCreate = async (data: CreateRunRequest) => {
    const run = await createRun(data)
    navigate(`/evaluation/parser/runs/${run.id}`)
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button onClick={() => setDialogOpen(true)}>New run</Button>
      </div>

      {isLoading ? (
        <p className="text-muted-foreground">Loading…</p>
      ) : runs.length === 0 ? (
        <p className="text-center py-8 text-muted-foreground">No runs yet.</p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Adapters</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {runs.map((r) => (
              <TableRow
                key={r.id}
                className="cursor-pointer"
                onClick={() => navigate(`/evaluation/parser/runs/${r.id}`)}
              >
                <TableCell>{r.name}</TableCell>
                <TableCell>
                  <EvalStatusBadge status={r.status} />
                </TableCell>
                <TableCell>{r.variants.map((v) => v.adapter).join(', ')}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      <NewRunDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        projectId={projectId}
        onCreate={handleCreate}
      />
    </div>
  )
}
