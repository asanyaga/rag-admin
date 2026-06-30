import { useState, useCallback, useRef } from 'react'
import type { RunWithParseRequest } from '@/types/extraction'
import type { ParseRunListItem } from '@/types/cdm'
import * as extractionApi from '@/api/extraction'
import { createParseRun, listParseRuns, getParseRun } from '@/api/parseRuns'

const POLLING_INTERVAL = 3_000
const PARSE_TIMEOUT_MS = 10 * 60 * 1_000

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function stableStringify(value: unknown): string {
  if (value === null || typeof value !== 'object') return JSON.stringify(value)
  if (Array.isArray(value)) return `[${(value as unknown[]).map(stableStringify).join(',')}]`
  const obj = value as Record<string, unknown>
  const sorted = Object.keys(obj)
    .sort()
    .map((k) => `${JSON.stringify(k)}:${stableStringify(obj[k])}`)
  return `{${sorted.join(',')}}`
}

function findMatchingRun(
  runs: ParseRunListItem[],
  parser: string,
  representationKind: string,
  config: Record<string, unknown>,
): ParseRunListItem | undefined {
  const target = stableStringify({ parser, ...config })
  return runs.find(
    (r) =>
      r.parser === parser &&
      r.representationKind === representationKind &&
      stableStringify(r.config) === target &&
      (r.status === 'succeeded' || r.status === 'partial'),
  )
}

export type SubmitPhase = 'idle' | 'parsing' | 'extracting' | 'failed'

export interface UseExtractionSubmitReturn {
  phase: SubmitPhase
  phaseError: string | null
  submit: (
    documentId: string,
    existingParseRuns: ParseRunListItem[],
    request: RunWithParseRequest,
  ) => Promise<string | null>
}

export function useExtractionSubmit(): UseExtractionSubmitReturn {
  const [phase, setPhase] = useState<SubmitPhase>('idle')
  const [phaseError, setPhaseError] = useState<string | null>(null)
  const cancelledRef = useRef(false)

  const submit = useCallback(
    async (
      documentId: string,
      existingParseRuns: ParseRunListItem[],
      request: RunWithParseRequest,
    ): Promise<string | null> => {
      const { parseConfig, extractionConfig } = request
      setPhaseError(null)
      cancelledRef.current = false

      const matched = findMatchingRun(
        existingParseRuns,
        parseConfig.parser,
        parseConfig.representationKind,
        parseConfig.config,
      )
      let parseRunId: string

      if (matched) {
        parseRunId = matched.id
      } else {
        setPhase('parsing')
        const started = Date.now()

        try {
          await createParseRun(documentId, parseConfig.parser, {
            ...parseConfig.config,
            representation_kind: parseConfig.representationKind,
          })
        } catch {
          setPhase('failed')
          setPhaseError('Failed to start parse')
          return null
        }

        let resolvedId: string | null = null
        while (resolvedId === null) {
          if (cancelledRef.current) return null
          if (Date.now() - started > PARSE_TIMEOUT_MS) {
            setPhase('failed')
            setPhaseError('Parse timed out')
            return null
          }
          await sleep(POLLING_INTERVAL)
          const runs = await listParseRuns(documentId)
          const target = stableStringify({ parser: parseConfig.parser, ...parseConfig.config })
          const found = runs.find(
            (r) =>
              r.parser === parseConfig.parser &&
              r.representationKind === parseConfig.representationKind &&
              stableStringify(r.config) === target,
          )
          if (found) resolvedId = found.id
        }

        const foundId = resolvedId
        for (;;) {
          if (cancelledRef.current) return null
          if (Date.now() - started > PARSE_TIMEOUT_MS) {
            setPhase('failed')
            setPhaseError('Parse timed out')
            return null
          }
          const run = await getParseRun(foundId)
          if (run.status === 'succeeded' || run.status === 'partial') {
            parseRunId = foundId
            break
          }
          if (run.status === 'failed') {
            setPhase('failed')
            setPhaseError(run.error ?? 'Parse failed')
            return null
          }
          await sleep(POLLING_INTERVAL)
        }
      }

      setPhase('extracting')
      try {
        const result = await extractionApi.runExtraction({
          parseRunId: parseRunId!,
          extractionSchemaId: extractionConfig.extractionSchemaId,
          extractionMethod: extractionConfig.extractionMethod,
          config: extractionConfig.config,
          llmConfig: extractionConfig.llmConfig,
          userPromptTemplate: extractionConfig.userPromptTemplate,
          chunking: extractionConfig.chunking,
          preprocess: extractionConfig.preprocess,
          timeoutMinutes: extractionConfig.timeoutMinutes,
        })
        setPhase('idle')
        return result.id
      } catch (err) {
        setPhase('failed')
        setPhaseError(err instanceof Error ? err.message : 'Extraction failed')
        return null
      }
    },
    [],
  )

  return { phase, phaseError, submit }
}
