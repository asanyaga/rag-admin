/**
 * Chunk preview panel for index creation
 */
import { useState } from 'react'
import { ChunkPreviewResponse, ChunkPreview } from '@/types/index'
import { Button } from '@/components/ui/button'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import { Loader2, ChevronDown, ChevronRight, Layers, Hash } from 'lucide-react'

interface ChunkPreviewPanelProps {
  preview: ChunkPreviewResponse | null
  isLoading: boolean
  onPreview: () => void
  disabled?: boolean
}

export function ChunkPreviewPanel({
  preview,
  isLoading,
  onPreview,
  disabled,
}: ChunkPreviewPanelProps) {
  const [expandedChunks, setExpandedChunks] = useState<Set<number>>(new Set([0]))

  const toggleChunk = (index: number) => {
    setExpandedChunks((prev) => {
      const next = new Set(prev)
      if (next.has(index)) {
        next.delete(index)
      } else {
        next.add(index)
      }
      return next
    })
  }

  return (
    <div className="border rounded-lg">
      <div className="p-3 border-b bg-muted/50 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Layers className="h-4 w-4" />
          <span className="font-medium text-sm">Chunk Preview</span>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={onPreview}
          disabled={disabled || isLoading}
        >
          {isLoading ? (
            <>
              <Loader2 className="mr-2 h-3 w-3 animate-spin" />
              Generating...
            </>
          ) : (
            'Preview Chunks'
          )}
        </Button>
      </div>

      {preview && (
        <>
          {/* Statistics Bar */}
          <div className="px-3 py-2 border-b bg-muted/30 flex items-center gap-4 text-xs text-muted-foreground">
            <span>~{preview.totalChunksEstimate} chunks</span>
            <span>|</span>
            <span>
              avg {Math.round(preview.avgChunkSizeChars)} chars (
              {Math.round(preview.avgChunkSizeTokens)} tokens)
            </span>
            <span>|</span>
            <span>
              range: {preview.minChunkSizeChars}–{preview.maxChunkSizeChars} chars
            </span>
          </div>

          {/* Chunk List */}
          <div className="max-h-[400px] overflow-y-auto">
            <div className="p-2 space-y-1">
              {preview.previewChunks.map((chunk) => (
                <ChunkPreviewItem
                  key={chunk.index}
                  chunk={chunk}
                  isExpanded={expandedChunks.has(chunk.index)}
                  onToggle={() => toggleChunk(chunk.index)}
                />
              ))}
            </div>
          </div>
        </>
      )}

      {!preview && !isLoading && (
        <div className="p-8 text-center text-sm text-muted-foreground">
          <p>Click "Preview Chunks" to see how your document will be split.</p>
          <p className="mt-1 text-xs">
            Select a document and configure chunking options first.
          </p>
        </div>
      )}
    </div>
  )
}

interface ChunkPreviewItemProps {
  chunk: ChunkPreview
  isExpanded: boolean
  onToggle: () => void
}

function ChunkPreviewItem({ chunk, isExpanded, onToggle }: ChunkPreviewItemProps) {
  return (
    <Collapsible open={isExpanded} onOpenChange={onToggle}>
      <CollapsibleTrigger asChild>
        <button className="w-full text-left p-2 rounded hover:bg-accent transition-colors flex items-center gap-2">
          {isExpanded ? (
            <ChevronDown className="h-4 w-4 shrink-0" />
          ) : (
            <ChevronRight className="h-4 w-4 shrink-0" />
          )}
          <span className="flex items-center gap-1 text-xs text-muted-foreground">
            <Hash className="h-3 w-3" />
            {chunk.index + 1}
          </span>
          <span className="text-sm truncate flex-1">
            {chunk.content.slice(0, 80)}...
          </span>
          <span className="text-xs text-muted-foreground shrink-0">
            {chunk.charCount} chars / {chunk.tokenCount} tokens
          </span>
        </button>
      </CollapsibleTrigger>
      <CollapsibleContent>
        <div className="ml-6 mr-2 mb-2 p-3 bg-muted/50 rounded text-sm">
          <ChunkContentWithOverlap
            content={chunk.content}
            overlapStart={chunk.overlapStartChars}
            overlapEnd={chunk.overlapEndChars}
          />
        </div>
      </CollapsibleContent>
    </Collapsible>
  )
}

interface ChunkContentWithOverlapProps {
  content: string
  overlapStart: number
  overlapEnd: number
}

function ChunkContentWithOverlap({
  content,
  overlapStart,
  overlapEnd,
}: ChunkContentWithOverlapProps) {
  // Split content into overlap and non-overlap regions
  const startOverlap = content.slice(0, overlapStart)
  const mainContent = content.slice(
    overlapStart,
    content.length - overlapEnd || content.length
  )
  const endOverlap = overlapEnd > 0 ? content.slice(-overlapEnd) : ''

  return (
    <div className="whitespace-pre-wrap break-words font-mono text-xs leading-relaxed">
      {startOverlap && (
        <span className="bg-yellow-200/50 dark:bg-yellow-900/30">
          {startOverlap}
        </span>
      )}
      <span>{mainContent}</span>
      {endOverlap && (
        <span className="bg-yellow-200/50 dark:bg-yellow-900/30">
          {endOverlap}
        </span>
      )}
    </div>
  )
}
