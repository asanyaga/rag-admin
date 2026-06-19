/**
 * Redesigned Index Detail page with persistent header, Content tab, and Playground tab
 */
import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useProject } from '@/contexts/ProjectContext'
import { useIndexDetail, useIndexes } from '@/hooks/useIndexes'
import { IndexUpdate, ChunkListItem, IndexParsedDocumentItem } from '@/types/index'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { IndexStatusBadge } from '@/components/indexes/IndexStatusBadge'
import { ParsedDocumentPicker } from '@/components/indexes/ParsedDocumentPicker'
import { PlaygroundPanel } from '@/components/indexes/PlaygroundPanel'
import {
  ArrowLeft,
  FileText,
  Play,
  Settings,
  Pencil,
  Check,
  Upload,
  Trash2,
  X,
  Search,
  ChevronLeft,
  ChevronRight,
  Layers,
  AlertTriangle,
} from 'lucide-react'
import { toast } from 'sonner'
import * as indexesApi from '@/api/indexes'
import { cn } from '@/lib/utils'

export default function IndexDetailPage() {
  const { indexId } = useParams<{ indexId: string }>()
  const navigate = useNavigate()
  const { currentProject } = useProject()
  const projectId = currentProject?.id ?? null

  const { index, chunks, isLoading, error, fetchIndex, fetchChunks } =
    useIndexDetail(projectId, indexId ?? null)
  const { updateIndex, processIndex } = useIndexes(projectId)

  // Tab state
  const [activeTab, setActiveTab] = useState<'content' | 'playground'>('content')

  // Header edit state
  const [editingName, setEditingName] = useState(false)
  const [editName, setEditName] = useState('')
  const [editingDesc, setEditingDesc] = useState(false)
  const [editDesc, setEditDesc] = useState('')
  const [isSaving, setIsSaving] = useState(false)
  const [showConfig, setShowConfig] = useState(false)

  // Content tab state
  const [selectedChunk, setSelectedChunk] = useState<ChunkListItem | null>(null)
  const [chunkSearch, setChunkSearch] = useState('')
  const [chunkPage, setChunkPage] = useState(1)

  // Add documents dialog
  const [addDocsDialogOpen, setAddDocsDialogOpen] = useState(false)
  const [selectedParsedDocIds, setSelectedParsedDocIds] = useState<string[]>([])

  // Remove document dialog
  const [removeDocDialogOpen, setRemoveDocDialogOpen] = useState(false)
  const [parsedDocToRemove, setParsedDocToRemove] = useState<string | null>(null)
  const [isRemovingDoc, setIsRemovingDoc] = useState(false)

  // Processing state
  const [isProcessing, setIsProcessing] = useState(false)

  // Initialize edit state when index loads
  useEffect(() => {
    if (index) {
      setEditName(index.name)
      setEditDesc(index.description || '')
    }
  }, [index])

  // Poll when index is processing
  useEffect(() => {
    if (index?.status !== 'processing') return
    const interval = setInterval(() => {
      fetchIndex()
      fetchChunks(chunkPage, chunkSearch || undefined)
    }, 3000)
    return () => clearInterval(interval)
  }, [index?.status, fetchIndex, fetchChunks, chunkPage, chunkSearch])

  const canEdit = index?.status !== 'processing'
  const canManageDocs = index?.status === 'created' || index?.status === 'ready'

  // Parsed documents state
  const [parsedDocs, setParsedDocs] = useState<IndexParsedDocumentItem[]>([])
  const [isParsedDocsLoading, setIsParsedDocsLoading] = useState(false)

  const fetchParsedDocs = useCallback(async () => {
    if (!projectId || !indexId) return
    setIsParsedDocsLoading(true)
    try {
      const data = await indexesApi.listIndexParsedDocuments(projectId, indexId)
      setParsedDocs(data)
    } catch {
      // silent — tab shows empty state on error
    } finally {
      setIsParsedDocsLoading(false)
    }
  }, [projectId, indexId])

  // Fetch parsed documents on mount
  useEffect(() => {
    fetchParsedDocs()
  }, [fetchParsedDocs])

  // ─── Handlers ─────────────────────────────────────────────────────────────

  const handleSaveName = async () => {
    if (!index || !projectId || !indexId || editName === index.name) {
      setEditingName(false)
      return
    }
    setIsSaving(true)
    try {
      const updates: IndexUpdate = { name: editName }
      await updateIndex(indexId, updates)
      await fetchIndex()
      toast.success('Name updated')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update name')
      setEditName(index.name)
    } finally {
      setIsSaving(false)
      setEditingName(false)
    }
  }

  const handleSaveDesc = async () => {
    if (!index || !projectId || !indexId || editDesc === (index.description || '')) {
      setEditingDesc(false)
      return
    }
    setIsSaving(true)
    try {
      const updates: IndexUpdate = { description: editDesc }
      await updateIndex(indexId, updates)
      await fetchIndex()
      toast.success('Description updated')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update')
      setEditDesc(index.description || '')
    } finally {
      setIsSaving(false)
      setEditingDesc(false)
    }
  }

  const handleAddDocuments = async () => {
    if (!projectId || !indexId || selectedParsedDocIds.length === 0) return
    try {
      await indexesApi.addParsedDocuments(projectId, indexId, {
        parsedDocumentIds: selectedParsedDocIds,
      })
      await fetchIndex()
      await fetchParsedDocs()
      setAddDocsDialogOpen(false)
      setSelectedParsedDocIds([])
      toast.success(
        `${selectedParsedDocIds.length} parsed document${selectedParsedDocIds.length > 1 ? 's' : ''} added`,
      )
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to add documents')
    }
  }

  const handleRemoveDocument = async () => {
    if (!projectId || !indexId || !parsedDocToRemove) return
    setIsRemovingDoc(true)
    try {
      await indexesApi.removeIndexParsedDocument(projectId, indexId, parsedDocToRemove)
      await fetchIndex()
      await fetchParsedDocs()
      setRemoveDocDialogOpen(false)
      setParsedDocToRemove(null)
      toast.success('Document removed')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to remove document')
    } finally {
      setIsRemovingDoc(false)
    }
  }

  const handleProcessIndex = async () => {
    if (!indexId) return
    setIsProcessing(true)
    try {
      await processIndex(indexId)
      await fetchIndex()
      toast.success('Processing started')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to start processing')
    } finally {
      setIsProcessing(false)
    }
  }

  const handleChunkSearch = () => {
    setChunkPage(1)
    fetchChunks(1, chunkSearch || undefined)
  }

  const handleChunkPageChange = (newPage: number) => {
    setChunkPage(newPage)
    fetchChunks(newPage, chunkSearch || undefined)
  }

  // ─── Guards ───────────────────────────────────────────────────────────────

  if (!projectId) {
    return (
      <Alert>
        <AlertTriangle className="h-4 w-4" />
        <AlertDescription>Please select a project first.</AlertDescription>
      </Alert>
    )
  }

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  if (error || !index) {
    return (
      <Alert variant="destructive">
        <AlertDescription>{error || 'Index not found'}</AlertDescription>
      </Alert>
    )
  }

  // ─── Config items for drawer ──────────────────────────────────────────────

  const configItems = [
    { label: 'Chunking Strategy', value: index.config.chunkingStrategy },
    { label: 'Chunk Size', value: `${index.config.chunkSize} ${index.config.chunkUnit}` },
    { label: 'Chunk Overlap', value: `${index.config.chunkOverlap} ${index.config.chunkUnit}` },
    { label: 'Embedding Provider', value: index.config.embeddingProvider },
    { label: 'Embedding Model', value: index.config.embeddingModel },
    { label: 'Dimensions', value: index.config.embeddingDimensions ?? 'Auto' },
  ]

  const tabs = [
    { id: 'content' as const, label: 'Content', icon: FileText },
    { id: 'playground' as const, label: 'Playground', icon: Play },
  ]

  return (
    <div className="-m-6 min-h-[calc(100vh-4rem)]">
      {/* ══════ Breadcrumb ══════ */}
      <div className="border-b px-6 py-3 flex items-center gap-2 sticky top-0 z-30 bg-background">
        <button
          onClick={() => navigate('/index')}
          className="p-1 rounded-md hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
        </button>
        <span className="text-sm text-muted-foreground">Indexes</span>
        <span className="text-muted-foreground/40">/</span>
        <span className="text-sm font-medium text-foreground">{index.name}</span>
        <div className="ml-auto">
          <IndexStatusBadge status={index.status} />
        </div>
      </div>

      {/* ══════ Index Header ══════ */}
      <div className="mx-6 mt-5 p-5 rounded-lg border">
        <div className="flex items-start justify-between mb-4">
          <div className="flex-1 min-w-0">
            {/* Editable Name */}
            {editingName ? (
              <div className="flex items-center gap-2">
                <Input
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  onBlur={handleSaveName}
                  onKeyDown={(e) => e.key === 'Enter' && handleSaveName()}
                  autoFocus
                  className="text-xl font-semibold h-auto py-1 w-96"
                  disabled={isSaving}
                />
                <Button
                  size="icon"
                  className="h-8 w-8"
                  onClick={handleSaveName}
                  disabled={isSaving}
                >
                  <Check className="h-3.5 w-3.5" />
                </Button>
              </div>
            ) : (
              <div className="flex items-center gap-2 group">
                <h1 className="text-xl font-semibold">{index.name}</h1>
                <span className="text-xs text-muted-foreground font-mono bg-muted px-1.5 py-0.5 rounded">
                  v{index.version ?? 1}
                </span>
                {canEdit && (
                  <button
                    onClick={() => setEditingName(true)}
                    className="p-1 rounded-md text-muted-foreground/40 hover:text-muted-foreground opacity-0 group-hover:opacity-100 transition-all"
                  >
                    <Pencil className="h-3.5 w-3.5" />
                  </button>
                )}
              </div>
            )}

            {/* Editable Description */}
            {editingDesc ? (
              <textarea
                value={editDesc}
                onChange={(e) => setEditDesc(e.target.value)}
                onBlur={handleSaveDesc}
                autoFocus
                rows={2}
                className="mt-1.5 text-sm text-muted-foreground bg-muted/50 border rounded-md px-2 py-1.5 outline-none focus:ring-2 focus:ring-ring focus:border-transparent w-full resize-vertical leading-relaxed"
              />
            ) : (
              <p
                onClick={() => canEdit && setEditingDesc(true)}
                className={cn(
                  'mt-1.5 text-sm text-muted-foreground max-w-xl leading-relaxed',
                  canEdit && 'cursor-pointer hover:text-foreground transition-colors'
                )}
              >
                {index.description || (
                  canEdit ? (
                    <span className="italic text-muted-foreground">Add a description...</span>
                  ) : null
                )}
              </p>
            )}
          </div>

          {/* Settings Toggle */}
          <button
            onClick={() => setShowConfig(!showConfig)}
            className={cn(
              'flex items-center gap-2 px-3 py-2 rounded-md border text-sm transition-colors',
              showConfig
                ? 'bg-muted border text-foreground'
                : 'border text-muted-foreground hover:bg-muted/50'
            )}
          >
            <Settings className="h-4 w-4" /> Config
          </button>
        </div>

        {/* Stats Row */}
        <div className="flex items-center gap-6 flex-wrap">
          {[
            { label: 'Documents', value: index.documentCount },
            { label: 'Chunks', value: index.chunkCount.toLocaleString() },
            {
              label: 'Avg Tokens',
              value: index.stats ? Math.round(index.stats.avgChunkSizeTokens) : '—',
            },
            { label: 'Model', value: index.config.embeddingModel },
            {
              label: 'Dimensions',
              value: index.stats
                ? index.stats.embeddingDimensions.toLocaleString()
                : index.config.embeddingDimensions ?? '—',
            },
          ].map((s) => (
            <div key={s.label} className="flex items-baseline gap-1.5">
              <span className="text-sm font-semibold font-mono text-foreground">
                {s.value}
              </span>
              <span className="text-xs text-muted-foreground uppercase tracking-wide">
                {s.label}
              </span>
            </div>
          ))}
        </div>

        {/* Processing banner */}
        {index.status === 'processing' && (
          <div className="mt-4 p-3 bg-blue-50 border border-blue-200 rounded-md text-sm text-blue-700 dark:bg-blue-950/30 dark:border-blue-900 dark:text-blue-400 flex items-center gap-2">
            <div className="h-3 w-3 rounded-full border-2 border-blue-500 border-t-transparent animate-spin" />
            Processing documents... This page will update automatically.
          </div>
        )}

        {/* Error message if failed */}
        {index.status === 'failed' && index.errorMessage && (
          <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-md text-sm text-red-700 dark:bg-red-950/30 dark:border-red-900 dark:text-red-400">
            {index.errorMessage}
          </div>
        )}

        {/* configDirty warning */}
        {index.configDirty && (
          <div className="mt-4 p-3 bg-amber-50 border border-amber-200 rounded-md text-sm text-amber-700 dark:bg-amber-950/30 dark:border-amber-900 dark:text-amber-400 flex items-center gap-2">
            <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
            Document set has changed since last index build — re-index to apply.
          </div>
        )}

        {/* Config Drawer */}
        {showConfig && (
          <div className="mt-4 pt-4 border-t grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-4">
            {configItems.map((item) => (
              <div key={item.label}>
                <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1">
                  {item.label}
                </div>
                <div className="text-sm font-mono text-foreground">{item.value}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ══════ Tabs ══════ */}
      <div className="mx-6 mt-5 flex gap-1 border-b">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              'flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors',
              activeTab === tab.id
                ? 'border-primary text-foreground'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            )}
          >
            <tab.icon className="h-4 w-4" />
            {tab.label}
          </button>
        ))}
      </div>

      {/* ══════ Content Tab ══════ */}
      {activeTab === 'content' && (
        <div className="flex mx-6 mt-4 mb-6 gap-4">
          <div className="flex-1 flex flex-col min-w-0">
            {/* Parsed Documents Section */}
            <div className="rounded-t-lg border border-b-0">
              <div className="px-4 py-3 flex items-center justify-between border-b">
                <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                  Parsed Documents ({parsedDocs.length})
                </h3>
                <div className="flex items-center gap-2">
                  {index.status === 'ready' && index.chunkCount > 0 && (
                    <button
                      onClick={handleProcessIndex}
                      disabled={isProcessing}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-md border text-xs font-medium bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50"
                    >
                      <Play className="h-3.5 w-3.5" />
                      {isProcessing ? 'Starting...' : 'Re-index'}
                    </button>
                  )}
                  {canManageDocs && (
                    <button
                      onClick={() => setAddDocsDialogOpen(true)}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-md border text-xs font-medium text-muted-foreground hover:bg-muted/50 transition-colors"
                    >
                      <Upload className="h-3.5 w-3.5" /> Add Document
                    </button>
                  )}
                </div>
              </div>

              {isParsedDocsLoading ? (
                <div className="px-4 py-3 space-y-2">
                  {[0, 1].map((i) => <Skeleton key={i} className="h-10 w-full" />)}
                </div>
              ) : parsedDocs.length === 0 ? (
                <div className="px-4 py-8 text-center text-sm text-muted-foreground">
                  No parsed documents in this index
                </div>
              ) : (
                <>
                  <div className="px-4 py-2 flex items-center gap-3 bg-muted/50 border-b text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
                    <span className="flex-1">Source filename</span>
                    <span className="w-24">Parse run</span>
                    <span className="w-32">Parsed at</span>
                    <span className="w-20">Status</span>
                    <span className="w-16 text-right">Chunks</span>
                    {canManageDocs && <span className="w-8" />}
                  </div>
                  {parsedDocs.map((pd) => (
                    <div
                      key={pd.parseRunId}
                      className="px-4 py-3 flex items-center gap-3 border-b last:border-b-0 hover:bg-muted/20"
                    >
                      <span className="flex-1 text-sm font-medium truncate">
                        {pd.sourceFilename ?? 'Unknown file'}
                      </span>
                      <span className="w-24 text-xs font-mono text-muted-foreground truncate">
                        {pd.parseRunId.slice(0, 8)}…
                      </span>
                      <span className="w-32 text-xs text-muted-foreground">
                        {pd.parsedAt
                          ? new Date(pd.parsedAt).toLocaleDateString('en-US', {
                              month: 'short', day: 'numeric',
                              hour: '2-digit', minute: '2-digit',
                            })
                          : '—'}
                      </span>
                      <span className={cn(
                        'w-20 text-xs font-medium',
                        pd.status === 'completed' ? 'text-green-700 dark:text-green-400' :
                        pd.status === 'processing' ? 'text-blue-700 dark:text-blue-400' :
                        pd.status === 'failed' ? 'text-red-700 dark:text-red-400' :
                        'text-muted-foreground',
                      )}>
                        {pd.status}
                      </span>
                      <span className="w-16 text-xs font-mono text-right text-muted-foreground">
                        {pd.chunksCreated ?? '—'}
                      </span>
                      {canManageDocs && (
                        <button
                          className="w-8 p-1 rounded text-muted-foreground/40 hover:text-red-500 transition-colors"
                          onClick={() => {
                            setParsedDocToRemove(pd.parseRunId)
                            setRemoveDocDialogOpen(true)
                          }}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      )}
                    </div>
                  ))}
                </>
              )}
            </div>

            {/* Chunks Section */}
            <div className="rounded-b-lg border flex-1 flex flex-col overflow-hidden">
              <div className="px-4 py-3 flex items-center justify-between border-b">
                <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                  Chunks ({index.chunkCount})
                </h3>
                <div className="flex items-center gap-1.5 bg-muted/50 border rounded-md px-2.5 py-1.5">
                  <Search className="h-3.5 w-3.5 text-muted-foreground" />
                  <input
                    placeholder="Search chunks..."
                    value={chunkSearch}
                    onChange={(e) => setChunkSearch(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleChunkSearch()}
                    className="bg-transparent border-none outline-none text-sm text-foreground placeholder:text-muted-foreground w-44"
                  />
                </div>
              </div>

              {chunks && chunks.items.length > 0 ? (
                <>
                  <div className="overflow-auto flex-1" style={{ maxHeight: 420 }}>
                    <Table>
                      <TableHeader>
                        <TableRow className="bg-muted/50">
                          <TableHead className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider w-12">
                            #
                          </TableHead>
                          <TableHead className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
                            Content Preview
                          </TableHead>
                          <TableHead className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider w-16">
                            Tokens
                          </TableHead>
                          <TableHead className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider w-16">
                            Chars
                          </TableHead>
                          <TableHead className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider w-24">
                            Source
                          </TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {chunks.items.map((chunk: ChunkListItem) => (
                          <TableRow
                            key={chunk.id}
                            onClick={() =>
                              setSelectedChunk(
                                selectedChunk?.id === chunk.id ? null : chunk
                              )
                            }
                            className={cn(
                              'cursor-pointer transition-colors',
                              selectedChunk?.id === chunk.id
                                ? 'bg-primary/10'
                                : 'hover:bg-primary/5'
                            )}
                          >
                            <TableCell className="text-muted-foreground font-mono text-xs">
                              {chunk.chunkIndex}
                            </TableCell>
                            <TableCell className="max-w-md truncate text-sm">
                              {chunk.contentPreview}
                            </TableCell>
                            <TableCell className="text-muted-foreground font-mono text-xs">
                              {chunk.tokenCount}
                            </TableCell>
                            <TableCell className="text-muted-foreground font-mono text-xs">
                              {chunk.charCount}
                            </TableCell>
                            <TableCell className="text-muted-foreground text-xs">
                              {chunk.documentTitle || 'Unknown'}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>

                  {/* Pagination */}
                  {chunks.totalPages > 1 && (
                    <div className="flex items-center justify-between px-4 py-3 border-t">
                      <p className="text-xs text-muted-foreground">
                        {(chunkPage - 1) * chunks.pageSize + 1}–
                        {Math.min(chunkPage * chunks.pageSize, chunks.total)} of{' '}
                        {chunks.total}
                      </p>
                      <div className="flex gap-1">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleChunkPageChange(chunkPage - 1)}
                          disabled={chunkPage <= 1}
                          className="h-7 px-2 text-xs"
                        >
                          <ChevronLeft className="h-3 w-3" />
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleChunkPageChange(chunkPage + 1)}
                          disabled={chunkPage >= chunks.totalPages}
                          className="h-7 px-2 text-xs"
                        >
                          <ChevronRight className="h-3 w-3" />
                        </Button>
                      </div>
                    </div>
                  )}
                </>
              ) : (
                <div className="flex flex-col items-center justify-center py-12">
                  <Layers className="h-10 w-10 text-muted-foreground/40 mb-3" />
                  <p className="text-sm text-muted-foreground">
                    {index.status === 'ready'
                      ? 'No chunks found'
                      : 'Process the index to generate chunks'}
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Chunk Detail Sidebar */}
          {selectedChunk && (
            <div className="w-80 rounded-lg border p-5 self-start sticky top-20 flex-shrink-0">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold">
                  Chunk #{selectedChunk.chunkIndex}
                </h3>
                <button
                  onClick={() => setSelectedChunk(null)}
                  className="p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
              <div className="grid grid-cols-2 gap-3 mb-4">
                <div>
                  <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-0.5">
                    Tokens
                  </div>
                  <div className="text-sm font-mono text-foreground">
                    {selectedChunk.tokenCount}
                  </div>
                </div>
                <div>
                  <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-0.5">
                    Chars
                  </div>
                  <div className="text-sm font-mono text-foreground">
                    {selectedChunk.charCount}
                  </div>
                </div>
                <div className="col-span-2">
                  <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-0.5">
                    Source
                  </div>
                  <div className="text-sm font-mono text-foreground">
                    {selectedChunk.documentTitle || 'Unknown'}
                  </div>
                </div>
              </div>

              {/* Chunk Metadata */}
              {selectedChunk.metadata && Object.keys(selectedChunk.metadata).length > 0 && (
                <div className="mb-4">
                  <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1.5">
                    Metadata
                  </div>
                  <div className="bg-muted/50 rounded-md border divide-y divide-border">
                    {Object.entries(selectedChunk.metadata).map(([key, value]) => (
                      <div key={key} className="px-3 py-2 flex items-start gap-2">
                        <span className="text-xs font-medium text-muted-foreground shrink-0">
                          {key}
                        </span>
                        <span className="text-xs text-foreground font-mono break-all ml-auto text-right">
                          {Array.isArray(value)
                            ? value.join(', ')
                            : typeof value === 'object' && value !== null
                              ? JSON.stringify(value)
                              : String(value ?? '—')}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1.5">
                Content
              </div>
              <div className="bg-muted/50 rounded-md p-3 text-sm leading-relaxed border max-h-96 overflow-auto whitespace-pre-wrap break-words">
                {selectedChunk.content}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ══════ Playground Tab ══════ */}
      {activeTab === 'playground' && projectId && indexId && (
        <div className="mx-6 mt-4 mb-6">
          <PlaygroundPanel
            projectId={projectId}
            indexId={indexId}
            indexStatus={index.status}
            chunkCount={index.chunkCount}
          />
        </div>
      )}

      {/* ══════ Add Documents Dialog ══════ */}
      <Dialog
        open={addDocsDialogOpen}
        onOpenChange={(open) => {
          setAddDocsDialogOpen(open)
          if (!open) setSelectedParsedDocIds([])
        }}
      >
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Add Parsed Documents</DialogTitle>
            <DialogDescription>
              Select parsed documents to add to this index
            </DialogDescription>
          </DialogHeader>
          <div className="max-h-96 overflow-y-auto">
            {index.config.parser && index.config.parseConfigHash ? (
              <ParsedDocumentPicker
                projectId={projectId!}
                parser={index.config.parser}
                parseConfigHash={index.config.parseConfigHash}
                representation={index.config.sourceRepresentation ?? 'full_text'}
                selectedIds={selectedParsedDocIds}
                onChange={setSelectedParsedDocIds}
              />
            ) : (
              <p className="text-center text-muted-foreground py-8">
                This index has no parse-config family set.
              </p>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAddDocsDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleAddDocuments}
              disabled={selectedParsedDocIds.length === 0}
            >
              Add
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ══════ Remove Document Dialog ══════ */}
      <Dialog open={removeDocDialogOpen} onOpenChange={setRemoveDocDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Remove Document</DialogTitle>
            <DialogDescription>
              Are you sure you want to remove this document from the index? This will
              also delete all chunks created from this document.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setRemoveDocDialogOpen(false)
                setParsedDocToRemove(null)
              }}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleRemoveDocument}
              disabled={isRemovingDoc}
            >
              {isRemovingDoc ? 'Removing...' : 'Remove'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
