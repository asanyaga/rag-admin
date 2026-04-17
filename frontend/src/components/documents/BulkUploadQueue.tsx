import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { ParseMethodSelector } from './ParseMethodSelector'
import type { ParseConfig } from '@/types/parsing'
import type {
  BulkDocumentUpload,
  BulkUploadResponse,
  DocumentListItem,
  QueueItem,
  QueueItemStatus,
} from '@/types/document'

const MAX_FILES = 20
const MAX_SIZE_BYTES = 25 * 1024 * 1024
const ALLOWED_TYPES = ['application/pdf', 'image/jpeg', 'image/png']

interface BulkUploadQueueProps {
  projectId: string
  initialFiles: File[]
  documents: DocumentListItem[]
  onBulkUpload: (data: BulkDocumentUpload) => Promise<BulkUploadResponse>
  onClose: () => void
}

function validateFile(file: File): string | null {
  if (file.size > MAX_SIZE_BYTES) return 'File exceeds 25MB limit'
  if (!ALLOWED_TYPES.includes(file.type)) return 'Unsupported file type (PDF, JPEG, PNG only)'
  return null
}

function QueueStatusBadge({ status }: { status: QueueItemStatus }) {
  const styles: Record<QueueItemStatus, string> = {
    pending: 'bg-gray-100 text-gray-700',
    uploading: 'bg-blue-100 text-blue-700',
    processing: 'bg-yellow-100 text-yellow-700',
    ready: 'bg-green-100 text-green-700',
    failed: 'bg-red-100 text-red-700',
  }
  const labels: Record<QueueItemStatus, string> = {
    pending: 'Pending',
    uploading: 'Uploading',
    processing: 'Processing',
    ready: 'Ready',
    failed: 'Failed',
  }
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap',
        styles[status]
      )}
    >
      {labels[status]}
    </span>
  )
}

export function BulkUploadQueue({
  projectId,
  initialFiles,
  documents,
  onBulkUpload,
  onClose,
}: BulkUploadQueueProps) {
  const truncated = initialFiles.length > MAX_FILES
  const cappedFiles = initialFiles.slice(0, MAX_FILES)

  const [queueItems, setQueueItems] = useState<QueueItem[]>(() =>
    cappedFiles.map((file) => {
      const error = validateFile(file)
      return {
        file,
        status: error ? ('failed' as QueueItemStatus) : ('pending' as QueueItemStatus),
        documentId: null,
        error,
      }
    })
  )
  const [parserType, setParserType] = useState('simple')
  const [parseConfig, setParseConfig] = useState<ParseConfig>({
    tier: 'agentic',
    expand: ['markdown', 'text'],
  })
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [uploadStarted, setUploadStarted] = useState(false)
  const [networkError, setNetworkError] = useState<string | null>(null)

  // Watch the documents list for processing status updates
  useEffect(() => {
    setQueueItems((prev) =>
      prev.map((item) => {
        if (!item.documentId) return item
        const doc = documents.find((d) => d.id === item.documentId)
        if (!doc) return item
        const newStatus = doc.status as QueueItemStatus
        if (newStatus === item.status) return item
        return { ...item, status: newStatus, error: doc.statusMessage ?? null }
      })
    )
  }, [documents])

  const validItems = queueItems.filter((item) => item.status === 'pending')
  const validCount = validItems.length

  const handleSubmit = async () => {
    if (validCount === 0) return
    setIsSubmitting(true)
    setUploadStarted(true)
    setNetworkError(null)

    setQueueItems((prev) =>
      prev.map((item) =>
        item.status === 'pending' ? { ...item, status: 'uploading' as QueueItemStatus } : item
      )
    )

    try {
      const response = await onBulkUpload({
        projectId,
        files: validItems.map((item) => item.file),
        parserType,
        parseConfig: parserType === 'llamaparse' ? parseConfig : undefined,
      })

      const responseMap = new Map(response.results.map((r) => [r.filename, r]))

      setQueueItems((prev) =>
        prev.map((item) => {
          if (item.status !== 'uploading') return item
          const result = responseMap.get(item.file.name)
          if (!result) return { ...item, status: 'failed' as QueueItemStatus, error: 'No response received' }
          if (result.error) return { ...item, status: 'failed' as QueueItemStatus, error: result.error }
          return {
            ...item,
            status: result.document!.status as QueueItemStatus,
            documentId: result.document!.id,
          }
        })
      )
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Upload failed'
      setNetworkError(message)
      setQueueItems((prev) =>
        prev.map((item) =>
          item.status === 'uploading'
            ? { ...item, status: 'failed' as QueueItemStatus, error: message }
            : item
        )
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="space-y-4">
      {truncated && (
        <div className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-md p-3">
          Maximum 20 files per batch. Showing first 20 of {initialFiles.length} selected files.
        </div>
      )}

      {networkError && (
        <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-md p-3">
          {networkError}
        </div>
      )}

      <div className="border rounded-md divide-y max-h-64 overflow-y-auto">
        {queueItems.map((item, index) => (
          <div key={index} className="flex items-center justify-between p-3 text-sm gap-3">
            <div className="flex-1 min-w-0">
              <p className="truncate font-medium">{item.file.name}</p>
              <p className="text-xs text-muted-foreground">
                {(item.file.size / 1024 / 1024).toFixed(2)} MB
              </p>
              {item.error && item.status === 'failed' && !item.documentId && (
                <p className="text-xs text-red-500 mt-0.5">{item.error}</p>
              )}
            </div>
            <QueueStatusBadge status={item.status} />
          </div>
        ))}
      </div>

      <ParseMethodSelector
        parserType={parserType}
        config={parseConfig}
        onParserTypeChange={setParserType}
        onConfigChange={setParseConfig}
        disabled={isSubmitting || uploadStarted}
      />

      <div className="flex gap-2 justify-end">
        <Button variant="outline" onClick={onClose} disabled={isSubmitting}>
          {uploadStarted ? 'Close' : 'Cancel'}
        </Button>
        {!uploadStarted && (
          <Button onClick={handleSubmit} disabled={validCount === 0 || isSubmitting}>
            {isSubmitting
              ? 'Uploading...'
              : `Upload ${validCount} file${validCount !== 1 ? 's' : ''}`}
          </Button>
        )}
      </div>
    </div>
  )
}
