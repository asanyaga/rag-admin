import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Loader2, Check, Pencil, X } from 'lucide-react'
import type { SubmitReviewRequest } from '@/types/agent'

interface ReceiptReviewFormProps {
  extractedData: Record<string, unknown>
  isSubmitting: boolean
  onSubmit: (request: SubmitReviewRequest) => Promise<void>
}

export function ReceiptReviewForm({
  extractedData,
  isSubmitting,
  onSubmit,
}: ReceiptReviewFormProps) {
  const [editedJson, setEditedJson] = useState(
    JSON.stringify(extractedData, null, 2)
  )
  const [isEditing, setIsEditing] = useState(false)
  const [parseError, setParseError] = useState<string | null>(null)

  const handleApprove = async () => {
    await onSubmit({ action: 'approve' })
  }

  const handleEditApprove = async () => {
    setParseError(null)
    try {
      const parsed = JSON.parse(editedJson)
      await onSubmit({ action: 'edit', data: parsed })
    } catch {
      setParseError('Invalid JSON')
    }
  }

  const handleReject = async () => {
    await onSubmit({ action: 'reject' })
  }

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-medium">Extracted Data</h3>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setIsEditing(!isEditing)}
          >
            <Pencil className="h-3.5 w-3.5 mr-1" />
            {isEditing ? 'Preview' : 'Edit'}
          </Button>
        </div>

        {isEditing ? (
          <div className="space-y-1">
            <Textarea
              value={editedJson}
              onChange={(e) => {
                setEditedJson(e.target.value)
                setParseError(null)
              }}
              className="font-mono text-sm min-h-[300px]"
            />
            {parseError && (
              <p className="text-xs text-destructive">{parseError}</p>
            )}
          </div>
        ) : (
          <pre className="rounded-lg border bg-muted/50 p-4 text-sm font-mono overflow-auto max-h-[400px]">
            {JSON.stringify(extractedData, null, 2)}
          </pre>
        )}
      </div>

      <div className="flex items-center gap-2 pt-2">
        <Button onClick={handleApprove} disabled={isSubmitting} size="sm">
          {isSubmitting ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <Check className="mr-2 h-4 w-4" />
          )}
          Approve
        </Button>

        {isEditing && (
          <Button
            onClick={handleEditApprove}
            disabled={isSubmitting}
            size="sm"
            variant="secondary"
          >
            {isSubmitting ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Pencil className="mr-2 h-4 w-4" />
            )}
            Edit & Approve
          </Button>
        )}

        <Button
          onClick={handleReject}
          disabled={isSubmitting}
          size="sm"
          variant="destructive"
        >
          <X className="mr-2 h-4 w-4" />
          Reject
        </Button>
      </div>
    </div>
  )
}
