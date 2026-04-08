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
  documentId: string
  schemas: ExtractionSchema[]
  extractors: ExtractorInfo[]
  onRun: (request: RunExtractionRequest) => Promise<void>
  onEditSchema?: (schema: ExtractionSchema) => void
}

export function ExtractionForm({
  documentId,
  schemas,
  extractors,
  onRun,
  onEditSchema,
}: ExtractionFormProps) {
  const [schemaId, setSchemaId] = useState('')
  const [extractionMethod, setExtractionMethod] = useState('')
  const [extractionMode, setExtractionMode] = useState('MULTIMODAL')
  const [citeSources, setCiteSources] = useState(false)
  const [useReasoning, setUseReasoning] = useState(false)
  const [pageRange, setPageRange] = useState('')
  const [isRunning, setIsRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (schemas.length > 0 && !schemaId) setSchemaId(schemas[0].id)
  }, [schemas, schemaId])

  useEffect(() => {
    if (extractors.length > 0 && !extractionMethod) setExtractionMethod(extractors[0].extractionMethod)
  }, [extractors, extractionMethod])

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

    const config: Record<string, unknown> = {
      extraction_mode: extractionMode,
    }
    if (citeSources) config.cite_sources = true
    if (useReasoning) config.use_reasoning = true
    if (pageRange.trim()) config.page_range = pageRange.trim()

    setIsRunning(true)
    try {
      await onRun({
        documentId,
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

  return (
    <div className="space-y-4">
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
                  <SelectItem key={e.extractionMethod} value={e.extractionMethod}>
                    {e.name}
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

      <div className="flex items-center justify-between">
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

        <Button onClick={handleRun} disabled={isRunning} size="sm">
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
    </div>
  )
}
