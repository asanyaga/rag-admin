// frontend/src/components/data-stores/DataStoreEditDialog.tsx
import { useState, useEffect } from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { DataStoreSchemaEditor } from './DataStoreSchemaEditor'
import type { DataStore, DataStoreUpdate, ColumnDefinition } from '@/types/dataStore'

interface DataStoreEditDialogProps {
  store: DataStore | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onSave: (storeId: string, data: DataStoreUpdate) => Promise<void>
}

export function DataStoreEditDialog({ store, open, onOpenChange, onSave }: DataStoreEditDialogProps) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [columns, setColumns] = useState<ColumnDefinition[]>([])
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (store) {
      setName(store.name)
      setDescription(store.description || '')
      setColumns([...store.schemaDefinition])
      setError(null)
    }
  }, [store])

  const handleSave = async () => {
    if (!store || !name.trim()) {
      setError('Name is required')
      return
    }
    const validColumns = columns.filter((c) => c.name.trim() !== '')
    if (validColumns.length === 0) {
      setError('At least one column is required')
      return
    }

    setIsSaving(true)
    setError(null)
    try {
      await onSave(store.id, {
        name: name.trim(),
        description: description.trim() || undefined,
        schema_definition: validColumns,
      })
      onOpenChange(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update data store')
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Edit Data Store</DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label>Name *</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} disabled={isSaving} />
          </div>

          <div className="space-y-2">
            <Label>Description</Label>
            <Textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              disabled={isSaving}
              rows={2}
            />
          </div>

          <DataStoreSchemaEditor columns={columns} onChange={setColumns} disabled={isSaving} />

          {error && <div className="text-sm text-red-600">{error}</div>}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isSaving}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={isSaving}>
            {isSaving ? 'Saving...' : 'Save Changes'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
