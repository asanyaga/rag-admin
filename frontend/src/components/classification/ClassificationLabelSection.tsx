import { useState } from 'react'
import { ChevronRight, ChevronDown } from 'lucide-react'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Badge } from '@/components/ui/badge'
import { ClassificationBlockRow } from './ClassificationBlockRow'
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
      <CollapsibleContent className="mt-1 space-y-1">
        {blocks.length === 0 ? (
          <p className="text-sm text-muted-foreground px-4 py-2">
            No regions identified for this label.
          </p>
        ) : (
          blocks.map((block) => (
            <ClassificationBlockRow
              key={block.blockId}
              block={block}
              isSelected={selectedBlockId === block.blockId}
              onSelect={onBlockSelect}
            />
          ))
        )}
      </CollapsibleContent>
    </Collapsible>
  )
}
