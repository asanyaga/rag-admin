/**
 * Hook for Playground state management and query execution.
 *
 * Supports two modes:
 * - Retrieval: existing chunk search (queryIndex API)
 * - Answer: retrieval + LLM generation via SSE streaming
 */
import { useState, useCallback, useRef } from 'react'
import { SearchType, RetrievalResult, QueryResponse } from '@/types/index'
import { queryIndex } from '@/api/indexes'
import {
  streamAnswer,
  AnswerDoneMetadata,
} from '@/api/playground'

// ─── Types ──────────────────────────────────────────────────────────────────

export type PlaygroundMode = 'retrieval' | 'answer'

export type StreamingPhase = 'idle' | 'retrieving' | 'generating' | 'done'

export interface AnswerMetrics {
  latencyMs: number
  promptTokens: number
  completionTokens: number
  totalTokens: number
}

export const LLM_MODEL_OPTIONS: Record<string, { value: string; label: string }[]> = {
  openai: [
    { value: 'gpt-4o', label: 'GPT-4o' },
    { value: 'gpt-4o-mini', label: 'GPT-4o Mini' },
    { value: 'gpt-4.1', label: 'GPT-4.1' },
    { value: 'gpt-4.1-mini', label: 'GPT-4.1 Mini' },
    { value: 'gpt-4.1-nano', label: 'GPT-4.1 Nano' },
  ],
}

export interface UsePlaygroundReturn {
  // Query input
  query: string
  setQuery: (query: string) => void

  // Retrieval params
  searchType: SearchType
  setSearchType: (type: SearchType) => void
  topK: number
  setTopK: (k: number) => void
  threshold: number
  setThreshold: (t: number) => void

  // Mode
  mode: PlaygroundMode
  setMode: (mode: PlaygroundMode) => void

  // LLM params (answer mode)
  provider: string
  setProvider: (provider: string) => void
  model: string
  setModel: (model: string) => void
  temperature: number
  setTemperature: (t: number) => void
  maxTokens: number
  setMaxTokens: (t: number) => void
  instructions: string
  setInstructions: (text: string) => void

  // Results
  results: RetrievalResult[]
  isSearching: boolean
  error: string | null
  executionTimeMs: number | null

  // Answer mode results
  answer: string
  streamingPhase: StreamingPhase
  answerMetrics: AnswerMetrics | null
  highlightedChunk: number | null
  setHighlightedChunk: (n: number | null) => void

  // Actions
  runSearch: () => Promise<void>
  handleStop: () => void
  handleCitationClick: (chunkNum: number) => void

  // UI state
  queryHistory: string[]
  votes: Record<string, 'up' | 'down' | null>
  setVote: (chunkId: string, vote: 'up' | 'down' | null) => void
  expandedResultId: string | null
  setExpandedResultId: (id: string | null) => void
}

export function usePlayground(
  projectId: string | null,
  indexId: string | null
): UsePlaygroundReturn {
  // ─── Input state ────────────────────────────────────────────────────────
  const [query, setQuery] = useState('')
  const [searchType, setSearchType] = useState<SearchType>('hybrid')
  const [topK, setTopK] = useState(5)
  const [threshold, setThreshold] = useState(0.0)

  // ─── Mode & LLM config ─────────────────────────────────────────────────
  const [mode, setMode] = useState<PlaygroundMode>('retrieval')
  const [provider, setProviderRaw] = useState('openai')
  const [model, setModel] = useState('gpt-4o')
  const [temperature, setTemperature] = useState(0.0)
  const [maxTokens, setMaxTokens] = useState(1024)
  const [instructions, setInstructions] = useState('')

  // ─── Results state ──────────────────────────────────────────────────────
  const [results, setResults] = useState<RetrievalResult[]>([])
  const [isSearching, setIsSearching] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [executionTimeMs, setExecutionTimeMs] = useState<number | null>(null)

  // ─── Answer mode state ──────────────────────────────────────────────────
  const [answer, setAnswer] = useState('')
  const [streamingPhase, setStreamingPhase] = useState<StreamingPhase>('idle')
  const [answerMetrics, setAnswerMetrics] = useState<AnswerMetrics | null>(null)
  const [highlightedChunk, setHighlightedChunk] = useState<number | null>(null)

  // ─── UI state ───────────────────────────────────────────────────────────
  const [queryHistory, setQueryHistory] = useState<string[]>([])
  const [votes, setVotes] = useState<Record<string, 'up' | 'down' | null>>({})
  const [expandedResultId, setExpandedResultId] = useState<string | null>(null)

  // ─── Abort controller ref ───────────────────────────────────────────────
  const abortRef = useRef<AbortController | null>(null)

  // ─── Provider change (auto-select first model) ─────────────────────────
  const setProvider = useCallback((p: string) => {
    setProviderRaw(p)
    const models = LLM_MODEL_OPTIONS[p]
    if (models?.length) {
      setModel(models[0].value)
    }
  }, [])

  // ─── Citation click handler ─────────────────────────────────────────────
  const handleCitationClick = useCallback(
    (chunkNum: number) => {
      setHighlightedChunk((prev) => (prev === chunkNum ? null : chunkNum))
    },
    []
  )

  // ─── Stop streaming ────────────────────────────────────────────────────
  const handleStop = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort()
      abortRef.current = null
    }
    setStreamingPhase('done')
    setIsSearching(false)
  }, [])

  // ─── Run search (branches on mode) ─────────────────────────────────────
  const runSearch = useCallback(async () => {
    const trimmed = query.trim()
    if (!trimmed || !projectId || !indexId) return

    // Reset state
    setIsSearching(true)
    setError(null)
    setResults([])
    setVotes({})
    setExpandedResultId(null)
    setAnswer('')
    setAnswerMetrics(null)
    setHighlightedChunk(null)

    // Cancel any in-flight stream
    if (abortRef.current) {
      abortRef.current.abort()
    }

    // Add to history
    setQueryHistory((prev) => {
      const filtered = prev.filter((q) => q !== trimmed)
      return [trimmed, ...filtered].slice(0, 8)
    })

    if (mode === 'retrieval') {
      // ── Retrieval mode: existing behavior ──
      setStreamingPhase('retrieving')
      try {
        const response: QueryResponse = await queryIndex(projectId, indexId, {
          query: trimmed,
          searchType,
          topK,
          similarityThreshold: threshold,
          projectId,
        })
        setResults(response.results)
        setExecutionTimeMs(response.executionTimeMs)
        setStreamingPhase('done')
      } catch (err) {
        const message =
          err instanceof Error
            ? err.message
            : 'Failed to run query. Check your connection and try again.'
        setError(message)
        setStreamingPhase('idle')
      } finally {
        setIsSearching(false)
      }
    } else {
      // ── Answer mode: SSE streaming ──
      setStreamingPhase('retrieving')
      const controller = new AbortController()
      abortRef.current = controller

      try {
        await streamAnswer(
          projectId,
          indexId,
          {
            query: trimmed,
            instructions: instructions || undefined,
            retrievalConfig: {
              searchType,
              topK,
              similarityThreshold: threshold,
            },
            llmConfig: {
              provider,
              model,
              temperature,
              maxTokens,
            },
          },
          {
            onChunks: (chunks: RetrievalResult[]) => {
              setResults(chunks)
              setExecutionTimeMs(null) // retrieval time not separate in answer mode
              setStreamingPhase('generating')
            },
            onToken: (content: string) => {
              setAnswer((prev) => prev + content)
            },
            onDone: (metadata: AnswerDoneMetadata) => {
              setAnswerMetrics({
                latencyMs: metadata.latencyMs,
                promptTokens: metadata.usage.promptTokens,
                completionTokens: metadata.usage.completionTokens,
                totalTokens: metadata.usage.totalTokens,
              })
              setStreamingPhase('done')
              setIsSearching(false)
            },
            onError: (err: { error: string; code: string }) => {
              setError(err.error)
              setStreamingPhase('done')
              setIsSearching(false)
            },
          },
          controller.signal
        )
        // Stream may complete without a done event on abort
        setIsSearching(false)
        if (streamingPhase !== 'done') {
          setStreamingPhase('done')
        }
      } catch (err) {
        if (err instanceof DOMException && err.name === 'AbortError') return
        const message =
          err instanceof Error
            ? err.message
            : 'Failed to generate answer. Check your connection and try again.'
        setError(message)
        setStreamingPhase('idle')
        setIsSearching(false)
      } finally {
        abortRef.current = null
      }
    }
  }, [
    query,
    searchType,
    topK,
    threshold,
    projectId,
    indexId,
    mode,
    provider,
    model,
    temperature,
    maxTokens,
    instructions,
    streamingPhase,
  ])

  const setVote = useCallback(
    (chunkId: string, vote: 'up' | 'down' | null) => {
      setVotes((prev) => ({ ...prev, [chunkId]: vote }))
    },
    []
  )

  return {
    // Query input
    query,
    setQuery,

    // Retrieval params
    searchType,
    setSearchType,
    topK,
    setTopK,
    threshold,
    setThreshold,

    // Mode
    mode,
    setMode,

    // LLM params
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

    // Results
    results,
    isSearching,
    error,
    executionTimeMs,

    // Answer mode
    answer,
    streamingPhase,
    answerMetrics,
    highlightedChunk,
    setHighlightedChunk,

    // Actions
    runSearch,
    handleStop,
    handleCitationClick,

    // UI state
    queryHistory,
    votes,
    setVote,
    expandedResultId,
    setExpandedResultId,
  }
}
