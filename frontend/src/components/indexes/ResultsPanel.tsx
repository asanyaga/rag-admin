/**
 * Results panel with empty, loading, error, no-results, and results states
 */
import { RetrievalResult } from '@/types/index'
import { ResultCard } from './ResultCard'
import { Search, Loader2, AlertCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'

interface ResultsPanelProps {
  results: RetrievalResult[]
  isSearching: boolean
  hasSearched: boolean
  error: string | null
  chunkCount: number
  queryTerms: string[]
  expandedResultId: string | null
  votes: Record<string, 'up' | 'down' | null>
  onExpandResult: (id: string | null) => void
  onVote: (chunkId: string, vote: 'up' | 'down' | null) => void
  onRetry: () => void
}

export function ResultsPanel({
  results,
  isSearching,
  hasSearched,
  error,
  chunkCount,
  queryTerms,
  expandedResultId,
  votes,
  onExpandResult,
  onVote,
  onRetry,
}: ResultsPanelProps) {
  // Error state
  if (error) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center py-20 text-center">
        <div className="w-12 h-12 rounded-full bg-red-50 flex items-center justify-center mb-4">
          <AlertCircle className="h-5 w-5 text-red-500" />
        </div>
        <div className="text-sm font-medium text-zinc-700 mb-1">
          Failed to run query
        </div>
        <div className="text-xs text-zinc-400 max-w-xs leading-relaxed mb-4">
          {error}
        </div>
        <Button variant="outline" size="sm" onClick={onRetry}>
          Retry
        </Button>
      </div>
    )
  }

  // Loading state
  if (isSearching) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center py-20" aria-live="polite">
        <Loader2 className="h-6 w-6 text-zinc-400 animate-spin mb-3" />
        <div className="text-sm text-zinc-500">
          Searching {chunkCount.toLocaleString()} chunks...
        </div>
      </div>
    )
  }

  // Empty state (no query run yet)
  if (!hasSearched) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center py-20 text-center">
        <div className="w-12 h-12 rounded-full bg-zinc-100 flex items-center justify-center mb-4">
          <Search className="h-5 w-5 text-zinc-400" />
        </div>
        <div className="text-sm font-medium text-zinc-500 mb-1">
          Run a query to test retrieval
        </div>
        <div className="text-xs text-zinc-400 max-w-xs leading-relaxed">
          Type a question your users might ask and see which chunks come back.
          Adjust parameters on the left to compare.
        </div>
      </div>
    )
  }

  // No results state
  if (results.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center py-20 text-center">
        <div className="w-12 h-12 rounded-full bg-zinc-100 flex items-center justify-center mb-4">
          <Search className="h-5 w-5 text-zinc-400" />
        </div>
        <div className="text-sm font-medium text-zinc-500 mb-1">
          No chunks matched your query
        </div>
        <div className="text-xs text-zinc-400 max-w-xs leading-relaxed">
          Try lowering the similarity threshold or using a different search type.
        </div>
      </div>
    )
  }

  // Results state
  return (
    <div className="flex flex-col gap-2">
      {results.map((result) => (
        <ResultCard
          key={result.chunkId}
          result={result}
          isExpanded={expandedResultId === result.chunkId}
          vote={votes[result.chunkId] ?? null}
          queryTerms={queryTerms}
          onToggleExpand={() =>
            onExpandResult(
              expandedResultId === result.chunkId ? null : result.chunkId
            )
          }
          onVote={(vote) => onVote(result.chunkId, vote)}
        />
      ))}
    </div>
  )
}
