import { useState, useCallback, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { AxiosError } from 'axios'
import { useProject } from '@/contexts/ProjectContext'
import { useIndexes } from '@/hooks/useIndexes'
import { IndexConfig, ChunkPreviewResponse, SourceRepresentation } from '@/types/index'
import { listParseConfigs } from '@/lib/parsed-documents'
import type { ParseConfigOption } from '@/lib/parsed-documents'
import {
  Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle,
} from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription } from '@/components/ui/alert'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { Slider } from '@/components/ui/slider'
import { ParseConfigFamilySelector } from '@/components/indexes/ParseConfigFamilySelector'
import { ParsedDocumentPicker } from '@/components/indexes/ParsedDocumentPicker'
import { ChunkPreviewPanel } from '@/components/indexes/ChunkPreviewPanel'
import { BlockConfigPanel } from '@/components/indexes/BlockConfigPanel'
import { toast } from 'sonner'
import {
  FileText, ChevronRight, ChevronLeft, Info, Check,
  Database, FileCode, Layers, Settings, Eye, Loader2,
} from 'lucide-react'

const STEPS = [
  { number: 1, title: 'Details',      icon: FileText  },
  { number: 2, title: 'Parse Config', icon: Database  },
  { number: 3, title: 'Source',       icon: FileCode  },
  { number: 4, title: 'Documents',    icon: Layers    },
  { number: 5, title: 'Chunking',     icon: Settings  },
  { number: 6, title: 'Preview',      icon: Eye       },
] as const

interface SelectedFamily {
  parser: string
  parseConfigHash: string
  hasFullMarkdown: boolean
}

const DEFAULT_CONFIG: Partial<IndexConfig> = {
  sourceRepresentation: 'full_text',
  chunkingStrategy: 'recursive_character',
  chunkSize: 512,
  chunkOverlap: 50,
  chunkUnit: 'characters',
  splitHeadingLevel: 2,
  maxSectionChars: 4000,
  groupByHeading: true,
  maxBlocksPerChunk: 10,
  blockRoleFilter: null,
  embeddingProvider: 'openai',
  embeddingModel: 'text-embedding-3-small',
}

function extractErrorMessage(data: unknown, fallback: string): string {
  if (!data || typeof data !== 'object') return fallback
  const d = data as Record<string, unknown>
  if (typeof d.detail === 'string') return d.detail
  if (Array.isArray(d.detail)) {
    return d.detail
      .map((e: unknown) => {
        if (e && typeof e === 'object' && 'msg' in e)
          return String((e as Record<string, unknown>).msg)
        return String(e)
      })
      .join('; ')
  }
  return fallback
}

const STEP_DESCRIPTIONS: Record<number, string> = {
  1: 'Enter basic information about your index',
  2: 'Choose which parse-config family to index',
  3: 'Select which segment of each parsed document to read',
  4: 'Choose which parsed documents to include',
  5: 'Configure chunking and embedding settings',
  6: 'Preview how documents will be chunked, then create the index',
}

export default function CreateIndexPage() {
  const navigate = useNavigate()
  const { currentProject } = useProject()
  const { createIndex, previewChunks } = useIndexes(currentProject?.id ?? null)

  const [currentStep, setCurrentStep] = useState(1)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isPreviewLoading, setIsPreviewLoading] = useState(false)
  const [preview, setPreview] = useState<ChunkPreviewResponse | null>(null)
  const [previewDocId, setPreviewDocId] = useState<string | null>(null)

  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [parseConfigs, setParseConfigs] = useState<ParseConfigOption[]>([])
  const [selectedFamily, setSelectedFamily] = useState<SelectedFamily | null>(null)
  const [selectedParsedDocIds, setSelectedParsedDocIds] = useState<string[]>([])
  const [config, setConfig] = useState<Partial<IndexConfig>>(DEFAULT_CONFIG)

  useEffect(() => {
    if (!currentProject) { navigate('/index'); return }
    listParseConfigs(currentProject.id)
      .then(setParseConfigs)
      .catch(() => toast.error('Failed to load parse configurations'))
  }, [currentProject, navigate])

  useEffect(() => {
    if (currentStep === 6 && selectedParsedDocIds.length > 0 && !previewDocId) {
      setPreviewDocId(selectedParsedDocIds[0])
    }
  }, [currentStep, selectedParsedDocIds, previewDocId])

  const updateConfig = (key: keyof IndexConfig, value: IndexConfig[keyof IndexConfig]) => {
    setConfig((prev) => ({ ...prev, [key]: value }))
    setPreview(null)
  }

  const handleSourceRepresentationChange = (value: SourceRepresentation) => {
    updateConfig('sourceRepresentation', value)
    if (value === 'full_markdown') updateConfig('chunkingStrategy', 'markdown_heading')
    else if (value === 'full_text') updateConfig('chunkingStrategy', 'recursive_character')
    else if (value === 'block') updateConfig('chunkingStrategy', 'block')
    setSelectedParsedDocIds([])
    setPreviewDocId(null)
    setPreview(null)
  }

  const handleFamilyChange = (f: { parser: string; parseConfigHash: string }) => {
    const opt = parseConfigs.find(
      (o) => o.parser === f.parser && o.parseConfigHash === f.parseConfigHash,
    )
    const hasMarkdown = opt?.hasFullMarkdown ?? false
    setSelectedFamily({ ...f, hasFullMarkdown: hasMarkdown })
    setSelectedParsedDocIds([])
    setPreviewDocId(null)
    setPreview(null)
    if (config.sourceRepresentation === 'full_markdown' && !hasMarkdown) {
      updateConfig('sourceRepresentation', 'full_text')
      updateConfig('chunkingStrategy', 'recursive_character')
    }
  }

  const canProceedFromStep = (step: number): boolean => {
    switch (step) {
      case 1: return name.trim() !== ''
      case 2: return selectedFamily !== null
      case 3: return true
      case 4: return selectedParsedDocIds.length > 0
      default: return true
    }
  }

  const isStepAccessible = (step: number): boolean => {
    if (step <= currentStep) return true
    if (step === currentStep + 1 && canProceedFromStep(currentStep)) return true
    return false
  }

  const handleNext = () => {
    if (currentStep < STEPS.length && canProceedFromStep(currentStep))
      setCurrentStep(currentStep + 1)
  }

  const handleBack = () => {
    if (currentStep > 1) setCurrentStep(currentStep - 1)
  }

  const handlePreview = useCallback(async () => {
    if (!previewDocId) { toast.error('Select a document to preview'); return }
    setIsPreviewLoading(true)
    try {
      const result = await previewChunks({
        parsedDocumentId: previewDocId,
        config: {
          ...config,
          parser: selectedFamily!.parser,
          parseConfigHash: selectedFamily!.parseConfigHash,
        } as IndexConfig,
        maxChunks: 10,
      })
      setPreview(result)
    } catch (error) {
      if (error instanceof AxiosError && error.response)
        toast.error(extractErrorMessage(error.response.data, 'Failed to generate preview'))
      else if (error instanceof Error) toast.error(error.message)
      else toast.error('Failed to generate preview')
    } finally {
      setIsPreviewLoading(false)
    }
  }, [previewDocId, config, selectedFamily, previewChunks])

  const handleSubmit = async (autoProcess: boolean) => {
    if (!name.trim()) { toast.error('Index name is required'); return }
    if (!selectedFamily) { toast.error('Select a parse config family'); return }
    if (selectedParsedDocIds.length === 0) { toast.error('Select at least one parsed document'); return }
    if (!currentProject) { toast.error('No project selected'); return }

    setIsSubmitting(true)
    try {
      await createIndex({
        name: name.trim(),
        description: description.trim() || undefined,
        parsedDocumentIds: selectedParsedDocIds,
        config: {
          ...config,
          parser: selectedFamily.parser,
          parseConfigHash: selectedFamily.parseConfigHash,
        } as IndexConfig,
        autoProcess,
      })
      toast.success(autoProcess ? 'Index created and processing started' : 'Index saved as draft')
      navigate('/index')
    } catch (error) {
      if (error instanceof AxiosError && error.response)
        toast.error(extractErrorMessage(error.response.data, 'Failed to create index'))
      else if (error instanceof Error) toast.error(error.message)
      else toast.error('Failed to create index')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="-m-6 min-h-[calc(100vh-4rem)]">
      <div className="max-w-5xl mx-auto px-6 py-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold">Create Index</h1>
          <p className="text-muted-foreground mt-2">
            Configure how your parsed documents will be chunked and embedded for retrieval
          </p>
        </div>

        {/* Step Indicator */}
        <div className="mb-8">
          <div className="flex items-center justify-between">
            {STEPS.map((step, index) => {
              const StepIcon = step.icon
              const isCompleted = currentStep > step.number
              const isCurrent = currentStep === step.number
              const isClickable = isStepAccessible(step.number)
              return (
                <div key={step.number} className="flex items-center flex-1 last:flex-initial">
                  <div
                    className={`flex flex-col items-center ${isClickable ? 'cursor-pointer' : 'cursor-not-allowed'}`}
                    onClick={() => isClickable && setCurrentStep(step.number)}
                  >
                    <div className={`w-10 h-10 rounded-full flex items-center justify-center mb-1 transition-all
                      ${isCompleted ? 'bg-primary text-primary-foreground'
                        : isCurrent ? 'bg-primary text-primary-foreground ring-4 ring-primary/20'
                        : isClickable ? 'bg-muted text-muted-foreground hover:bg-muted/80'
                        : 'bg-muted/50 text-muted-foreground/50'}`}
                    >
                      {isCompleted ? <Check className="w-4 h-4" /> : <StepIcon className="w-4 h-4" />}
                    </div>
                    <span className={`text-xs font-medium ${isCurrent ? 'text-primary' : isClickable ? 'text-foreground' : 'text-muted-foreground/50'}`}>
                      {step.title}
                    </span>
                  </div>
                  {index < STEPS.length - 1 && (
                    <div className={`flex-1 h-px mx-2 mt-[-0.75rem] ${isCompleted ? 'bg-primary' : 'bg-border'}`} />
                  )}
                </div>
              )
            })}
          </div>
        </div>

        <Card>
          <CardHeader>
            <CardTitle role="heading" aria-level={2}>{STEPS[currentStep - 1].title}</CardTitle>
            <CardDescription>{STEP_DESCRIPTIONS[currentStep]}</CardDescription>
          </CardHeader>

          <CardContent className="min-h-[400px]">
            {/* Step 1: Details */}
            {currentStep === 1 && (
              <div className="space-y-6 max-w-lg">
                <div className="space-y-2">
                  <Label htmlFor="name">Name <span className="text-destructive">*</span></Label>
                  <Input
                    id="name"
                    placeholder="My Index"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    disabled={isSubmitting}
                    autoFocus
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="description">Description</Label>
                  <Textarea
                    id="description"
                    placeholder="Optional description..."
                    rows={4}
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    disabled={isSubmitting}
                  />
                </div>
              </div>
            )}

            {/* Step 2: Parse-Config Family */}
            {currentStep === 2 && (
              <ParseConfigFamilySelector
                options={parseConfigs}
                selected={selectedFamily}
                onChange={handleFamilyChange}
              />
            )}

            {/* Step 3: Source Representation */}
            {currentStep === 3 && (
              <div className="space-y-4 max-w-lg">
                <div className="space-y-2">
                  <Label>Source segment</Label>
                  <ToggleGroup
                    type="single"
                    value={config.sourceRepresentation ?? 'full_text'}
                    onValueChange={(v) =>
                      v && handleSourceRepresentationChange(v as SourceRepresentation)
                    }
                    className="justify-start"
                  >
                    <ToggleGroupItem value="full_text" aria-label="Full text">
                      Full text
                    </ToggleGroupItem>
                    <ToggleGroupItem
                      value="full_markdown"
                      aria-label="Full Markdown"
                      disabled={!selectedFamily?.hasFullMarkdown}
                    >
                      Full Markdown
                    </ToggleGroupItem>
                    <ToggleGroupItem value="block" aria-label="Blocks">
                      Blocks
                    </ToggleGroupItem>
                  </ToggleGroup>
                  {!selectedFamily?.hasFullMarkdown && (
                    <p className="text-sm text-muted-foreground">
                      Full Markdown is unavailable — the selected parse-config family does not produce markdown output.
                    </p>
                  )}
                </div>
              </div>
            )}

            {/* Step 4: Parsed Documents */}
            {currentStep === 4 && selectedFamily && (
              <div className="space-y-4">
                <div className="flex items-center justify-between mb-2">
                  <p className="text-sm text-muted-foreground">
                    Select parsed documents to include in this index
                  </p>
                  <Badge variant="outline">{selectedParsedDocIds.length} selected</Badge>
                </div>
                {selectedParsedDocIds.length === 0 && (
                  <Alert>
                    <Info className="h-4 w-4" />
                    <AlertDescription>
                      Select at least one parsed document to continue
                    </AlertDescription>
                  </Alert>
                )}
                <ParsedDocumentPicker
                  projectId={currentProject!.id}
                  parser={selectedFamily.parser}
                  parseConfigHash={selectedFamily.parseConfigHash}
                  representation={config.sourceRepresentation ?? 'full_text'}
                  selectedIds={selectedParsedDocIds}
                  onChange={setSelectedParsedDocIds}
                />
              </div>
            )}

            {/* Step 5: Chunking & Embedding */}
            {currentStep === 5 && (
              <div className="space-y-8">
                <div className="space-y-4">
                  <h3 className="text-lg font-semibold">Chunking</h3>
                  {config.sourceRepresentation === 'full_markdown' ? (
                    <>
                      <div className="space-y-2">
                        <Label>Heading split level</Label>
                        <ToggleGroup
                          type="single"
                          value={String(config.splitHeadingLevel ?? 2)}
                          onValueChange={(v) => v && updateConfig('splitHeadingLevel', parseInt(v))}
                          className="justify-start"
                        >
                          <ToggleGroupItem value="1">H1 only</ToggleGroupItem>
                          <ToggleGroupItem value="2">H1 + H2</ToggleGroupItem>
                          <ToggleGroupItem value="3">H1 + H2 + H3</ToggleGroupItem>
                        </ToggleGroup>
                      </div>
                      <div className="space-y-2">
                        <div className="flex items-center justify-between">
                          <Label>Max section size</Label>
                          <span className="text-sm text-muted-foreground">
                            {(config.maxSectionChars ?? 4000).toLocaleString()} chars
                          </span>
                        </div>
                        <Slider
                          min={500} max={16000} step={500}
                          value={[config.maxSectionChars ?? 4000]}
                          onValueChange={([v]) => updateConfig('maxSectionChars', v)}
                        />
                        <p className="text-xs text-muted-foreground">
                          Sections larger than this are split further.
                        </p>
                      </div>
                    </>
                  ) : config.sourceRepresentation === 'block' ? (
                    <BlockConfigPanel config={config} onUpdate={updateConfig} />
                  ) : (
                    <>
                      <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                          <Label>Strategy</Label>
                          <Select
                            value={config.chunkingStrategy}
                            onValueChange={(v) =>
                              updateConfig('chunkingStrategy', v as IndexConfig['chunkingStrategy'])
                            }
                          >
                            <SelectTrigger><SelectValue /></SelectTrigger>
                            <SelectContent>
                              <SelectItem value="recursive_character">
                                Recursive Character (Recommended)
                              </SelectItem>
                              <SelectItem value="fixed_size">Fixed Size</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        <div className="space-y-2">
                          <Label>Unit</Label>
                          <Select
                            value={config.chunkUnit}
                            onValueChange={(v) =>
                              updateConfig('chunkUnit', v as IndexConfig['chunkUnit'])
                            }
                          >
                            <SelectTrigger><SelectValue /></SelectTrigger>
                            <SelectContent>
                              <SelectItem value="characters">Characters</SelectItem>
                              <SelectItem value="tokens">Tokens</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                      </div>
                      <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                          <Label htmlFor="chunk-size">Chunk Size</Label>
                          <Input
                            id="chunk-size"
                            type="number" min={100} max={8000}
                            value={config.chunkSize}
                            onChange={(e) =>
                              updateConfig('chunkSize', parseInt(e.target.value) || 512)
                            }
                          />
                          <p className="text-xs text-muted-foreground">
                            Target size per chunk (100–8000)
                          </p>
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="chunk-overlap">Overlap</Label>
                          <Input
                            id="chunk-overlap"
                            type="number" min={0} max={(config.chunkSize || 512) / 2}
                            value={config.chunkOverlap}
                            onChange={(e) =>
                              updateConfig('chunkOverlap', parseInt(e.target.value) || 0)
                            }
                          />
                          <p className="text-xs text-muted-foreground">
                            512–1024 characters works well for most documents.
                          </p>
                        </div>
                      </div>
                      <Alert>
                        <Info className="h-4 w-4" />
                        <AlertDescription>
                          Smaller chunks provide more precise retrieval but may increase costs.
                        </AlertDescription>
                      </Alert>
                    </>
                  )}
                </div>

                <div className="space-y-4">
                  <h3 className="text-lg font-semibold">Embedding</h3>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>Provider</Label>
                      <Select
                        value={config.embeddingProvider}
                        onValueChange={(v) => {
                          updateConfig('embeddingProvider', v)
                          if (v === 'openai') updateConfig('embeddingModel', 'text-embedding-3-small')
                          else if (v === 'voyage') updateConfig('embeddingModel', 'voyage-large-2')
                          else if (v === 'local') updateConfig('embeddingModel', 'nomic-embed-text')
                        }}
                      >
                        <SelectTrigger><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="openai">OpenAI</SelectItem>
                          <SelectItem value="voyage">Voyage AI</SelectItem>
                          <SelectItem value="local">Local (Ollama)</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2">
                      <Label>Model</Label>
                      <Select
                        value={config.embeddingModel}
                        onValueChange={(v) => updateConfig('embeddingModel', v)}
                      >
                        <SelectTrigger><SelectValue /></SelectTrigger>
                        <SelectContent>
                          {config.embeddingProvider === 'openai' && (
                            <>
                              <SelectItem value="text-embedding-3-small">text-embedding-3-small (1536)</SelectItem>
                              <SelectItem value="text-embedding-3-large">text-embedding-3-large (3072)</SelectItem>
                              <SelectItem value="text-embedding-ada-002">text-embedding-ada-002 (1536)</SelectItem>
                            </>
                          )}
                          {config.embeddingProvider === 'voyage' && (
                            <>
                              <SelectItem value="voyage-large-2">voyage-large-2 (1536)</SelectItem>
                              <SelectItem value="voyage-code-2">voyage-code-2 (1536)</SelectItem>
                              <SelectItem value="voyage-2">voyage-2 (1024)</SelectItem>
                            </>
                          )}
                          {config.embeddingProvider === 'local' && (
                            <>
                              <SelectItem value="nomic-embed-text">nomic-embed-text (768)</SelectItem>
                              <SelectItem value="mxbai-embed-large">mxbai-embed-large (1024)</SelectItem>
                            </>
                          )}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Step 6: Preview + Submit */}
            {currentStep === 6 && (
              <div className="space-y-6">
                <div className="rounded-lg border bg-muted/30 p-4">
                  <h3 className="font-medium mb-3">Configuration Summary</h3>
                  <div className="grid grid-cols-2 gap-x-8 gap-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Parser:</span>
                      <span className="font-medium">{selectedFamily?.parser}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Source:</span>
                      <span className="font-medium">{config.sourceRepresentation}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Parsed docs:</span>
                      <span className="font-medium">{selectedParsedDocIds.length}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Strategy:</span>
                      <span className="font-medium">{config.chunkingStrategy}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Chunk size:</span>
                      <span className="font-medium">
                        {config.chunkSize} {config.chunkUnit}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Model:</span>
                      <span className="font-medium">{config.embeddingModel}</span>
                    </div>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label>Select document to preview</Label>
                  <Select
                    value={previewDocId ?? ''}
                    onValueChange={(v) => { setPreviewDocId(v); setPreview(null) }}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Choose a parsed document..." />
                    </SelectTrigger>
                    <SelectContent>
                      {selectedParsedDocIds.map((id) => (
                        <SelectItem key={id} value={id}>
                          {id.slice(0, 8)}…
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <ChunkPreviewPanel
                  preview={preview}
                  isLoading={isPreviewLoading}
                  onPreview={handlePreview}
                  disabled={!previewDocId}
                />
              </div>
            )}
          </CardContent>

          <CardFooter className="flex justify-between border-t pt-6">
            <div>
              {currentStep > 1 ? (
                <Button variant="outline" onClick={handleBack} disabled={isSubmitting}>
                  <ChevronLeft className="w-4 h-4 mr-2" />Back
                </Button>
              ) : (
                <Button variant="outline" onClick={() => navigate('/index')} disabled={isSubmitting}>
                  Cancel
                </Button>
              )}
            </div>
            <div className="flex gap-2">
              <Button
                variant="outline"
                onClick={() => handleSubmit(false)}
                disabled={
                  isSubmitting ||
                  !name.trim() ||
                  !selectedFamily ||
                  selectedParsedDocIds.length === 0
                }
              >
                {isSubmitting ? (
                  <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Saving...</>
                ) : (
                  'Save as Draft'
                )}
              </Button>
              {currentStep < STEPS.length ? (
                <Button
                  onClick={handleNext}
                  disabled={!canProceedFromStep(currentStep)}
                >
                  Continue<ChevronRight className="w-4 h-4 ml-2" />
                </Button>
              ) : (
                <Button onClick={() => handleSubmit(true)} disabled={isSubmitting}>
                  {isSubmitting ? (
                    <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Creating...</>
                  ) : (
                    'Create & Build Index'
                  )}
                </Button>
              )}
            </div>
          </CardFooter>
        </Card>
      </div>
    </div>
  )
}
