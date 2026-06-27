import { useState, useEffect, useCallback, useRef } from 'react'
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
  RunWithParseRequest,
} from '@/types/extraction'
import type { ParseConfig } from '@/types/parsing'
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
import { exportResultToCsv } from '@/lib/exportCsv'

export default function ExtractionPage(): JSX.Element {
  const { currentProject } = useProject()
  const projectId = currentProject?.id || null

  const { documents, isLoading: documentsLoading, uploadDocument } = useDocuments(projectId)
  const { schemas, error: schemasError, createSchema, updateSchema, deleteSchema } = useExtractionSchemas(projectId)

  const [searchParams, setSearchParams] = useSearchParams()
  const preselectedDocumentId = searchParams.get('documentId')
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(preselectedDocumentId)

  const {
    results,
    selectedResult,
    isLoading: resultsLoading,
    isLoadingResult,
    error: resultsError,
    extractionPhase,
    phaseError,
    selectResult,
    clearSelection,
    deleteResult,
    runExtractionWithParse,
  } = useExtractionResults(selectedDocumentId)

  const { parseRuns, isLoading: parseRunsLoading } = useParseRuns(selectedDocumentId)

  // Latest viable parse run drives form defaults
  const latestViableRun = parseRuns.find((r) => r.status === 'succeeded' || r.status === 'partial')

  // Strip the backend-added "parser" key from config before passing as default
  const defaultParser: string = latestViableRun?.parser ?? 'simple'
  const defaultParserConfig: ParseConfig = (() => {
    if (!latestViableRun?.config) return {}
    const config = { ...(latestViableRun.config as Record<string, unknown>) }
    delete config['parser']
    return config as ParseConfig
  })()

  const [extractors, setExtractors] = useState<ExtractorInfo[]>([])
  const [schemaEditorOpen, setSchemaEditorOpen] = useState(false)
  const [editingSchema, setEditingSchema] = useState<ExtractionSchema | null>(null)
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false)

  // Store last request for retry after parse failure
  const lastRequestRef = useRef<RunWithParseRequest | null>(null)

  const fetchExtractors = useCallback(async () => {
    try {
      const data = await extractionApi.listExtractors()
      setExtractors(data)
    } catch {
      // Extractors not available
    }
  }, [])

  useEffect(() => { fetchExtractors() }, [fetchExtractors])

  const handleSelectDocument = (docId: string) => {
    setSelectedDocumentId(docId)
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      next.set('documentId', docId)
      return next
    })
  }

  const handleCreateSchema = () => { setEditingSchema(null); setSchemaEditorOpen(true) }
  const handleEditSchema = (schema: ExtractionSchema) => { setEditingSchema(schema); setSchemaEditorOpen(true) }

  const handleDeleteSchema = async (schemaId: string) => {
    try {
      await deleteSchema(schemaId)
      toast.success('Schema deleted')
    } catch (err) {
      toast.error('Failed to delete schema', { description: err instanceof Error ? err.message : 'An error occurred' })
    }
  }

  const handleSaveSchema = async (data: ExtractionSchemaCreate | ExtractionSchemaUpdate) => {
    try {
      if (editingSchema) {
        await updateSchema(editingSchema.id, data as ExtractionSchemaUpdate)
        toast.success('Schema updated')
      } else {
        await createSchema(data as ExtractionSchemaCreate)
        toast.success('Schema created')
      }
    } catch (err) {
      toast.error('Failed to save schema', { description: err instanceof Error ? err.message : 'An error occurred' })
      throw err
    }
  }

  const handleRunExtraction = async (request: RunWithParseRequest) => {
    lastRequestRef.current = request
    await runExtractionWithParse(selectedDocumentId!, parseRuns, request)
  }

  const handleRetry = async () => {
    if (lastRequestRef.current && selectedDocumentId) {
      await runExtractionWithParse(selectedDocumentId, parseRuns, lastRequestRef.current)
    }
  }

  const handleExportResult = async (resultId: string) => {
    try {
      const result =
        selectedResult?.id === resultId
          ? selectedResult
          : await extractionApi.getExtractionResult(resultId)
      if (!result.structuredData || Object.keys(result.structuredData).length === 0) return
      const schema = schemas?.find((s) => s.id === result.extractionSchemaId)
      const filename = `${schema?.name ?? 'extraction'}_${resultId.slice(0, 8)}.csv`
      exportResultToCsv(result.structuredData, filename)
    } catch {
      toast.error('Failed to fetch result for export')
    }
  }

  const handleUpload = async (data: DocumentUpload): Promise<AppDocument> => {
    const newDoc = await uploadDocument(data)
    toast.success('Document uploaded', { description: newDoc.status === 'processing' ? 'Processing in progress...' : undefined })
    handleSelectDocument(newDoc.id)
    return newDoc
  }

  if (!currentProject) {
    return (
      <div className="space-y-6">
        <Alert><AlertDescription>Loading project...</AlertDescription></Alert>
      </div>
    )
  }

  const selectedDocument = documents.find((d) => d.id === selectedDocumentId)
  const isDocumentReady = selectedDocument?.status === 'ready'

  const inProgressPhase =
    extractionPhase === 'parsing' || extractionPhase === 'extracting'
      ? { phase: extractionPhase as 'parsing' | 'extracting' }
      : extractionPhase === 'failed' && phaseError
        ? { phase: 'failed' as const, phaseError, onRetry: handleRetry }
        : undefined

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
        {/* Left panel */}
        <div className="w-72 border-r shrink-0 flex flex-col">
          <DocumentSelector
            documents={documents}
            isLoading={documentsLoading}
            selectedDocumentId={selectedDocumentId}
            onSelect={handleSelectDocument}
            onUploadClick={() => setUploadDialogOpen(true)}
          />
        </div>

        {/* Right panel */}
        <div className="flex-1 overflow-y-auto">
          {!selectedDocumentId ? (
            <div className="flex flex-col items-center justify-center h-full text-center px-6">
              <FileSearch className="h-12 w-12 text-muted-foreground/40 mb-4" />
              <h2 className="text-lg font-medium text-muted-foreground">Select a document to get started</h2>
              <p className="text-sm text-muted-foreground/70 mt-1 max-w-sm">
                Choose a document from the list, or upload a new one to begin extracting structured data.
              </p>
            </div>
          ) : (
            <div className="p-6 space-y-6 max-w-3xl">
              <SchemaManager schemas={schemas} onEdit={handleEditSchema} onDelete={handleDeleteSchema} onCreate={handleCreateSchema} />

              <Separator />

              {selectedDocument && (
                <div className="flex items-center gap-3">
                  <h2 className="text-base font-medium truncate">{selectedDocument.title}</h2>
                  <Badge
                    variant={selectedDocument.status === 'ready' ? 'outline' : selectedDocument.status === 'processing' ? 'secondary' : 'destructive'}
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
                <h3 className="text-sm font-medium mb-3">Run New Extraction</h3>
                {!isDocumentReady ? (
                  <div className="rounded-lg border border-dashed p-4 text-center text-sm text-muted-foreground">
                    {selectedDocument?.status === 'processing'
                      ? 'Document is still processing. Extraction will be available once it completes.'
                      : 'This document cannot be used for extraction.'}
                  </div>
                ) : parseRunsLoading ? (
                  <div className="rounded-lg border border-dashed p-4 text-center text-sm text-muted-foreground">
                    Loading...
                  </div>
                ) : (
                  <div className="rounded-lg border p-4">
                    <ExtractionForm
                      defaultParser={defaultParser}
                      defaultParserConfig={defaultParserConfig}
                      schemas={schemas}
                      extractors={extractors}
                      onRun={handleRunExtraction}
                      onEditSchema={handleEditSchema}
                    />
                  </div>
                )}
              </div>

              <Separator />

              {/* Previous Extractions */}
              <div>
                <h3 className="text-sm font-medium mb-3">
                  Previous Extractions
                  {results.length > 0 && (
                    <span className="text-muted-foreground font-normal ml-1.5">({results.length})</span>
                  )}
                </h3>
                <ExtractionHistory
                  results={results}
                  isLoading={resultsLoading}
                  selectedResult={selectedResult}
                  isLoadingResult={isLoadingResult}
                  schemas={schemas}
                  onSelectResult={selectResult}
                  onDeselectResult={clearSelection}
                  onDeleteResult={deleteResult}
                  onExportResult={handleExportResult}
                  inProgressPhase={inProgressPhase}
                  projectId={projectId ?? undefined}
                />
              </div>
            </div>
          )}
        </div>
      </div>

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
