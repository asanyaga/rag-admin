import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useProject } from '@/contexts/ProjectContext'
import { useDocuments } from '@/hooks/useDocuments'
import { useFolders } from '@/hooks/useFolders'
import { DocumentListItem } from '@/types/document'
import { FolderCreate } from '@/types/folder'
import type { ParseConfig } from '@/types/parsing'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { ScrollArea } from '@/components/ui/scroll-area'
import { DocumentTextViewer } from '@/components/documents/DocumentTextViewer'
import { DocumentEditDialog } from '@/components/documents/DocumentEditDialog'
import { DocumentDeleteDialog } from '@/components/documents/DocumentDeleteDialog'
import { DocumentUploadDialog } from '@/components/documents/DocumentUploadDialog'
import { ParsedDocumentViewer } from '@/components/documents/ParsedDocumentViewer'
import { ReParseDialog } from '@/components/documents/ReParseDialog'
import { DocumentProbePanel } from '@/components/documents/DocumentProbePanel'
import { DocumentStatusBadge } from '@/components/documents/DocumentStatusBadge'
import { FolderEditPopover } from '@/components/documents/FolderEditPopover'
import { SourceDocumentBrowser } from '@/components/documents/SourceDocumentBrowser'
import { RunTimeline } from '@/components/parse-runs/RunTimeline'
import { useParseRuns } from '@/hooks/useParseRuns'
import { useDocumentProbe } from '@/hooks/useDocumentProbe'
import {
  Plus,
  RotateCw,
  ScanSearch,
  Search,
  Library,
  FileText,
  Settings,
  MoreHorizontal,
  Pencil,
  Trash2,
  Download,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { toast } from 'sonner'
import { createParseRun } from '@/api/parseRuns'

export default function DocumentsPage(): JSX.Element {
  const { currentProject } = useProject()
  const [searchParams] = useSearchParams()

  const [selectedFolderId, setSelectedFolderId] = useState<string | null>(null)
  const [documentSearch, setDocumentSearch] = useState('')
  const [fromSourceOpen, setFromSourceOpen] = useState(false)
  const [viewDocumentId, setViewDocumentId] = useState<string | null>(
    searchParams.get('documentId'),
  )

  const {
    documents,
    isLoading,
    error,
    uploadDocument,
    addDocumentFromSource,
    updateDocument,
    deleteDocument,
    downloadDocument,
  } = useDocuments(currentProject?.id || null, undefined, selectedFolderId)

  const {
    folders,
    createFolder,
    updateFolder,
    deleteFolder,
  } = useFolders(currentProject?.id || null)

  const [uploadDialogOpen, setUploadDialogOpen] = useState(false)
  const [editDialogOpen, setEditDialogOpen] = useState(false)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [selectedDocument, setSelectedDocument] = useState<DocumentListItem | null>(null)
  const [reparseDialogOpen, setReparseDialogOpen] = useState(false)

  const { parseRuns, refresh: refreshParseRuns } = useParseRuns(viewDocumentId)

  const { profile: probeProfile, isLoading: probeLoading, error: probeError, runProbe, reset: resetProbe } = useDocumentProbe(viewDocumentId)

  useEffect(() => {
    resetProbe()
  }, [viewDocumentId, resetProbe])

  if (!currentProject) {
    return (
      <div className="space-y-6">
        <Alert>
          <AlertDescription>Loading project...</AlertDescription>
        </Alert>
      </div>
    )
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
      if (viewDocumentId === documentId) setViewDocumentId(null)
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

  const handleReparse = async (parserType: string, config?: ParseConfig) => {
    if (!viewDocumentId) return
    try {
      await createParseRun(viewDocumentId, parserType, config)
      toast.success('Re-parse started', { description: 'Parsing is in progress' })
      refreshParseRuns()
    } catch (err) {
      toast.error('Re-parse failed', {
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

  void handleUpdateFolder
  void handleDeleteFolder

  const viewedDocument = documents.find((d) => d.id === viewDocumentId)

  const filteredDocuments = documents.filter((doc) => {
    const matchesFolder = selectedFolderId === null || doc.folderId === selectedFolderId
    const matchesSearch = doc.title.toLowerCase().includes(documentSearch.toLowerCase())
    return matchesFolder && matchesSearch
  })

  const existingSourceIds = new Set(
    documents.flatMap((d) => (d.sourceDocumentId ? [d.sourceDocumentId] : [])),
  )

  const handleFromSourceAdd = async (
    sourceDocumentId: string,
    parserType: string,
    parseConfig?: ParseConfig,
  ) => {
    const doc = await addDocumentFromSource({
      projectId: currentProject.id,
      sourceDocumentId,
      parserType,
      parseConfig,
    })
    setViewDocumentId(doc.id)
  }

  return (
    <div className="-m-6 flex h-[calc(100vh-3.5rem)]">
      {/* Left panel */}
      <div className="w-72 border-r shrink-0 flex flex-col">
        {/* Folder filter + management */}
        <div className="p-3 border-b flex items-center gap-2">
          <Select
            value={selectedFolderId ?? '__all__'}
            onValueChange={(v) => {
              setSelectedFolderId(v === '__all__' ? null : v)
              setViewDocumentId(null)
            }}
          >
            <SelectTrigger className="h-8 text-sm flex-1">
              <SelectValue placeholder="All folders" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__all__">All folders</SelectItem>
              {folders.map((f) => (
                <SelectItem key={f.id} value={f.id}>{f.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <FolderEditPopover
            trigger={
              <Button variant="ghost" size="icon" className="h-8 w-8 shrink-0">
                <Settings className="h-3.5 w-3.5" />
              </Button>
            }
            onSave={handleCreateFolder}
          />
        </div>

        {/* Search */}
        <div className="p-3 border-b">
          <div className="relative">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search documents..."
              value={documentSearch}
              onChange={(e) => setDocumentSearch(e.target.value)}
              className="pl-9 h-9"
            />
          </div>
        </div>

        {/* Document list */}
        <ScrollArea className="flex-1">
          <div className="p-2">
            {error && (
              <p className="text-xs text-destructive text-center py-4">{error}</p>
            )}
            {isLoading ? (
              <div className="space-y-2 p-2">
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
              </div>
            ) : filteredDocuments.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-8">
                {documentSearch ? 'No documents match your search' : 'No documents yet'}
              </p>
            ) : (
              filteredDocuments.map((doc) => (
                <button
                  key={doc.id}
                  onClick={() => setViewDocumentId(doc.id)}
                  className={cn(
                    'w-full text-left rounded-md px-3 py-2.5 mb-1 transition-colors',
                    'hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                    viewDocumentId === doc.id && 'bg-muted',
                  )}
                >
                  <div className="flex items-center gap-2">
                    <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
                    <span className="text-sm truncate flex-1">{doc.title}</span>
                    <DocumentStatusBadge status={doc.status} />
                  </div>
                </button>
              ))
            )}
          </div>
        </ScrollArea>

        {/* Actions */}
        <div className="p-3 border-t space-y-2">
          <Button
            variant="outline"
            className="w-full"
            size="sm"
            onClick={() => setUploadDialogOpen(true)}
          >
            <Plus className="h-4 w-4 mr-2" />
            Upload New
          </Button>
          <Button
            variant="outline"
            className="w-full"
            size="sm"
            onClick={() => setFromSourceOpen(true)}
          >
            <Library className="h-4 w-4 mr-2" />
            From Source
          </Button>
        </div>
      </div>

      {/* Right panel */}
      <div className="flex-1 overflow-y-auto">
        {!viewDocumentId ? (
          <div className="flex items-center justify-center h-full text-muted-foreground">
            <p className="text-sm">Select a document to view parse runs</p>
          </div>
        ) : (
          <div className="p-6 space-y-6 max-w-3xl">
            {/* Document header with actions */}
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold">{viewedDocument?.title}</h2>
                {viewedDocument && (
                  <p className="text-xs text-muted-foreground">
                    {new Date(viewedDocument.createdAt).toLocaleDateString()}
                  </p>
                )}
              </div>
              <div className="flex items-center gap-1">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={runProbe}
                  disabled={probeLoading}
                  title="Probe document"
                >
                  <ScanSearch className="h-4 w-4 mr-1.5" />
                  {probeLoading ? 'Probing…' : 'Probe'}
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setReparseDialogOpen(true)}
                  title="Re-parse document"
                >
                  <RotateCw className="h-4 w-4 mr-1.5" />
                  Re-parse
                </Button>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="ghost" size="icon">
                      <MoreHorizontal className="h-4 w-4" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem onClick={() => handleEdit(viewDocumentId)}>
                      <Pencil className="h-4 w-4 mr-2" />
                      Edit
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      onClick={() =>
                        viewedDocument &&
                        handleDownload(viewedDocument.id, viewedDocument.title)
                      }
                    >
                      <Download className="h-4 w-4 mr-2" />
                      Download
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem
                      className="text-destructive focus:text-destructive"
                      onClick={() => handleDelete(viewDocumentId)}
                    >
                      <Trash2 className="h-4 w-4 mr-2" />
                      Delete
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            </div>

            <DocumentProbePanel profile={probeProfile} isLoading={probeLoading} error={probeError} onClear={resetProbe} />

            <section>
              <h3 className="text-sm font-medium mb-2">Parse runs</h3>
              <RunTimeline
                documentId={viewDocumentId}
                runs={parseRuns}
                onRunDeleted={refreshParseRuns}
              />
            </section>

            <ParsedDocumentViewer documentId={viewDocumentId} />

            {viewedDocument && (
              <DocumentTextViewer
                documentId={viewDocumentId}
                documentTitle={viewedDocument.title}
                onDownload={() => handleDownload(viewDocumentId, viewedDocument.title)}
              />
            )}
          </div>
        )}
      </div>

      {/* Dialogs */}
      <DocumentEditDialog
        document={selectedDocument}
        open={editDialogOpen}
        onOpenChange={setEditDialogOpen}
        onSave={handleEditSave}
        folders={folders}
      />
      <DocumentDeleteDialog
        document={selectedDocument}
        open={deleteDialogOpen}
        onOpenChange={setDeleteDialogOpen}
        onConfirm={handleDeleteConfirm}
      />
      <DocumentUploadDialog
        open={uploadDialogOpen}
        onOpenChange={setUploadDialogOpen}
        projectId={currentProject.id}
        onUpload={uploadDocument}
        documents={documents}
        folders={folders}
        initialFolderId={selectedFolderId}
      />
      <ReParseDialog
        open={reparseDialogOpen}
        onOpenChange={setReparseDialogOpen}
        onReparse={handleReparse}
      />
      <SourceDocumentBrowser
        open={fromSourceOpen}
        onOpenChange={setFromSourceOpen}
        existingSourceDocumentIds={existingSourceIds}
        onAdd={handleFromSourceAdd}
      />
    </div>
  )
}
