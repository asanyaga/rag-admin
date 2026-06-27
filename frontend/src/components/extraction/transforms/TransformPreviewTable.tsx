import { Badge } from '@/components/ui/badge'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'

interface Props {
  rows: Record<string, unknown>[]
  flags: { rowIndex: number; flag: string }[]
}

export function TransformPreviewTable({ rows, flags }: Props) {
  const cols = Array.from(
    new Set(rows.flatMap((r) => Object.keys(r).filter((k) => k !== '_provenance'))),
  )
  const flagsByRow = flags.reduce<Record<number, string[]>>((acc, f) => {
    if (!acc[f.rowIndex]) acc[f.rowIndex] = []
    acc[f.rowIndex].push(f.flag)
    return acc
  }, {})
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Flags</TableHead>
          {cols.map((c) => <TableHead key={c}>{c}</TableHead>)}
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((row, i) => (
          <TableRow key={i}>
            <TableCell className="space-x-1">
              {(flagsByRow[i] ?? []).map((f) => (
                <Badge key={f} variant="outline">{f}</Badge>
              ))}
            </TableCell>
            {cols.map((c) => <TableCell key={c}>{String(row[c] ?? '')}</TableCell>)}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
