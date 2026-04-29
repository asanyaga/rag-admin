/**
 * Dialog for creating a new index
 */
import { useState, useCallback } from 'react'
import { AxiosError } from 'axios'
import { IndexCreate, IndexConfig, ChunkPreviewResponse } from '@/types/index'
import { DocumentListItem } from '@/types/document'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { Slider } from '@/components/ui/slider'
import { SourceRepresentation } from '@/types/index'
import { DocumentSelector } from './DocumentSelector'
import { ChunkPreviewPanel } from './ChunkPreviewPanel'
import { toast } from 'sonner'

interface IndexCreateDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSubmit: (data: IndexCreate) => Promise<void>
  onPreviewChunks: (
    documentId: string,
    config: Partial<IndexConfig>
  ) => Promise<ChunkPreviewResponse>
  documents: DocumentListItem[]
  preselectedDocumentIds?: string[]
}

const DEFAULT_CONFIG: Partial<IndexConfig> = {
  sourceRepresentation: 'raw_text',
  chunkingStrategy: 'recursive_character',
  chunkSize: 512,
  chunkOverlap: 50,
  chunkUnit: 'characters',
  splitHeadingLevel: 2,
  maxSectionChars: 4000,
  embeddingProvider: 'openai',
  embeddingModel: 'text-embedding-3-small',
}

export function IndexCreateDialog({
  open,
  onOpenChange,
  onSubmit,
  onPreviewChunks,
  documents,
  preselectedDocumentIds = [],
}: IndexCreateDialogProps) {
  const [isLoading, setIsLoading] = useState(false)
  const [isPreviewLoading, setIsPreviewLoading] = useState(false)
  const [preview, setPreview] = useState<ChunkPreviewResponse | null>(null)

  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [selectedDocumentIds, setSelectedDocumentIds] = useState<string[]>(
    preselectedDocumentIds
  )
  const [config, setConfig] = useState<Partial<IndexConfig>>(DEFAULT_CONFIG)

  const handlePreview = useCallback(async () => {
    if (selectedDocumentIds.length === 0) {
      toast.error('Select at least one document to preview')
      return
    }

    setIsPreviewLoading(true)
    try {
      // Preview using the first selected document
      const result = await onPreviewChunks(selectedDocumentIds[0], config)
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
  }, [selectedDocumentIds, config, onPreviewChunks])

  const handleSubmit = async (autoProcess: boolean) => {
    if (!name.trim()) {
      toast.error('Index name is required')
      return
    }

    if (selectedDocumentIds.length === 0) {
      toast.error('Select at least one document')
      return
    }

    setIsLoading(true)
    try {
      await onSubmit({
        name: name.trim(),
        description: description.trim() || undefined,
        documentIds: selectedDocumentIds,
        config,
        autoProcess,
      })
      handleClose()
      toast.success(
        autoProcess
          ? 'Index created and processing started'
          : 'Index saved as draft'
      )
    } catch (error) {
      if (error instanceof AxiosError && error.response) {
        toast.error(error.response.data?.detail || 'Failed to create index')
      } else {
        toast.error('Failed to create index')
      }
    } finally {
      setIsLoading(false)
    }
  }

  const handleClose = () => {
    if (!isLoading) {
      setName('')
      setDescription('')
      setSelectedDocumentIds(preselectedDocumentIds)
      setConfig(DEFAULT_CONFIG)
      setPreview(null)
      onOpenChange(false)
    }
  }

  const updateConfig = (key: keyof IndexConfig, value: IndexConfig[keyof IndexConfig]) => {
    setConfig((prev) => ({ ...prev, [key]: value }))
    setPreview(null) // Clear preview when config changes
  }

  const handleSourceRepresentationChange = (value: SourceRepresentation) => {
    updateConfig('sourceRepresentation', value)
    if (value === 'full_markdown') {
      updateConfig('chunkingStrategy', 'markdown_heading')
    } else if (value === 'raw_text' || value === 'full_text') {
      updateConfig('chunkingStrategy', 'recursive_character')
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle>Create Index</DialogTitle>
          <DialogDescription>
            Configure how your documents will be chunked and embedded for
            retrieval.
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto py-4">
          <div className="space-y-6">
            {/* Basic Info */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="name">
                  Name <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="name"
                  placeholder="My Index"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  disabled={isLoading}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="description">Description</Label>
                <Input
                  id="description"
                  placeholder="Optional description..."
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  disabled={isLoading}
                />
              </div>
            </div>

            {/* Documents */}
            <div className="space-y-2">
              <Label>Documents</Label>
              <DocumentSelector
                documents={documents}
                selectedIds={selectedDocumentIds}
                onChange={setSelectedDocumentIds}
              />
            </div>

            {/* Configuration */}
            <Tabs defaultValue="chunking" className="w-full">
              <TabsList className="grid w-full grid-cols-2">
                <TabsTrigger value="chunking">Chunking</TabsTrigger>
                <TabsTrigger value="embedding">Embedding</TabsTrigger>
              </TabsList>

              <TabsContent value="chunking" className="space-y-4 mt-4">
                {/* Source representation */}
                <div className="space-y-2">
                  <Label>Source</Label>
                  <ToggleGroup
                    type="single"
                    value={config.sourceRepresentation ?? 'raw_text'}
                    onValueChange={(v) =>
                      v && handleSourceRepresentationChange(v as SourceRepresentation)
                    }
                    className="justify-start"
                  >
                    <ToggleGroupItem value="raw_text" aria-label="Raw text">
                      Raw text
                    </ToggleGroupItem>
                    <ToggleGroupItem value="full_text" aria-label="Full text">
                      Full text
                    </ToggleGroupItem>
                    <ToggleGroupItem value="full_markdown" aria-label="Full Markdown">
                      Full Markdown
                    </ToggleGroupItem>
                  </ToggleGroup>
                </div>

                {config.sourceRepresentation === 'full_markdown' ? (
                  /* Markdown-specific controls */
                  <>
                    <div className="space-y-2">
                      <Label>Heading split level</Label>
                      <ToggleGroup
                        type="single"
                        value={String(config.splitHeadingLevel ?? 2)}
                        onValueChange={(v) =>
                          v && updateConfig('splitHeadingLevel', parseInt(v))
                        }
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
                        min={500}
                        max={16000}
                        step={500}
                        value={[config.maxSectionChars ?? 4000]}
                        onValueChange={([v]) => updateConfig('maxSectionChars', v)}
                        disabled={isLoading}
                      />
                      <p className="text-xs text-muted-foreground">
                        Sections larger than this are split further.
                      </p>
                    </div>
                  </>
                ) : (
                  /* Text-based chunking controls */
                  <>
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
                        <Label htmlFor="chunk-size">Chunk Size</Label>
                        <Input
                          id="chunk-size"
                          type="number"
                          min={100}
                          max={8000}
                          value={config.chunkSize}
                          onChange={(e) =>
                            updateConfig('chunkSize', parseInt(e.target.value) || 512)
                          }
                        />
                        <p className="text-xs text-muted-foreground">
                          Target size per chunk (100-8000)
                        </p>
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="chunk-overlap">Overlap</Label>
                        <Input
                          id="chunk-overlap"
                          type="number"
                          min={0}
                          max={(config.chunkSize || 512) / 2}
                          value={config.chunkOverlap}
                          onChange={(e) =>
                            updateConfig('chunkOverlap', parseInt(e.target.value) || 0)
                          }
                        />
                        <p className="text-xs text-muted-foreground">
                          Overlap between chunks (max{' '}
                          {Math.floor((config.chunkSize || 512) / 2)})
                        </p>
                      </div>
                    </div>
                  </>
                )}
              </TabsContent>

              <TabsContent value="embedding" className="space-y-4 mt-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Provider</Label>
                    <Select
                      value={config.embeddingProvider}
                      onValueChange={(v) => {
                        updateConfig('embeddingProvider', v)
                        // Reset model when provider changes
                        if (v === 'openai') {
                          updateConfig('embeddingModel', 'text-embedding-3-small')
                        } else if (v === 'voyage') {
                          updateConfig('embeddingModel', 'voyage-large-2')
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
                      onValueChange={(v) => updateConfig('embeddingModel', v)}
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
              </TabsContent>
            </Tabs>

            {/* Chunk Preview */}
            <ChunkPreviewPanel
              preview={preview}
              isLoading={isPreviewLoading}
              onPreview={handlePreview}
              disabled={selectedDocumentIds.length === 0}
            />
          </div>
        </div>

        <DialogFooter className="flex-shrink-0 gap-2">
          <Button variant="outline" onClick={handleClose} disabled={isLoading}>
            Cancel
          </Button>
          <Button
            variant="outline"
            onClick={() => handleSubmit(false)}
            disabled={isLoading}
          >
            {isLoading ? 'Saving...' : 'Save as Draft'}
          </Button>
          <Button onClick={() => handleSubmit(true)} disabled={isLoading}>
            {isLoading ? 'Creating...' : 'Create & Build Index'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
