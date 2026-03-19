import { useState, useEffect, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useProject } from '@/contexts/ProjectContext'
import { useDocuments } from '@/hooks/useDocuments'
import { useExtractionSchemas } from '@/hooks/useExtractionSchemas'
import { useExtractionResults } from '@/hooks/useExtractionResults'
import type {
  ExtractionSchema,
  ExtractionSchemaCreate,
  ExtractionSchemaUpdate,
  ExtractorInfo,
  RunExtractionRequest,
} from '@/types/extraction'
import { ExtractionSchemaEditor } from '@/components/extraction/ExtractionSchemaEditor'
import { RunExtractionDialog } from '@/components/extraction/RunExtractionDialog'
import { ExtractionResultViewer } from '@/components/extraction/ExtractionResultViewer'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Plus, Play, MoreHorizontal, Pencil, Trash2, Eye } from 'lucide-react'
import { toast } from 'sonner'
import * as extractionApi from '@/api/extraction'

export default function ExtractionPage(): JSX.Element {
  const { currentProject } = useProject()
  const projectId = currentProject?.id || null

  const { documents } = useDocuments(projectId)
  const {
    schemas,
    isLoading: schemasLoading,
    error: schemasError,
    createSchema,
    updateSchema,
    deleteSchema,
  } = useExtractionSchemas(projectId)

  const [searchParams] = useSearchParams()
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

  const [extractors, setExtractors] = useState<ExtractorInfo[]>([])
  const [schemaEditorOpen, setSchemaEditorOpen] = useState(false)
  const [editingSchema, setEditingSchema] = useState<ExtractionSchema | null>(null)
  const [runDialogOpen, setRunDialogOpen] = useState(false)

  const fetchExtractors = useCallback(async () => {
    try {
      const data = await extractionApi.listExtractors()
      setExtractors(data)
    } catch {
      // Extractors not available — that's fine
    }
  }, [])

  useEffect(() => {
    fetchExtractors()
  }, [fetchExtractors])

  if (!currentProject) {
    return (
      <div className="space-y-6">
        <Alert>
          <AlertDescription>Loading project...</AlertDescription>
        </Alert>
      </div>
    )
  }

  const handleCreateSchema = () => {
    setEditingSchema(null)
    setSchemaEditorOpen(true)
  }

  const handleEditSchema = (schema: ExtractionSchema) => {
    setEditingSchema(schema)
    setSchemaEditorOpen(true)
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

  const handleDeleteSchema = async (schema: ExtractionSchema) => {
    try {
      await deleteSchema(schema.id)
      toast.success('Schema deleted')
    } catch (err) {
      toast.error('Failed to delete schema', {
        description: err instanceof Error ? err.message : 'An error occurred',
      })
    }
  }

  const handleRunExtraction = async (request: RunExtractionRequest) => {
    try {
      setSelectedDocumentId(request.documentId)
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

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Extraction</h1>
          <p className="text-muted-foreground mt-1">{currentProject.name}</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={handleCreateSchema}>
            <Plus className="h-4 w-4 mr-2" />
            New Schema
          </Button>
          <Button
            onClick={() => setRunDialogOpen(true)}
            disabled={schemas.length === 0 || extractors.length === 0}
          >
            <Play className="h-4 w-4 mr-2" />
            Run Extraction
          </Button>
        </div>
      </div>

      {/* Errors */}
      {(schemasError || resultsError) && (
        <Alert variant="destructive">
          <AlertDescription>{schemasError || resultsError}</AlertDescription>
        </Alert>
      )}

      {extractors.length === 0 && (
        <Alert>
          <AlertDescription>
            No extraction methods available. Please contact your administrator to configure an extraction provider.
          </AlertDescription>
        </Alert>
      )}

      {/* Schemas Section */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Schemas</CardTitle>
        </CardHeader>
        <CardContent>
          {schemasLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : schemas.length === 0 ? (
            <p className="text-sm text-muted-foreground py-4 text-center">
              No schemas yet. Create one to get started.
            </p>
          ) : (
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Target</TableHead>
                    <TableHead>Description</TableHead>
                    <TableHead className="w-10"></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {schemas.map((schema) => (
                    <TableRow key={schema.id}>
                      <TableCell className="font-medium">{schema.name}</TableCell>
                      <TableCell>
                        <Badge variant="outline" className="text-xs">
                          {schema.extractionTarget}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-muted-foreground text-sm">
                        {schema.description || '—'}
                      </TableCell>
                      <TableCell>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="icon" className="h-8 w-8">
                              <MoreHorizontal className="h-4 w-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem onClick={() => handleEditSchema(schema)}>
                              <Pencil className="h-4 w-4 mr-2" />
                              Edit
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              className="text-destructive"
                              onClick={() => handleDeleteSchema(schema)}
                            >
                              <Trash2 className="h-4 w-4 mr-2" />
                              Delete
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Results Section */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Extraction Results</CardTitle>
        </CardHeader>
        <CardContent>
          {!selectedDocumentId ? (
            <p className="text-sm text-muted-foreground py-4 text-center">
              Run an extraction to see results here.
            </p>
          ) : resultsLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : results.length === 0 ? (
            <p className="text-sm text-muted-foreground py-4 text-center">
              No extraction results for this document.
            </p>
          ) : (
            <div className="space-y-4">
              <div className="rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Method</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Created</TableHead>
                      <TableHead className="w-10"></TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {results.map((r) => (
                      <TableRow key={r.id}>
                        <TableCell>
                          <Badge variant="outline">{r.extractionMethod}</Badge>
                        </TableCell>
                        <TableCell>
                          <Badge
                            variant={
                              r.status === 'completed'
                                ? 'default'
                                : r.status === 'pending'
                                  ? 'secondary'
                                  : 'destructive'
                            }
                          >
                            {r.status}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {new Date(r.createdAt).toLocaleString()}
                        </TableCell>
                        <TableCell>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8"
                            onClick={() => selectResult(r.id)}
                          >
                            <Eye className="h-4 w-4" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>

              {/* Selected result detail */}
              <ExtractionResultViewer
                result={selectedResult}
                isLoading={isLoadingResult}
              />
            </div>
          )}
        </CardContent>
      </Card>

      {/* Dialogs */}
      <ExtractionSchemaEditor
        open={schemaEditorOpen}
        onOpenChange={setSchemaEditorOpen}
        schema={editingSchema}
        onSave={handleSaveSchema}
      />

      <RunExtractionDialog
        open={runDialogOpen}
        onOpenChange={setRunDialogOpen}
        schemas={schemas}
        extractors={extractors}
        documents={documents}
        preselectedDocumentId={preselectedDocumentId}
        onRun={handleRunExtraction}
      />
    </div>
  )
}
