import { useMemo } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { useProject } from '@/contexts/ProjectContext'
import { EvalStatusBadge } from '@/components/evaluation/EvalStatusBadge'
import { ParserComparisonTable } from '@/components/parser-eval/ParserComparisonTable'
import { useParserEvalRunDetail, useParserEvalCases } from '@/hooks/useParserEval'
import { useSourceDocuments } from '@/hooks/useSourceDocuments'

export default function ParserEvalRunDetailPage(): JSX.Element {
  const { runId } = useParams<{ runId: string }>()
  const { currentProject } = useProject()
  const projectId = currentProject?.id ?? null
  const { run, results, isLoading } = useParserEvalRunDetail(projectId, runId ?? null)
  const { cases } = useParserEvalCases(projectId)
  const { sourceDocuments } = useSourceDocuments()

  const caseLabels = useMemo(() => {
    const fname = new Map(sourceDocuments.map((d) => [d.id, d.filename ?? d.id]))
    const labels: Record<string, string> = {}
    cases.forEach((c) => {
      labels[c.id] = fname.get(c.sourceDocumentId) ?? c.sourceDocumentId
    })
    return labels
  }, [cases, sourceDocuments])

  const backToRuns = (
    <Link
      to="/evaluation/parser?tab=runs"
      className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
    >
      <ArrowLeft className="h-4 w-4" /> Back to runs
    </Link>
  )

  if (isLoading && !run) return <p className="text-muted-foreground">Loading…</p>
  if (!run) return <div className="space-y-4">{backToRuns}<p className="text-muted-foreground">Run not found.</p></div>

  return (
    <div className="space-y-6">
      {backToRuns}
      <div className="flex items-center gap-3">
        <h1 className="text-2xl font-bold">{run.name}</h1>
        <EvalStatusBadge status={run.status} />
      </div>
      <p className="text-sm text-muted-foreground">
        {run.variants.map((v) => v.adapter).join(', ')}
      </p>

      {run.status === 'failed' && (
        <p className="text-sm text-destructive">{run.errorMessage ?? 'Run failed.'}</p>
      )}
      {(run.status === 'pending' || run.status === 'running') && (
        <p className="text-muted-foreground">Running… results will appear when complete.</p>
      )}
      {run.status === 'completed' && (
        <ParserComparisonTable results={results} caseLabels={caseLabels} />
      )}
    </div>
  )
}
