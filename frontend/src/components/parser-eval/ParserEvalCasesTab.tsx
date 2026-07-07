import { useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { EvalStatusBadge } from '@/components/evaluation/EvalStatusBadge'
import { useParserEvalCases } from '@/hooks/useParserEval'
import { useSourceDocuments } from '@/hooks/useSourceDocuments'

export function ParserEvalCasesTab({ projectId }: { projectId: string }) {
  const { cases, isLoading } = useParserEvalCases(projectId)
  const { sourceDocuments } = useSourceDocuments()
  const navigate = useNavigate()

  const filenameById = useMemo(() => {
    const map = new Map<string, string>()
    sourceDocuments.forEach((d) => map.set(d.id, d.filename ?? d.id))
    return map
  }, [sourceDocuments])

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button onClick={() => navigate('/evaluation/parser/cases/new')}>New case</Button>
      </div>

      {isLoading ? (
        <p className="text-muted-foreground">Loading…</p>
      ) : cases.length === 0 ? (
        <p className="text-center py-8 text-muted-foreground">No cases yet — author one.</p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Document</TableHead>
              <TableHead>Dimension</TableHead>
              <TableHead>Review</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {cases.map((c) => (
              <TableRow key={c.id} className="cursor-pointer"
                onClick={() => navigate(`/evaluation/parser/cases/${c.id}`)}>
                <TableCell>{filenameById.get(c.sourceDocumentId) ?? c.sourceDocumentId}</TableCell>
                <TableCell>{c.dimension}</TableCell>
                <TableCell><EvalStatusBadge status={c.reviewStatus} /></TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  )
}
