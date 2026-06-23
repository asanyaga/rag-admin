import { useState, useEffect, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useProject } from '@/contexts/ProjectContext'
import { useDocuments } from '@/hooks/useDocuments'
import { useExtractionSchemas } from '@/hooks/useExtractionSchemas'
import { useExtractionResults } from '@/hooks/useExtractionResults'
import { useParseRuns } from '@/hooks/useParseRuns'
import type {
  ExtractionSchema,
  ExtractionSchemaCreate,
  ExtractionSchemaUpdate,
  ExtractorInfo,
  RunExtractionRequest,
} from '@/types/extraction'
import type { Document as AppDocument, DocumentUpload } from '@/types/document'
import { ExtractionSchemaEditor } from '@/components/extraction/ExtractionSchemaEditor'
import { ExtractionForm } from '@/components/extraction/ExtractionForm'
import { ExtractionHistory } from '@/components/extraction/ExtractionHistory'
import { SchemaManager } from '@/components/extraction/SchemaManager'
import { DocumentSelector } from '@/components/extraction/DocumentSelector'
import { DocumentUploadDialog } from '@/components/documents/DocumentUploadDialog'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { FileSearch } from 'lucide-react'
import { toast } from 'sonner'
import * as extractionApi from '@/api/extraction'

export default function ExtractionPage(): JSX.Element {
  const { currentProject } = useProject()
  const projectId = currentProject?.id || null

  const {
    documents,
    isLoading: documentsLoading,
    uploadDocument,
  } = useDocuments(projectId)
  const {
    schemas,
    error: schemasError,
    createSchema,
    updateSchema,
    deleteSchema,
  } = useExtractionSchemas(projectId)

  const [searchParams, setSearchParams] = useSearchParams()
  const preselectedDocumentId = searchParams.get('documentId')

  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(
    preselectedDocumentId
  )
  const {
    results,
    selectedResult,
    isLoading: resultsLoading,
    isLoadingResult,
    error: resultsError,
    selectResult,
    runExtraction,
  } = useExtractionResults(selectedDocumentId)

  const { parseRuns, isLoading: parseRunsLoading } = useParseRuns(selectedDocumentId)
  const latestViableRun = parseRuns.find(
    (r) => r.status === 'succeeded' || r.status === 'partial'
  )

  const [extractors, setExtractors] = useState<ExtractorInfo[]>([])
  const [schemaEditorOpen, setSchemaEditorOpen] = useState(false)
  const [editingSchema, setEditingSchema] = useState<ExtractionSchema | null>(null)
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false)

  const fetchExtractors = useCallback(async () => {
    try {
      const data = await extractionApi.listExtractors()
      setExtractors(data)
    } catch {
      // Extractors not available
    }
  }, [])

  useEffect(() => {
    fetchExtractors()
  }, [fetchExtractors])

  const handleSelectDocument = (docId: string) => {
    setSelectedDocumentId(docId)
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      next.set('documentId', docId)
      return next
    })
  }

  const handleCreateSchema = () => {
    setEditingSchema(null)
    setSchemaEditorOpen(true)
  }

  const handleEditSchema = (schema: ExtractionSchema) => {
    setEditingSchema(schema)
    setSchemaEditorOpen(true)
  }

  const handleDeleteSchema = async (schemaId: string) => {
    try {
      await deleteSchema(schemaId)
      toast.success('Schema deleted')
    } catch (err) {
      toast.error('Failed to delete schema', {
        description: err instanceof Error ? err.message : 'An error occurred',
      })
    }
  }

  const handleSaveSchema = async (
    data: ExtractionSchemaCreate | ExtractionSchemaUpdate
  ) => {
    try {
      if (editingSchema) {
        await updateSchema(editingSchema.id, data as ExtractionSchemaUpdate)
        toast.success('Schema updated')
      } else {
        await createSchema(data as ExtractionSchemaCreate)
        toast.success('Schema created')
      }
    } catch (err) {
      toast.error('Failed to save schema', {
        description: err instanceof Error ? err.message : 'An error occurred',
      })
      throw err
    }
  }

  const handleRunExtraction = async (request: RunExtractionRequest) => {
    try {
      await runExtraction(request)
      toast.success('Extraction started', {
        description: 'Processing is in progress',
      })
    } catch (err) {
      toast.error('Extraction failed', {
        description: err instanceof Error ? err.message : 'An error occurred',
      })
      throw err
    }
  }

  const handleUpload = async (data: DocumentUpload): Promise<AppDocument> => {
    const newDoc = await uploadDocument(data)
    toast.success('Document uploaded', {
      description: newDoc.status === 'processing' ? 'Processing in progress...' : undefined,
    })
    handleSelectDocument(newDoc.id)
    return newDoc
  }

  if (!currentProject) {
    return (
      <div className="space-y-6">
        <Alert>
          <AlertDescription>Loading project...</AlertDescription>
        </Alert>
      </div>
    )
  }

  const selectedDocument = documents.find((d) => d.id === selectedDocumentId)
  const isDocumentReady = selectedDocument?.status === 'ready'

  return (
    <div className="-m-6 flex flex-col h-[calc(100vh-3.5rem)]">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-3 border-b shrink-0">
        <div>
          <h1 className="text-lg font-semibold">Extraction</h1>
          <p className="text-xs text-muted-foreground">{currentProject.name}</p>
        </div>
      </div>

      {/* Errors */}
      {(schemasError || resultsError) && (
        <div className="px-6 pt-3 shrink-0">
          <Alert variant="destructive">
            <AlertDescription>{schemasError || resultsError}</AlertDescription>
          </Alert>
        </div>
      )}

      {/* Two-panel layout */}
      <div className="flex flex-1 min-h-0">
        {/* Left panel: Document selector */}
        <div className="w-72 border-r shrink-0 flex flex-col">
          <DocumentSelector
            documents={documents}
            isLoading={documentsLoading}
            selectedDocumentId={selectedDocumentId}
            onSelect={handleSelectDocument}
            onUploadClick={() => setUploadDialogOpen(true)}
          />
        </div>

        {/* Right panel: Extraction workspace */}
        <div className="flex-1 overflow-y-auto">
          {!selectedDocumentId ? (
            /* Empty state */
            <div className="flex flex-col items-center justify-center h-full text-center px-6">
              <FileSearch className="h-12 w-12 text-muted-foreground/40 mb-4" />
              <h2 className="text-lg font-medium text-muted-foreground">
                Select a document to get started
              </h2>
              <p className="text-sm text-muted-foreground/70 mt-1 max-w-sm">
                Choose a document from the list, or upload a new one to begin extracting structured data.
              </p>
            </div>
          ) : (
            <div className="p-6 space-y-6 max-w-3xl">
              {/* Schema management */}
              <SchemaManager
                schemas={schemas}
                onEdit={handleEditSchema}
                onDelete={handleDeleteSchema}
                onCreate={handleCreateSchema}
              />

              <Separator />

              {/* Document header */}
              {selectedDocument && (
                <div className="flex items-center gap-3">
                  <h2 className="text-base font-medium truncate">
                    {selectedDocument.title}
                  </h2>
                  <Badge
                    variant={
                      selectedDocument.status === 'ready'
                        ? 'outline'
                        : selectedDocument.status === 'processing'
                          ? 'secondary'
                          : 'destructive'
                    }
                    className="shrink-0 text-xs"
                  >
                    {selectedDocument.status}
                  </Badge>
                  <span className="text-xs text-muted-foreground shrink-0">
                    Uploaded {new Date(selectedDocument.createdAt).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                  </span>
                </div>
              )}

              {/* Run New Extraction */}
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <h3 className="text-sm font-medium">Run New Extraction</h3>
                  {(!isDocumentReady || (!parseRunsLoading && !latestViableRun)) && selectedDocument && (
                    <span className="text-xs text-muted-foreground">
                      {isDocumentReady ? '(parse document first)' : '(document must be ready)'}
                    </span>
                  )}
                </div>
                {isDocumentReady ? (
                  parseRunsLoading ? (
                    <div className="rounded-lg border border-dashed p-4 text-center text-sm text-muted-foreground">
                      Loading...
                    </div>
                  ) : latestViableRun ? (
                    <div className="rounded-lg border p-4">
                      <ExtractionForm
                        parseRunId={latestViableRun.id}
                        schemas={schemas}
                        extractors={extractors}
                        onRun={handleRunExtraction}
                        onEditSchema={handleEditSchema}
                      />
                    </div>
                  ) : (
                    <div className="rounded-lg border border-dashed p-4 text-center text-sm text-muted-foreground">
                      Parse the document first to enable extraction.
                    </div>
                  )
                ) : (
                  <div className="rounded-lg border border-dashed p-4 text-center text-sm text-muted-foreground">
                    {selectedDocument?.status === 'processing'
                      ? 'Document is still processing. Extraction will be available once it completes.'
                      : 'This document cannot be used for extraction.'}
                  </div>
                )}
              </div>

              <Separator />

              {/* Previous Extractions */}
              <div>
                <h3 className="text-sm font-medium mb-3">
                  Previous Extractions
                  {results.length > 0 && (
                    <span className="text-muted-foreground font-normal ml-1.5">
                      ({results.length})
                    </span>
                  )}
                </h3>
                <ExtractionHistory
                  results={results}
                  isLoading={resultsLoading}
                  selectedResult={selectedResult}
                  isLoadingResult={isLoadingResult}
                  onSelectResult={selectResult}
                />
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Dialogs */}
      <ExtractionSchemaEditor
        open={schemaEditorOpen}
        onOpenChange={setSchemaEditorOpen}
        schema={editingSchema}
        onSave={handleSaveSchema}
      />

      <DocumentUploadDialog
        open={uploadDialogOpen}
        onOpenChange={setUploadDialogOpen}
        onUpload={handleUpload}
        projectId={projectId || ''}
      />
    </div>
  )
}
