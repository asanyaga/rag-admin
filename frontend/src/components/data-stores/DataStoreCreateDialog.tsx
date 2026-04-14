// frontend/src/components/data-stores/DataStoreCreateDialog.tsx
import { useState } from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { DataStoreSchemaEditor } from './DataStoreSchemaEditor'
import type { DataStoreCreate, ColumnDefinition } from '@/types/dataStore'

interface DataStoreCreateDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onCreate: (data: DataStoreCreate) => Promise<void>
  extractionSchemas?: Array<{ id: string; name: string; schemaDefinition: Record<string, unknown> }>
}

export function DataStoreCreateDialog({ open, onOpenChange, onCreate, extractionSchemas }: DataStoreCreateDialogProps) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [columns, setColumns] = useState<ColumnDefinition[]>([
    { name: '', type: 'text', nullable: false, description: '' },
  ])
  const [isCreating, setIsCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSeedFromSchema = (schema: { schemaDefinition: Record<string, unknown> }) => {
    // Convert extraction schema properties to column definitions
    const props = (schema.schemaDefinition as { properties?: Record<string, { type?: string; description?: string }> }).properties || {}
    const required = (schema.schemaDefinition as { required?: string[] }).required || []
    const seeded: ColumnDefinition[] = Object.entries(props).map(([key, val]) => {
      const colName = key.toLowerCase().replace(/\s+/g, '_').replace(/[^a-z0-9_]/g, '')
      let colType: ColumnDefinition['type'] = 'text'
      if (val.type === 'integer' || val.type === 'number') colType = val.type === 'integer' ? 'integer' : 'numeric'
      else if (val.type === 'boolean') colType = 'boolean'
      return {
        name: colName,
        type: colType,
        nullable: !required.includes(key),
        description: val.description || '',
      }
    })
    setColumns(seeded)
  }

  const handleCreate = async () => {
    if (!name.trim()) {
      setError('Name is required')
      return
    }
    const validColumns = columns.filter((c) => c.name.trim() !== '')
    if (validColumns.length === 0) {
      setError('At least one column is required')
      return
    }

    setIsCreating(true)
    setError(null)
    try {
      await onCreate({
        name: name.trim(),
        description: description.trim() || undefined,
        schema_definition: validColumns,
      })
      onOpenChange(false)
      setName('')
      setDescription('')
      setColumns([{ name: '', type: 'text', nullable: false, description: '' }])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create data store')
    } finally {
      setIsCreating(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Create Data Store</DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label htmlFor="store-name">Name *</Label>
            <Input
              id="store-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Budget Items"
              disabled={isCreating}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="store-desc">Description</Label>
            <Textarea
              id="store-desc"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Optional description"
              disabled={isCreating}
              rows={2}
            />
          </div>

          {extractionSchemas && extractionSchemas.length > 0 && (
            <div className="space-y-2">
              <Label>Seed from Extraction Schema</Label>
              <Select onValueChange={(id) => {
                const schema = extractionSchemas.find((s) => s.id === id)
                if (schema) handleSeedFromSchema(schema)
              }}>
                <SelectTrigger>
                  <SelectValue placeholder="Optional — pre-fill columns from a schema" />
                </SelectTrigger>
                <SelectContent>
                  {extractionSchemas.map((s) => (
                    <SelectItem key={s.id} value={s.id}>{s.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          <DataStoreSchemaEditor
            columns={columns}
            onChange={setColumns}
            disabled={isCreating}
          />

          {error && <div className="text-sm text-red-600">{error}</div>}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isCreating}>
            Cancel
          </Button>
          <Button onClick={handleCreate} disabled={isCreating}>
            {isCreating ? 'Creating...' : 'Create Data Store'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
