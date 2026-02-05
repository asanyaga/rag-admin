import { useState } from 'react'
import { DocumentListItem } from '@/types/document'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'

interface DocumentDeleteDialogProps {
  document: DocumentListItem | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onConfirm: (id: string) => Promise<void>
}

export function DocumentDeleteDialog({
  document,
  open,
  onOpenChange,
  onConfirm,
}: DocumentDeleteDialogProps) {
  const [isDeleting, setIsDeleting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleConfirm = async () => {
    if (!document) return

    setIsDeleting(true)
    setError(null)

    try {
      await onConfirm(document.id)
      onOpenChange(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete')
    } finally {
      setIsDeleting(false)
    }
  }

  const handleCancel = () => {
    if (!isDeleting) {
      setError(null)
      onOpenChange(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Delete Document</DialogTitle>
          <DialogDescription>
            Are you sure you want to delete this document? This action cannot be
            undone.
          </DialogDescription>
        </DialogHeader>

        {document && (
          <div className="py-4">
            <div className="rounded-lg bg-muted p-4">
              <p className="font-medium">{document.title}</p>
              {document.description && (
                <p className="text-sm text-muted-foreground mt-1">
                  {document.description}
                </p>
              )}
            </div>
          </div>
        )}

        {error && (
          <div className="text-sm text-red-600 dark:text-red-400">{error}</div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={handleCancel} disabled={isDeleting}>
            Cancel
          </Button>
          <Button
            variant="destructive"
            onClick={handleConfirm}
            disabled={isDeleting}
          >
            {isDeleting ? 'Deleting...' : 'Delete Document'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
