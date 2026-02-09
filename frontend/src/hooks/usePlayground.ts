/**
 * Hook for Playground state management and query execution
 */
import { useState, useCallback } from 'react'
import { SearchType, RetrievalResult, QueryResponse } from '@/types/index'
import { queryIndex } from '@/api/indexes'

interface UsePlaygroundReturn {
  query: string
  setQuery: (query: string) => void
  searchType: SearchType
  setSearchType: (type: SearchType) => void
  topK: number
  setTopK: (k: number) => void
  threshold: number
  setThreshold: (t: number) => void
  results: RetrievalResult[]
  isSearching: boolean
  error: string | null
  executionTimeMs: number | null
  runSearch: () => Promise<void>
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
  // Input state
  const [query, setQuery] = useState('')
  const [searchType, setSearchType] = useState<SearchType>('hybrid')
  const [topK, setTopK] = useState(5)
  const [threshold, setThreshold] = useState(0.0)

  // Results state
  const [results, setResults] = useState<RetrievalResult[]>([])
  const [isSearching, setIsSearching] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [executionTimeMs, setExecutionTimeMs] = useState<number | null>(null)

  // UI state
  const [queryHistory, setQueryHistory] = useState<string[]>([])
  const [votes, setVotes] = useState<Record<string, 'up' | 'down' | null>>({})
  const [expandedResultId, setExpandedResultId] = useState<string | null>(null)

  const runSearch = useCallback(async () => {
    const trimmed = query.trim()
    if (!trimmed || !projectId || !indexId) return

    setIsSearching(true)
    setError(null)
    setResults([])
    setVotes({})
    setExpandedResultId(null)

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

      // Add to history (deduplicated, most recent first, max 8)
      setQueryHistory((prev) => {
        const filtered = prev.filter((q) => q !== trimmed)
        return [trimmed, ...filtered].slice(0, 8)
      })
    } catch (err) {
      const message =
        err instanceof Error
          ? err.message
          : 'Failed to run query. Check your connection and try again.'
      setError(message)
    } finally {
      setIsSearching(false)
    }
  }, [query, searchType, topK, threshold, projectId, indexId])

  const setVote = useCallback(
    (chunkId: string, vote: 'up' | 'down' | null) => {
      setVotes((prev) => ({ ...prev, [chunkId]: vote }))
    },
    []
  )

  return {
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
    executionTimeMs,
    runSearch,
    queryHistory,
    votes,
    setVote,
    expandedResultId,
    setExpandedResultId,
  }
}
