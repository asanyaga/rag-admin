import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Tags, Search, FileText, Plus } from 'lucide-react'
import { useProject } from '@/contexts/ProjectContext'
import { useDocuments } from '@/hooks/useDocuments'
import { useFolders } from '@/hooks/useFolders'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { DocumentStatusBadge } from '@/components/documents/DocumentStatusBadge'
import { DocumentUploadDialog } from '@/components/documents/DocumentUploadDialog'
import { ClassificationRunHistory } from '@/components/classification/ClassificationRunHistory'
import { ClassificationRunSheet } from '@/components/classification/ClassificationRunSheet'
import { cn } from '@/lib/utils'

export default function ClassificationPage(): JSX.Element {
  const navigate = useNavigate()
  const { currentProject } = useProject()
  const projectId = currentProject?.id ?? null

  const [searchParams, setSearchParams] = useSearchParams()
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(
    searchParams.get('documentId'),
  )
  const [selectedFolderId, setSelectedFolderId] = useState<string | null>(null)
  const [documentSearch, setDocumentSearch] = useState('')
  const [uploadOpen, setUploadOpen] = useState(false)
  const [sheetOpen, setSheetOpen] = useState(false)

  const { documents, isLoading, uploadDocument } = useDocuments(projectId, undefined, selectedFolderId)
  const { folders } = useFolders(projectId)

  const filtered = documents.filter((doc) =>
    doc.title.toLowerCase().includes(documentSearch.toLowerCase()),
  )

  const selectedDocument = documents.find((d) => d.id === selectedDocumentId)

  const handleSelectDocument = (docId: string) => {
    setSelectedDocumentId(docId)
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      next.set('documentId', docId)
      return next
    })
  }

  const handleSelectRun = (runId: string) => {
    navigate(`/classify/${runId}`)
  }

  const handleRunStarted = (runId: string) => {
    setSheetOpen(false)
    navigate(`/classify/${runId}`)
  }

  return (
    <div className="-m-6 flex flex-col h-[calc(100vh-3.5rem)]">
      {/* Header */}
      <div className="px-6 py-3 border-b shrink-0">
        <h1 className="text-lg font-semibold">Classify</h1>
        <p className="text-xs text-muted-foreground">{currentProject?.name}</p>
      </div>

      {/* Body */}
      <div className="flex flex-1 min-h-0">
        {/* Left: document picker (Parse-style) */}
        <div className="w-72 border-r shrink-0 flex flex-col">
          {/* Folder filter */}
          <div className="p-3 border-b">
            <Select
              value={selectedFolderId ?? '__all__'}
              onValueChange={(v) => {
                setSelectedFolderId(v === '__all__' ? null : v)
                setSelectedDocumentId(null)
              }}
            >
              <SelectTrigger className="h-8 text-sm">
                <SelectValue placeholder="All folders" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__all__">All folders</SelectItem>
                {folders.map((f) => (
                  <SelectItem key={f.id} value={f.id}>{f.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
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
              {isLoading ? (
                <div className="space-y-2 p-2">
                  {[0, 1, 2].map((i) => <Skeleton key={i} className="h-10 w-full" />)}
                </div>
              ) : filtered.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-8">
                  {documentSearch ? 'No documents match your search' : 'No documents yet'}
                </p>
              ) : (
                filtered.map((doc) => (
                  <button
                    key={doc.id}
                    onClick={() => handleSelectDocument(doc.id)}
                    className={cn(
                      'w-full text-left rounded-md px-3 py-2.5 mb-1 transition-colors',
                      'hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                      selectedDocumentId === doc.id && 'bg-muted',
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

          {/* Upload */}
          <div className="p-3 border-t">
            <Button
              variant="outline"
              className="w-full"
              size="sm"
              onClick={() => setUploadOpen(true)}
            >
              <Plus className="h-4 w-4 mr-2" />
              Upload New
            </Button>
          </div>
        </div>

        {/* Right: run history */}
        <div className="flex-1 min-h-0 overflow-y-auto">
          {!selectedDocumentId ? (
            <div className="flex flex-col items-center justify-center h-full text-center px-6">
              <Tags className="h-12 w-12 text-muted-foreground/40 mb-4" />
              <h2 className="text-lg font-medium text-muted-foreground">
                Select a document to get started
              </h2>
              <p className="text-sm text-muted-foreground/70 mt-1 max-w-sm">
                Choose a document from the list to see its classification history.
              </p>
            </div>
          ) : (
            <ClassificationRunHistory
              documentId={selectedDocumentId}
              selectedRunId={null}
              onSelectRun={handleSelectRun}
              onNewRun={() => setSheetOpen(true)}
            />
          )}
        </div>
      </div>

      {currentProject && (
        <DocumentUploadDialog
          open={uploadOpen}
          onOpenChange={setUploadOpen}
          onUpload={uploadDocument}
          projectId={currentProject.id}
          documents={documents}
          folders={folders}
        />
      )}

      {selectedDocumentId && (
        <ClassificationRunSheet
          open={sheetOpen}
          onOpenChange={setSheetOpen}
          documentId={selectedDocumentId}
          documentTitle={selectedDocument?.title ?? ''}
          onStarted={handleRunStarted}
        />
      )}
    </div>
  )
}
