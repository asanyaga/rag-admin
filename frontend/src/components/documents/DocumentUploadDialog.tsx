import { useState, useEffect } from 'react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { DocumentUploadZone } from './DocumentUploadZone'
import { BulkUploadQueue } from './BulkUploadQueue'
import type { ParseConfig } from '@/types/parsing'
import type {
  BulkDocumentUpload,
  BulkUploadResponse,
  DocumentListItem,
} from '@/types/document'

interface DocumentUploadDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onUpload: (
    file: File,
    title: string,
    description?: string,
    parserType?: string,
    parseConfig?: ParseConfig
  ) => Promise<void>
  onBulkUpload?: (data: BulkDocumentUpload) => Promise<BulkUploadResponse>
  documents?: DocumentListItem[]
  projectId: string
  mode?: 'single' | 'bulk'
}

export function DocumentUploadDialog({
  open,
  onOpenChange,
  onUpload,
  onBulkUpload,
  documents = [],
  projectId,
  mode = 'single',
}: DocumentUploadDialogProps) {
  const [bulkFiles, setBulkFiles] = useState<File[]>([])

  // Reset bulk files when the dialog closes
  useEffect(() => {
    if (!open) setBulkFiles([])
  }, [open])

  const handleUpload = async (
    file: File,
    title: string,
    description?: string,
    parserType?: string,
    parseConfig?: ParseConfig
  ) => {
    await onUpload(file, title, description, parserType, parseConfig)
    if (mode === 'single') onOpenChange(false)
  }

  const showQueue = mode === 'bulk' && bulkFiles.length > 0

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>
            {mode === 'bulk' ? 'Bulk Upload Documents' : 'Upload Document'}
          </DialogTitle>
          <DialogDescription>
            {mode === 'bulk'
              ? 'Select multiple files to upload at once. Titles are set from filenames.'
              : 'Upload a PDF document to extract and index its content'}
          </DialogDescription>
        </DialogHeader>

        {showQueue ? (
          <BulkUploadQueue
            projectId={projectId}
            initialFiles={bulkFiles}
            documents={documents}
            onBulkUpload={onBulkUpload!}
            onClose={() => onOpenChange(false)}
          />
        ) : (
          <DocumentUploadZone
            projectId={projectId}
            onUpload={handleUpload}
            onBulkUpload={mode === 'bulk' ? setBulkFiles : undefined}
            multiple={mode === 'bulk'}
          />
        )}
      </DialogContent>
    </Dialog>
  )
}
