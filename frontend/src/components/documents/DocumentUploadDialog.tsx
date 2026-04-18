import { useState, useEffect } from 'react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
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
import { DocumentUploadZone } from './DocumentUploadZone'
import { BulkUploadQueue } from './BulkUploadQueue'
import type { Folder } from '@/types/folder'
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
    parseConfig?: ParseConfig,
    folderId?: string | null
  ) => Promise<void>
  onBulkUpload?: (data: BulkDocumentUpload) => Promise<BulkUploadResponse>
  documents?: DocumentListItem[]
  projectId: string
  mode?: 'single' | 'bulk'
  folders?: Folder[]
  initialFolderId?: string | null
}

const NO_FOLDER_VALUE = '__none__'

export function DocumentUploadDialog({
  open,
  onOpenChange,
  onUpload,
  onBulkUpload,
  documents = [],
  projectId,
  mode = 'single',
  folders = [],
  initialFolderId = null,
}: DocumentUploadDialogProps) {
  const [bulkFiles, setBulkFiles] = useState<File[]>([])
  const [folderId, setFolderId] = useState<string | null>(initialFolderId)

  useEffect(() => {
    if (!open) {
      setBulkFiles([])
      setFolderId(initialFolderId)
    }
  }, [open, initialFolderId])

  const handleUpload = async (
    file: File,
    title: string,
    description?: string,
    parserType?: string,
    parseConfig?: ParseConfig
  ) => {
    await onUpload(file, title, description, parserType, parseConfig, folderId)
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

        {folders.length > 0 && (
          <div className="space-y-2">
            <Label htmlFor="upload-folder">Folder (optional)</Label>
            <Select
              value={folderId ?? NO_FOLDER_VALUE}
              onValueChange={(v) => setFolderId(v === NO_FOLDER_VALUE ? null : v)}
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
