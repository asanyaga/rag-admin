import { useState, useEffect, useRef } from 'react'
import type { ExtractionSchema, ExtractionSchemaCreate, ExtractionSchemaUpdate } from '@/types/extraction'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { SchemaBuilder } from './SchemaBuilder'

const EMPTY_SCHEMA: Record<string, unknown> = { type: 'object', properties: {} }

interface ExtractionSchemaEditorProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  schema?: ExtractionSchema | null
  onSave: (data: ExtractionSchemaCreate | ExtractionSchemaUpdate) => Promise<void>
}

export function ExtractionSchemaEditor({
  open,
  onOpenChange,
  schema,
  onSave,
}: ExtractionSchemaEditorProps) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [extractionTarget, setExtractionTarget] = useState('PER_DOC')
  const [isSchemaValid, setIsSchemaValid] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [schemaBuilderKey, setSchemaBuilderKey] = useState(0)
  const schemaDefinitionRef = useRef<Record<string, unknown>>(EMPTY_SCHEMA)

  const isEditing = !!schema

  useEffect(() => {
    if (schema) {
      setName(schema.name)
      setDescription(schema.description || '')
      schemaDefinitionRef.current = schema.schemaDefinition
      setExtractionTarget(schema.extractionTarget)
    } else {
      setName('')
      setDescription('')
      schemaDefinitionRef.current = EMPTY_SCHEMA
      setExtractionTarget('PER_DOC')
    }
    setIsSchemaValid(true)
    setError(null)
    setSchemaBuilderKey(k => k + 1)
  }, [schema, open])

  const handleSave = async () => {
    setError(null)

    if (!name.trim()) {
      setError('Name is required')
      return
    }

    const schemaDefinition = schemaDefinitionRef.current
    if (schemaDefinition.type !== 'object') {
      setError('Root schema type must be "object"')
      return
    }

    setIsSaving(true)
    try {
      if (isEditing) {
        await onSave({
          name: name.trim(),
          description: description.trim() || undefined,
          schemaDefinition,
          extractionTarget,
        } as ExtractionSchemaUpdate)
      } else {
        await onSave({
          name: name.trim(),
          description: description.trim() || undefined,
          schemaDefinition,
          extractionTarget,
        } as ExtractionSchemaCreate)
      }
      onOpenChange(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save schema')
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{isEditing ? 'Edit Schema' : 'Create Schema'}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label htmlFor="schema-name">Name</Label>
            <Input
              id="schema-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Invoice Fields"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="schema-description">Description</Label>
            <Input
              id="schema-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Optional description"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="extraction-target">Extraction Target</Label>
            <Select value={extractionTarget} onValueChange={setExtractionTarget}>
              <SelectTrigger id="extraction-target">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="PER_DOC">Per Document</SelectItem>
                <SelectItem value="PER_PAGE">Per Page</SelectItem>
                <SelectItem value="PER_TABLE_ROW">Per Table Row</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label>Schema Definition</Label>
            <SchemaBuilder
              key={schemaBuilderKey}
              value={schemaDefinitionRef.current}
              onChange={(v) => { schemaDefinitionRef.current = v }}
              onValidChange={setIsSchemaValid}
            />
          </div>

          {error && (
            <p className="text-sm text-destructive">{error}</p>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isSaving}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={isSaving || !isSchemaValid}>
            {isSaving ? 'Saving...' : isEditing ? 'Update' : 'Create'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
