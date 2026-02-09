import { useState, useEffect } from 'react'
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useDocuments } from '@/hooks/useDocuments'
import type { SourceCreate } from '@/types/golden-set'

interface AddSourceDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  projectId: string
  onAdd: (data: SourceCreate) => Promise<void>
}

export function AddSourceDialog({
  open,
  onOpenChange,
  projectId,
  onAdd,
}: AddSourceDialogProps) {
  const { documents, isLoading } = useDocuments(projectId, 'ready')
  const [documentId, setDocumentId] = useState('')
  const [pagesInput, setPagesInput] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  // Reset form when dialog opens
  useEffect(() => {
    if (open) {
      setDocumentId('')
      setPagesInput('')
    }
  }, [open])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!documentId || !pagesInput.trim()) return

    const pages = pagesInput
      .split(',')
      .map((s) => parseInt(s.trim(), 10))
      .filter((n) => !isNaN(n) && n > 0)

    if (pages.length === 0) return

    setIsSubmitting(true)
    try {
      await onAdd({
        documentId,
        locator: { type: 'page', pages },
      })
      onOpenChange(false)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add Source</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label>Document</Label>
            <Select value={documentId} onValueChange={setDocumentId}>
              <SelectTrigger>
                <SelectValue placeholder={isLoading ? 'Loading...' : 'Select a document'} />
              </SelectTrigger>
              <SelectContent>
                {documents.map((doc) => (
                  <SelectItem key={doc.id} value={doc.id}>
                    {doc.title}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="pages">Pages</Label>
            <Input
              id="pages"
              value={pagesInput}
              onChange={(e) => setPagesInput(e.target.value)}
              placeholder="e.g. 1, 3, 5"
            />
            <p className="text-xs text-muted-foreground">
              Comma-separated page numbers that should be retrieved.
            </p>
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={!documentId || !pagesInput.trim() || isSubmitting}
            >
              {isSubmitting ? 'Adding...' : 'Add Source'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
