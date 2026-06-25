import { useState } from 'react'
import axios from 'axios'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { deleteParseRun } from '@/api/parseRuns'

interface Blockers {
  index_documents: number
  classification_runs: number
  extraction_results: number
}

interface ParseRunDeleteDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  runId: string
  onDeleted: () => void
}

function formatBlockers(b: Blockers): string {
  return [
    b.index_documents > 0 && `${b.index_documents} index document(s)`,
    b.classification_runs > 0 && `${b.classification_runs} classification run(s)`,
    b.extraction_results > 0 && `${b.extraction_results} extraction result(s)`,
  ]
    .filter(Boolean)
    .join(', ')
}

export function ParseRunDeleteDialog({
  open,
  onOpenChange,
  runId,
  onDeleted,
}: ParseRunDeleteDialogProps) {
  const [isDeleting, setIsDeleting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [blockers, setBlockers] = useState<Blockers | null>(null)

  const handleConfirm = async () => {
    setIsDeleting(true)
    setError(null)
    setBlockers(null)
    try {
      await deleteParseRun(runId)
      onOpenChange(false)
      onDeleted()
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.status === 409) {
        const body = err.response.data as {
          detail: { blockers: Blockers }
        }
        setBlockers(body.detail.blockers)
      } else {
        setError(
          err instanceof Error ? err.message : 'Failed to delete parse run',
        )
      }
    } finally {
      setIsDeleting(false)
    }
  }

  const handleClose = () => {
    if (!isDeleting) {
      setError(null)
      setBlockers(null)
      onOpenChange(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Delete Parse Run</DialogTitle>
          <DialogDescription>
            {blockers
              ? `This run cannot be deleted: ${formatBlockers(blockers)}. Remove these references first.`
              : 'Are you sure you want to delete this parse run? This cannot be undone.'}
          </DialogDescription>
        </DialogHeader>
        {error && (
          <p className="text-sm text-destructive">{error}</p>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={handleClose} disabled={isDeleting}>
            Cancel
          </Button>
          {!blockers && (
            <Button
              variant="destructive"
              onClick={handleConfirm}
              disabled={isDeleting}
            >
              {isDeleting ? 'Deleting...' : 'Delete'}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
