import { useState, useEffect, useCallback } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useProject } from '@/contexts/ProjectContext'
import { useDocuments } from '@/hooks/useDocuments'
import { useExtractionSchemas } from '@/hooks/useExtractionSchemas'
import { useExtractionSubmit } from '@/hooks/useExtractionSubmit'
import { useParseRuns } from '@/hooks/useParseRuns'
import type {
  ExtractionSchema,
  ExtractionSchemaCreate,
  ExtractionSchemaUpdate,
  ExtractorInfo,
  RunWithParseRequest,
  ChunkingConfig,
} from '@/types/extraction'
import type { ParseConfig } from '@/types/parsing'
import { SchemaManager } from '@/components/extraction/SchemaManager'
import { ExtractionSchemaEditor } from '@/components/extraction/ExtractionSchemaEditor'
import { PromptConfigEditor } from '@/components/shared/PromptConfigEditor'
import { ParseMethodSelector } from '@/components/documents/ParseMethodSelector'
import { usePromptConfig } from '@/hooks/usePromptConfig'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import { Separator } from '@/components/ui/separator'
import { Textarea } from '@/components/ui/textarea'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ArrowLeft, ChevronDown, Loader2, Pencil, Play } from 'lucide-react'
import { getLlmDefaults } from '@/api/extraction'
import * as extractionApi from '@/api/extraction'
import { toast } from 'sonner'

const REPRESENTATION_KIND = 'extract_rich'

export default function NewExtractionRunPage(): JSX.Element {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { currentProject } = useProject()
  const projectId = currentProject?.id ?? null

  const documentId = searchParams.get('documentId')

  const { documents } = useDocuments(projectId)
  const { parseRuns, isLoading: parseRunsLoading } = useParseRuns(documentId)
  const { schemas, error: schemasError, createSchema, updateSchema, deleteSchema } =
    useExtractionSchemas(projectId)
  const { phase, phaseError, submit } = useExtractionSubmit()

  const [schemaEditorOpen, setSchemaEditorOpen] = useState(false)
  const [editingSchema, setEditingSchema] = useState<ExtractionSchema | null>(null)
  const [extractors, setExtractors] = useState<ExtractorInfo[]>([])

  // Parse config
  const latestViableRun = parseRuns.find(
    (r) => r.status === 'succeeded' || r.status === 'partial',
  )
  const defaultParser: string = latestViableRun?.parser ?? 'simple'
  const defaultParserConfig: ParseConfig = (() => {
    if (!latestViableRun?.config) return {}
    const config = { ...(latestViableRun.config as Record<string, unknown>) }
    delete config['parser']
    return config as ParseConfig
  })()

  const [parserType, setParserType] = useState(defaultParser)
  const [parserConfig, setParserConfig] = useState<ParseConfig>(defaultParserConfig)

  useEffect(() => {
    setParserType(defaultParser)
    setParserConfig(defaultParserConfig)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [latestViableRun?.id])

  // Extraction config
  const [schemaId, setSchemaId] = useState('')
  const [extractionMethod, setExtractionMethod] = useState('')
  const [extractionMode, setExtractionMode] = useState('MULTIMODAL')
  const [citeSources, setCiteSources] = useState(false)
  const [useReasoning, setUseReasoning] = useState(false)
  const [pageRange, setPageRange] = useState('')
  const [extractionTarget, setExtractionTarget] = useState('PER_DOC')
  const [confidenceScores, setConfidenceScores] = useState(false)
  const { promptConfig, setPromptConfig, setProvider } = usePromptConfig()
  const [userPromptTemplate, setUserPromptTemplate] = useState('')
  const [structuredOutputMode, setStructuredOutputMode] = useState('json_schema')
  const [injectBlockIds, setInjectBlockIds] = useState(false)
  const [chunkStrategy, setChunkStrategy] = useState<'none' | 'token_budget_pages'>('none')
  const [maxInputTokens, setMaxInputTokens] = useState('8000')
  const [pageOverlap, setPageOverlap] = useState('0')
  const [dedupeKey, setDedupeKey] = useState('')
  const [maxTokensPerMinute, setMaxTokensPerMinute] = useState('')
  const [timeoutMinutes, setTimeoutMinutes] = useState('')
  const [citationLevel, setCitationLevel] =
    useState<'auto' | 'full' | 'page_only' | 'off'>('auto')

  const [formError, setFormError] = useState<string | null>(null)

  const fetchExtractors = useCallback(async () => {
    try {
      const data = await extractionApi.listExtractors()
      setExtractors(data)
    } catch {
      // Extractors not available
    }
  }, [])

  useEffect(() => {
    void fetchExtractors()
  }, [fetchExtractors])

  useEffect(() => {
    if (schemas.length > 0 && !schemaId) setSchemaId(schemas[0].id)
  }, [schemas, schemaId])

  useEffect(() => {
    if (extractors.length > 0 && !extractionMethod) {
      const firstConfigured = extractors.find((e) => e.configured)
      setExtractionMethod(firstConfigured?.extractionMethod ?? extractors[0].extractionMethod)
    }
  }, [extractors, extractionMethod])

  useEffect(() => {
    if (extractionMethod !== 'llm') return
    let cancelled = false
    getLlmDefaults()
      .then((defaults) => {
        if (cancelled) return
        setPromptConfig((prev) => ({
          ...prev,
          systemPrompt: prev.systemPrompt || defaults.systemPrompt,
        }))
        setUserPromptTemplate((prev) => prev || defaults.userPromptTemplate)
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [extractionMethod, setPromptConfig])

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

  const handleRun = async () => {
    if (!documentId) return
    setFormError(null)

    if (!schemaId) {
      setFormError('Please select a schema')
      return
    }
    if (!extractionMethod) {
      setFormError('No extraction method available')
      return
    }

    const parseConfig = {
      parser: parserType,
      config: parserConfig as Record<string, unknown>,
      representationKind: REPRESENTATION_KIND,
    }

    let extractionConfig: RunWithParseRequest['extractionConfig']

    if (extractionMethod === 'llamaextract') {
      const config: Record<string, unknown> = { extraction_mode: extractionMode }
      if (citeSources) config.cite_sources = true
      if (useReasoning) config.use_reasoning = true
      if (pageRange.trim()) config.page_range = pageRange.trim()
      config.extraction_target = extractionTarget
      if (confidenceScores) config.confidence_scores = true
      extractionConfig = { extractionSchemaId: schemaId, extractionMethod, config }
    } else if (extractionMethod === 'llm') {
      let chunking: ChunkingConfig | undefined
      if (chunkStrategy !== 'none') {
        const cfg: Record<string, unknown> = {}
        const max = parseInt(maxInputTokens, 10)
        if (!Number.isNaN(max)) cfg.maxInputTokens = max
        const overlap = parseInt(pageOverlap, 10)
        if (!Number.isNaN(overlap) && overlap > 0) cfg.pageOverlap = overlap
        if (dedupeKey.trim()) cfg.dedupeKey = dedupeKey.trim()
        const tpm = parseInt(maxTokensPerMinute, 10)
        chunking = {
          strategy: chunkStrategy,
          config: cfg,
          citationLevel,
          ...(!Number.isNaN(tpm) && tpm > 0 ? { maxTokensPerMinute: tpm } : {}),
        }
      } else if (citationLevel !== 'auto') {
        chunking = { strategy: 'none', citationLevel }
      }
      const tm = parseInt(timeoutMinutes, 10)
      extractionConfig = {
        extractionSchemaId: schemaId,
        extractionMethod,
        config: { structured_output_mode: structuredOutputMode, inject_block_ids: injectBlockIds },
        llmConfig: promptConfig,
        userPromptTemplate: userPromptTemplate.trim() || undefined,
        ...(chunking ? { chunking } : {}),
        ...(!Number.isNaN(tm) && tm >= 1 ? { timeoutMinutes: Math.min(tm, 120) } : {}),
      }
    } else {
      extractionConfig = { extractionSchemaId: schemaId, extractionMethod, config: {} }
    }

    const resultId = await submit(documentId, parseRuns, { parseConfig, extractionConfig })
    if (resultId) {
      navigate(`/extract/${resultId}`)
    }
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

  if (!documentId) {
    return (
      <div className="p-6">
        <Alert variant="destructive">
          <AlertDescription>No document selected. Go back and select a document.</AlertDescription>
        </Alert>
      </div>
    )
  }

  const selectedDocument = documents.find((d) => d.id === documentId)
  const selectedExtractor = extractors.find((e) => e.extractionMethod === extractionMethod)
  const isConfigured = selectedExtractor?.configured ?? true
  const isRunning = phase === 'parsing' || phase === 'extracting'
  const hasSchemas = schemas.length > 0
  const hasExtractors = extractors.length > 0

  const phaseLabel = phase === 'parsing' ? 'Parsing document…' : 'Extracting data…'

  return (
    <div className="-m-6 flex flex-col h-[calc(100vh-3.5rem)]">
      {/* Header */}
      <div className="flex items-center gap-3 px-6 py-3 border-b shrink-0">
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          onClick={() =>
            navigate(documentId ? `/extract?documentId=${documentId}` : '/extract')
          }
        >
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div>
          <h1 className="text-lg font-semibold">New Extraction Run</h1>
          {selectedDocument && (
            <p className="text-xs text-muted-foreground truncate max-w-xs">
              {selectedDocument.title}
            </p>
          )}
        </div>
        {selectedDocument && (
          <Badge
            variant={
              selectedDocument.status === 'ready'
                ? 'outline'
                : selectedDocument.status === 'processing'
                  ? 'secondary'
                  : 'destructive'
            }
            className="text-xs shrink-0"
          >
            {selectedDocument.status}
          </Badge>
        )}
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-2xl mx-auto space-y-6">
          {schemasError && (
            <Alert variant="destructive">
              <AlertDescription>{schemasError}</AlertDescription>
            </Alert>
          )}

          {/* Schema management */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm">Schemas</CardTitle>
            </CardHeader>
            <CardContent>
              <SchemaManager
                schemas={schemas}
                onEdit={handleEditSchema}
                onDelete={handleDeleteSchema}
                onCreate={handleCreateSchema}
              />
            </CardContent>
          </Card>

          {/* Extraction config */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm">Extraction Configuration</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {parseRunsLoading ? (
                <div className="text-sm text-muted-foreground">Loading parse history…</div>
              ) : !hasExtractors ? (
                <p className="text-sm text-muted-foreground">
                  No extraction methods available. Contact your administrator.
                </p>
              ) : !hasSchemas ? (
                <p className="text-sm text-muted-foreground">
                  Create a schema above to run extractions.
                </p>
              ) : (
                <>
                  {/* Schema + Method */}
                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1.5">
                      <Label className="text-xs">Schema</Label>
                      <div className="flex items-center gap-1">
                        <Select value={schemaId} onValueChange={setSchemaId}>
                          <SelectTrigger className="h-9">
                            <SelectValue placeholder="Select schema" />
                          </SelectTrigger>
                          <SelectContent>
                            {schemas.map((s) => (
                              <SelectItem key={s.id} value={s.id}>
                                {s.name}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        {schemaId && (
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-9 w-9 shrink-0"
                            title="Edit selected schema"
                            onClick={() => {
                              const selected = schemas.find((s) => s.id === schemaId)
                              if (selected) handleEditSchema(selected)
                            }}
                          >
                            <Pencil className="h-3.5 w-3.5" />
                          </Button>
                        )}
                      </div>
                    </div>

                    {extractors.length > 1 ? (
                      <div className="space-y-1.5">
                        <Label className="text-xs">Method</Label>
                        <Select value={extractionMethod} onValueChange={setExtractionMethod}>
                          <SelectTrigger className="h-9">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {extractors.map((e) => (
                              <SelectItem
                                key={e.extractionMethod}
                                value={e.extractionMethod}
                                disabled={!e.configured}
                              >
                                {e.name}
                                {!e.configured ? ' (not configured)' : ''}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    ) : (
                      <div className="space-y-1.5">
                        <Label className="text-xs">Method</Label>
                        <div className="h-9 flex items-center text-sm text-muted-foreground px-3 border rounded-md bg-muted/50">
                          {extractors[0]?.name}
                        </div>
                      </div>
                    )}
                  </div>

                  {/* LlamaExtract config */}
                  {extractionMethod === 'llamaextract' && (
                    <>
                      <div className="grid grid-cols-2 gap-3">
                        <div className="space-y-1.5">
                          <Label className="text-xs">Mode</Label>
                          <Select value={extractionMode} onValueChange={setExtractionMode}>
                            <SelectTrigger className="h-9">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="FAST">Fast</SelectItem>
                              <SelectItem value="BALANCED">Balanced</SelectItem>
                              <SelectItem value="MULTIMODAL">Multimodal</SelectItem>
                              <SelectItem value="PREMIUM">Premium</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        <div className="space-y-1.5">
                          <Label className="text-xs">Page Range</Label>
                          <Input
                            value={pageRange}
                            onChange={(e) => setPageRange(e.target.value)}
                            placeholder="e.g. 1-5"
                            className="h-9"
                          />
                        </div>
                      </div>
                      <div className="grid grid-cols-2 gap-3">
                        <div className="space-y-1.5">
                          <Label htmlFor="extraction-target" className="text-xs">
                            Target
                          </Label>
                          <Select value={extractionTarget} onValueChange={setExtractionTarget}>
                            <SelectTrigger id="extraction-target" className="h-9">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="PER_DOC">Per Document</SelectItem>
                              <SelectItem value="PER_PAGE">Per Page</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        <div className="flex items-end pb-2">
                          <div className="flex items-center space-x-2">
                            <Checkbox
                              id="confidence-scores"
                              checked={confidenceScores}
                              onCheckedChange={(c) => setConfidenceScores(c === true)}
                            />
                            <Label htmlFor="confidence-scores" className="text-xs font-normal">
                              Confidence Scores
                            </Label>
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-4">
                        <div className="flex items-center space-x-2">
                          <Checkbox
                            id="cite-sources"
                            checked={citeSources}
                            onCheckedChange={(c) => setCiteSources(c === true)}
                          />
                          <Label htmlFor="cite-sources" className="text-xs font-normal">
                            Citations
                          </Label>
                        </div>
                        <div className="flex items-center space-x-2">
                          <Checkbox
                            id="use-reasoning"
                            checked={useReasoning}
                            onCheckedChange={(c) => setUseReasoning(c === true)}
                          />
                          <Label htmlFor="use-reasoning" className="text-xs font-normal">
                            Reasoning
                          </Label>
                        </div>
                      </div>
                    </>
                  )}

                  {/* LLM config */}
                  {extractionMethod === 'llm' && (
                    <div className="space-y-4">
                      <PromptConfigEditor
                        value={promptConfig}
                        onChange={setPromptConfig}
                        onProviderChange={setProvider}
                        capabilities={{ thinking: true }}
                      />
                      <div className="space-y-1.5">
                        <Label className="text-xs">User prompt template</Label>
                        <p className="text-[11px] text-muted-foreground">
                          Variables: <code>{'{schema_json}'}</code> and{' '}
                          <code>{'{document_context}'}</code>. Leave blank to use the default.
                        </p>
                        <Textarea
                          value={userPromptTemplate}
                          onChange={(e) => setUserPromptTemplate(e.target.value)}
                          className="font-mono text-xs min-h-[80px]"
                          placeholder="Extract structured data from the following document..."
                        />
                      </div>
                      <div className="grid grid-cols-2 gap-3">
                        <div className="space-y-1.5">
                          <Label className="text-xs">Output mode</Label>
                          <Select
                            value={structuredOutputMode}
                            onValueChange={setStructuredOutputMode}
                          >
                            <SelectTrigger className="h-9">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="json_schema">JSON Schema</SelectItem>
                              <SelectItem value="json_mode">JSON Mode</SelectItem>
                              <SelectItem value="prompt_only">Prompt Only</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        <div className="flex items-end pb-2">
                          <div className="flex items-center space-x-2">
                            <Checkbox
                              id="inject-block-ids"
                              checked={injectBlockIds}
                              onCheckedChange={(v) => setInjectBlockIds(v === true)}
                            />
                            <Label htmlFor="inject-block-ids" className="text-xs font-normal">
                              Inject block IDs
                            </Label>
                          </div>
                        </div>
                      </div>
                      <Collapsible>
                        <CollapsibleTrigger asChild>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="w-full justify-between px-0"
                          >
                            <span className="text-xs font-medium">Large document handling</span>
                            <ChevronDown className="h-4 w-4" />
                          </Button>
                        </CollapsibleTrigger>
                        <CollapsibleContent className="space-y-3 pt-2">
                          <div className="grid grid-cols-2 gap-3">
                            <div className="space-y-1.5">
                              <Label className="text-xs">Chunking</Label>
                              <Select
                                value={chunkStrategy}
                                onValueChange={(v) =>
                                  setChunkStrategy(v as 'none' | 'token_budget_pages')
                                }
                              >
                                <SelectTrigger className="h-9" aria-label="Chunking strategy">
                                  <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                  <SelectItem value="none">None (single-shot)</SelectItem>
                                  <SelectItem value="token_budget_pages">
                                    Token-budgeted pages
                                  </SelectItem>
                                </SelectContent>
                              </Select>
                            </div>
                            <div className="space-y-1.5">
                              <Label className="text-xs">Citation detail</Label>
                              <Select
                                value={citationLevel}
                                onValueChange={(v) =>
                                  setCitationLevel(v as 'auto' | 'full' | 'page_only' | 'off')
                                }
                              >
                                <SelectTrigger className="h-9" aria-label="Citation detail">
                                  <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                  <SelectItem value="auto">Auto</SelectItem>
                                  <SelectItem value="full">Full</SelectItem>
                                  <SelectItem value="page_only">Page only</SelectItem>
                                  <SelectItem value="off">Off</SelectItem>
                                </SelectContent>
                              </Select>
                            </div>
                          </div>
                          {chunkStrategy === 'token_budget_pages' && (
                            <>
                              <div className="grid grid-cols-3 gap-3">
                                <div className="space-y-1.5">
                                  <Label className="text-xs">Max input tokens</Label>
                                  <Input
                                    type="number"
                                    value={maxInputTokens}
                                    onChange={(e) => setMaxInputTokens(e.target.value)}
                                    className="h-9"
                                  />
                                </div>
                                <div className="space-y-1.5">
                                  <Label className="text-xs">Page overlap</Label>
                                  <Input
                                    type="number"
                                    value={pageOverlap}
                                    onChange={(e) => setPageOverlap(e.target.value)}
                                    className="h-9"
                                  />
                                </div>
                                <div className="space-y-1.5">
                                  <Label className="text-xs">Dedupe key</Label>
                                  <Input
                                    value={dedupeKey}
                                    onChange={(e) => setDedupeKey(e.target.value)}
                                    placeholder="e.g. sku"
                                    className="h-9"
                                  />
                                </div>
                              </div>
                              <div className="space-y-1.5">
                                <Label className="text-xs">Rate limit (TPM)</Label>
                                <Input
                                  type="number"
                                  value={maxTokensPerMinute}
                                  onChange={(e) => setMaxTokensPerMinute(e.target.value)}
                                  placeholder="e.g. 30000 for OpenAI tier 1"
                                  className="h-9"
                                />
                              </div>
                            </>
                          )}
                          <div className="space-y-1.5">
                            <Label className="text-xs">Timeout (minutes)</Label>
                            <Input
                              type="number"
                              value={timeoutMinutes}
                              onChange={(e) => setTimeoutMinutes(e.target.value)}
                              placeholder="10"
                              min={1}
                              max={120}
                              className="h-9"
                            />
                          </div>
                          <p className="text-[11px] text-muted-foreground">
                            {citationLevel === 'off'
                              ? 'No provenance will be captured.'
                              : 'Auto uses page-level provenance on large documents. Chunking splits big docs to avoid truncation and rate limits.'}
                          </p>
                        </CollapsibleContent>
                      </Collapsible>
                    </div>
                  )}

                  <Separator />

                  {/* Parse config */}
                  <ParseMethodSelector
                    parserType={parserType}
                    config={parserConfig}
                    onParserTypeChange={setParserType}
                    onConfigChange={setParserConfig}
                    disabled={isRunning}
                    compact
                  />

                  {/* Run */}
                  <div className="flex items-center justify-between pt-2">
                    <div>
                      {formError && <p className="text-sm text-destructive">{formError}</p>}
                      {phaseError && <p className="text-sm text-destructive">{phaseError}</p>}
                      {!isConfigured && (
                        <p className="text-xs text-amber-600">
                          {selectedExtractor?.name ?? 'This extractor'} is not configured. Contact
                          your administrator.
                        </p>
                      )}
                    </div>
                    <Button
                      onClick={() => void handleRun()}
                      disabled={isRunning || !isConfigured || selectedDocument?.status !== 'ready'}
                      size="sm"
                    >
                      {isRunning ? (
                        <>
                          <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
                          {phaseLabel}
                        </>
                      ) : (
                        <>
                          <Play className="h-3.5 w-3.5 mr-1.5" />
                          Run Extraction
                        </>
                      )}
                    </Button>
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      <ExtractionSchemaEditor
        open={schemaEditorOpen}
        onOpenChange={setSchemaEditorOpen}
        schema={editingSchema}
        onSave={handleSaveSchema}
      />
    </div>
  )
}
