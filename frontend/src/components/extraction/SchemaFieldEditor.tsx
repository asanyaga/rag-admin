import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Plus, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { SchemaField, FieldType } from '@/lib/schemaBuilder'
import { newBlankField, getDuplicateKeys } from '@/lib/schemaBuilder'

interface SchemaFieldEditorProps {
  field: SchemaField
  onChange: (updated: SchemaField) => void
  onDelete: () => void
  depth?: number
  duplicateKeys?: Set<string>
  hideDelete?: boolean
}

export function SchemaFieldEditor({
  field,
  onChange,
  onDelete,
  depth = 0,
  duplicateKeys = new Set(),
  hideDelete = false,
}: SchemaFieldEditorProps) {
  const isDuplicate = field.key !== '' && duplicateKeys.has(field.key)

  const update = (patch: Partial<SchemaField>) => onChange({ ...field, ...patch })

  const handleTypeChange = (type: FieldType) => {
    const patch: Partial<SchemaField> = { type }
    if (type !== 'string' && type !== 'number' && type !== 'integer') patch.enumValues = undefined
    if (type !== 'object') patch.properties = undefined
    if (type !== 'array') patch.items = undefined
    if (type === 'object') patch.properties = field.properties ?? []
    if (type === 'array') patch.items = field.items ?? newBlankField()
    update(patch)
  }

  const addEnumValue = () => update({ enumValues: [...(field.enumValues ?? []), ''] })
  const updateEnumValue = (i: number, v: string) => {
    const enumValues = [...(field.enumValues ?? [])]
    enumValues[i] = v
    update({ enumValues })
  }
  const deleteEnumValue = (i: number) =>
    update({ enumValues: (field.enumValues ?? []).filter((_, idx) => idx !== i) })

  const addNestedField = () =>
    update({ properties: [...(field.properties ?? []), newBlankField()] })
  const updateNestedField = (i: number, updated: SchemaField) => {
    const properties = [...(field.properties ?? [])]
    properties[i] = updated
    update({ properties })
  }
  const deleteNestedField = (i: number) =>
    update({ properties: (field.properties ?? []).filter((_, idx) => idx !== i) })

  const nestedDuplicateKeys = getDuplicateKeys(field.properties ?? [])

  return (
    <div className={cn('space-y-2', depth > 0 && 'ml-4 pl-3 border-l border-border')}>
      <div className="flex items-start gap-2">
        <div className="flex-1 grid grid-cols-[1fr_auto_2fr] gap-2 items-center min-w-0">
          <Input
            value={field.key}
            onChange={(e) => update({ key: e.target.value })}
            placeholder="field_name"
            className={cn('font-mono text-sm h-8', isDuplicate && 'border-destructive')}
          />
          <Select value={field.type} onValueChange={handleTypeChange}>
            <SelectTrigger className="w-28 h-8 text-sm">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="string">string</SelectItem>
              <SelectItem value="number">number</SelectItem>
              <SelectItem value="integer">integer</SelectItem>
              <SelectItem value="boolean">boolean</SelectItem>
              <SelectItem value="object">object</SelectItem>
              <SelectItem value="array">array</SelectItem>
            </SelectContent>
          </Select>
          <Input
            value={field.description}
            onChange={(e) => update({ description: e.target.value })}
            placeholder="Description (guides extraction)"
            className="text-sm h-8"
          />
        </div>
        <div className="flex items-center gap-2 shrink-0 pt-0.5">
          <label className="flex items-center gap-1 text-xs text-muted-foreground cursor-pointer select-none">
            <Checkbox
              checked={field.required}
              onCheckedChange={(v) => update({ required: !!v })}
              className="h-3.5 w-3.5"
            />
            Req
          </label>
          <label className="flex items-center gap-1 text-xs text-muted-foreground cursor-pointer select-none">
            <Checkbox
              checked={field.nullable}
              onCheckedChange={(v) => update({ nullable: !!v })}
              className="h-3.5 w-3.5"
            />
            Null
          </label>
          {!hideDelete && (
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 text-muted-foreground hover:text-destructive"
              onClick={onDelete}
              type="button"
            >
              <X className="h-3.5 w-3.5" />
            </Button>
          )}
        </div>
      </div>

      {isDuplicate && (
        <p className="text-xs text-destructive">Duplicate field name</p>
      )}

      {(field.type === 'string' || field.type === 'number' || field.type === 'integer') && (
        <div className="ml-4 space-y-1.5">
          <p className="text-xs text-muted-foreground font-medium">Enum values</p>
          {(field.enumValues ?? []).map((val, i) => (
            <div key={i} className="flex items-center gap-2">
              <Input
                value={val}
                onChange={(e) => updateEnumValue(i, e.target.value)}
                placeholder="value"
                className="text-sm h-7 flex-1"
              />
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                onClick={() => deleteEnumValue(i)}
                type="button"
              >
                <X className="h-3 w-3" />
              </Button>
            </div>
          ))}
          <Button
            variant="ghost"
            size="sm"
            className="h-6 text-xs px-2"
            onClick={addEnumValue}
            type="button"
          >
            <Plus className="h-3 w-3 mr-1" />
            Add enum value
          </Button>
        </div>
      )}

      {field.type === 'object' && (
        <div className="space-y-2">
          {(field.properties ?? []).map((nested, i) => (
            <SchemaFieldEditor
              key={i}
              field={nested}
              onChange={(updated) => updateNestedField(i, updated)}
              onDelete={() => deleteNestedField(i)}
              depth={depth + 1}
              duplicateKeys={nestedDuplicateKeys}
            />
          ))}
          <div className={cn(depth > 0 && 'ml-4')}>
            <Button
              variant="ghost"
              size="sm"
              className="h-6 text-xs px-2"
              onClick={addNestedField}
              type="button"
            >
              <Plus className="h-3 w-3 mr-1" />
              Add field
            </Button>
          </div>
        </div>
      )}

      {field.type === 'array' && field.items && (
        <div className="ml-4 space-y-1.5">
          <p className="text-xs text-muted-foreground font-medium">Item type</p>
          <SchemaFieldEditor
            field={field.items}
            onChange={(updated) => update({ items: updated })}
            onDelete={() => {}}
            depth={depth + 1}
            hideDelete
          />
        </div>
      )}
    </div>
  )
}
