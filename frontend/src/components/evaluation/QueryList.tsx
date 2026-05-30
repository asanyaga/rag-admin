import { useState, useMemo, useRef, useEffect } from 'react'
import { Plus, Search, X, Check } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'
import type { GoldenSetQuery, SourceMethod } from '@/types/golden-set'

interface QueryListProps {
  queries: GoldenSetQuery[]
  selectedId: string | null
  onSelect: (id: string) => void
  onAdd: (queryText: string) => void
}

type FilterKey = SourceMethod | 'all'

const FILTER_CHIPS: { key: FilterKey; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'manual', label: 'Manual' },
  { key: 'auto_generated', label: 'Auto' },
  { key: 'imported', label: 'Imported' },
]

const ORIGIN_LABEL: Record<SourceMethod, string> = {
  manual: 'Manual',
  auto_generated: 'Auto',
  imported: 'Imported',
}

export function QueryList({ queries, selectedId, onSelect, onAdd }: QueryListProps) {
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState<FilterKey>('all')
  const [adding, setAdding] = useState(false)
  const [newText, setNewText] = useState('')
  const newInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (adding) newInputRef.current?.focus()
  }, [adding])

  const filtered = useMemo(() => {
    return queries.filter((q) => {
      const matchesSearch = search === '' ||
        q.queryText.toLowerCase().includes(search.toLowerCase())
      const matchesFilter = filter === 'all' || q.sourceMethod === filter
      return matchesSearch && matchesFilter
    })
  }, [queries, search, filter])

  const handleAddSubmit = () => {
    const trimmed = newText.trim()
    if (!trimmed) {
      setAdding(false)
      return
    }
    onAdd(trimmed)
    setNewText('')
    setAdding(false)
  }

  return (
    <div className="flex flex-col h-full border rounded-lg">
      {/* Header */}
      <div className="flex items-center justify-between p-3 border-b shrink-0">
        <h3 className="text-sm font-medium">Queries ({queries.length})</h3>
        <Button variant="ghost" size="icon" onClick={() => setAdding(true)}>
          <Plus className="h-4 w-4" />
        </Button>
      </div>

      {/* Search */}
      <div className="px-3 pt-2 pb-1 shrink-0">
        <div className="relative">
          <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
          <Input
            className="pl-8 h-8 text-sm"
            placeholder="Search queries…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          {search && (
            <button
              className="absolute right-2.5 top-2.5 text-muted-foreground hover:text-foreground"
              onClick={() => setSearch('')}
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Filter chips */}
      <div className="px-3 pb-2 flex gap-1.5 flex-wrap shrink-0">
        {FILTER_CHIPS.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setFilter(key)}
            className={cn(
              'text-xs px-2 py-0.5 rounded-full border transition-colors',
              filter === key
                ? 'bg-primary text-primary-foreground border-primary'
                : 'border-border text-muted-foreground hover:border-foreground hover:text-foreground'
            )}
          >
            {label}
          </button>
        ))}
      </div>

      {/* List */}
      <ScrollArea className="flex-1">
        <div className="p-1">
          {filtered.length === 0 && !adding ? (
            <p className="text-sm text-muted-foreground text-center py-8 px-4">
              {queries.length === 0
                ? 'No queries yet. Click + to add one.'
                : 'No queries match this filter.'}
            </p>
          ) : (
            filtered.map((q) => (
              <button
                key={q.id}
                onClick={() => onSelect(q.id)}
                className={cn(
                  'w-full text-left px-3 py-2 rounded-md text-sm transition-colors',
                  'hover:bg-accent',
                  selectedId === q.id && 'bg-accent border-l-2 border-l-primary'
                )}
              >
                <p className="whitespace-pre-wrap break-words">{q.queryText}</p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {q.sources.length} source{q.sources.length !== 1 ? 's' : ''}
                  {' · '}
                  <span className="opacity-70">{ORIGIN_LABEL[q.sourceMethod]}</span>
                </p>
              </button>
            ))
          )}

          {/* Inline add */}
          {adding && (
            <div className="px-3 py-2 space-y-1.5">
              <Input
                ref={newInputRef}
                value={newText}
                onChange={(e) => setNewText(e.target.value)}
                placeholder="Enter query text…"
                className="text-sm"
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    handleAddSubmit()
                  }
                  if (e.key === 'Escape') {
                    setAdding(false)
                    setNewText('')
                  }
                }}
              />
              <div className="flex gap-1">
                <Button size="sm" variant="ghost" onClick={handleAddSubmit} disabled={!newText.trim()}>
                  <Check className="h-4 w-4" />
                </Button>
                <Button size="sm" variant="ghost" onClick={() => { setAdding(false); setNewText('') }}>
                  <X className="h-4 w-4" />
                </Button>
              </div>
            </div>
          )}
        </div>
      </ScrollArea>
    </div>
  )
}
