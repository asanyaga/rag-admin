/**
 * Multi-step wizard for creating a new index
 * Steps: Details → Documents → Configuration → Preview
 */
import { useState, useCallback, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { AxiosError } from 'axios'
import { useProject } from '@/contexts/ProjectContext'
import { useIndexes } from '@/hooks/useIndexes'
import { useDocuments } from '@/hooks/useDocuments'
import { IndexConfig, ChunkPreviewResponse } from '@/types/index'
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription } from '@/components/ui/alert'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { DocumentSelector } from '@/components/indexes/DocumentSelector'
import { ChunkPreviewPanel } from '@/components/indexes/ChunkPreviewPanel'
import { toast } from 'sonner'
import {
  FileText,
  ChevronRight,
  ChevronLeft,
  Info,
  Check,
  Layers,
  Settings,
  Eye,
  Loader2,
} from 'lucide-react'

const STEPS = [
  { number: 1, title: 'Details', icon: FileText },
  { number: 2, title: 'Documents', icon: Layers },
  { number: 3, title: 'Configuration', icon: Settings },
  { number: 4, title: 'Preview', icon: Eye },
] as const

const DEFAULT_CONFIG: Partial<IndexConfig> = {
  chunkingStrategy: 'recursive_character',
  chunkSize: 512,
  chunkOverlap: 50,
  chunkUnit: 'characters',
  embeddingProvider: 'openai',
  embeddingModel: 'text-embedding-3-small',
}

export default function CreateIndexPage() {
  const navigate = useNavigate()
  const { currentProject } = useProject()
  const { createIndex, previewChunks } = useIndexes(currentProject?.id ?? null)
  const { documents } = useDocuments(currentProject?.id ?? null)

  const [currentStep, setCurrentStep] = useState(1)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isPreviewLoading, setIsPreviewLoading] = useState(false)
  const [preview, setPreview] = useState<ChunkPreviewResponse | null>(null)
  const [previewDocumentId, setPreviewDocumentId] = useState<string | null>(null)

  // Form state
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [selectedDocumentIds, setSelectedDocumentIds] = useState<string[]>([])
  const [config, setConfig] = useState<Partial<IndexConfig>>(DEFAULT_CONFIG)

  const readyDocuments = documents.filter((d) => d.status === 'ready')

  // Redirect if no project
  useEffect(() => {
    if (!currentProject) {
      navigate('/index')
    }
  }, [currentProject, navigate])

  const updateConfig = (key: keyof IndexConfig, value: string | number) => {
    setConfig((prev) => ({ ...prev, [key]: value }))
    setPreview(null)
  }

  const canProceedFromStep = (step: number): boolean => {
    switch (step) {
      case 1:
        return name.trim() !== ''
      case 2:
        return selectedDocumentIds.length > 0
      case 3:
        return true
      default:
        return true
    }
  }

  const isStepAccessible = (step: number): boolean => {
    if (step <= currentStep) return true
    // Can go forward one step if current step is valid
    if (step === currentStep + 1 && canProceedFromStep(currentStep)) return true
    return false
  }

  const handleNext = () => {
    if (currentStep < 4 && canProceedFromStep(currentStep)) {
      setCurrentStep(currentStep + 1)
    }
  }

  const handleBack = () => {
    if (currentStep > 1) setCurrentStep(currentStep - 1)
  }

  const handleStepClick = (step: number) => {
    if (isStepAccessible(step)) {
      setCurrentStep(step)
    }
  }

  // Auto-select first document for preview when entering step 4
  useEffect(() => {
    if (currentStep === 4 && selectedDocumentIds.length > 0 && !previewDocumentId) {
      setPreviewDocumentId(selectedDocumentIds[0])
    }
  }, [currentStep, selectedDocumentIds, previewDocumentId])

  // Clear preview when selected document changes
  const handlePreviewDocumentChange = (docId: string) => {
    setPreviewDocumentId(docId)
    setPreview(null)
  }

  const handlePreview = useCallback(async () => {
    if (!previewDocumentId) {
      toast.error('Select a document to preview')
      return
    }

    setIsPreviewLoading(true)
    try {
      const result = await previewChunks({
        documentId: previewDocumentId,
        config,
        maxChunks: 10,
      })
      setPreview(result)
    } catch (error) {
      if (error instanceof AxiosError && error.response) {
        toast.error(error.response.data?.detail || 'Failed to generate preview')
      } else {
        toast.error('Failed to generate preview')
      }
    } finally {
      setIsPreviewLoading(false)
    }
  }, [previewDocumentId, config, previewChunks])

  const handleSubmit = async (autoProcess: boolean) => {
    if (!name.trim()) {
      toast.error('Index name is required')
      return
    }
    if (selectedDocumentIds.length === 0) {
      toast.error('Select at least one document')
      return
    }

    setIsSubmitting(true)
    try {
      await createIndex({
        name: name.trim(),
        description: description.trim() || undefined,
        documentIds: selectedDocumentIds,
        config,
        autoProcess,
      })
      toast.success(
        autoProcess
          ? 'Index created and processing started'
          : 'Index saved as draft'
      )
      navigate('/index')
    } catch (error) {
      if (error instanceof AxiosError && error.response) {
        toast.error(error.response.data?.detail || 'Failed to create index')
      } else {
        toast.error('Failed to create index')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  const stepDescriptions: Record<number, string> = {
    1: 'Enter basic information about your index',
    2: 'Select documents to include in this index',
    3: 'Configure chunking and embedding settings',
    4: 'Preview how your documents will be chunked',
  }

  return (
    <div className="-m-6 min-h-[calc(100vh-4rem)]">
      <div className="max-w-5xl mx-auto px-6 py-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold">Create Index</h1>
          <p className="text-muted-foreground mt-2">
            Configure how your documents will be chunked and embedded for
            retrieval
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
                    className={`flex flex-col items-center ${
                      isClickable ? 'cursor-pointer' : 'cursor-not-allowed'
                    }`}
                    onClick={() => handleStepClick(step.number)}
                  >
                    <div
                      className={`
                      w-12 h-12 rounded-full flex items-center justify-center mb-2 transition-all
                      ${
                        isCompleted
                          ? 'bg-primary text-primary-foreground'
                          : isCurrent
                            ? 'bg-primary text-primary-foreground ring-4 ring-primary/20'
                            : isClickable
                              ? 'bg-muted text-muted-foreground hover:bg-muted/80'
                              : 'bg-muted/50 text-muted-foreground/50'
                      }
                    `}
                    >
                      {isCompleted ? (
                        <Check className="w-5 h-5" />
                      ) : (
                        <StepIcon className="w-5 h-5" />
                      )}
                    </div>
                    <span
                      className={`text-sm font-medium ${
                        isCurrent
                          ? 'text-primary'
                          : isClickable
                            ? 'text-foreground'
                            : 'text-muted-foreground/50'
                      }`}
                    >
                      {step.title}
                    </span>
                  </div>
                  {index < STEPS.length - 1 && (
                    <div
                      className={`flex-1 h-px mx-4 mt-[-1.25rem] ${
                        isCompleted ? 'bg-primary' : 'bg-border'
                      }`}
                    />
                  )}
                </div>
              )
            })}
          </div>
        </div>

        {/* Main Content Card */}
        <Card>
          <CardHeader>
            <CardTitle>{STEPS[currentStep - 1].title}</CardTitle>
            <CardDescription>
              {stepDescriptions[currentStep]}
            </CardDescription>
          </CardHeader>

          <CardContent className="min-h-[400px]">
            {/* Step 1: Details */}
            {currentStep === 1 && (
              <div className="space-y-6 max-w-lg">
                <div className="space-y-2">
                  <Label htmlFor="name">
                    Name <span className="text-destructive">*</span>
                  </Label>
                  <Input
                    id="name"
                    placeholder="My Index"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    disabled={isSubmitting}
                    autoFocus
                  />
                  {name.trim() === '' && (
                    <p className="text-sm text-muted-foreground">
                      Index name is required
                    </p>
                  )}
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
                  <p className="text-sm text-muted-foreground">
                    Help others understand what this index is for
                  </p>
                </div>
              </div>
            )}

            {/* Step 2: Documents */}
            {currentStep === 2 && (
              <div className="space-y-4">
                <div className="flex items-center justify-between mb-2">
                  <p className="text-sm text-muted-foreground">
                    {readyDocuments.length} documents available
                  </p>
                  <Badge variant="outline">
                    {selectedDocumentIds.length} selected
                  </Badge>
                </div>

                {selectedDocumentIds.length === 0 && (
                  <Alert>
                    <Info className="h-4 w-4" />
                    <AlertDescription>
                      Select at least one document to create an index
                    </AlertDescription>
                  </Alert>
                )}

                <DocumentSelector
                  documents={readyDocuments}
                  selectedIds={selectedDocumentIds}
                  onChange={setSelectedDocumentIds}
                />
              </div>
            )}

            {/* Step 3: Configuration */}
            {currentStep === 3 && (
              <div className="space-y-8">
                {/* Chunking Section */}
                <div className="space-y-4">
                  <div className="flex items-center gap-2">
                    <h3 className="text-lg font-semibold">Chunking</h3>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>Strategy</Label>
                      <Select
                        value={config.chunkingStrategy}
                        onValueChange={(v) =>
                          updateConfig(
                            'chunkingStrategy',
                            v as IndexConfig['chunkingStrategy']
                          )
                        }
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="recursive_character">
                            Recursive Character (Recommended)
                          </SelectItem>
                          <SelectItem value="fixed_size">
                            Fixed Size
                          </SelectItem>
                        </SelectContent>
                      </Select>
                      <p className="text-xs text-muted-foreground">
                        Splits text recursively by common separators
                      </p>
                    </div>

                    <div className="space-y-2">
                      <Label>Unit</Label>
                      <Select
                        value={config.chunkUnit}
                        onValueChange={(v) =>
                          updateConfig(
                            'chunkUnit',
                            v as IndexConfig['chunkUnit']
                          )
                        }
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="characters">Characters</SelectItem>
                          <SelectItem value="tokens">Tokens</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>Chunk Size</Label>
                      <Input
                        type="number"
                        min={100}
                        max={8000}
                        value={config.chunkSize}
                        onChange={(e) =>
                          updateConfig(
                            'chunkSize',
                            parseInt(e.target.value) || 512
                          )
                        }
                      />
                      <p className="text-xs text-muted-foreground">
                        Target size per chunk (100-8000)
                      </p>
                    </div>

                    <div className="space-y-2">
                      <Label>Overlap</Label>
                      <Input
                        type="number"
                        min={0}
                        max={Math.floor((config.chunkSize || 512) / 2)}
                        value={config.chunkOverlap}
                        onChange={(e) =>
                          updateConfig(
                            'chunkOverlap',
                            parseInt(e.target.value) || 0
                          )
                        }
                      />
                      <p className="text-xs text-muted-foreground">
                        Overlap between chunks (max{' '}
                        {Math.floor((config.chunkSize || 512) / 2)})
                      </p>
                    </div>
                  </div>

                  <Alert>
                    <Info className="h-4 w-4" />
                    <AlertDescription>
                      Smaller chunks provide more precise retrieval but may
                      increase costs. 512-1024 characters works well for most
                      documents.
                    </AlertDescription>
                  </Alert>
                </div>

                {/* Embedding Section */}
                <div className="space-y-4">
                  <h3 className="text-lg font-semibold">Embedding</h3>

                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>Provider</Label>
                      <Select
                        value={config.embeddingProvider}
                        onValueChange={(v) => {
                          updateConfig('embeddingProvider', v)
                          if (v === 'openai') {
                            updateConfig(
                              'embeddingModel',
                              'text-embedding-3-small'
                            )
                          } else if (v === 'voyage') {
                            updateConfig('embeddingModel', 'voyage-large-2')
                          } else if (v === 'local') {
                            updateConfig('embeddingModel', 'nomic-embed-text')
                          }
                        }}
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
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
                        onValueChange={(v) =>
                          updateConfig('embeddingModel', v)
                        }
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {config.embeddingProvider === 'openai' && (
                            <>
                              <SelectItem value="text-embedding-3-small">
                                text-embedding-3-small (1536 dims)
                              </SelectItem>
                              <SelectItem value="text-embedding-3-large">
                                text-embedding-3-large (3072 dims)
                              </SelectItem>
                              <SelectItem value="text-embedding-ada-002">
                                text-embedding-ada-002 (1536 dims)
                              </SelectItem>
                            </>
                          )}
                          {config.embeddingProvider === 'voyage' && (
                            <>
                              <SelectItem value="voyage-large-2">
                                voyage-large-2 (1536 dims)
                              </SelectItem>
                              <SelectItem value="voyage-code-2">
                                voyage-code-2 (1536 dims)
                              </SelectItem>
                              <SelectItem value="voyage-2">
                                voyage-2 (1024 dims)
                              </SelectItem>
                            </>
                          )}
                          {config.embeddingProvider === 'local' && (
                            <>
                              <SelectItem value="nomic-embed-text">
                                nomic-embed-text (768 dims)
                              </SelectItem>
                              <SelectItem value="mxbai-embed-large">
                                mxbai-embed-large (1024 dims)
                              </SelectItem>
                            </>
                          )}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Step 4: Preview */}
            {currentStep === 4 && (
              <div className="space-y-6">
                {/* Configuration Summary */}
                <div className="rounded-lg border bg-muted/30 p-4">
                  <h3 className="font-medium mb-3">Configuration Summary</h3>
                  <div className="grid grid-cols-2 gap-x-8 gap-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Documents:</span>
                      <span className="font-medium">
                        {selectedDocumentIds.length}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Strategy:</span>
                      <span className="font-medium">
                        {config.chunkingStrategy === 'recursive_character'
                          ? 'Recursive Character'
                          : 'Fixed Size'}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Chunk Size:</span>
                      <span className="font-medium">
                        {config.chunkSize} {config.chunkUnit}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Overlap:</span>
                      <span className="font-medium">
                        {config.chunkOverlap} {config.chunkUnit}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Provider:</span>
                      <span className="font-medium">
                        {config.embeddingProvider}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Model:</span>
                      <span className="font-medium">
                        {config.embeddingModel}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Document Selector for Preview */}
                <div className="space-y-2">
                  <Label>Select Document to Preview</Label>
                  <Select
                    value={previewDocumentId ?? ''}
                    onValueChange={handlePreviewDocumentChange}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Choose a document..." />
                    </SelectTrigger>
                    <SelectContent>
                      {selectedDocumentIds.map((docId) => {
                        const doc = readyDocuments.find((d) => d.id === docId)
                        return doc ? (
                          <SelectItem key={docId} value={docId}>
                            {doc.title}
                          </SelectItem>
                        ) : null
                      })}
                    </SelectContent>
                  </Select>
                  <p className="text-sm text-muted-foreground">
                    Preview how this document will be split into chunks
                  </p>
                </div>

                {/* Chunk Preview */}
                <ChunkPreviewPanel
                  preview={preview}
                  isLoading={isPreviewLoading}
                  onPreview={handlePreview}
                  disabled={!previewDocumentId}
                />
              </div>
            )}
          </CardContent>

          <CardFooter className="flex justify-between border-t pt-6">
            <div>
              {currentStep > 1 ? (
                <Button
                  variant="outline"
                  onClick={handleBack}
                  disabled={isSubmitting}
                >
                  <ChevronLeft className="w-4 h-4 mr-2" />
                  Back
                </Button>
              ) : (
                <Button
                  variant="outline"
                  onClick={() => navigate('/index')}
                  disabled={isSubmitting}
                >
                  Cancel
                </Button>
              )}
            </div>

            <div className="flex gap-2">
              <Button
                variant="outline"
                onClick={() => handleSubmit(false)}
                disabled={
                  isSubmitting || !name.trim() || selectedDocumentIds.length === 0
                }
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Saving...
                  </>
                ) : (
                  'Save as Draft'
                )}
              </Button>

              {currentStep < 4 ? (
                <Button
                  onClick={handleNext}
                  disabled={!canProceedFromStep(currentStep)}
                >
                  Continue
                  <ChevronRight className="w-4 h-4 ml-2" />
                </Button>
              ) : (
                <Button
                  onClick={() => handleSubmit(true)}
                  disabled={isSubmitting}
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      Creating...
                    </>
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
