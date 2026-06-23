import { useState, useEffect, useCallback } from 'react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'
import { X } from 'lucide-react'
import { cn } from '@/lib/utils'
import { DocumentUploadZone } from './DocumentUploadZone'
import { ParseMethodSelector } from './ParseMethodSelector'
import type { Folder } from '@/types/folder'
import type { ParseConfig } from '@/types/parsing'
import type { Document, DocumentListItem, DocumentUpload } from '@/types/document'

type QueueItemStatus = 'pending' | 'uploading' | 'processing' | 'ready' | 'failed'

interface QueueItem {
  file: File
  status: QueueItemStatus
  documentId: string | null
  error: string | null
}

interface DocumentUploadDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onUpload: (data: DocumentUpload) => Promise<Document>
  projectId: string
  documents?: DocumentListItem[]
  folders?: Folder[]
  initialFolderId?: string | null
}

const ALLOWED_TYPES = ['application/pdf', 'image/jpeg', 'image/png']
const MAX_SIZE_BYTES = 25 * 1024 * 1024
const NO_FOLDER_VALUE = '__none__'

function validateFile(file: File): string | null {
  if (!ALLOWED_TYPES.includes(file.type)) return 'Unsupported file type (PDF, JPEG, PNG only)'
  if (file.size > MAX_SIZE_BYTES) return 'File exceeds 25MB limit'
  return null
}

function titleFromFilename(filename: string): string {
  return filename.replace(/\.[^/.]+$/, '')
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

export function DocumentUploadDialog({
  open,
  onOpenChange,
  onUpload,
  projectId,
  documents = [],
  folders = [],
  initialFolderId = null,
}: DocumentUploadDialogProps) {
  const [queue, setQueue] = useState<QueueItem[]>([])
  const [phase, setPhase] = useState<'select' | 'review' | 'uploading'>('select')
  const [parserType, setParserType] = useState('simple')
  const [parseConfig, setParseConfig] = useState<ParseConfig>({})
  const [folderId, setFolderId] = useState<string | null>(initialFolderId)

  // Reset all state when dialog closes
  useEffect(() => {
    if (!open) {
      setQueue([])
      setPhase('select')
      setParserType('simple')
      setParseConfig({})
      setFolderId(initialFolderId)
    }
  }, [open, initialFolderId])

  // Return to select phase if user removes all files during review
  useEffect(() => {
    if (queue.length === 0 && phase === 'review') setPhase('select')
  }, [queue.length, phase])

  // Watch documents list for Processing → Ready/Failed transitions
  useEffect(() => {
    if (documents.length === 0) return
    setQueue((prev) =>
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

  const handleAddFiles = useCallback((files: File[]) => {
    const newItems: QueueItem[] = files.map((file) => {
      const error = validateFile(file)
      return { file, status: error ? 'failed' : 'pending', documentId: null, error }
    })
    setQueue((prev) => [...prev, ...newItems])
    setPhase('review')
  }, [])

  const handleRemove = (index: number) => {
    setQueue((prev) => prev.filter((_, i) => i !== index))
  }

  const handleUpload = async () => {
    setPhase('uploading')

    // Snapshot pending entries before the loop so we don't read stale closure state
    const pendingEntries = queue
      .map((item, i) => ({ i, file: item.file, status: item.status }))
      .filter(({ status }) => status === 'pending')
      .map(({ i, file }) => ({ i, file }))

    for (const { i, file } of pendingEntries) {
      setQueue((prev) =>
        prev.map((item, idx) => (idx === i ? { ...item, status: 'uploading' } : item))
      )
      try {
        const doc = await onUpload({
          projectId,
          title: titleFromFilename(file.name),
          file,
          parserType,
          parseConfig: parserType !== 'simple' ? parseConfig : undefined,
          folderId,
        })
        setQueue((prev) =>
          prev.map((item, idx) =>
            idx === i
              ? { ...item, status: doc.status as QueueItemStatus, documentId: doc.id }
              : item
          )
        )
      } catch (err) {
        setQueue((prev) =>
          prev.map((item, idx) =>
            idx === i
              ? {
                  ...item,
                  status: 'failed',
                  error: err instanceof Error ? err.message : 'Upload failed',
                }
              : item
          )
        )
      }
    }
  }

  const validCount = queue.filter((item) => item.status === 'pending').length
  const isUploading = phase === 'uploading'

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Upload Documents</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          {/* Drop zone: full in select phase, compact strip in review, hidden while uploading */}
          {phase === 'select' && <DocumentUploadZone onFiles={handleAddFiles} />}
          {phase === 'review' && <DocumentUploadZone onFiles={handleAddFiles} compact />}

          {/* File queue */}
          {queue.length > 0 && (
            <div className="border rounded-md divide-y max-h-64 overflow-y-auto">
              {queue.map((item, index) => (
                <div key={index} className="flex items-center gap-3 p-3 text-sm">
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
                  {!isUploading && item.status === 'pending' && (
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-6 w-6 shrink-0"
                      onClick={() => handleRemove(index)}
                    >
                      <X className="h-3 w-3" />
                    </Button>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Folder selector */}
          {folders.length > 0 && (
            <div className="space-y-2">
              <Label htmlFor="upload-folder">Folder (optional)</Label>
              <Select
                value={folderId ?? NO_FOLDER_VALUE}
                onValueChange={(v) => setFolderId(v === NO_FOLDER_VALUE ? null : v)}
                disabled={isUploading}
              >
                <SelectTrigger id="upload-folder">
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

          {/* Parser selector — shown once files are in the queue */}
          {phase !== 'select' && (
            <ParseMethodSelector
              parserType={parserType}
              config={parseConfig}
              onParserTypeChange={setParserType}
              onConfigChange={setParseConfig}
              disabled={isUploading}
            />
          )}

          {/* Footer */}
          <div className="flex justify-end gap-2">
            {isUploading ? (
              <Button variant="outline" onClick={() => onOpenChange(false)}>
                Close
              </Button>
            ) : (
              <>
                <Button variant="outline" onClick={() => onOpenChange(false)}>
                  Cancel
                </Button>
                {phase === 'review' && (
                  <Button onClick={handleUpload} disabled={validCount === 0}>
                    Upload {validCount} file{validCount !== 1 ? 's' : ''}
                  </Button>
                )}
              </>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
