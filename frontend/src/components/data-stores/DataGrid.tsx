// frontend/src/components/data-stores/DataGrid.tsx
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Checkbox } from '@/components/ui/checkbox'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { MoreHorizontal, Check, X } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import type { ColumnDefinition, DataStoreRow } from '@/types/dataStore'

interface DataGridProps {
  columns: ColumnDefinition[]
  rows: DataStoreRow[]
  total: number
  page: number
  pageSize: number
  onPageChange: (page: number) => void
  onUpdateRow: (rowId: string, data: Record<string, unknown>) => Promise<void>
  onDeleteRow: (rowId: string) => Promise<void>
}

export function DataGrid({
  columns,
  rows,
  total,
  page,
  pageSize,
  onPageChange,
  onUpdateRow,
  onDeleteRow,
}: DataGridProps) {
  const [editingRowId, setEditingRowId] = useState<string | null>(null)
  const [editData, setEditData] = useState<Record<string, unknown>>({})

  const startEdit = (row: DataStoreRow) => {
    setEditingRowId(row.id)
    setEditData({ ...row.data })
  }

  const cancelEdit = () => {
    setEditingRowId(null)
    setEditData({})
  }

  const saveEdit = async () => {
    if (!editingRowId) return
    await onUpdateRow(editingRowId, editData)
    setEditingRowId(null)
    setEditData({})
  }

  const totalPages = Math.ceil(total / pageSize)

  const renderCellInput = (col: ColumnDefinition, value: unknown) => {
    if (col.type === 'boolean') {
      return (
        <Checkbox
          checked={!!value}
          onCheckedChange={(v) =>
            setEditData((prev) => ({ ...prev, [col.name]: !!v }))
          }
        />
      )
    }
    return (
      <Input
        value={value != null ? String(value) : ''}
        onChange={(e) =>
          setEditData((prev) => ({ ...prev, [col.name]: e.target.value }))
        }
        type={col.type === 'integer' || col.type === 'numeric' ? 'number' : 'text'}
        className="h-8 text-sm"
      />
    )
  }

  const renderCellValue = (col: ColumnDefinition, value: unknown) => {
    if (value == null) return <span className="text-muted-foreground">—</span>
    if (col.type === 'boolean') return value ? 'Yes' : 'No'
    return String(value)
  }

  if (rows.length === 0 && total === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center border rounded-lg">
        <p className="text-muted-foreground">No data yet. Add rows manually or import a CSV.</p>
      </div>
    )
  }

  return (
    <div>
      <div className="border rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-muted/50">
              <tr>
                {columns.map((col) => (
                  <th key={col.name} className="text-left py-3 px-4 font-medium text-sm">
                    {col.name}
                    <span className="text-xs text-muted-foreground ml-1">({col.type})</span>
                  </th>
                ))}
                <th className="text-left py-3 px-4 font-medium text-sm">Created</th>
                <th className="text-right py-3 px-4 font-medium text-sm w-20">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {rows.map((row) => (
                <tr key={row.id} className="hover:bg-primary/5 transition-colors">
                  {columns.map((col) => (
                    <td key={col.name} className="py-2 px-4 text-sm">
                      {editingRowId === row.id
                        ? renderCellInput(col, editData[col.name])
                        : renderCellValue(col, row.data[col.name])}
                    </td>
                  ))}
                  <td className="py-2 px-4 text-sm text-muted-foreground">
                    {formatDistanceToNow(new Date(row.createdAt), { addSuffix: true })}
                  </td>
                  <td className="py-2 px-4 text-right">
                    {editingRowId === row.id ? (
                      <div className="flex justify-end gap-1">
                        <Button variant="ghost" size="sm" onClick={saveEdit}>
                          <Check className="h-4 w-4" />
                        </Button>
                        <Button variant="ghost" size="sm" onClick={cancelEdit}>
                          <X className="h-4 w-4" />
                        </Button>
                      </div>
                    ) : (
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="sm">
                            <MoreHorizontal className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem onClick={() => startEdit(row)}>Edit</DropdownMenuItem>
                          <DropdownMenuItem
                            onClick={() => onDeleteRow(row.id)}
                            className="text-red-600"
                          >
                            Delete
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-4">
          <p className="text-sm text-muted-foreground">
            Showing {page * pageSize + 1}–{Math.min((page + 1) * pageSize, total)} of {total}
          </p>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => onPageChange(page - 1)}
              disabled={page === 0}
            >
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => onPageChange(page + 1)}
              disabled={page >= totalPages - 1}
            >
              Next
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
