import { useState, useEffect } from 'react'
import type { ExtractionSchema, ExtractorInfo, RunExtractionRequest } from '@/types/extraction'
import type { DocumentListItem } from '@/types/document'
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
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'

interface RunExtractionDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  schemas: ExtractionSchema[]
  extractors: ExtractorInfo[]
  documents: DocumentListItem[]
  preselectedDocumentId?: string | null
  onRun: (request: RunExtractionRequest) => Promise<void>
}

export function RunExtractionDialog({
  open,
  onOpenChange,
  schemas,
  extractors,
  documents,
  preselectedDocumentId,
  onRun,
}: RunExtractionDialogProps) {
  const [documentId, setDocumentId] = useState('')
  const [schemaId, setSchemaId] = useState('')
  const [extractionMethod, setExtractionMethod] = useState('')
  const [extractionMode, setExtractionMode] = useState('MULTIMODAL')
  const [citeSources, setCiteSources] = useState(false)
  const [useReasoning, setUseReasoning] = useState(false)
  const [pageRange, setPageRange] = useState('')
  const [isRunning, setIsRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (open) {
      setDocumentId(preselectedDocumentId || '')
      setSchemaId(schemas.length > 0 ? schemas[0].id : '')
      setExtractionMethod(extractors.length > 0 ? extractors[0].extractionMethod : '')
      setExtractionMode('MULTIMODAL')
      setCiteSources(false)
      setUseReasoning(false)
      setPageRange('')
      setError(null)
    }
  }, [open, preselectedDocumentId, schemas, extractors])

  const handleRun = async () => {
    setError(null)

    if (!documentId) {
      setError('Please select a document')
      return
    }
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
      onOpenChange(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to run extraction')
    } finally {
      setIsRunning(false)
    }
  }

  const readyDocuments = documents.filter((d) => d.status === 'ready')

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Run Extraction</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label>Document</Label>
            <Select value={documentId} onValueChange={setDocumentId}>
              <SelectTrigger>
                <SelectValue placeholder="Select a document" />
              </SelectTrigger>
              <SelectContent>
                {readyDocuments.map((doc) => (
                  <SelectItem key={doc.id} value={doc.id}>
                    {doc.title}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label>Schema</Label>
            <Select value={schemaId} onValueChange={setSchemaId}>
              <SelectTrigger>
                <SelectValue placeholder="Select a schema" />
              </SelectTrigger>
              <SelectContent>
                {schemas.map((s) => (
                  <SelectItem key={s.id} value={s.id}>
                    {s.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {extractors.length > 0 && (
            <div className="space-y-2">
              <Label>Extraction Method</Label>
              <Select value={extractionMethod} onValueChange={setExtractionMethod}>
                <SelectTrigger>
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
          )}

          <div className="space-y-2">
            <Label>Extraction Mode</Label>
            <Select value={extractionMode} onValueChange={setExtractionMode}>
              <SelectTrigger>
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

          <div className="space-y-2">
            <Label>Page Range (optional)</Label>
            <Input
              value={pageRange}
              onChange={(e) => setPageRange(e.target.value)}
              placeholder="e.g. 1-5"
            />
          </div>

          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-2">
              <Checkbox
                id="cite-sources"
                checked={citeSources}
                onCheckedChange={(checked) => setCiteSources(checked === true)}
              />
              <Label htmlFor="cite-sources" className="text-sm font-normal">
                Citations
              </Label>
            </div>
            <div className="flex items-center space-x-2">
              <Checkbox
                id="use-reasoning"
                checked={useReasoning}
                onCheckedChange={(checked) => setUseReasoning(checked === true)}
              />
              <Label htmlFor="use-reasoning" className="text-sm font-normal">
                Reasoning
              </Label>
            </div>
          </div>

          {error && (
            <p className="text-sm text-destructive">{error}</p>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isRunning}>
            Cancel
          </Button>
          <Button onClick={handleRun} disabled={isRunning}>
            {isRunning ? 'Running...' : 'Run Extraction'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
