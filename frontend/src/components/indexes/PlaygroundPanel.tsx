/**
 * Playground panel — two-column layout with parameters sidebar and query/results area
 */
import { usePlayground } from '@/hooks/usePlayground'
import { RetrievalParameters } from './RetrievalParameters'
import { QueryHistory } from './QueryHistory'
import { QueryBar } from './QueryBar'
import { ResultsPanel } from './ResultsPanel'

interface PlaygroundPanelProps {
  projectId: string
  indexId: string
  indexStatus: string
  chunkCount: number
}

export function PlaygroundPanel({
  projectId,
  indexId,
  indexStatus,
  chunkCount,
}: PlaygroundPanelProps) {
  const {
    query,
    setQuery,
    searchType,
    setSearchType,
    topK,
    setTopK,
    threshold,
    setThreshold,
    results,
    isSearching,
    error,
    runSearch,
    queryHistory,
    votes,
    setVote,
    expandedResultId,
    setExpandedResultId,
  } = usePlayground(projectId, indexId)

  const isReady = indexStatus === 'ready'
  const hasSearched = queryHistory.length > 0
  const queryTerms = hasSearched && queryHistory[0]
    ? queryHistory[0].split(/\s+/).filter((t) => t.length > 2)
    : []

  // If index isn't ready, show a disabled state
  if (!isReady) {
    return (
      <div className="flex items-center justify-center py-20 text-center">
        <div>
          <div className="text-sm font-medium text-zinc-500 mb-1">
            Index is still processing
          </div>
          <div className="text-xs text-zinc-400">
            Playground will be available once processing is complete.
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex gap-4">
      {/* Left sidebar */}
      <div className="w-64 flex flex-col gap-3 flex-shrink-0">
        <RetrievalParameters
          searchType={searchType}
          topK={topK}
          threshold={threshold}
          onSearchTypeChange={setSearchType}
          onTopKChange={setTopK}
          onThresholdChange={setThreshold}
        />
        <QueryHistory history={queryHistory} onSelect={(q) => { setQuery(q) }} />
      </div>

      {/* Right main area */}
      <div className="flex-1 min-w-0 flex flex-col gap-3">
        <QueryBar
          query={query}
          isSearching={isSearching}
          resultCount={hasSearched ? results.length : null}
          lastQuery={queryHistory[0] ?? null}
          searchType={searchType}
          topK={topK}
          threshold={threshold}
          autoFocus
          onQueryChange={setQuery}
          onSearch={runSearch}
        />
        <ResultsPanel
          results={results}
          isSearching={isSearching}
          hasSearched={hasSearched}
          error={error}
          chunkCount={chunkCount}
          queryTerms={queryTerms}
          expandedResultId={expandedResultId}
          votes={votes}
          onExpandResult={setExpandedResultId}
          onVote={setVote}
          onRetry={runSearch}
        />
      </div>
    </div>
  )
}
