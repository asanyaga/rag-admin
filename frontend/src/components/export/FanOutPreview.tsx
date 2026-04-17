// frontend/src/components/export/FanOutPreview.tsx
import type { ColumnDefinition } from '@/types/dataStore'

interface FanOutPreviewProps {
  rows: Record<string, unknown>[]
  columns: ColumnDefinition[]
}

export function FanOutPreview({ rows, columns }: FanOutPreviewProps) {
  if (rows.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-8 text-center border rounded-lg">
        <p className="text-muted-foreground text-sm">No rows to preview. Check your source data and mapping.</p>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      <p className="text-sm text-muted-foreground">
        {rows.length} row{rows.length !== 1 ? 's' : ''} will be exported
      </p>
      <div className="border rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-muted/50">
              <tr>
                <th className="text-left py-2 px-3 font-medium text-xs text-muted-foreground w-10">#</th>
                {columns.map((col) => (
                  <th key={col.name} className="text-left py-2 px-3 font-medium text-xs">
                    {col.name}
                    <span className="text-muted-foreground ml-1">({col.type})</span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y">
              {rows.map((row, i) => (
                <tr key={i} className="hover:bg-primary/5 transition-colors">
                  <td className="py-2 px-3 text-xs text-muted-foreground">{i + 1}</td>
                  {columns.map((col) => (
                    <td key={col.name} className="py-2 px-3 text-sm">
                      {row[col.name] != null ? (
                        String(row[col.name])
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
