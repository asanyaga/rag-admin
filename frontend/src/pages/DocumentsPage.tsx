import { useState } from 'react'
import { useProject } from '@/contexts/ProjectContext'
import { useDocuments } from '@/hooks/useDocuments'
import { useFolders } from '@/hooks/useFolders'
import { DocumentListItem } from '@/types/document'
import { FolderCreate } from '@/types/folder'
import type { ParseConfig } from '@/types/parsing'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import { DocumentsTable } from '@/components/documents/DocumentsTable'
import { FolderSidebar } from '@/components/documents/FolderSidebar'
import { BulkActionBar } from '@/components/documents/BulkActionBar'
import { DocumentTextViewer } from '@/components/documents/DocumentTextViewer'
import { DocumentEditDialog } from '@/components/documents/DocumentEditDialog'
import { DocumentDeleteDialog } from '@/components/documents/DocumentDeleteDialog'
import { DocumentUploadDialog } from '@/components/documents/DocumentUploadDialog'
import { ParseResultViewer } from '@/components/documents/ParseResultViewer'
import { ParsedDocumentViewer } from '@/components/documents/ParsedDocumentViewer'
import { ReParseDialog } from '@/components/documents/ReParseDialog'
import { RunTimeline } from '@/components/parse-runs/RunTimeline'
import { useParseRuns } from '@/hooks/useParseRuns'
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Plus, RotateCw, Files } from 'lucide-react'
import type { BulkDocumentUpload, BulkUploadResponse } from '@/types/document'
import { toast } from 'sonner'
import { useNavigate } from 'react-router-dom'
import { useParseResults } from '@/hooks/useParseResults'

export default function DocumentsPage(): JSX.Element {
  const navigate = useNavigate()
  const { currentProject } = useProject()

  const [selectedFolderId, setSelectedFolderId] = useState<string | null>(null)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())

  const {
    documents,
    isLoading,
    error,
    uploadDocument,
    uploadDocumentsBulk,
    updateDocument,
    deleteDocument,
    downloadDocument,
    bulkMoveDocuments,
  } = useDocuments(currentProject?.id || null, undefined, selectedFolderId)

  const {
    folders,
    createFolder,
    updateFolder,
    deleteFolder,
  } = useFolders(currentProject?.id || null)

  const [uploadDialogOpen, setUploadDialogOpen] = useState(false)
  const [bulkUploadOpen, setBulkUploadOpen] = useState(false)
  const [viewDocumentId, setViewDocumentId] = useState<string | null>(null)
  const [editDialogOpen, setEditDialogOpen] = useState(false)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [selectedDocument, setSelectedDocument] = useState<DocumentListItem | null>(null)
  const [reparseDialogOpen, setReparseDialogOpen] = useState(false)

  const { parseResults, reparseDocument } = useParseResults(viewDocumentId)
  const { parseRuns } = useParseRuns(viewDocumentId)

  if (!currentProject) {
    return (
      <div className="space-y-6">
        <Alert>
          <AlertDescription>Loading project...</AlertDescription>
        </Alert>
      </div>
    )
  }

  const handleUpload = async (
    file: File,
    title: string,
    description?: string,
    parserType?: string,
    parseConfig?: ParseConfig,
    folderId?: string | null,
  ) => {
    try {
      await uploadDocument({
        projectId: currentProject.id,
        title,
        description,
        file,
        parserType,
        parseConfig,
        folderId: folderId ?? selectedFolderId ?? undefined,
      })
      toast.success('Document uploaded successfully', {
        description: parserType === 'llamaparse'
          ? 'LlamaParse processing is in progress'
          : 'Text extraction is in progress',
      })
    } catch (err) {
      toast.error('Upload failed', {
        description: err instanceof Error ? err.message : 'An error occurred',
      })
      throw err
    }
  }

  const handleBulkUpload = async (data: BulkDocumentUpload): Promise<BulkUploadResponse> => {
    try {
      const response = await uploadDocumentsBulk(data)
      const successCount = response.results.filter((r) => r.document !== null).length
      const failureCount = response.results.filter((r) => r.error !== null).length
      if (failureCount === 0) {
        toast.success(`${successCount} document${successCount !== 1 ? 's' : ''} uploaded`)
      } else {
        toast.success(`${successCount} uploaded`, {
          description: `${failureCount} failed — check the queue for details`,
        })
      }
      return response
    } catch (err) {
      toast.error('Bulk upload failed', {
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

  const handleEditSave = async (
    id: string,
    title: string,
    description?: string,
    folderId?: string | null,
  ) => {
    try {
      await updateDocument(id, { title, description, folderId })
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

  const handleExtract = (documentId: string) => {
    navigate(`/extraction?documentId=${documentId}`)
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

  const handleReparse = async (parserType: string, config?: ParseConfig) => {
    try {
      await reparseDocument(parserType, config)
      toast.success('Re-parse started', {
        description: 'Parsing is in progress',
      })
    } catch (err) {
      toast.error('Re-parse failed', {
        description: err instanceof Error ? err.message : 'An error occurred',
      })
      throw err
    }
  }

  const handleToggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const handleToggleSelectAll = () => {
    if (selectedIds.size === documents.length) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(documents.map((d) => d.id)))
    }
  }

  const handleBulkMove = async (folderId: string | null) => {
    try {
      const count = await bulkMoveDocuments(Array.from(selectedIds), folderId)
      toast.success(`${count} document${count !== 1 ? 's' : ''} moved`)
    } catch (err) {
      toast.error('Move failed', {
        description: err instanceof Error ? err.message : 'An error occurred',
      })
      throw err
    }
  }

  const handleCreateFolder = async (data: FolderCreate) => {
    try {
      await createFolder(data)
      toast.success(`Folder "${data.name}" created`)
    } catch (err) {
      toast.error('Failed to create folder', {
        description: err instanceof Error ? err.message : 'An error occurred',
      })
      throw err
    }
  }

  const handleUpdateFolder = async (folderId: string, data: FolderCreate) => {
    try {
      await updateFolder(folderId, data)
      toast.success('Folder updated')
    } catch (err) {
      toast.error('Failed to update folder', {
        description: err instanceof Error ? err.message : 'An error occurred',
      })
      throw err
    }
  }

  const handleDeleteFolder = async (folderId: string) => {
    try {
      await deleteFolder(folderId)
      if (selectedFolderId === folderId) setSelectedFolderId(null)
      toast.success('Folder deleted')
    } catch (err) {
      toast.error('Failed to delete folder', {
        description: err instanceof Error ? err.message : 'An error occurred',
      })
      throw err
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
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setBulkUploadOpen(true)}>
            <Files className="h-4 w-4 mr-2" />
            Bulk Upload
          </Button>
          <Button onClick={() => setUploadDialogOpen(true)}>
            <Plus className="h-4 w-4 mr-2" />
            Upload Document
          </Button>
        </div>
      </div>

      {/* Error Alert */}
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Two-column layout: folder sidebar + documents */}
      <div className="flex gap-6">
        <FolderSidebar
          folders={folders}
          selectedFolderId={selectedFolderId}
          onSelectFolder={(id) => {
            setSelectedFolderId(id)
            setSelectedIds(new Set())
          }}
          onCreateFolder={handleCreateFolder}
          onUpdateFolder={handleUpdateFolder}
          onDeleteFolder={handleDeleteFolder}
        />

        <div className="flex-1 min-w-0 space-y-3">
          {selectedIds.size > 0 && (
            <BulkActionBar
              selectedCount={selectedIds.size}
              folders={folders}
              onMove={handleBulkMove}
              onClearSelection={() => setSelectedIds(new Set())}
            />
          )}

          {isLoading ? (
            <div className="space-y-4">
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-12 w-full" />
            </div>
          ) : (
            <DocumentsTable
              documents={documents}
              folders={folders}
              selectedIds={selectedIds}
              onToggleSelect={handleToggleSelect}
              onToggleSelectAll={handleToggleSelectAll}
              onView={handleView}
              onEdit={handleEdit}
              onDelete={handleDelete}
              onDownload={handleDownload}
              onExtract={handleExtract}
              onUploadClick={() => setUploadDialogOpen(true)}
            />
          )}
        </div>
      </div>

      {/* View Document Sheet */}
      <Sheet open={viewDocumentId !== null} onOpenChange={(open) => !open && setViewDocumentId(null)}>
        <SheetContent side="right" className="w-full sm:max-w-2xl overflow-y-auto">
          <SheetHeader>
            <div className="flex items-center justify-between pr-8">
              <SheetTitle>{viewedDocument?.title}</SheetTitle>
              {viewDocumentId && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setReparseDialogOpen(true)}
                >
                  <RotateCw className="h-4 w-4 mr-2" />
                  Re-parse
                </Button>
              )}
            </div>
          </SheetHeader>
          <div className="mt-6 space-y-6">
            {viewDocumentId && (
              <section>
                <h3 className="text-sm font-medium mb-2">Parse runs</h3>
                <RunTimeline
                  documentId={viewDocumentId}
                  runs={parseRuns}
                  onReparse={() => setReparseDialogOpen(true)}
                />
              </section>
            )}
            {viewDocumentId && (
              <ParsedDocumentViewer documentId={viewDocumentId} />
            )}
            {viewDocumentId && parseResults.length > 0 && (
              <ParseResultViewer documentId={viewDocumentId} />
            )}
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
        folders={folders}
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
        folders={folders}
        initialFolderId={selectedFolderId}
      />

      {/* Bulk Upload Dialog */}
      <DocumentUploadDialog
        open={bulkUploadOpen}
        onOpenChange={setBulkUploadOpen}
        onUpload={handleUpload}
        onBulkUpload={handleBulkUpload}
        documents={documents}
        projectId={currentProject.id}
        mode="bulk"
        folders={folders}
        initialFolderId={selectedFolderId}
      />

      {/* Re-parse Dialog */}
      <ReParseDialog
        open={reparseDialogOpen}
        onOpenChange={setReparseDialogOpen}
        onReparse={handleReparse}
      />
    </div>
  )
}
