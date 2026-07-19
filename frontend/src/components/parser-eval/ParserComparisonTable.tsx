import { Fragment, useState } from 'react'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { ScorePill } from '@/components/evaluation/ScorePill'
import { PARSER_REGISTRY } from '@/components/documents/ParseMethodSelector'
import type { ParserEvalResult } from '@/types/parserEval'

interface MetricColumns {
  primary: { key: string; label: string }
  rest: { key: string; label: string }[]
}

interface PerTable {
  expected_index: number | null
  parsed_index: number | null
  page: number | null
  status: string
  teds: number
  teds_struct: number
  cell_content_f1: number
}

const METRIC_COLUMNS: Record<string, MetricColumns> = {
  text: {
    primary: { key: 'similarity', label: 'Similarity' },
    rest: [{ key: 'omission', label: 'Omission' }, { key: 'hallucination', label: 'Hallucination' }],
  },
  table: {
    primary: { key: 'teds', label: 'TEDS' },
    rest: [
      { key: 'teds_struct', label: 'Structure' },
      { key: 'cell_content_f1', label: 'Content' },
      { key: 'table_recall', label: 'Table recall' },
    ],
  },
}

function adapterLabel(adapter: string): string {
  // docling is back in PARSER_REGISTRY, so historical rows resolve normally and
  // no retirement shim is needed.
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

  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const toggle = (key: string) => setExpanded((prev) => {
    const next = new Set(prev)
    if (next.has(key)) next.delete(key)
    else next.add(key)
    return next
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
                {sorted.map((r) => {
                  const perTable = (r.details?.per_table as PerTable[] | undefined) ?? []
                  const canExpand = dimension === 'table' && perTable.length > 0
                  const isOpen = expanded.has(r.variantKey)
                  const colSpan = 2 + cols.rest.length + 2
                  return (
                    <Fragment key={r.variantKey}>
                      <TableRow data-testid="cmp-row">
                        <TableCell>
                          {canExpand && (
                            <button type="button" aria-label="Toggle diagnostics"
                              className="mr-1 text-muted-foreground hover:text-foreground"
                              onClick={() => toggle(r.variantKey)}>{isOpen ? '▾' : '▸'}</button>
                          )}
                          {adapterLabel(r.adapter)}
                        </TableCell>
                        <TableCell><ScorePill score={r.metrics[cols.primary.key] ?? null} /></TableCell>
                        {cols.rest.map((c) => <TableCell key={c.key}>{pct(r.metrics[c.key])}</TableCell>)}
                        <TableCell>{fmtCost(r.cost)}</TableCell>
                        <TableCell>{fmtLatency(r.latencyMs)}</TableCell>
                      </TableRow>
                      {canExpand && isOpen && (
                        <TableRow>
                          <TableCell colSpan={colSpan} className="bg-muted/30">
                            <table className="w-full text-xs">
                              <thead>
                                <tr className="text-muted-foreground">
                                  <th className="py-1 text-left">Table</th>
                                  <th className="text-left">TEDS</th>
                                  <th className="text-left">Structure</th>
                                  <th className="text-left">Content</th>
                                </tr>
                              </thead>
                              <tbody>
                                {perTable.map((t, i) => (
                                  <tr key={i}>
                                    <td className="py-1">Page {t.page ?? '—'} · {t.status}</td>
                                    <td>{pct(t.teds)}</td>
                                    <td>{pct(t.teds_struct)}</td>
                                    <td>{pct(t.cell_content_f1)}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </TableCell>
                        </TableRow>
                      )}
                    </Fragment>
                  )
                })}
              </TableBody>
            </Table>
          </div>
        )
      })}
    </div>
  )
}
