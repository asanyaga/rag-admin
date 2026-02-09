import { Plus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'
import type { GoldenSetQuery } from '@/types/golden-set'

interface QueryListProps {
  queries: GoldenSetQuery[]
  selectedId: string | null
  onSelect: (id: string) => void
  onAdd: () => void
}

export function QueryList({ queries, selectedId, onSelect, onAdd }: QueryListProps) {
  return (
    <div className="flex flex-col h-full border rounded-lg">
      <div className="flex items-center justify-between p-3 border-b">
        <h3 className="text-sm font-medium">Queries ({queries.length})</h3>
        <Button variant="ghost" size="icon" onClick={onAdd}>
          <Plus className="h-4 w-4" />
        </Button>
      </div>
      <ScrollArea className="flex-1">
        <div className="p-1">
          {queries.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-8 px-4">
              No queries yet. Click + to add one.
            </p>
          ) : (
            queries.map((q) => (
              <button
                key={q.id}
                onClick={() => onSelect(q.id)}
                className={cn(
                  'w-full text-left px-3 py-2 rounded-md text-sm transition-colors',
                  'hover:bg-accent',
                  selectedId === q.id &&
                    'bg-accent border-l-2 border-l-primary'
                )}
              >
                <p className="line-clamp-2">{q.queryText}</p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {q.sources.length} source{q.sources.length !== 1 ? 's' : ''}
                </p>
              </button>
            ))
          )}
        </div>
      </ScrollArea>
    </div>
  )
}
