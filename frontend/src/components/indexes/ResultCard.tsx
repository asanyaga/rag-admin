/**
 * Individual retrieval result card with rank, score, content, and feedback
 */
import { RetrievalResult } from '@/types/index'
import { ScoreBar } from './ScoreBar'
import { Button } from '@/components/ui/button'
import { FileText, ThumbsUp, ThumbsDown } from 'lucide-react'
import { cn } from '@/lib/utils'

interface ResultCardProps {
  result: RetrievalResult
  isExpanded: boolean
  vote: 'up' | 'down' | null
  queryTerms: string[]
  onToggleExpand: () => void
  onVote: (vote: 'up' | 'down' | null) => void
}

function highlightTerms(text: string, terms: string[]) {
  if (terms.length === 0) return text

  const escaped = terms.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
  const pattern = new RegExp(`(${escaped.join('|')})`, 'gi')
  const parts = text.split(pattern)

  return parts.map((part, i) =>
    pattern.test(part) ? (
      <mark key={i} className="bg-yellow-100 text-yellow-900 rounded-sm px-0.5">
        {part}
      </mark>
    ) : (
      part
    )
  )
}

export function ResultCard({
  result,
  isExpanded,
  vote,
  queryTerms,
  onToggleExpand,
  onVote,
}: ResultCardProps) {
  const contentPreview = isExpanded
    ? result.content
    : result.content.slice(0, 200)
  const showExpandToggle = result.content.length > 200

  return (
    <div className="rounded-lg border border-zinc-200 hover:border-zinc-300 transition-colors">
      <div className="p-4">
        {/* Header: Rank + Score + Feedback */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-3">
            <span className="w-7 h-7 rounded-md bg-zinc-100 text-zinc-600 text-xs font-mono font-bold flex items-center justify-center">
              {result.rank}
            </span>
            <ScoreBar score={result.score} />
          </div>
          <div className="flex gap-0.5">
            <Button
              variant="ghost"
              size="icon"
              className={cn(
                'h-7 w-7',
                vote === 'up'
                  ? 'bg-emerald-50 text-emerald-600 hover:bg-emerald-100 hover:text-emerald-700'
                  : 'text-zinc-300 hover:text-zinc-500'
              )}
              aria-pressed={vote === 'up'}
              aria-label="Mark as relevant"
              onClick={() => onVote(vote === 'up' ? null : 'up')}
            >
              <ThumbsUp className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className={cn(
                'h-7 w-7',
                vote === 'down'
                  ? 'bg-red-50 text-red-500 hover:bg-red-100 hover:text-red-600'
                  : 'text-zinc-300 hover:text-zinc-500'
              )}
              aria-pressed={vote === 'down'}
              aria-label="Mark as not relevant"
              onClick={() => onVote(vote === 'down' ? null : 'down')}
            >
              <ThumbsDown className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>

        {/* Content */}
        <p
          className={cn(
            'text-sm text-zinc-600 leading-relaxed mb-2',
            !isExpanded && showExpandToggle && 'line-clamp-3'
          )}
        >
          {highlightTerms(contentPreview, queryTerms)}
          {!isExpanded && showExpandToggle && '...'}
        </p>
        {showExpandToggle && (
          <button
            onClick={onToggleExpand}
            className="text-xs font-medium text-zinc-400 hover:text-zinc-600 transition-colors mb-3"
          >
            {isExpanded ? 'Show less' : 'Show full chunk'}
          </button>
        )}

        {/* Source metadata */}
        <div className="flex items-center gap-4 pt-3 border-t border-zinc-100 text-xs text-zinc-400">
          <span className="flex items-center gap-1">
            <FileText className="h-3 w-3" />
            {result.metadata.documentName}
          </span>
          {result.metadata.pageNumbers && result.metadata.pageNumbers.length > 0 ? (
            <span>
              {result.metadata.pageNumbers.length === 1
                ? `Page ${result.metadata.pageNumbers[0]}`
                : `Pages ${result.metadata.pageNumbers.join(', ')}`}
            </span>
          ) : result.metadata.page != null ? (
            <span>Page {result.metadata.page}</span>
          ) : null}
          <span>Chunk #{result.metadata.chunkIndex}</span>
          <span>{result.metadata.tokenCount} tokens</span>
        </div>

        {/* Chunk metadata */}
        {result.metadata.chunkMetadata && Object.keys(result.metadata.chunkMetadata).length > 0 && isExpanded && (
          <div className="mt-3 pt-3 border-t border-zinc-100">
            <div className="text-[10px] text-zinc-400 uppercase tracking-wider mb-1.5">
              Metadata
            </div>
            <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
              {Object.entries(result.metadata.chunkMetadata).map(([key, value]) => (
                <span key={key} className="text-zinc-400">
                  <span className="font-medium text-zinc-500">{key}:</span>{' '}
                  <span className="font-mono">
                    {Array.isArray(value)
                      ? value.join(', ')
                      : typeof value === 'object' && value !== null
                        ? JSON.stringify(value)
                        : String(value ?? '—')}
                  </span>
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
