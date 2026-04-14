// frontend/src/components/data-stores/AddRowDialog.tsx
import { useState } from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'
import type { ColumnDefinition } from '@/types/dataStore'

interface AddRowDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  columns: ColumnDefinition[]
  onAdd: (data: Record<string, unknown>) => Promise<void>
}

export function AddRowDialog({ open, onOpenChange, columns, onAdd }: AddRowDialogProps) {
  const [data, setData] = useState<Record<string, string>>({})
  const [isAdding, setIsAdding] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleAdd = async () => {
    setIsAdding(true)
    setError(null)
    try {
      const coerced: Record<string, unknown> = {}
      for (const col of columns) {
        const raw = data[col.name]
        if (raw === undefined || raw === '') {
          if (!col.nullable) {
            setError(`${col.name} is required`)
            setIsAdding(false)
            return
          }
          continue
        }
        if (col.type === 'integer') coerced[col.name] = parseInt(raw, 10)
        else if (col.type === 'numeric') coerced[col.name] = parseFloat(raw)
        else if (col.type === 'boolean') coerced[col.name] = raw === 'true'
        else coerced[col.name] = raw
      }

      await onAdd(coerced)
      onOpenChange(false)
      setData({})
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add row')
    } finally {
      setIsAdding(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add Row</DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {columns.map((col) => (
            <div key={col.name} className="space-y-2">
              <Label>
                {col.name}
                {!col.nullable && <span className="text-red-500 ml-1">*</span>}
                <span className="text-xs text-muted-foreground ml-2">({col.type})</span>
              </Label>
              {col.type === 'boolean' ? (
                <div className="flex items-center gap-2">
                  <Checkbox
                    checked={data[col.name] === 'true'}
                    onCheckedChange={(v) =>
                      setData((prev) => ({ ...prev, [col.name]: v ? 'true' : 'false' }))
                    }
                    disabled={isAdding}
                  />
                  <span className="text-sm">{data[col.name] === 'true' ? 'Yes' : 'No'}</span>
                </div>
              ) : (
                <Input
                  value={data[col.name] || ''}
                  onChange={(e) =>
                    setData((prev) => ({ ...prev, [col.name]: e.target.value }))
                  }
                  type={col.type === 'integer' || col.type === 'numeric' ? 'number' : 'text'}
                  placeholder={col.nullable ? 'Optional' : 'Required'}
                  disabled={isAdding}
                />
              )}
            </div>
          ))}

          {error && <div className="text-sm text-red-600">{error}</div>}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isAdding}>
            Cancel
          </Button>
          <Button onClick={handleAdd} disabled={isAdding}>
            {isAdding ? 'Adding...' : 'Add Row'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
