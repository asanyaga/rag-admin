import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams, Link, useLocation } from 'react-router-dom'
import { ChevronLeft } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ParseMethodSelector } from '@/components/documents/ParseMethodSelector'
import { ClassificationConfig } from '@/components/classification/ClassificationConfig'
import type { ClassificationConfigValue } from '@/components/classification/ClassificationConfig'
import { PromptConfigEditor } from '@/components/shared/PromptConfigEditor'
import { useParseRuns } from '@/hooks/useParseRuns'
import { createClassificationRun, getClassificationSystemPromptConfig } from '@/api/classification'
import type { ParseConfig } from '@/types/parsing'
import type { PromptConfig } from '@/types/prompt-config'
import type { RerunDefaults } from '@/types/classification'

const DEFAULT_PROMPT_CONFIG: PromptConfig = {
  provider: 'ollama_local',
  model: 'qwen2.5:7b',
  temperature: 0.0,
  maxTokens: 4096,
}

function configToPromptConfig(config: Record<string, unknown>): PromptConfig {
  const llm = (config.llm_config as Record<string, unknown> | undefined) ?? {}
  return {
    provider: (config.provider as string | undefined) ?? DEFAULT_PROMPT_CONFIG.provider,
    model: (config.model as string | undefined) ?? DEFAULT_PROMPT_CONFIG.model,
    temperature: (llm.temperature as number | undefined) ?? DEFAULT_PROMPT_CONFIG.temperature,
    maxTokens: (llm.max_tokens as number | undefined) ?? DEFAULT_PROMPT_CONFIG.maxTokens,
    systemPrompt: llm.system_prompt as string | undefined,
  }
}

export function NewClassificationRunPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const location = useLocation()

  const documentId = searchParams.get('documentId') ?? ''
  const defaults = (location.state as { defaults?: RerunDefaults; documentTitle?: string } | null)
    ?.defaults
  const documentTitle = (location.state as { documentTitle?: string } | null)?.documentTitle

  const { parseRuns } = useParseRuns(documentId || null)

  const latestViableRun = parseRuns.find(
    (r) => r.status === 'succeeded' || r.status === 'partial',
  )

  const [parserType, setParserType] = useState('simple')
  const [parserConfig, setParserConfig] = useState<ParseConfig>({})
  const [classifyConfig, setClassifyConfig] = useState<ClassificationConfigValue>({
    labels: defaults?.labels ?? [],
    classifierType: defaults?.classifierType ?? 'llm',
  })
  const [promptConfig, setPromptConfig] = useState<PromptConfig>(
    defaults?.classifierConfig && Object.keys(defaults.classifierConfig).length > 0
      ? configToPromptConfig(defaults.classifierConfig)
      : DEFAULT_PROMPT_CONFIG,
  )
  const [batchSize, setBatchSize] = useState(
    (defaults?.classifierConfig?.batch_size as number | undefined) ?? 10,
  )
  const [batchOverlap, setBatchOverlap] = useState(
    (defaults?.classifierConfig?.batch_overlap as number | undefined) ?? 3,
  )
  const [systemPromptConfig, setSystemPromptConfig] = useState<{
    instruction: string
    requiredFormat: string
  } | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Seed parse config from the latest successful parse run
  useEffect(() => {
    if (!latestViableRun) return
    setParserType(latestViableRun.parser ?? 'simple')
    const cfg = { ...(latestViableRun.config as Record<string, unknown> ?? {}) }
    delete cfg['parser']
    setParserConfig(cfg as ParseConfig)
  }, [latestViableRun?.id]) // eslint-disable-line react-hooks/exhaustive-deps

  // Fetch the default system prompt instruction + required format section from the backend
  useEffect(() => {
    getClassificationSystemPromptConfig()
      .then(setSystemPromptConfig)
      .catch(() => {
        // silently degrade — required format section simply won't render
      })
  }, [])

  // Pre-populate the system prompt textarea with the default instruction when not from re-run
  useEffect(() => {
    if (!systemPromptConfig) return
    setPromptConfig((prev) => {
      if (prev.systemPrompt !== undefined) return prev // already set from re-run defaults
      return { ...prev, systemPrompt: systemPromptConfig.instruction }
    })
  }, [systemPromptConfig])

  const backHref = `/classify${documentId ? `?documentId=${documentId}` : ''}`

  const handleSubmit = async () => {
    if (!documentId || classifyConfig.labels.length === 0) return
    if (!latestViableRun) {
      setError('No completed parse run found for this document. Parse it first.')
      return
    }
    setIsSubmitting(true)
    setError(null)
    try {
      const classifierConfig =
        classifyConfig.classifierType === 'llm'
          ? {
              provider: promptConfig.provider,
              model: promptConfig.model,
              batch_size: batchSize,
              batch_overlap: batchOverlap,
              llm_config: {
                system_prompt: promptConfig.systemPrompt ?? null,
                temperature: promptConfig.temperature ?? 0.0,
                max_tokens: promptConfig.maxTokens ?? 4096,
              },
            }
          : {}

      const run = await createClassificationRun(documentId, {
        parseRunId: latestViableRun.id,
        labels: classifyConfig.labels,
        classifierType: classifyConfig.classifierType,
        classifierConfig,
      })
      navigate(`/classify/${run.id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start classification')
      setIsSubmitting(false)
    }
  }

  const isLlm = classifyConfig.classifierType === 'llm'

  return (
    <div className="max-w-2xl mx-auto py-8 px-6 space-y-6">
      <Button variant="ghost" size="sm" asChild className="-ml-2">
        <Link to={backHref}>
          <ChevronLeft className="h-4 w-4 mr-1" />
          Back
        </Link>
      </Button>

      <div>
        <h1 className="text-2xl font-semibold">New classification run</h1>
        {documentTitle && (
          <p className="text-sm text-muted-foreground mt-1">{documentTitle}</p>
        )}
      </div>

      {/* Section 1: Classification */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Classification</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <ClassificationConfig
            defaultValues={{
              labels: classifyConfig.labels,
              classifierType: classifyConfig.classifierType,
            }}
            onChange={setClassifyConfig}
          />
          {classifyConfig.classifierType === 'llamaindex_split' && (
            <p className="text-sm text-muted-foreground">
              LlamaIndex split classifier is not yet implemented. Select LLM classifier to proceed.
            </p>
          )}
          {isLlm && (
            <div className="grid grid-cols-2 gap-4 pt-2 border-t">
              <div className="space-y-2">
                <Label>Batch size (pages)</Label>
                <Input
                  type="number"
                  min={1}
                  value={batchSize}
                  onChange={(e) => setBatchSize(Number(e.target.value))}
                  disabled={isSubmitting}
                />
              </div>
              <div className="space-y-2">
                <Label>Batch overlap (pages)</Label>
                <Input
                  type="number"
                  min={0}
                  value={batchOverlap}
                  onChange={(e) => setBatchOverlap(Number(e.target.value))}
                  disabled={isSubmitting}
                />
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Section 3: LLM configuration (only when LLM classifier selected) */}
      {isLlm && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">LLM configuration</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            <PromptConfigEditor
              value={promptConfig}
              onChange={setPromptConfig}
              capabilities={{ thinking: true }}
            />
            {systemPromptConfig && (
              <div className="border-t pt-4 space-y-2">
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                  Required output format · always appended by the app
                </p>
                <pre className="text-xs bg-muted rounded-md p-3 font-mono text-muted-foreground whitespace-pre-wrap break-words cursor-default select-text">
                  {systemPromptConfig.requiredFormat}
                </pre>
                <p className="text-xs text-muted-foreground">
                  ⓘ The app parses this JSON structure from the model response to build
                  classification regions.
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Section 3: Parse configuration */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Parse configuration</CardTitle>
        </CardHeader>
        <CardContent>
          <ParseMethodSelector
            parserType={parserType}
            config={parserConfig}
            onParserTypeChange={setParserType}
            onConfigChange={setParserConfig}
            disabled={isSubmitting}
          />
        </CardContent>
      </Card>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className="flex gap-3 pt-2">
        <Button
          onClick={handleSubmit}
          disabled={classifyConfig.labels.length === 0 || isSubmitting || !isLlm}
        >
          {isSubmitting ? 'Starting…' : 'Start classification'}
        </Button>
        <Button variant="outline" asChild>
          <Link to={backHref}>Cancel</Link>
        </Button>
      </div>
    </div>
  )
}
