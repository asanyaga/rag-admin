/**
 * Playground panel — two-column layout with parameters sidebar and query/results area.
 * Supports Retrieval mode (chunk search) and Answer mode (retrieval + LLM generation).
 */
import { useRef } from 'react'
import { usePlayground } from '@/hooks/usePlayground'
import { RetrievalParameters } from './RetrievalParameters'
import { GenerationParameters } from './GenerationParameters'
import { QueryHistory } from './QueryHistory'
import { ResultsPanel } from './ResultsPanel'
import { AnswerPanel } from './AnswerPanel'
import { QueryTracePanel } from './QueryTracePanel'
import { cn } from '@/lib/utils'
import { Search, Sparkles, Square } from 'lucide-react'
import { Button } from '@/components/ui/button'

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
  const playground = usePlayground(projectId, indexId)
  const chunkRefs = useRef<Record<number, HTMLDivElement | null>>({})

  const {
    query,
    setQuery,
    searchType,
    setSearchType,
    topK,
    setTopK,
    threshold,
    setThreshold,
    mode,
    setMode,
    provider,
    setProvider,
    model,
    setModel,
    temperature,
    setTemperature,
    maxTokens,
    setMaxTokens,
    instructions,
    setInstructions,
    results,
    isSearching,
    error,
    runSearch,
    handleStop,
    queryHistory,
    votes,
    setVote,
    expandedResultId,
    setExpandedResultId,
    answer,
    streamingPhase,
    answerMetrics,
    highlightedChunk,
    handleCitationClick,
    trace,
  } = playground

  const isReady = indexStatus === 'ready'
  const hasSearched = queryHistory.length > 0
  const queryTerms =
    hasSearched && queryHistory[0]
      ? queryHistory[0].split(/\s+/).filter((t) => t.length > 2)
      : []

  const isAnswerMode = mode === 'answer'
  const showAnswerPanel =
    isAnswerMode && (streamingPhase === 'generating' || streamingPhase === 'done')
  const showChunks =
    streamingPhase === 'done' || streamingPhase === 'generating'

  // Citation click: highlight + scroll to chunk ref
  const onCitationClick = (chunkNum: number) => {
    handleCitationClick(chunkNum)
    const el = chunkRefs.current[chunkNum]
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    }
  }

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
        {/* Mode toggle */}
        <div className="rounded-lg border border-zinc-200 p-4">
          <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-3">
            Mode
          </h3>
          <div className="flex gap-0.5 bg-zinc-100 rounded-md p-0.5">
            {(['retrieval', 'answer'] as const).map((m) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                className={cn(
                  'flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded text-xs font-medium capitalize transition-all',
                  mode === m
                    ? 'bg-white text-zinc-900 shadow-sm'
                    : 'text-zinc-400 hover:text-zinc-600'
                )}
              >
                {m === 'retrieval' ? (
                  <Search className="h-3 w-3" />
                ) : (
                  <Sparkles className="h-3 w-3" />
                )}
                {m}
              </button>
            ))}
          </div>
        </div>

        <RetrievalParameters
          searchType={searchType}
          topK={topK}
          threshold={threshold}
          onSearchTypeChange={setSearchType}
          onTopKChange={setTopK}
          onThresholdChange={setThreshold}
        />

        {isAnswerMode && (
          <GenerationParameters
            provider={provider}
            model={model}
            temperature={temperature}
            maxTokens={maxTokens}
            instructions={instructions}
            onProviderChange={setProvider}
            onModelChange={setModel}
            onTemperatureChange={setTemperature}
            onMaxTokensChange={setMaxTokens}
            onInstructionsChange={setInstructions}
          />
        )}

        <QueryHistory
          history={queryHistory}
          onSelect={(q) => {
            setQuery(q)
          }}
        />
      </div>

      {/* Right main area */}
      <div className="flex-1 min-w-0 flex flex-col gap-3">
        {/* Query bar with stop button support */}
        <div className="rounded-lg border border-zinc-200 p-4">
          <div className="flex gap-3">
            <textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  if (streamingPhase === 'generating') {
                    handleStop()
                  } else {
                    runSearch()
                  }
                }
              }}
              placeholder={
                isAnswerMode
                  ? 'Ask a question to test the full RAG pipeline...'
                  : 'What would your users ask? Try a natural language query...'
              }
              rows={2}
              className="flex-1 resize-none rounded-md border border-zinc-200 bg-zinc-50 px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-zinc-900"
            />
            {streamingPhase === 'generating' ? (
              <Button
                variant="outline"
                onClick={handleStop}
                className="px-5 self-stretch"
              >
                <Square className="h-4 w-4 mr-2" />
                Stop
              </Button>
            ) : (
              <Button
                onClick={runSearch}
                disabled={!query.trim() || isSearching}
                className="px-5 self-stretch"
              >
                {isSearching ? (
                  <>
                    <Search className="h-4 w-4 mr-2 animate-spin" />
                    Running...
                  </>
                ) : (
                  <>
                    <Search className="h-4 w-4 mr-2" />
                    Search
                  </>
                )}
              </Button>
            )}
          </div>
        </div>

        {/* Results area */}
        {showAnswerPanel && (
          <AnswerPanel
            answer={answer}
            streamingPhase={streamingPhase}
            metrics={answerMetrics}
            highlightedChunk={highlightedChunk}
            model={model}
            provider={provider}
            onCitationClick={onCitationClick}
          />
        )}

        {showChunks ? (
          <ChunksWithHighlight
            results={results}
            highlightedChunk={highlightedChunk}
            chunkRefs={chunkRefs}
            expandedResultId={expandedResultId}
            votes={votes}
            queryTerms={queryTerms}
            onExpandResult={setExpandedResultId}
            onVote={setVote}
          />
        ) : (
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
        )}

        {/* Query Trace */}
        {trace && <QueryTracePanel trace={trace} />}
      </div>
    </div>
  )
}

/**
 * Chunk results with citation highlight support.
 * Wraps each ResultCard with a ref for scroll-to and highlight styling.
 */
import { ResultCard } from './ResultCard'
import { RetrievalResult } from '@/types/index'

function ChunksWithHighlight({
  results,
  highlightedChunk,
  chunkRefs,
  expandedResultId,
  votes,
  queryTerms,
  onExpandResult,
  onVote,
}: {
  results: RetrievalResult[]
  highlightedChunk: number | null
  chunkRefs: React.MutableRefObject<Record<number, HTMLDivElement | null>>
  expandedResultId: string | null
  votes: Record<string, 'up' | 'down' | null>
  queryTerms: string[]
  onExpandResult: (id: string | null) => void
  onVote: (chunkId: string, vote: 'up' | 'down' | null) => void
}) {
  if (results.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center py-12 text-center">
        <div className="text-sm text-zinc-500">No chunks retrieved</div>
        <div className="text-xs text-zinc-400 mt-1">
          Try adjusting the retrieval parameters.
        </div>
      </div>
    )
  }

  return (
    <div>
      <div className="flex items-center gap-1.5 mb-2">
        <Search className="h-3.5 w-3.5 text-zinc-400" />
        <span className="text-[11px] font-semibold text-zinc-500 uppercase tracking-wider">
          Retrieved Chunks
        </span>
        <span className="text-[11px] text-zinc-400">
          ({results.length} results)
        </span>
      </div>
      <div className="flex flex-col gap-2">
        {results.map((result, index) => {
          const chunkNum = index + 1
          const isHighlighted = highlightedChunk === chunkNum
          return (
            <div
              key={result.chunkId}
              ref={(el) => {
                chunkRefs.current[chunkNum] = el
              }}
              className={cn(
                'transition-all rounded-lg',
                isHighlighted && 'ring-2 ring-zinc-900 ring-offset-1'
              )}
            >
              <ResultCard
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
            </div>
          )
        })}
      </div>
    </div>
  )
}
