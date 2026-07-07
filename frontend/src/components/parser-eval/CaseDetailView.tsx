import { useNavigate } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { useParserEvalCase } from '@/hooks/useParserEval'
import { EvalStatusBadge } from '@/components/evaluation/EvalStatusBadge'
import { Button } from '@/components/ui/button'
import type { TableGroundTruth } from '@/types/parserEval'

export function CaseDetailView({ projectId, caseId }: { projectId: string | null; caseId: string }) {
  const { caseDetail, isLoading, verify, reject } = useParserEvalCase(projectId, caseId)
  const navigate = useNavigate()

  const back = (
    <button onClick={() => navigate('/evaluation/parser')}
      className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
      <ArrowLeft className="h-4 w-4" /> Back to cases
    </button>
  )

  if (isLoading && !caseDetail) return <p className="text-muted-foreground">Loading…</p>
  if (!caseDetail) return <div className="space-y-4">{back}<p className="text-muted-foreground">Case not found.</p></div>

  const tables = caseDetail.dimension === 'table'
    ? ((caseDetail.expected as unknown as TableGroundTruth).tables ?? [])
    : []

  const handleReject = async () => { await reject(); navigate('/evaluation/parser') }

  return (
    <div className="space-y-6">
      {back}
      <div className="flex items-center gap-3">
        <h1 className="text-2xl font-bold">Ground truth · {caseDetail.dimension}</h1>
        <EvalStatusBadge status={caseDetail.reviewStatus} />
      </div>

      {caseDetail.dimension === 'table' ? (
        tables.length === 0 ? (
          <p className="text-muted-foreground">The parser found no tables in this document.</p>
        ) : (
          <div className="space-y-4">
            {tables.map((t, i) => (
              <div key={i} className="space-y-1">
                <span className="text-xs text-muted-foreground">Page {t.page}</span>
                {/* Parser-generated HTML rendered read-only for review. Follow-up: sanitize (Slice 2). */}
                <div className="rounded-md border p-3 overflow-x-auto [&_table]:border-collapse [&_td]:border [&_th]:border [&_td]:px-2 [&_th]:px-2"
                  dangerouslySetInnerHTML={{ __html: t.html }} />
              </div>
            ))}
          </div>
        )
      ) : (
        <p className="text-muted-foreground">Text ground truth review is unchanged.</p>
      )}

      {caseDetail.reviewStatus === 'draft' && (
        <div className="flex gap-2">
          <Button onClick={() => verify()}>Accept</Button>
          <Button variant="outline" onClick={handleReject}>Reject</Button>
        </div>
      )}
    </div>
  )
}
