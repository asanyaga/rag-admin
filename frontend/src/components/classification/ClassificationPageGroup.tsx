import { useState, useEffect } from 'react'
import { ChevronRight, ChevronDown } from 'lucide-react'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Badge } from '@/components/ui/badge'
import { ClassificationBlockRow } from './ClassificationBlockRow'
import type { AnnotatedBlock } from '@/types/classification'

interface Props {
  pageIndex: number
  blocks: AnnotatedBlock[]
  selectedBlockId?: string | null
  onBlockSelect?: (blockId: string) => void
  onPageSelect?: (pageIndex: number) => void
}

export function ClassificationPageGroup({ pageIndex, blocks, selectedBlockId, onBlockSelect, onPageSelect }: Props) {
  const [open, setOpen] = useState(false)

  // Auto-expand when a block in this page group becomes selected (e.g. via PDF click)
  useEffect(() => {
    if (selectedBlockId && blocks.some((b) => b.blockId === selectedBlockId)) {
      setOpen(true)
    }
  }, [selectedBlockId, blocks])

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <CollapsibleTrigger asChild>
        <button
          className="w-full flex items-center gap-2 px-4 py-2 text-sm hover:bg-muted/30 text-left"
          onClick={() => onPageSelect?.(pageIndex)}
        >
          {open ? (
            <ChevronDown className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
          )}
          <span className="text-muted-foreground">Page {pageIndex + 1}</span>
          <Badge variant="secondary" className="font-mono text-xs">
            {blocks.length}
          </Badge>
        </button>
      </CollapsibleTrigger>
      <CollapsibleContent className="space-y-1 pb-1 px-2">
        {blocks.map((block) => (
          <ClassificationBlockRow
            key={block.blockId}
            block={block}
            isSelected={selectedBlockId === block.blockId}
            onSelect={(id) => {
              onBlockSelect?.(id)
            }}
          />
        ))}
      </CollapsibleContent>
    </Collapsible>
  )
}
