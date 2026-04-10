import { StatusBadge } from './StatusBadge'
import { ReceiptReviewForm } from './ReceiptReviewForm'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Skeleton } from '@/components/ui/skeleton'
import { Loader2 } from 'lucide-react'
import type { AgentReceipt, SubmitReviewRequest } from '@/types/agent'

interface ReceiptDetailProps {
  receipt: AgentReceipt | null
  isLoading: boolean
  isSubmitting: boolean
  error: string | null
  onSubmitReview: (request: SubmitReviewRequest) => Promise<void>
}

export function ReceiptDetail({
  receipt,
  isLoading,
  isSubmitting,
  error,
  onSubmitReview,
}: ReceiptDetailProps) {
  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-4 w-32" />
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  if (!receipt) {
    return (
      <Alert variant="destructive">
        <AlertDescription>Receipt not found.</AlertDescription>
      </Alert>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <StatusBadge status={receipt.status} />
        <span className="text-sm text-muted-foreground">
          Created{' '}
          {new Date(receipt.createdAt).toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
          })}
        </span>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Status-specific content */}
      {(receipt.status === 'pending' || receipt.status === 'extracting') && (
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground mb-4" />
          <p className="text-sm text-muted-foreground">
            {receipt.status === 'pending'
              ? 'Waiting to start extraction...'
              : 'Extracting data from receipt...'}
          </p>
          <p className="text-xs text-muted-foreground/70 mt-1">
            This may take 10-30 seconds
          </p>
        </div>
      )}

      {receipt.status === 'reviewing' && receipt.extractedData && (
        <ReceiptReviewForm
          extractedData={receipt.extractedData}
          isSubmitting={isSubmitting}
          onSubmit={onSubmitReview}
        />
      )}

      {(receipt.status === 'approved' || receipt.status === 'exported') && (
        <div className="space-y-3">
          <h3 className="text-sm font-medium">Final Data</h3>
          <pre className="rounded-lg border bg-muted/50 p-4 text-sm font-mono overflow-auto max-h-[400px]">
            {JSON.stringify(
              receipt.reviewedData || receipt.extractedData,
              null,
              2
            )}
          </pre>
        </div>
      )}

      {receipt.status === 'failed' && (
        <Alert variant="destructive">
          <AlertDescription>
            {receipt.statusMessage || 'Processing failed.'}
          </AlertDescription>
        </Alert>
      )}
    </div>
  )
}
