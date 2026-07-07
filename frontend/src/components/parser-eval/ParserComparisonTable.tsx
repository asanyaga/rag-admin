import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { ScorePill } from '@/components/evaluation/ScorePill'
import { PARSER_REGISTRY } from '@/components/documents/ParseMethodSelector'
import type { ParserEvalResult } from '@/types/parserEval'

interface MetricColumns {
  primary: { key: string; label: string }
  rest: { key: string; label: string }[]
}

const METRIC_COLUMNS: Record<string, MetricColumns> = {
  text: {
    primary: { key: 'similarity', label: 'Similarity' },
    rest: [{ key: 'omission', label: 'Omission' }, { key: 'hallucination', label: 'Hallucination' }],
  },
  table: {
    primary: { key: 'teds', label: 'TEDS' },
    rest: [{ key: 'table_recall', label: 'Table recall' }],
  },
}

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
  caseLabels: Record<string, string>        // evalCaseId -> filename
  caseDimensions?: Record<string, string>   // evalCaseId -> dimension (defaults to text)
}

export function ParserComparisonTable({ results, caseLabels, caseDimensions }: Props) {
  const byCase = new Map<string, ParserEvalResult[]>()
  results.forEach((r) => {
    const arr = byCase.get(r.evalCaseId) ?? []
    arr.push(r)
    byCase.set(r.evalCaseId, arr)
  })

  return (
    <div className="space-y-6">
      {[...byCase.entries()].map(([caseId, rows]) => {
        const dimension = caseDimensions?.[caseId] ?? 'text'
        const cols = METRIC_COLUMNS[dimension] ?? METRIC_COLUMNS.text
        const sorted = [...rows].sort(
          (a, b) => (b.metrics[cols.primary.key] ?? 0) - (a.metrics[cols.primary.key] ?? 0),
        )
        return (
          <div key={caseId} className="space-y-2">
            <h3 className="text-sm font-semibold">{caseLabels[caseId] ?? caseId} · {dimension}</h3>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Adapter</TableHead>
                  <TableHead>{cols.primary.label}</TableHead>
                  {cols.rest.map((c) => <TableHead key={c.key}>{c.label}</TableHead>)}
                  <TableHead>Cost</TableHead>
                  <TableHead>Latency</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sorted.map((r) => (
                  <TableRow key={r.variantKey} data-testid="cmp-row">
                    <TableCell>{adapterLabel(r.adapter)}</TableCell>
                    <TableCell><ScorePill score={r.metrics[cols.primary.key] ?? null} /></TableCell>
                    {cols.rest.map((c) => <TableCell key={c.key}>{pct(r.metrics[c.key])}</TableCell>)}
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
