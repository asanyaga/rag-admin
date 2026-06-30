import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useProject } from '@/contexts/ProjectContext'
import { useDocuments } from '@/hooks/useDocuments'
import { useFolders } from '@/hooks/useFolders'
import { useExtractionSchemas } from '@/hooks/useExtractionSchemas'
import { useExtractionResults } from '@/hooks/useExtractionResults'
import type {
  ExtractionSchema,
  ExtractionSchemaCreate,
  ExtractionSchemaUpdate,
} from '@/types/extraction'
import type { Document as AppDocument, DocumentListItem, DocumentUpload } from '@/types/document'
import { DocumentPickerPanel } from '@/components/shared/DocumentPickerPanel'
import { ExtractionHistory } from '@/components/extraction/ExtractionHistory'
import { SchemaManager } from '@/components/extraction/SchemaManager'
import { ExtractionSchemaEditor } from '@/components/extraction/ExtractionSchemaEditor'
import { DocumentUploadDialog } from '@/components/documents/DocumentUploadDialog'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { FileSearch, Plus } from 'lucide-react'
import { toast } from 'sonner'
import * as extractionApi from '@/api/extraction'
import { exportResultToCsv } from '@/lib/exportCsv'

export default function ExtractionPage(): JSX.Element {
  const navigate = useNavigate()
  const { currentProject } = useProject()
  const projectId = currentProject?.id ?? null

  const [searchParams, setSearchParams] = useSearchParams()
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(
    searchParams.get('documentId'),
  )
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false)
  const [schemaEditorOpen, setSchemaEditorOpen] = useState(false)
  const [editingSchema, setEditingSchema] = useState<ExtractionSchema | null>(null)

  const { documents, isLoading: documentsLoading, uploadDocument } = useDocuments(projectId)
  const { folders } = useFolders(projectId)
  const { schemas, error: schemasError, createSchema, updateSchema, deleteSchema } =
    useExtractionSchemas(projectId)
  const { results, isLoading: resultsLoading, deleteResult } =
    useExtractionResults(selectedDocumentId)

  const handleSelectDocument = (docId: string) => {
    setSelectedDocumentId(docId)
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      next.set('documentId', docId)
      return next
    })
  }

  const handleNewRun = () => {
    if (!selectedDocumentId) return
    navigate(`/extract/new?documentId=${selectedDocumentId}`, {
      state: { documentTitle: selectedDocument?.title },
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
        description: err instanceof Error ? err.message : undefined,
      })
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
      toast.error('Failed to save schema', {
        description: err instanceof Error ? err.message : undefined,
      })
      throw err
    }
  }

  const handleExportResult = async (resultId: string) => {
    try {
      const result = await extractionApi.getExtractionResult(resultId)
      if (!result.structuredData || Object.keys(result.structuredData).length === 0) return
      const schema = schemas?.find((s) => s.id === result.extractionSchemaId)
      exportResultToCsv(
        result.structuredData,
        `${schema?.name ?? 'extraction'}_${resultId.slice(0, 8)}.csv`,
      )
    } catch {
      toast.error('Failed to fetch result for export')
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
      <div className="p-6">
        <Alert>
          <AlertDescription>Loading project...</AlertDescription>
        </Alert>
      </div>
    )
  }

  const selectedDocument = documents.find((d) => d.id === selectedDocumentId) as
    | DocumentListItem
    | undefined

  return (
    <div className="-m-6 flex flex-col h-[calc(100vh-3.5rem)]">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-3 border-b shrink-0">
        <div>
          <h1 className="text-lg font-semibold">Extract</h1>
          <p className="text-xs text-muted-foreground">{currentProject.name}</p>
        </div>
      </div>

      {schemasError && (
        <div className="px-6 pt-3 shrink-0">
          <Alert variant="destructive">
            <AlertDescription>{schemasError}</AlertDescription>
          </Alert>
        </div>
      )}

      {/* Two-panel layout */}
      <div className="flex flex-1 min-h-0">
        {/* Left: document picker */}
        <div className="w-72 border-r shrink-0 flex flex-col">
          <DocumentPickerPanel
            documents={documents}
            folders={folders}
            isLoading={documentsLoading}
            selectedDocumentId={selectedDocumentId}
            onSelect={handleSelectDocument}
            onUploadClick={() => setUploadDialogOpen(true)}
          />
        </div>

        {/* Right: schema + history */}
        <div className="flex-1 overflow-y-auto">
          {!selectedDocumentId ? (
            <div className="flex flex-col items-center justify-center h-full text-center px-6">
              <FileSearch className="h-12 w-12 text-muted-foreground/40 mb-4" />
              <h2 className="text-lg font-medium text-muted-foreground">
                Select a document to get started
              </h2>
              <p className="text-sm text-muted-foreground/70 mt-1 max-w-sm">
                Choose a document from the list, or upload a new one to begin extracting structured
                data.
              </p>
            </div>
          ) : (
            <div className="p-6 space-y-6 max-w-3xl">
              <SchemaManager
                schemas={schemas}
                onEdit={handleEditSchema}
                onDelete={handleDeleteSchema}
                onCreate={handleCreateSchema}
              />

              <Separator />

              {selectedDocument && (
                <div className="flex items-center gap-3">
                  <h2 className="text-base font-medium truncate">{selectedDocument.title}</h2>
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
                </div>
              )}

              <Button
                size="sm"
                onClick={handleNewRun}
                disabled={
                  (documentsLoading && !selectedDocument) ||
                  selectedDocument?.status === 'processing'
                }
              >
                <Plus className="h-4 w-4 mr-1.5" />
                New Run
              </Button>

              <Separator />

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
                  schemas={schemas}
                  onDeleteResult={deleteResult}
                  onExportResult={handleExportResult}
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
        projectId={projectId ?? ''}
        documents={documents}
        folders={folders}
      />
    </div>
  )
}
