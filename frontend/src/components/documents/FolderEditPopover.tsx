import { useState, useEffect } from 'react'
import { Folder, FolderCreate } from '@/types/folder'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'

interface FolderEditPopoverProps {
  folder?: Folder
  trigger: React.ReactNode
  onSave: (data: FolderCreate) => Promise<void>
  onDelete?: () => Promise<void>
}

export function FolderEditPopover({
  folder,
  trigger,
  onSave,
  onDelete,
}: FolderEditPopoverProps) {
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [tagsInput, setTagsInput] = useState('')
  const [isSaving, setIsSaving] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (open) {
      setName(folder?.name ?? '')
      setDescription(folder?.description ?? '')
      setTagsInput(folder?.tags.join(', ') ?? '')
      setError(null)
    }
  }, [open, folder])

  const handleSave = async () => {
    if (!name.trim()) {
      setError('Name is required')
      return
    }
    setIsSaving(true)
    setError(null)
    try {
      const tags = tagsInput
        .split(',')
        .map((t) => t.trim())
        .filter(Boolean)
      await onSave({ name: name.trim(), description: description.trim() || undefined, tags })
      setOpen(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save')
    } finally {
      setIsSaving(false)
    }
  }

  const handleDelete = async () => {
    if (!onDelete) return
    setIsDeleting(true)
    try {
      await onDelete()
      setOpen(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete')
    } finally {
      setIsDeleting(false)
    }
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>{trigger}</PopoverTrigger>
      <PopoverContent className="w-72" align="start">
        <div className="space-y-3">
          <p className="text-sm font-medium">{folder ? 'Edit Folder' : 'New Folder'}</p>

          <div className="space-y-1">
            <Label htmlFor="folder-name" className="text-xs">Name *</Label>
            <Input
              id="folder-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Folder name"
              disabled={isSaving}
              className="h-8 text-sm"
            />
          </div>

          <div className="space-y-1">
            <Label htmlFor="folder-description" className="text-xs">Description</Label>
            <Textarea
              id="folder-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Optional description"
              disabled={isSaving}
              rows={2}
              className="text-sm resize-none"
            />
          </div>

          <div className="space-y-1">
            <Label htmlFor="folder-tags" className="text-xs">Tags (comma-separated)</Label>
            <Input
              id="folder-tags"
              value={tagsInput}
              onChange={(e) => setTagsInput(e.target.value)}
              placeholder="e.g. receipts, 2024"
              disabled={isSaving}
              className="h-8 text-sm"
            />
          </div>

          {error && (
            <p className="text-xs text-red-600 dark:text-red-400">{error}</p>
          )}

          <div className="flex justify-between pt-1">
            {onDelete ? (
              <Button
                variant="ghost"
                size="sm"
                onClick={handleDelete}
                disabled={isSaving || isDeleting}
                className="text-red-600 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-950 px-2"
              >
                {isDeleting ? 'Deleting...' : 'Delete'}
              </Button>
            ) : (
              <span />
            )}
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setOpen(false)}
                disabled={isSaving || isDeleting}
              >
                Cancel
              </Button>
              <Button
                size="sm"
                onClick={handleSave}
                disabled={!name.trim() || isSaving || isDeleting}
              >
                {isSaving ? 'Saving...' : 'Save'}
              </Button>
            </div>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  )
}
