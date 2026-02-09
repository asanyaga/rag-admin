import { Trash2, FileText } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import type { GoldenSetSource } from '@/types/golden-set'

interface SourcesListProps {
  sources: GoldenSetSource[]
  onDelete: (sourceId: string) => void
}

export function SourcesList({ sources, onDelete }: SourcesListProps) {
  if (sources.length === 0) {
    return (
      <p className="text-sm text-muted-foreground py-4 text-center">
        No sources yet. Add a document source to define expected results.
      </p>
    )
  }

  return (
    <div className="space-y-2">
      {sources.map((source) => (
        <div
          key={source.id}
          className="flex items-center justify-between p-2 rounded-md border bg-muted/30"
        >
          <div className="flex items-center gap-2 min-w-0">
            <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
            <span className="text-sm truncate">{source.documentName}</span>
            {source.locator?.type === 'page' &&
              source.locator.pages?.map((page) => (
                <Badge key={page} variant="secondary" className="text-xs">
                  p.{page}
                </Badge>
              ))}
          </div>
          <Button
            variant="ghost"
            size="icon"
            className="shrink-0"
            onClick={() => onDelete(source.id)}
          >
            <Trash2 className="h-3.5 w-3.5 text-muted-foreground" />
          </Button>
        </div>
      ))}
    </div>
  )
}
