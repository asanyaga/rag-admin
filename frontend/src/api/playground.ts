/**
 * SSE streaming client for the Answer Playground endpoint.
 */
import { getAccessToken } from './client'
import { RetrievalResult } from '@/types/index'
import { QueryTrace } from '@/types/trace'
import type { PromptConfig } from '@/types/prompt-config'

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1'

export interface PlaygroundAnswerRequest {
  query: string
  retrievalConfig: {
    searchType: string
    topK: number
    similarityThreshold: number
  }
  llmConfig?: PromptConfig
}

export interface TokenUsage {
  promptTokens: number
  completionTokens: number
  totalTokens: number
}

export interface AnswerDoneMetadata {
  usage: TokenUsage
  latencyMs: number
}

export interface StreamAnswerCallbacks {
  onChunks: (chunks: RetrievalResult[]) => void
  onToken: (content: string) => void
  onDone: (metadata: AnswerDoneMetadata) => void
  onTrace?: (trace: QueryTrace) => void
  onError: (error: { error: string; code: string }) => void
}

/**
 * Parse SSE events from a text buffer.
 * Returns parsed events and any remaining incomplete text.
 */
function parseSSEEvents(buffer: string): {
  events: Array<{ type: string; data: string }>
  remaining: string
} {
  const events: Array<{ type: string; data: string }> = []
  // Split on double newlines (SSE event boundary)
  const parts = buffer.split('\n\n')
  // The last part may be incomplete — keep it as remaining
  const remaining = parts.pop() ?? ''

  for (const part of parts) {
    if (!part.trim()) continue

    let eventType = 'message'
    let data = ''

    for (const line of part.split('\n')) {
      if (line.startsWith('event: ')) {
        eventType = line.slice(7).trim()
      } else if (line.startsWith('data: ')) {
        data = line.slice(6)
      }
    }

    if (data) {
      events.push({ type: eventType, data })
    }
  }

  return { events, remaining }
}

/**
 * Stream an answer from the playground endpoint via SSE.
 *
 * Uses fetch + ReadableStream to consume the SSE stream and
 * dispatch typed callbacks for each event.
 */
export async function streamAnswer(
  projectId: string,
  indexId: string,
  params: PlaygroundAnswerRequest,
  callbacks: StreamAnswerCallbacks,
  signal?: AbortSignal,
  options?: { trace?: boolean }
): Promise<void> {
  const token = getAccessToken()

  const url = new URL(
    `${API_BASE_URL}/projects/${projectId}/indexes/${indexId}/playground/answer`,
    window.location.origin
  )
  if (options?.trace) {
    url.searchParams.set('trace', 'true')
  }

  const response = await fetch(
    url.toString(),
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({
        query: params.query,
        retrieval_config: {
          search_type: params.retrievalConfig.searchType,
          top_k: params.retrievalConfig.topK,
          similarity_threshold: params.retrievalConfig.similarityThreshold,
        },
        llm_config: params.llmConfig ? {
          system_prompt: params.llmConfig.systemPrompt ?? null,
          provider: params.llmConfig.provider ?? null,
          model: params.llmConfig.model ?? null,
          temperature: params.llmConfig.temperature ?? null,
          max_tokens: params.llmConfig.maxTokens ?? null,
          top_p: params.llmConfig.topP ?? null,
          thinking: params.llmConfig.thinking ? {
            enabled: params.llmConfig.thinking.enabled,
            effort: params.llmConfig.thinking.effort ?? null,
            budget_tokens: params.llmConfig.thinking.budgetTokens ?? null,
          } : null,
          json_mode: params.llmConfig.jsonMode ?? false,
          structured_output: params.llmConfig.structuredOutput ?? null,
          tools: params.llmConfig.tools ?? null,
        } : null,
      }),
      signal,
    }
  )

  if (!response.ok) {
    let errorMessage = `Request failed with status ${response.status}`
    try {
      const body = await response.json()
      errorMessage = body.detail || body.message || errorMessage
    } catch {
      // Response body wasn't JSON
    }
    callbacks.onError({ error: errorMessage, code: `http_${response.status}` })
    return
  }

  const reader = response.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    let done = false
    while (!done) {
      const result = await reader.read()
      done = result.done
      if (done) break
      const value = result.value

      buffer += decoder.decode(value, { stream: true })
      const { events, remaining } = parseSSEEvents(buffer)
      buffer = remaining

      for (const event of events) {
        switch (event.type) {
          case 'chunks':
            callbacks.onChunks(JSON.parse(event.data))
            break
          case 'token':
            callbacks.onToken(JSON.parse(event.data).content)
            break
          case 'done':
            callbacks.onDone(JSON.parse(event.data))
            break
          case 'trace':
            callbacks.onTrace?.(JSON.parse(event.data))
            break
          case 'error':
            callbacks.onError(JSON.parse(event.data))
            break
        }
      }
    }
  } catch (err) {
    // Don't report abort errors — the user intentionally cancelled
    if (err instanceof DOMException && err.name === 'AbortError') return
    callbacks.onError({
      error: err instanceof Error ? err.message : 'Stream connection lost',
      code: 'stream_error',
    })
  }
}
