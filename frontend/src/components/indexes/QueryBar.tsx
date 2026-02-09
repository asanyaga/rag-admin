/**
 * Query input bar with textarea, search button, and results summary
 */
import { useRef, useEffect } from 'react'
import { Textarea } from '@/components/ui/textarea'
import { Button } from '@/components/ui/button'
import { Search, Loader2 } from 'lucide-react'
import { SearchType } from '@/types/index'

interface QueryBarProps {
  query: string
  isSearching: boolean
  resultCount: number | null
  lastQuery: string | null
  searchType: SearchType
  topK: number
  threshold: number
  autoFocus?: boolean
  onQueryChange: (query: string) => void
  onSearch: () => void
}

export function QueryBar({
  query,
  isSearching,
  resultCount,
  lastQuery,
  searchType,
  topK,
  threshold,
  autoFocus,
  onQueryChange,
  onSearch,
}: QueryBarProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    if (autoFocus) {
      textareaRef.current?.focus()
    }
  }, [autoFocus])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      onSearch()
    }
  }

  return (
    <div className="rounded-lg border border-zinc-200 p-4">
      <div className="flex gap-3">
        <Textarea
          ref={textareaRef}
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="What would your users ask? Try a natural language query..."
          rows={2}
          className="flex-1 resize-none bg-zinc-50 border-zinc-200 focus-visible:ring-zinc-900"
        />
        <Button
          onClick={onSearch}
          disabled={!query.trim() || isSearching}
          className="px-5 self-stretch"
        >
          {isSearching ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin mr-2" />
              Running...
            </>
          ) : (
            <>
              <Search className="h-4 w-4 mr-2" />
              Search
            </>
          )}
        </Button>
      </div>
      {resultCount !== null && lastQuery && (
        <div className="flex items-center justify-between mt-3 pt-3 border-t border-zinc-100">
          <span className="text-xs text-zinc-400">
            {resultCount} result{resultCount !== 1 ? 's' : ''} for &ldquo;
            <span className="text-zinc-600 font-medium">{lastQuery}</span>
            &rdquo;
          </span>
          <span className="text-xs text-zinc-400">
            {searchType} · top-{topK} · threshold &ge; {threshold.toFixed(1)}
          </span>
        </div>
      )}
    </div>
  )
}

export { type QueryBarProps }
