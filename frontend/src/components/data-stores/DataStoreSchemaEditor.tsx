// frontend/src/components/data-stores/DataStoreSchemaEditor.tsx
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import { Trash2, Plus } from 'lucide-react'
import type { ColumnDefinition } from '@/types/dataStore'

const COLUMN_TYPES = [
  { value: 'text', label: 'Text' },
  { value: 'integer', label: 'Integer' },
  { value: 'numeric', label: 'Numeric' },
  { value: 'boolean', label: 'Boolean' },
  { value: 'timestamptz', label: 'Timestamp' },
] as const

interface DataStoreSchemaEditorProps {
  columns: ColumnDefinition[]
  onChange: (columns: ColumnDefinition[]) => void
  disabled?: boolean
}

function normalizeColumnName(name: string): string {
  return name
    .toLowerCase()
    .replace(/\s+/g, '_')
    .replace(/[^a-z0-9_]/g, '')
    .replace(/^[^a-z]/, '')
}

export function DataStoreSchemaEditor({ columns, onChange, disabled }: DataStoreSchemaEditorProps) {
  const addColumn = () => {
    onChange([
      ...columns,
      { name: '', type: 'text', nullable: true, description: '' },
    ])
  }

  const removeColumn = (index: number) => {
    onChange(columns.filter((_, i) => i !== index))
  }

  const updateColumn = (index: number, field: keyof ColumnDefinition, value: unknown) => {
    const updated = columns.map((col, i) => {
      if (i !== index) return col
      if (field === 'name') {
        return { ...col, name: normalizeColumnName(value as string) }
      }
      return { ...col, [field]: value }
    })
    onChange(updated)
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <Label>Columns</Label>
        <Button type="button" variant="outline" size="sm" onClick={addColumn} disabled={disabled}>
          <Plus className="h-4 w-4 mr-1" />
          Add Column
        </Button>
      </div>

      {columns.length === 0 && (
        <p className="text-sm text-muted-foreground py-4 text-center">
          No columns defined. Add at least one column.
        </p>
      )}

      {columns.map((col, index) => (
        <div key={index} className="flex items-center gap-2 p-3 border rounded-md bg-muted/30">
          <div className="flex-1">
            <Input
              placeholder="column_name"
              value={col.name}
              onChange={(e) => updateColumn(index, 'name', e.target.value)}
              disabled={disabled}
              className="font-mono text-sm"
            />
          </div>
          <div className="w-36">
            <Select
              value={col.type}
              onValueChange={(v) => updateColumn(index, 'type', v)}
              disabled={disabled}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {COLUMN_TYPES.map((t) => (
                  <SelectItem key={t.value} value={t.value}>
                    {t.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex items-center gap-1">
            <Checkbox
              checked={col.nullable}
              onCheckedChange={(v) => updateColumn(index, 'nullable', !!v)}
              disabled={disabled}
            />
            <span className="text-xs text-muted-foreground">Nullable</span>
          </div>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => removeColumn(index)}
            disabled={disabled}
            className="text-red-600 hover:text-red-700"
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      ))}
    </div>
  )
}
