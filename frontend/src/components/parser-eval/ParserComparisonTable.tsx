import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { ScorePill } from '@/components/evaluation/ScorePill'
import { PARSER_REGISTRY } from '@/components/documents/ParseMethodSelector'
import type { ParserEvalResult } from '@/types/parserEval'

function adapterLabel(adapter: string): string {
  return PARSER_REGISTRY[adapter]?.label ?? adapter
}
function fmtCost(cost: Record<string, number> | null): string {
  const usd = cost?.usd ?? 0
  return usd === 0 ? '$0' : `$${usd.toFixed(3)}`
}
function fmtLatency(ms: number | null): string {
  if (ms == null) return '—'
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${ms}ms`
}
function pct(v: number | undefined): string {
  return v == null ? '—' : `${(v * 100).toFixed(0)}%`
}

interface Props {
  results: ParserEvalResult[]
  caseLabels: Record<string, string> // evalCaseId -> filename
}

export function ParserComparisonTable({ results, caseLabels }: Props) {
  const byCase = new Map<string, ParserEvalResult[]>()
  results.forEach((r) => {
    const arr = byCase.get(r.evalCaseId) ?? []
    arr.push(r)
    byCase.set(r.evalCaseId, arr)
  })

  return (
    <div className="space-y-6">
      {[...byCase.entries()].map(([caseId, rows]) => {
        const sorted = [...rows].sort(
          (a, b) => (b.metrics.similarity ?? 0) - (a.metrics.similarity ?? 0)
        )
        return (
          <div key={caseId} className="space-y-2">
            <h3 className="text-sm font-semibold">{caseLabels[caseId] ?? caseId} · text</h3>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Adapter</TableHead>
                  <TableHead>Similarity</TableHead>
                  <TableHead>Omission</TableHead>
                  <TableHead>Hallucination</TableHead>
                  <TableHead>Cost</TableHead>
                  <TableHead>Latency</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sorted.map((r) => (
                  <TableRow key={r.variantKey} data-testid="cmp-row">
                    <TableCell>{adapterLabel(r.adapter)}</TableCell>
                    <TableCell>
                      <ScorePill score={r.metrics.similarity ?? null} />
                    </TableCell>
                    <TableCell>{pct(r.metrics.omission)}</TableCell>
                    <TableCell>{pct(r.metrics.hallucination)}</TableCell>
                    <TableCell>{fmtCost(r.cost)}</TableCell>
                    <TableCell>{fmtLatency(r.latencyMs)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )
      })}
    </div>
  )
}
