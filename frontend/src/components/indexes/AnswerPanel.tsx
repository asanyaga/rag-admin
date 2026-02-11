/**
 * Answer panel — shows the streamed LLM answer with citation badges and metrics.
 * Renders above the chunk results in Answer mode.
 */
import { useCallback, useState } from 'react'
import { Sparkles, Clock, Copy, Check } from 'lucide-react'
import { Button } from '@/components/ui/button'
import type { AnswerMetrics, StreamingPhase } from '@/hooks/usePlayground'

interface AnswerPanelProps {
  answer: string
  streamingPhase: StreamingPhase
  metrics: AnswerMetrics | null
  highlightedChunk: number | null
  model: string
  provider: string
  onCitationClick: (chunkNum: number) => void
}

/**
 * Parse answer text and render [N] citations as clickable badges.
 */
function renderWithCitations(
  text: string,
  highlightedChunk: number | null,
  onCitationClick: (n: number) => void
) {
  const parts: React.ReactNode[] = []
  const regex = /\[(\d+)\]/g
  let lastIndex = 0
  let match: RegExpExecArray | null

  while ((match = regex.exec(text)) !== null) {
    // Text before this citation
    if (match.index > lastIndex) {
      parts.push(
        <span key={`t-${lastIndex}`}>{text.slice(lastIndex, match.index)}</span>
      )
    }

    const num = parseInt(match[1])
    const isHighlighted = highlightedChunk === num
    parts.push(
      <button
        key={`c-${match.index}`}
        onClick={() => onCitationClick(num)}
        className={
          'inline-flex items-center justify-center rounded text-[11px] font-semibold ' +
          'px-1.5 py-0 leading-none cursor-pointer transition-colors align-super mx-0.5 ' +
          (isHighlighted
            ? 'bg-zinc-900 text-white'
            : 'bg-zinc-100 text-zinc-700 hover:bg-zinc-200')
        }
      >
        {num}
      </button>
    )
    lastIndex = regex.lastIndex
  }

  // Remaining text
  if (lastIndex < text.length) {
    parts.push(<span key={`t-${lastIndex}`}>{text.slice(lastIndex)}</span>)
  }

  return parts
}

export function AnswerPanel({
  answer,
  streamingPhase,
  metrics,
  highlightedChunk,
  model,
  provider,
  onCitationClick,
}: AnswerPanelProps) {
  const [copied, setCopied] = useState(false)

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(answer)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }, [answer])

  const isGenerating = streamingPhase === 'generating'
  const isDone = streamingPhase === 'done'

  return (
    <div className="rounded-lg border border-zinc-200 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-3.5 py-2 bg-zinc-50 border-b border-zinc-200">
        <div className="flex items-center gap-1.5 text-[11px] font-semibold text-zinc-500 uppercase tracking-wider">
          <Sparkles className="h-3.5 w-3.5" />
          Answer
        </div>
        <div className="flex items-center gap-2">
          {isGenerating && (
            <span className="flex items-center gap-1.5 text-[11px] text-zinc-500">
              <span className="h-1.5 w-1.5 rounded-full bg-green-500 animate-pulse" />
              Generating...
            </span>
          )}
          {isDone && answer && (
            <Button
              variant="outline"
              size="sm"
              className="h-6 text-[11px] px-2 text-zinc-500"
              onClick={handleCopy}
            >
              {copied ? (
                <>
                  <Check className="h-3 w-3 mr-1" />
                  Copied
                </>
              ) : (
                <>
                  <Copy className="h-3 w-3 mr-1" />
                  Copy
                </>
              )}
            </Button>
          )}
        </div>
      </div>

      {/* Answer body */}
      <div className="px-4 py-3 text-sm leading-7 whitespace-pre-wrap min-h-[60px]">
        {answer ? (
          renderWithCitations(answer, highlightedChunk, onCitationClick)
        ) : (
          <span className="text-zinc-400">Waiting for response...</span>
        )}
      </div>

      {/* Metrics bar */}
      {isDone && metrics && (
        <div className="flex items-center gap-4 px-4 py-2 border-t border-zinc-100 bg-zinc-50 text-xs text-zinc-500">
          <span className="flex items-center gap-1">
            <Clock className="h-3.5 w-3.5" />
            {(metrics.latencyMs / 1000).toFixed(2)}s
          </span>
          {metrics.completionTokens > 0 && (
            <span>
              {metrics.promptTokens > 0
                ? `${metrics.promptTokens} in → ${metrics.completionTokens} out tokens`
                : `${metrics.completionTokens} tokens`}
            </span>
          )}
          <span className="ml-auto text-[11px] text-zinc-400">
            {model} via {provider}
          </span>
        </div>
      )}
    </div>
  )
}
