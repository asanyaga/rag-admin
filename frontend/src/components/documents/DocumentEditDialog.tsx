import { useState, useEffect } from 'react'
import { DocumentListItem } from '@/types/document'
import { Folder } from '@/types/folder'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
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

interface DocumentEditDialogProps {
  document: DocumentListItem | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onSave: (id: string, title: string, description?: string, folderId?: string | null) => Promise<void>
  folders?: Folder[]
}

const NO_FOLDER_VALUE = '__none__'

export function DocumentEditDialog({
  document,
  open,
  onOpenChange,
  onSave,
  folders = [],
}: DocumentEditDialogProps) {
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [folderId, setFolderId] = useState<string | null>(null)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (document) {
      setTitle(document.title)
      setDescription(document.description || '')
      setFolderId(document.folderId)
      setError(null)
    }
  }, [document])

  const handleSave = async () => {
    if (!document || !title.trim()) {
      setError('Title is required')
      return
    }

    setIsSaving(true)
    setError(null)

    try {
      await onSave(
        document.id,
        title.trim(),
        description.trim() || undefined,
        folderId
      )
      onOpenChange(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save')
    } finally {
      setIsSaving(false)
    }
  }

  const handleCancel = () => {
    if (!isSaving) {
      onOpenChange(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit Document</DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label htmlFor="edit-title">Title *</Label>
            <Input
              id="edit-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Enter document title"
              disabled={isSaving}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="edit-description">Description</Label>
            <Textarea
              id="edit-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Optional description"
              disabled={isSaving}
              rows={4}
            />
          </div>

          {folders.length > 0 && (
            <div className="space-y-2">
              <Label htmlFor="edit-folder">Folder</Label>
              <Select
                value={folderId ?? NO_FOLDER_VALUE}
                onValueChange={(v) => setFolderId(v === NO_FOLDER_VALUE ? null : v)}
                disabled={isSaving}
              >
                <SelectTrigger id="edit-folder">
                  <SelectValue placeholder="No folder" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={NO_FOLDER_VALUE}>
                    <span className="text-muted-foreground">No folder</span>
                  </SelectItem>
                  {folders.map((folder) => (
                    <SelectItem key={folder.id} value={folder.id}>
                      {folder.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          {error && (
            <div className="text-sm text-red-600 dark:text-red-400">
              {error}
            </div>
          )}
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={handleCancel}
            disabled={isSaving}
          >
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={!title.trim() || isSaving}>
            {isSaving ? 'Saving...' : 'Save Changes'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
