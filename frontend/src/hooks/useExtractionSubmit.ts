import { useState, useCallback, useRef } from 'react'
import type { PreprocessStage, RunWithParseRequest } from '@/types/extraction'
import type { ParseRunListItem } from '@/types/cdm'
import * as extractionApi from '@/api/extraction'
import { createParseRun, listParseRuns, getParseRun } from '@/api/parseRuns'
import { createClassificationRun, getClassificationRun } from '@/api/classification'
import type { ClassificationFilterIntent } from '@/lib/classificationFilter'

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

export type SubmitPhase = 'idle' | 'parsing' | 'classifying' | 'extracting' | 'failed'

export interface UseExtractionSubmitReturn {
  phase: SubmitPhase
  phaseError: string | null
  submit: (
    documentId: string,
    existingParseRuns: ParseRunListItem[],
    request: RunWithParseRequest,
    intent?: ClassificationFilterIntent,
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
      intent: ClassificationFilterIntent = { mode: 'none' },
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

      // Resolve the classification filter into a category_filter stage (method-agnostic).
      let categoryStage: PreprocessStage | null = null
      if (intent.mode === 'select') {
        categoryStage = {
          stage: 'category_filter',
          config: {
            classificationRunId: intent.classificationRunId,
            categories: intent.categories,
            granularity: intent.granularity,
          },
        }
      } else if (intent.mode === 'configure') {
        setPhase('classifying')
        let runId: string
        try {
          const created = await createClassificationRun(documentId, {
            parseRunId: parseRunId!,
            labels: intent.classify.labels,
            classifierType: intent.classify.classifierType,
            classifierConfig: intent.classify.classifierConfig,
          })
          runId = created.id
        } catch {
          setPhase('failed')
          setPhaseError('Failed to start classification')
          return null
        }
        const clsStarted = Date.now()
        for (;;) {
          if (cancelledRef.current) return null
          if (Date.now() - clsStarted > PARSE_TIMEOUT_MS) {
            setPhase('failed')
            setPhaseError('Classification timed out')
            return null
          }
          const run = await getClassificationRun(runId)
          if (run.status === 'completed') break
          if (run.status === 'failed') {
            setPhase('failed')
            setPhaseError(run.error ?? 'Classification failed')
            return null
          }
          await sleep(POLLING_INTERVAL)
        }
        categoryStage = {
          stage: 'category_filter',
          config: {
            classificationRunId: runId,
            categories: intent.categories,
            granularity: intent.granularity,
          },
        }
      }

      setPhase('extracting')
      try {
        const preprocess = [
          ...(extractionConfig.preprocess ?? []),
          ...(categoryStage ? [categoryStage] : []),
        ]
        const result = await extractionApi.runExtraction({
          parseRunId: parseRunId!,
          extractionSchemaId: extractionConfig.extractionSchemaId,
          extractionMethod: extractionConfig.extractionMethod,
          config: extractionConfig.config,
          llmConfig: extractionConfig.llmConfig,
          userPromptTemplate: extractionConfig.userPromptTemplate,
          chunking: extractionConfig.chunking,
          preprocess: preprocess.length ? preprocess : undefined,
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
