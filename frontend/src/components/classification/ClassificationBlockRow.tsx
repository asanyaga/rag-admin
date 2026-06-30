import { useState } from 'react'
import { ChevronRight, ChevronDown } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import type { AnnotatedBlock } from '@/types/classification'

interface Props {
  block: AnnotatedBlock
  isSelected?: boolean
  onSelect?: (blockId: string) => void
}

export function ClassificationBlockRow({ block, isSelected, onSelect }: Props) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className={`border rounded-md overflow-hidden ${isSelected ? 'border-primary ring-1 ring-primary' : ''}`}>
      <button
        className="w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-muted/50 text-left"
        onClick={() => {
          setExpanded((v) => !v)
          onSelect?.(block.blockId)
        }}
      >
        <Badge variant="secondary" className="shrink-0 font-mono text-xs">
          p.{block.pageIndex + 1}
        </Badge>
        <Badge variant="outline" className="shrink-0 text-xs">
          {block.role}
        </Badge>
        <span className="flex-1 truncate text-muted-foreground line-clamp-1">
          {block.text}
        </span>
        {expanded ? (
          <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
        ) : (
          <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
        )}
      </button>
      {expanded && (
        <div className="px-3 pb-3 pt-1 border-t bg-muted/20">
          <pre className="text-xs leading-relaxed whitespace-pre-wrap break-words font-mono">
            {block.markdown ?? block.text}
          </pre>
        </div>
      )}
    </div>
  )
}
