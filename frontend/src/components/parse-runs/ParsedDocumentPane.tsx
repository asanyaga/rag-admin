import { useEffect, useMemo, useState } from 'react'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeRaw from 'rehype-raw'
import { Badge } from '@/components/ui/badge'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import type { Block, ParsedDocumentDetail } from '@/types/cdm'

export interface ParsedDocumentPaneProps {
  parsedDocument: ParsedDocumentDetail | undefined
  isLoading?: boolean
  error?: string | null
  selectedBlockId?: string | null
  onBlockSelect?: (id: string) => void
  /** blockId → label name — renders a coloured badge on matching block rows */
  blockLabels?: Map<string, string>
  /** page index (0-based) → label name — renders a coloured badge on matching page headers */
  pageLabels?: Map<number, string>
  /** label name → CSS colour string e.g. 'hsl(221 83% 53%)' */
  labelColors?: Map<string, string>
}

function BlockRow({
  block,
  isSelected,
  onBlockSelect,
  label,
  labelColor,
}: {
  block: Block
  isSelected: boolean
  onBlockSelect?: (id: string) => void
  label?: string
  labelColor?: string
}) {
  const [localOpen, setLocalOpen] = useState(false)
  const confidence = block.quality?.confidence

  useEffect(() => {
    if (isSelected) setLocalOpen(true)
  }, [isSelected])

  const preview = (block.text ?? block.markdown ?? '').slice(0, 140)

  return (
    <Collapsible
      open={localOpen}
      onOpenChange={(open) => {
        setLocalOpen(open)
        if (open && onBlockSelect) onBlockSelect(block.id)
      }}
    >
      <CollapsibleTrigger asChild>
        <button
          data-block-id={block.id}
          className={`w-full text-left border rounded-md px-2 py-1 hover:bg-muted/50 ${
            isSelected ? 'border-primary ring-1 ring-primary' : ''
          }`}
        >
          <div className="flex items-center gap-2">
            <Badge variant="secondary" className="text-xs">
              {block.role}
            </Badge>
            {label && (
              <span
                className="text-xs px-1.5 py-0.5 rounded font-medium text-white shrink-0"
                style={{ backgroundColor: labelColor }}
              >
                {label}
              </span>
            )}
            {typeof confidence === 'number' && (
              <Badge variant="outline" className="text-xs">
                {confidence.toFixed(2)}
              </Badge>
            )}
            <span className="text-xs text-muted-foreground truncate flex-1">
              {preview || <em>empty</em>}
            </span>
          </div>
        </button>
      </CollapsibleTrigger>
      <CollapsibleContent className="border border-t-0 rounded-b-md px-3 py-2 space-y-2 -mt-px">
        {block.markdown ? (
          <div className="prose prose-sm dark:prose-invert max-w-none">
            <Markdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw]}>
              {block.markdown}
            </Markdown>
          </div>
        ) : block.text ? (
          <pre className="whitespace-pre-wrap font-mono text-xs">{block.text}</pre>
        ) : (
          <p className="text-xs text-muted-foreground">No text/markdown.</p>
        )}
        <div className="text-xs text-muted-foreground space-y-0.5">
          {block.native_type && <div>native_type: {block.native_type}</div>}
          {block.bbox && (
            <div>
              bbox: ({block.bbox.x0.toFixed(3)}, {block.bbox.y0.toFixed(3)}) →
              ({block.bbox.x1.toFixed(3)}, {block.bbox.y1.toFixed(3)})
            </div>
          )}
        </div>
      </CollapsibleContent>
    </Collapsible>
  )
}

export function PageBlockList({
  blocks,
  selectedBlockId,
  onBlockSelect,
  blockLabels,
  labelColors,
}: {
  blocks: Block[]
  selectedBlockId?: string | null
  onBlockSelect?: (id: string) => void
  blockLabels?: Map<string, string>
  labelColors?: Map<string, string>
}) {
  if (blocks.length === 0) {
    return <p className="text-xs text-muted-foreground">No blocks on this page.</p>
  }
  return (
    <div className="space-y-2">
      {blocks.map((b) => {
        const label = blockLabels?.get(b.id)
        const labelColor = label ? labelColors?.get(label) : undefined
        return (
          <BlockRow
            key={b.id}
            block={b}
            isSelected={selectedBlockId === b.id}
            onBlockSelect={onBlockSelect}
            label={label}
            labelColor={labelColor}
          />
        )
      })}
    </div>
  )
}

export function ParsedDocumentPane({
  parsedDocument,
  isLoading = false,
  error = null,
  selectedBlockId,
  onBlockSelect,
  blockLabels,
  pageLabels,
  labelColors,
}: ParsedDocumentPaneProps) {
  const blocksByPage = useMemo<Map<number, Block[]>>(() => {
    const map = new Map<number, Block[]>()
    const blocks = parsedDocument?.content?.blocks ?? []
    for (const b of blocks) {
      const arr = map.get(b.page_index) ?? []
      arr.push(b)
      map.set(b.page_index, arr)
    }
    return map
  }, [parsedDocument])

  useEffect(() => {
    if (!selectedBlockId) return
    const el = document.querySelector(`[data-block-id="${selectedBlockId}"]`)
    el?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }, [selectedBlockId])

  if (isLoading) {
    return <div className="p-4 text-sm text-muted-foreground">Loading…</div>
  }
  if (error) {
    return <div className="p-4 text-sm text-destructive">{error}</div>
  }
  if (!parsedDocument) {
    return (
      <div className="p-4 text-sm text-muted-foreground">
        No adapted document for this run.
      </div>
    )
  }

  const pages = parsedDocument.content?.pages ?? []
  if (pages.length === 0) {
    return <div className="p-4 text-sm text-muted-foreground">No pages.</div>
  }

  return (
    <div className="space-y-3 p-3">
      {pages.map((p) => {
        const pageBlocks = blocksByPage.get(p.index) ?? []
        const confidence = p.quality?.confidence
        const pageLabel = pageLabels?.get(p.index)
        const pageLabelColor = pageLabel ? labelColors?.get(pageLabel) : undefined

        return (
          <Collapsible key={p.index} defaultOpen>
            <CollapsibleTrigger asChild>
              <button className="w-full text-left border rounded-md px-3 py-2 hover:bg-muted/50">
                <div className="flex items-center gap-3 text-sm">
                  <span className="font-medium">Page {p.index + 1}</span>
                  <span className="text-muted-foreground text-xs">
                    {pageBlocks.length} block{pageBlocks.length === 1 ? '' : 's'}
                  </span>
                  {pageLabel && (
                    <span
                      className="text-xs px-1.5 py-0.5 rounded font-medium text-white shrink-0"
                      style={{ backgroundColor: pageLabelColor }}
                    >
                      {pageLabel}
                    </span>
                  )}
                  {typeof confidence === 'number' && (
                    <Badge variant="outline" className="text-xs ml-auto">
                      confidence {confidence.toFixed(2)}
                    </Badge>
                  )}
                </div>
              </button>
            </CollapsibleTrigger>
            <CollapsibleContent className="border border-t-0 rounded-b-md p-3 -mt-px">
              <PageBlockList
                blocks={pageBlocks}
                selectedBlockId={selectedBlockId}
                onBlockSelect={onBlockSelect}
                blockLabels={blockLabels}
                labelColors={labelColors}
              />
            </CollapsibleContent>
          </Collapsible>
        )
      })}
    </div>
  )
}
