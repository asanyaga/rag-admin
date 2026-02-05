import { useState } from 'react'
import { useProject } from '@/contexts/ProjectContext'
import { useDocuments } from '@/hooks/useDocuments'
import { DocumentListItem } from '@/types/document'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import { DocumentsTable } from '@/components/documents/DocumentsTable'
import { DocumentTextViewer } from '@/components/documents/DocumentTextViewer'
import { DocumentEditDialog } from '@/components/documents/DocumentEditDialog'
import { DocumentDeleteDialog } from '@/components/documents/DocumentDeleteDialog'
import { DocumentUploadDialog } from '@/components/documents/DocumentUploadDialog'
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Plus } from 'lucide-react'
import { toast } from 'sonner'

export default function DocumentsPage(): JSX.Element {
  const { currentProject } = useProject()

  const {
    documents,
    isLoading,
    error,
    uploadDocument,
    updateDocument,
    deleteDocument,
    downloadDocument,
  } = useDocuments(currentProject?.id || null)

  const [uploadDialogOpen, setUploadDialogOpen] = useState(false)
  const [viewDocumentId, setViewDocumentId] = useState<string | null>(null)
  const [editDialogOpen, setEditDialogOpen] = useState(false)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [selectedDocument, setSelectedDocument] = useState<DocumentListItem | null>(null)

  if (!currentProject) {
    return (
      <div className="space-y-6">
        <Alert>
          <AlertDescription>Loading project...</AlertDescription>
        </Alert>
      </div>
    )
  }

  const handleUpload = async (file: File, title: string, description?: string) => {
    try {
      await uploadDocument({
        projectId: currentProject.id,
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
          <h1 className="text-3xl font-bold">Documents</h1>
          <p className="text-muted-foreground mt-1">
            {currentProject.name}
          </p>
        </div>
        <Button onClick={() => setUploadDialogOpen(true)}>
          <Plus className="h-4 w-4 mr-2" />
          Upload Document
        </Button>
      </div>

      {/* Error Alert */}
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Documents Table */}
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
          onUploadClick={() => setUploadDialogOpen(true)}
        />
      )}

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

      {/* Upload Dialog */}
      <DocumentUploadDialog
        open={uploadDialogOpen}
        onOpenChange={setUploadDialogOpen}
        onUpload={handleUpload}
        projectId={currentProject.id}
      />
    </div>
  )
}
