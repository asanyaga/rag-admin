// frontend/src/components/export/FieldMappingEditor.tsx
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Plus, Trash2, Wand2 } from 'lucide-react'
import type { ColumnDefinition } from '@/types/dataStore'

interface MappingEntry {
  sourcePath: string
  destinationColumn: string
}

interface FieldMappingEditorProps {
  sourceJson: string
  destinationColumns: ColumnDefinition[]
  mapping: MappingEntry[]
  onChange: (mapping: MappingEntry[]) => void
}

function isArrayPath(sourcePath: string, parsedSource: Record<string, unknown> | null): boolean {
  if (!sourcePath.includes('.') || !parsedSource) return false
  const arrayName = sourcePath.split('.')[0]
  return Array.isArray(parsedSource[arrayName])
}

function getValidationErrors(
  mapping: MappingEntry[],
  destinationColumns: ColumnDefinition[]
): string[] {
  const errors: string[] = []

  if (mapping.length === 0) {
    errors.push('At least one mapping is required')
    return errors
  }

  const destCounts: Record<string, number> = {}
  for (const entry of mapping) {
    if (entry.sourcePath.split('.').length > 2) {
      errors.push(`Nested array paths not supported: "${entry.sourcePath}"`)
    }
    if (entry.destinationColumn) {
      destCounts[entry.destinationColumn] = (destCounts[entry.destinationColumn] || 0) + 1
    }
  }

  for (const [col, count] of Object.entries(destCounts)) {
    if (count > 1) errors.push(`Duplicate destination: "${col}"`)
  }

  const mappedDests = new Set(mapping.map((m) => m.destinationColumn).filter(Boolean))
  for (const col of destinationColumns) {
    if (!col.nullable && !mappedDests.has(col.name)) {
      errors.push(`Required column "${col.name}" has no mapping`)
    }
  }

  return errors
}

export function FieldMappingEditor({
  sourceJson,
  destinationColumns,
  mapping,
  onChange,
}: FieldMappingEditorProps) {
  let parsedSource: Record<string, unknown> | null = null
  try {
    parsedSource = JSON.parse(sourceJson)
  } catch {
    // invalid JSON — that's fine, we just won't show array indicators
  }

  const errors = getValidationErrors(mapping, destinationColumns)

  const addRow = () => {
    onChange([...mapping, { sourcePath: '', destinationColumn: '' }])
  }

  const removeRow = (index: number) => {
    onChange(mapping.filter((_, i) => i !== index))
  }

  const updateRow = (index: number, field: keyof MappingEntry, value: string) => {
    const updated = mapping.map((entry, i) =>
      i === index ? { ...entry, [field]: value } : entry
    )
    onChange(updated)
  }

  const autoDetect = () => {
    if (!parsedSource) return
    const colNames = new Set(destinationColumns.map((c) => c.name))
    const newMapping: MappingEntry[] = []

    // Match top-level scalar fields
    for (const key of Object.keys(parsedSource)) {
      if (colNames.has(key) && !Array.isArray(parsedSource[key]) && typeof parsedSource[key] !== 'object') {
        newMapping.push({ sourcePath: key, destinationColumn: key })
      }
    }

    // Match array fields
    for (const key of Object.keys(parsedSource)) {
      if (Array.isArray(parsedSource[key]) && (parsedSource[key] as unknown[]).length > 0) {
        const firstElement = (parsedSource[key] as Record<string, unknown>[])[0]
        if (typeof firstElement === 'object' && firstElement !== null) {
          for (const subKey of Object.keys(firstElement)) {
            // Try exact match: array.field -> field
            if (colNames.has(subKey)) {
              newMapping.push({ sourcePath: `${key}.${subKey}`, destinationColumn: subKey })
            }
            // Try prefixed match: array.field -> arrayfield or array_field
            for (const colName of colNames) {
              if (colName === `${key}_${subKey}` || colName === `${key}${subKey}`) {
                newMapping.push({ sourcePath: `${key}.${subKey}`, destinationColumn: colName })
              }
            }
          }
        }
      }
    }

    // Deduplicate by destination
    const seen = new Set<string>()
    const deduped = newMapping.filter((m) => {
      if (seen.has(m.destinationColumn)) return false
      seen.add(m.destinationColumn)
      return true
    })

    onChange(deduped)
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium">Field Mapping</h3>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={autoDetect} disabled={!parsedSource}>
            <Wand2 className="h-4 w-4 mr-1" /> Auto-detect
          </Button>
          <Button variant="outline" size="sm" onClick={addRow}>
            <Plus className="h-4 w-4 mr-1" /> Add Mapping
          </Button>
        </div>
      </div>

      {mapping.length > 0 && (
        <div className="space-y-2">
          <div className="grid grid-cols-[1fr_auto_1fr_auto] gap-2 items-center text-xs text-muted-foreground font-medium px-1">
            <span>Source Path</span>
            <span />
            <span>Destination Column</span>
            <span />
          </div>
          {mapping.map((entry, index) => (
            <div key={index} className="grid grid-cols-[1fr_auto_1fr_auto] gap-2 items-center">
              <div className="relative">
                <Input
                  value={entry.sourcePath}
                  onChange={(e) => updateRow(index, 'sourcePath', e.target.value)}
                  placeholder="e.g. items.description"
                  className="text-sm"
                />
                {isArrayPath(entry.sourcePath, parsedSource) && (
                  <Badge
                    variant="secondary"
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-[10px] px-1 py-0"
                  >
                    array
                  </Badge>
                )}
              </div>
              <span className="text-muted-foreground text-sm">→</span>
              <Select
                value={entry.destinationColumn}
                onValueChange={(v) => updateRow(index, 'destinationColumn', v)}
              >
                <SelectTrigger className="text-sm">
                  <SelectValue placeholder="Select column" />
                </SelectTrigger>
                <SelectContent>
                  {destinationColumns.map((col) => (
                    <SelectItem key={col.name} value={col.name}>
                      {col.name}
                      <span className="text-muted-foreground ml-1">({col.type})</span>
                      {!col.nullable && <span className="text-red-500 ml-1">*</span>}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button variant="ghost" size="sm" onClick={() => removeRow(index)}>
                <Trash2 className="h-4 w-4 text-muted-foreground" />
              </Button>
            </div>
          ))}
        </div>
      )}

      {errors.length > 0 && (
        <Alert variant="destructive">
          <AlertDescription>
            <ul className="list-disc list-inside text-sm">
              {errors.map((err, i) => (
                <li key={i}>{err}</li>
              ))}
            </ul>
          </AlertDescription>
        </Alert>
      )}
    </div>
  )
}

export type { MappingEntry }
