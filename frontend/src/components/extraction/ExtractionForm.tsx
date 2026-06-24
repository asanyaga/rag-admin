import { useState, useEffect } from 'react'
import type { ExtractionSchema, ExtractorInfo, RunWithParseRequest, ChunkingConfig } from '@/types/extraction'
import type { ParseConfig } from '@/types/parsing'
import { getLlmDefaults } from '@/api/extraction'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Checkbox } from '@/components/ui/checkbox'
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
import { Pencil, Play, ChevronDown } from 'lucide-react'
import { PromptConfigEditor } from '@/components/shared/PromptConfigEditor'
import { usePromptConfig } from '@/hooks/usePromptConfig'
import { ParseMethodSelector } from '@/components/documents/ParseMethodSelector'

const REPRESENTATION_KIND = 'extract_rich'

interface ExtractionFormProps {
  defaultParser: string
  defaultParserConfig: ParseConfig
  schemas: ExtractionSchema[]
  extractors: ExtractorInfo[]
  onRun: (request: RunWithParseRequest) => Promise<void>
  onEditSchema?: (schema: ExtractionSchema) => void
}

export function ExtractionForm({
  defaultParser,
  defaultParserConfig,
  schemas,
  extractors,
  onRun,
  onEditSchema,
}: ExtractionFormProps) {
  const [parserType, setParserType] = useState(defaultParser)
  const [parserConfig, setParserConfig] = useState<ParseConfig>(defaultParserConfig)

  const [schemaId, setSchemaId] = useState('')
  const [extractionMethod, setExtractionMethod] = useState('')

  // LlamaExtract config
  const [extractionMode, setExtractionMode] = useState('MULTIMODAL')
  const [citeSources, setCiteSources] = useState(false)
  const [useReasoning, setUseReasoning] = useState(false)
  const [pageRange, setPageRange] = useState('')
  const [extractionTarget, setExtractionTarget] = useState('PER_DOC')
  const [confidenceScores, setConfidenceScores] = useState(false)

  // LLM method config
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

  const [isRunning, setIsRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Reset parse config when defaults change (document selection changed)
  useEffect(() => {
    setParserType(defaultParser)
    setParserConfig(defaultParserConfig)
  }, [defaultParser, defaultParserConfig])

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
  }, [extractionMethod, setPromptConfig, setUserPromptTemplate])

  const selectedExtractor = extractors.find((e) => e.extractionMethod === extractionMethod)
  const isConfigured = selectedExtractor?.configured ?? true

  const handleRun = async () => {
    setError(null)

    if (!schemaId) {
      setError('Please select a schema')
      return
    }
    if (!extractionMethod) {
      setError('No extraction method available')
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

    setIsRunning(true)
    try {
      await onRun({ parseConfig, extractionConfig })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to run extraction')
    } finally {
      setIsRunning(false)
    }
  }

  const hasSchemas = schemas.length > 0
  const hasExtractors = extractors.length > 0

  if (!hasSchemas || !hasExtractors) {
    return (
      <div className="rounded-lg border border-dashed p-4 text-center text-sm text-muted-foreground">
        {!hasExtractors
          ? 'No extraction methods available. Contact your administrator.'
          : 'Create a schema first to run extractions.'}
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Schema + Method row */}
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
            {onEditSchema && schemaId && (
              <Button
                variant="ghost"
                size="icon"
                className="h-9 w-9 shrink-0"
                title="Edit selected schema"
                onClick={() => {
                  const selected = schemas.find((s) => s.id === schemaId)
                  if (selected) onEditSchema(selected)
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
                  <SelectItem key={e.extractionMethod} value={e.extractionMethod} disabled={!e.configured}>
                    {e.name}{!e.configured ? ' (not configured)' : ''}
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

      {/* LlamaExtract-specific config */}
      {extractionMethod === 'llamaextract' && (
        <>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label className="text-xs">Mode</Label>
              <Select value={extractionMode} onValueChange={setExtractionMode}>
                <SelectTrigger className="h-9"><SelectValue /></SelectTrigger>
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
              <Input value={pageRange} onChange={(e) => setPageRange(e.target.value)} placeholder="e.g. 1-5" className="h-9" />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="extraction-target" className="text-xs">Target</Label>
              <Select value={extractionTarget} onValueChange={setExtractionTarget}>
                <SelectTrigger id="extraction-target" className="h-9"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="PER_DOC">Per Document</SelectItem>
                  <SelectItem value="PER_PAGE">Per Page</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-end pb-2">
              <div className="flex items-center space-x-2">
                <Checkbox id="confidence-scores" checked={confidenceScores} onCheckedChange={(c) => setConfidenceScores(c === true)} />
                <Label htmlFor="confidence-scores" className="text-xs font-normal">Confidence Scores</Label>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <div className="flex items-center space-x-2">
              <Checkbox id="cite-sources-inline" checked={citeSources} onCheckedChange={(c) => setCiteSources(c === true)} />
              <Label htmlFor="cite-sources-inline" className="text-xs font-normal">Citations</Label>
            </div>
            <div className="flex items-center space-x-2">
              <Checkbox id="use-reasoning-inline" checked={useReasoning} onCheckedChange={(c) => setUseReasoning(c === true)} />
              <Label htmlFor="use-reasoning-inline" className="text-xs font-normal">Reasoning</Label>
            </div>
          </div>
        </>
      )}

      {/* LLM method config */}
      {extractionMethod === 'llm' && (
        <div className="space-y-4">
          <PromptConfigEditor value={promptConfig} onChange={setPromptConfig} onProviderChange={setProvider} capabilities={{ thinking: true }} />
          <div className="space-y-1.5">
            <Label className="text-xs">User prompt template</Label>
            <p className="text-[11px] text-muted-foreground">
              Variables: <code>{'{schema_json}'}</code> and <code>{'{document_context}'}</code>. Leave blank to use the default.
            </p>
            <Textarea value={userPromptTemplate} onChange={(e) => setUserPromptTemplate(e.target.value)} className="font-mono text-xs min-h-[80px]" placeholder="Extract structured data from the following document..." />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label className="text-xs">Output mode</Label>
              <Select value={structuredOutputMode} onValueChange={setStructuredOutputMode}>
                <SelectTrigger className="h-9"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="json_schema">JSON Schema</SelectItem>
                  <SelectItem value="json_mode">JSON Mode</SelectItem>
                  <SelectItem value="prompt_only">Prompt Only</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-end pb-2">
              <div className="flex items-center space-x-2">
                <Checkbox id="inject-block-ids" checked={injectBlockIds} onCheckedChange={(v) => setInjectBlockIds(v === true)} />
                <Label htmlFor="inject-block-ids" className="text-xs font-normal">Inject block IDs</Label>
              </div>
            </div>
          </div>
          <Collapsible>
            <CollapsibleTrigger asChild>
              <Button variant="ghost" size="sm" className="w-full justify-between px-0">
                <span className="text-xs font-medium">Large document handling</span>
                <ChevronDown className="h-4 w-4" />
              </Button>
            </CollapsibleTrigger>
            <CollapsibleContent className="space-y-3 pt-2">
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label className="text-xs">Chunking</Label>
                  <Select value={chunkStrategy} onValueChange={(v) => setChunkStrategy(v as 'none' | 'token_budget_pages')}>
                    <SelectTrigger className="h-9" aria-label="Chunking strategy"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">None (single-shot)</SelectItem>
                      <SelectItem value="token_budget_pages">Token-budgeted pages</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs">Citation detail</Label>
                  <Select value={citationLevel} onValueChange={(v) => setCitationLevel(v as 'auto' | 'full' | 'page_only' | 'off')}>
                    <SelectTrigger className="h-9" aria-label="Citation detail"><SelectValue /></SelectTrigger>
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
                      <Input type="number" value={maxInputTokens} onChange={(e) => setMaxInputTokens(e.target.value)} className="h-9" />
                    </div>
                    <div className="space-y-1.5">
                      <Label className="text-xs">Page overlap</Label>
                      <Input type="number" value={pageOverlap} onChange={(e) => setPageOverlap(e.target.value)} className="h-9" />
                    </div>
                    <div className="space-y-1.5">
                      <Label className="text-xs">Dedupe key</Label>
                      <Input value={dedupeKey} onChange={(e) => setDedupeKey(e.target.value)} placeholder="e.g. sku" className="h-9" />
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

      {/* Parse Configuration — secondary */}
      <ParseMethodSelector
        parserType={parserType}
        config={parserConfig}
        onParserTypeChange={setParserType}
        onConfigChange={setParserConfig}
        disabled={isRunning}
        compact
      />

      {/* Run button */}
      <div className="flex items-center justify-between">
        <div />
        <Button onClick={handleRun} disabled={isRunning || !isConfigured} size="sm">
          {isRunning ? 'Running...' : (
            <><Play className="h-3.5 w-3.5 mr-1.5" />Run Extraction</>
          )}
        </Button>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}
      {!isConfigured && (
        <p className="text-xs text-amber-600">
          {selectedExtractor?.name ?? 'This extractor'} is not configured. Contact your administrator.
        </p>
      )}
    </div>
  )
}
