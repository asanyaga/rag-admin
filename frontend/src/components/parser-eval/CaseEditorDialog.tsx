import { useState } from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { useSourceDocuments } from '@/hooks/useSourceDocuments'
import type { CreateCaseRequest } from '@/types/parserEval'

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSubmit: (data: CreateCaseRequest) => Promise<unknown>
}

export function CaseEditorDialog({ open, onOpenChange, onSubmit }: Props) {
  const { sourceDocuments } = useSourceDocuments()
  const [sourceDocumentId, setSourceDocumentId] = useState('')
  const [pages, setPages] = useState<string[]>([''])
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const canSubmit = sourceDocumentId !== '' && pages.some((p) => p.trim() !== '')

  const handleSubmit = async () => {
    setSubmitting(true)
    setError(null)
    try {
      await onSubmit({ sourceDocumentId, dimension: 'text', expected: { pages } })
      onOpenChange(false)
      setSourceDocumentId('')
      setPages([''])
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status
      setError(
        status === 409 || status === 400
          ? 'A text case already exists for this document.'
          : 'Failed to save case.'
      )
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>New Case</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div>
            <Label>Source document</Label>
            <Select value={sourceDocumentId} onValueChange={setSourceDocumentId}>
              <SelectTrigger>
                <SelectValue placeholder="Select a document" />
              </SelectTrigger>
              <SelectContent>
                {sourceDocuments.map((d) => (
                  <SelectItem key={d.id} value={d.id}>
                    {d.filename ?? d.id}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label>Dimension</Label>
            <Select value="text" disabled>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="text">Text faithfulness</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>Ground truth (per page)</Label>
            {pages.map((page, i) => (
              <div key={i} className="space-y-1">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-muted-foreground">Page {i + 1}</span>
                  {pages.length > 1 && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setPages((p) => p.filter((_, idx) => idx !== i))}
                    >
                      Remove
                    </Button>
                  )}
                </div>
                <Textarea
                  value={page}
                  rows={4}
                  onChange={(e) =>
                    setPages((p) => p.map((v, idx) => (idx === i ? e.target.value : v)))
                  }
                  placeholder={`Correct readable text for page ${i + 1}`}
                />
              </div>
            ))}
            <Button variant="outline" size="sm" onClick={() => setPages((p) => [...p, ''])}>
              Add page
            </Button>
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button disabled={!canSubmit || submitting} onClick={handleSubmit}>
            {submitting ? 'Saving…' : 'Create case'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
