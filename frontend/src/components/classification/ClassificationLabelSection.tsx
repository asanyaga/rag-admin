import { useState } from 'react'
import { ChevronRight, ChevronDown } from 'lucide-react'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Badge } from '@/components/ui/badge'
import { ClassificationPageGroup } from './ClassificationPageGroup'
import type { AnnotatedBlock } from '@/types/classification'

interface Props {
  label: string | null
  blocks: AnnotatedBlock[]
  selectedBlockId?: string | null
  onBlockSelect?: (blockId: string) => void
}

function pageRange(blocks: AnnotatedBlock[]): string {
  if (blocks.length === 0) return ''
  const pages = blocks.map((b) => b.pageIndex)
  const min = Math.min(...pages) + 1
  const max = Math.max(...pages) + 1
  return min === max ? `Page ${min}` : `Pages ${min}–${max}`
}

export function ClassificationLabelSection({ label, blocks, selectedBlockId, onBlockSelect }: Props) {
  const displayName = label ?? 'Unmatched'
  const [open, setOpen] = useState(label !== null)

  const pageGroups = Array.from(
    blocks.reduce((map, block) => {
      const key = block.pageIndex
      if (!map.has(key)) map.set(key, [])
      map.get(key)!.push(block)
      return map
    }, new Map<number, AnnotatedBlock[]>()),
  ).sort(([a], [b]) => a - b)

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <CollapsibleTrigger asChild>
        <button className="w-full flex items-center justify-between px-4 py-3 bg-muted/30 rounded-lg hover:bg-muted/50 text-sm font-medium">
          <div className="flex items-center gap-2">
            {open ? (
              <ChevronDown className="h-4 w-4 text-muted-foreground" />
            ) : (
              <ChevronRight className="h-4 w-4 text-muted-foreground" />
            )}
            <span>{displayName}</span>
            <Badge variant="secondary">{blocks.length}</Badge>
          </div>
          {blocks.length > 0 && (
            <span className="text-xs text-muted-foreground">{pageRange(blocks)}</span>
          )}
        </button>
      </CollapsibleTrigger>
      <CollapsibleContent className="mt-1 space-y-0.5">
        {blocks.length === 0 ? (
          <p className="text-sm text-muted-foreground px-4 py-2">
            No regions identified for this label.
          </p>
        ) : (
          pageGroups.map(([pageIndex, pageBlocks]) => (
            <ClassificationPageGroup
              key={pageIndex}
              pageIndex={pageIndex}
              blocks={pageBlocks}
              selectedBlockId={selectedBlockId}
              onBlockSelect={onBlockSelect}
            />
          ))
        )}
      </CollapsibleContent>
    </Collapsible>
  )
}
