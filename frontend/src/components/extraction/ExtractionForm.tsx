import { useState, useEffect } from 'react'
import type { ExtractionSchema, ExtractorInfo, RunExtractionRequest } from '@/types/extraction'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Pencil, Play } from 'lucide-react'

interface ExtractionFormProps {
  parseRunId: string
  schemas: ExtractionSchema[]
  extractors: ExtractorInfo[]
  onRun: (request: RunExtractionRequest) => Promise<void>
  onEditSchema?: (schema: ExtractionSchema) => void
}

type OllamaEndpointPreset = 'local' | 'cloud' | 'custom'

const OLLAMA_ENDPOINTS: Record<OllamaEndpointPreset, string> = {
  local: 'http://host.docker.internal:11434/v1',
  cloud: 'https://ollama.com/v1',
  custom: '',
}

export function ExtractionForm({
  parseRunId,
  schemas,
  extractors,
  onRun,
  onEditSchema,
}: ExtractionFormProps) {
  const [schemaId, setSchemaId] = useState('')
  const [extractionMethod, setExtractionMethod] = useState('')

  // LlamaExtract config
  const [extractionMode, setExtractionMode] = useState('MULTIMODAL')
  const [citeSources, setCiteSources] = useState(false)
  const [useReasoning, setUseReasoning] = useState(false)
  const [pageRange, setPageRange] = useState('')
  const [extractionTarget, setExtractionTarget] = useState('PER_DOC')
  const [confidenceScores, setConfidenceScores] = useState(false)

  // Ollama config
  const [ollamaModel, setOllamaModel] = useState('')
  const [ollamaEndpointPreset, setOllamaEndpointPreset] = useState<OllamaEndpointPreset>('local')
  const [ollamaCustomEndpoint, setOllamaCustomEndpoint] = useState('')
  const [ollamaStructuredOutputMode, setOllamaStructuredOutputMode] = useState('json_schema')
  const [ollamaInjectBlockIds, setOllamaInjectBlockIds] = useState(false)

  const [isRunning, setIsRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (schemas.length > 0 && !schemaId) setSchemaId(schemas[0].id)
  }, [schemas, schemaId])

  useEffect(() => {
    if (extractors.length > 0 && !extractionMethod) setExtractionMethod(extractors[0].extractionMethod)
  }, [extractors, extractionMethod])

  const selectedExtractor = extractors.find((e) => e.extractionMethod === extractionMethod)
  const isConfigured = selectedExtractor?.configured ?? true

  function getOllamaEndpoint(): string {
    if (ollamaEndpointPreset === 'custom') return ollamaCustomEndpoint
    return OLLAMA_ENDPOINTS[ollamaEndpointPreset]
  }

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
    if (extractionMethod === 'ollama' && !ollamaModel.trim()) {
      setError('Model name is required for Ollama')
      return
    }

    let config: Record<string, unknown>

    if (extractionMethod === 'llamaextract') {
      config = { extraction_mode: extractionMode }
      if (citeSources) config.cite_sources = true
      if (useReasoning) config.use_reasoning = true
      if (pageRange.trim()) config.page_range = pageRange.trim()
      config.extraction_target = extractionTarget
      if (confidenceScores) config.confidence_scores = true
    } else if (extractionMethod === 'ollama') {
      config = {
        model: ollamaModel.trim(),
        endpoint: getOllamaEndpoint(),
        structured_output_mode: ollamaStructuredOutputMode,
        inject_block_ids: ollamaInjectBlockIds,
      }
    } else {
      config = {}
    }

    setIsRunning(true)
    try {
      await onRun({
        parseRunId,
        extractionSchemaId: schemaId,
        extractionMethod,
        config,
      })
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

  const isOllamaModelMissing = extractionMethod === 'ollama' && !ollamaModel.trim()
  const isRunDisabled = isRunning || !isConfigured || isOllamaModelMissing

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
              <Label htmlFor="extraction-target" className="text-xs">Target</Label>
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
                  onCheckedChange={(checked) => setConfidenceScores(checked === true)}
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
                id="cite-sources-inline"
                checked={citeSources}
                onCheckedChange={(checked) => setCiteSources(checked === true)}
              />
              <Label htmlFor="cite-sources-inline" className="text-xs font-normal">
                Citations
              </Label>
            </div>
            <div className="flex items-center space-x-2">
              <Checkbox
                id="use-reasoning-inline"
                checked={useReasoning}
                onCheckedChange={(checked) => setUseReasoning(checked === true)}
              />
              <Label htmlFor="use-reasoning-inline" className="text-xs font-normal">
                Reasoning
              </Label>
            </div>
          </div>
        </>
      )}

      {/* Ollama-specific config */}
      {extractionMethod === 'ollama' && (
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label className="text-xs">Model</Label>
              <Input
                value={ollamaModel}
                onChange={(e) => setOllamaModel(e.target.value)}
                placeholder="e.g. llama3.2:8b"
                className="h-9"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">Output Mode</Label>
              <Select value={ollamaStructuredOutputMode} onValueChange={setOllamaStructuredOutputMode}>
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
          </div>

          <div className="space-y-1.5">
            <Label className="text-xs">Endpoint</Label>
            <Select
              value={ollamaEndpointPreset}
              onValueChange={(v) => setOllamaEndpointPreset(v as OllamaEndpointPreset)}
            >
              <SelectTrigger className="h-9">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="local">Local (host.docker.internal:11434)</SelectItem>
                <SelectItem value="cloud">Ollama Cloud</SelectItem>
                <SelectItem value="custom">Custom</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {(ollamaEndpointPreset === 'cloud' || ollamaEndpointPreset === 'custom') && (
            <p className="text-[11px] text-muted-foreground">
              API key is resolved from Settings → API Keys (Ollama Cloud). No key is sent in the request.
            </p>
          )}

          {ollamaEndpointPreset === 'custom' && (
            <div className="space-y-1.5">
              <Label className="text-xs">Custom Endpoint URL</Label>
              <Input
                value={ollamaCustomEndpoint}
                onChange={(e) => setOllamaCustomEndpoint(e.target.value)}
                placeholder="https://your-ollama-host/v1"
                className="h-9"
              />
            </div>
          )}

          {ollamaEndpointPreset !== 'custom' && (
            <p className="text-[11px] text-muted-foreground font-mono">
              {OLLAMA_ENDPOINTS[ollamaEndpointPreset]}
            </p>
          )}

          <div className="flex items-center space-x-2">
            <Checkbox
              id="inject-block-ids"
              checked={ollamaInjectBlockIds}
              onCheckedChange={(checked) => setOllamaInjectBlockIds(checked === true)}
            />
            <Label htmlFor="inject-block-ids" className="text-xs font-normal">
              Inject block IDs (block-level citations)
            </Label>
          </div>
        </div>
      )}

      {/* Run button */}
      <div className="flex items-center justify-between">
        <div />
        <Button onClick={handleRun} disabled={isRunDisabled} size="sm">
          {isRunning ? (
            'Running...'
          ) : (
            <>
              <Play className="h-3.5 w-3.5 mr-1.5" />
              Run Extraction
            </>
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
