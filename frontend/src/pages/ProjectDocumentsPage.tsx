import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useDocuments } from '@/hooks/useDocuments'
import { DocumentListItem } from '@/types/document'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Skeleton } from '@/components/ui/skeleton'
import { DocumentUploadZone } from '@/components/documents/DocumentUploadZone'
import { DocumentsTable } from '@/components/documents/DocumentsTable'
import { DocumentTextViewer } from '@/components/documents/DocumentTextViewer'
import { DocumentEditDialog } from '@/components/documents/DocumentEditDialog'
import { DocumentDeleteDialog } from '@/components/documents/DocumentDeleteDialog'
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { toast } from 'sonner'

export default function ProjectDocumentsPage(): JSX.Element {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()

  const {
    documents,
    isLoading,
    error,
    uploadDocument,
    updateDocument,
    deleteDocument,
    downloadDocument,
  } = useDocuments(projectId || null)

  const [viewDocumentId, setViewDocumentId] = useState<string | null>(null)
  const [editDialogOpen, setEditDialogOpen] = useState(false)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [selectedDocument, setSelectedDocument] = useState<DocumentListItem | null>(null)

  if (!projectId) {
    return (
      <div className="space-y-6">
        <Alert>
          <AlertDescription>No project selected</AlertDescription>
        </Alert>
      </div>
    )
  }

  const handleUpload = async (file: File, title: string, description?: string) => {
    try {
      await uploadDocument({
        projectId,
        title,
        description,
        file,
      })
      toast.success('Document uploaded successfully', {
        description: 'Text extraction is in progress',
      })
    } catch (err) {
      toast.error('Upload failed', {
        description: err instanceof Error ? err.message : 'An error occurred',
      })
      throw err
    }
  }

  const handleView = (documentId: string) => {
    setViewDocumentId(documentId)
  }

  const handleEdit = (documentId: string) => {
    const doc = documents.find((d) => d.id === documentId)
    if (doc) {
      setSelectedDocument(doc)
      setEditDialogOpen(true)
    }
  }

  const handleEditSave = async (id: string, title: string, description?: string) => {
    try {
      await updateDocument(id, { title, description })
      toast.success('Document updated successfully')
    } catch (err) {
      toast.error('Update failed', {
        description: err instanceof Error ? err.message : 'An error occurred',
      })
      throw err
    }
  }

  const handleDelete = (documentId: string) => {
    const doc = documents.find((d) => d.id === documentId)
    if (doc) {
      setSelectedDocument(doc)
      setDeleteDialogOpen(true)
    }
  }

  const handleDeleteConfirm = async (documentId: string) => {
    try {
      await deleteDocument(documentId)
      toast.success('Document deleted successfully')
    } catch (err) {
      toast.error('Delete failed', {
        description: err instanceof Error ? err.message : 'An error occurred',
      })
      throw err
    }
  }

  const handleDownload = async (documentId: string, title: string) => {
    try {
      await downloadDocument(documentId, `${title}.pdf`)
      toast.success('Download started')
    } catch (err) {
      toast.error('Download failed', {
        description: err instanceof Error ? err.message : 'An error occurred',
      })
    }
  }

  const viewedDocument = documents.find((d) => d.id === viewDocumentId)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate('/projects')}
            className="mb-2"
          >
            <svg
              className="h-4 w-4 mr-2"
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 20 20"
              fill="currentColor"
            >
              <path
                fillRule="evenodd"
                d="M17 10a.75.75 0 01-.75.75H5.612l4.158 3.96a.75.75 0 11-1.04 1.08l-5.5-5.25a.75.75 0 010-1.08l5.5-5.25a.75.75 0 111.04 1.08L5.612 9.25H16.25A.75.75 0 0117 10z"
                clipRule="evenodd"
              />
            </svg>
            Back to Projects
          </Button>
          <h1 className="text-3xl font-bold">Documents</h1>
          <p className="text-muted-foreground mt-1">
            Upload and manage your documents
          </p>
        </div>
      </div>

      {/* Error Alert */}
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Upload Zone */}
      <DocumentUploadZone
        projectId={projectId}
        onUpload={handleUpload}
        disabled={isLoading}
      />

      {/* Documents Table */}
      <div>
        <h2 className="text-xl font-semibold mb-4">Your Documents</h2>
        {isLoading ? (
          <div className="space-y-4">
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
          </div>
        ) : (
          <DocumentsTable
            documents={documents}
            onView={handleView}
            onEdit={handleEdit}
            onDelete={handleDelete}
            onDownload={handleDownload}
          />
        )}
      </div>

      {/* View Document Sheet */}
      <Sheet open={viewDocumentId !== null} onOpenChange={(open) => !open && setViewDocumentId(null)}>
        <SheetContent side="right" className="w-full sm:max-w-2xl overflow-y-auto">
          <SheetHeader>
            <SheetTitle>{viewedDocument?.title}</SheetTitle>
          </SheetHeader>
          <div className="mt-6">
            {viewDocumentId && viewedDocument && (
              <DocumentTextViewer
                documentId={viewDocumentId}
                documentTitle={viewedDocument.title}
                onDownload={() => handleDownload(viewDocumentId, viewedDocument.title)}
              />
            )}
          </div>
        </SheetContent>
      </Sheet>

      {/* Edit Dialog */}
      <DocumentEditDialog
        document={selectedDocument}
        open={editDialogOpen}
        onOpenChange={setEditDialogOpen}
        onSave={handleEditSave}
      />

      {/* Delete Dialog */}
      <DocumentDeleteDialog
        document={selectedDocument}
        open={deleteDialogOpen}
        onOpenChange={setDeleteDialogOpen}
        onConfirm={handleDeleteConfirm}
      />
    </div>
  )
}
