import { useNavigate } from 'react-router-dom'
import { cn } from '@/lib/utils'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { ScorePill } from './ScorePill'
import type { EvalRunResult } from '@/types/eval-run'

interface RunResultsListProps {
  results: EvalRunResult[]
  isAnswerMode?: boolean
  runId: string
}

function metricColor(val: number): string {
  if (val >= 0.8) return 'text-green-600'
  if (val >= 0.5) return 'text-amber-600'
  return 'text-red-600'
}

export function RunResultsList({ results, isAnswerMode, runId }: RunResultsListProps) {
  const navigate = useNavigate()

  if (results.length === 0) {
    return (
      <p className="text-muted-foreground text-center py-8">
        No results available.
      </p>
    )
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Question</TableHead>
          <TableHead className="text-right w-20">Precision</TableHead>
          <TableHead className="text-right w-16">Hit?</TableHead>
          {isAnswerMode && (
            <>
              <TableHead className="text-right w-24">Faithfulness</TableHead>
              <TableHead className="text-right w-24">Relevance</TableHead>
            </>
          )}
        </TableRow>
      </TableHeader>
      <TableBody>
        {results.map((r) => (
          <TableRow
            key={r.id}
            className="cursor-pointer"
            onClick={() => navigate(`/evaluation/runs/${runId}/results/${r.id}`)}
          >
            <TableCell className="max-w-md">
              <p className="text-sm truncate">{r.queryText}</p>
              {(r.judgeError || r.generationError) && (
                <p className="text-xs text-red-500 mt-0.5 truncate">
                  {r.generationError ? 'Gen error' : 'Judge error'}
                </p>
              )}
            </TableCell>
            <TableCell className="text-right">
              <span className={cn('text-sm font-mono', metricColor(r.precision))}>
                {(r.precision * 100).toFixed(0)}%
              </span>
            </TableCell>
            <TableCell className="text-right">
              <span
                className={cn(
                  'text-sm font-mono font-bold',
                  r.recall >= 0.5 ? 'text-green-600' : 'text-red-600'
                )}
              >
                {r.recall >= 0.5 ? 'Yes' : 'No'}
              </span>
            </TableCell>
            {isAnswerMode && (
              <>
                <TableCell className="text-right">
                  <ScorePill score={r.faithfulnessScore} />
                </TableCell>
                <TableCell className="text-right">
                  <ScorePill score={r.relevanceScore} />
                </TableCell>
              </>
            )}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
