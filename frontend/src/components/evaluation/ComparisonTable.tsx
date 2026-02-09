import { cn } from '@/lib/utils'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import type { QueryComparisonItem } from '@/types/eval-run'

interface ComparisonTableProps {
  items: QueryComparisonItem[]
}

function deltaColor(delta: number): string {
  if (delta > 0.001) return 'text-green-600'
  if (delta < -0.001) return 'text-red-600'
  return 'text-muted-foreground'
}

function formatDelta(delta: number): string {
  const sign = delta > 0 ? '+' : ''
  return sign + (delta * 100).toFixed(1) + '%'
}

export function ComparisonTable({ items }: ComparisonTableProps) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Query</TableHead>
          <TableHead className="text-right">Baseline F1</TableHead>
          <TableHead className="text-right">Challenger F1</TableHead>
          <TableHead className="text-right">Delta</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {items.map((item) => (
          <TableRow key={item.queryId}>
            <TableCell className="max-w-md truncate text-sm">
              {item.queryText}
            </TableCell>
            <TableCell className="text-right font-mono text-sm">
              {(item.baseline.f1 * 100).toFixed(1)}%
            </TableCell>
            <TableCell className="text-right font-mono text-sm">
              {(item.challenger.f1 * 100).toFixed(1)}%
            </TableCell>
            <TableCell
              className={cn(
                'text-right font-mono text-sm font-bold',
                deltaColor(item.deltaF1)
              )}
            >
              {formatDelta(item.deltaF1)}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
