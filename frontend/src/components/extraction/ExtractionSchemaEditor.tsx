import { useState, useEffect } from 'react'
import type { ExtractionSchema, ExtractionSchemaCreate, ExtractionSchemaUpdate } from '@/types/extraction'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
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
  const [schemaText, setSchemaText] = useState('')
  const [extractionTarget, setExtractionTarget] = useState('PER_DOC')
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const isEditing = !!schema

  useEffect(() => {
    if (schema) {
      setName(schema.name)
      setDescription(schema.description || '')
      setSchemaText(JSON.stringify(schema.schemaDefinition, null, 2))
      setExtractionTarget(schema.extractionTarget)
    } else {
      setName('')
      setDescription('')
      setSchemaText('{\n  "type": "object",\n  "properties": {\n    \n  }\n}')
      setExtractionTarget('PER_DOC')
    }
    setError(null)
  }, [schema, open])

  const handleSave = async () => {
    setError(null)

    if (!name.trim()) {
      setError('Name is required')
      return
    }

    let parsedSchema: Record<string, unknown>
    try {
      parsedSchema = JSON.parse(schemaText)
    } catch {
      setError('Invalid JSON schema')
      return
    }

    if (parsedSchema.type !== 'object') {
      setError('Root schema type must be "object"')
      return
    }

    setIsSaving(true)
    try {
      if (isEditing) {
        const update: ExtractionSchemaUpdate = {
          name: name.trim(),
          description: description.trim() || undefined,
          schemaDefinition: parsedSchema,
          extractionTarget,
        }
        await onSave(update)
      } else {
        const create: ExtractionSchemaCreate = {
          name: name.trim(),
          description: description.trim() || undefined,
          schemaDefinition: parsedSchema,
          extractionTarget,
        }
        await onSave(create)
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
            <Label htmlFor="schema-definition">JSON Schema</Label>
            <Textarea
              id="schema-definition"
              value={schemaText}
              onChange={(e) => setSchemaText(e.target.value)}
              className="font-mono text-sm min-h-[200px]"
              placeholder='{"type": "object", "properties": {...}}'
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
          <Button onClick={handleSave} disabled={isSaving}>
            {isSaving ? 'Saving...' : isEditing ? 'Update' : 'Create'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
