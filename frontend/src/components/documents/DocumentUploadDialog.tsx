import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { DocumentUploadZone } from './DocumentUploadZone'
import type { ParseConfig } from '@/types/parsing'

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
  projectId: string
}

export function DocumentUploadDialog({
  open,
  onOpenChange,
  onUpload,
  projectId,
}: DocumentUploadDialogProps) {
  const handleUpload = async (
    file: File,
    title: string,
    description?: string,
    parserType?: string,
    parseConfig?: ParseConfig
  ) => {
    await onUpload(file, title, description, parserType, parseConfig)
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Upload Document</DialogTitle>
          <DialogDescription>
            Upload a PDF document to extract and index its content
          </DialogDescription>
        </DialogHeader>
        <DocumentUploadZone
          projectId={projectId}
          onUpload={handleUpload}
        />
      </DialogContent>
    </Dialog>
  )
}
