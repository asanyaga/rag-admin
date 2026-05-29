import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { ArrowLeft, Play, Search, MessageSquare, AlertTriangle, Copy } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Slider } from '@/components/ui/slider'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { useProject } from '@/contexts/ProjectContext'
import { useGoldenSets } from '@/hooks/useGoldenSets'
import { useEvalRuns } from '@/hooks/useEvalRuns'
import { useIndexes } from '@/hooks/useIndexes'
import { getEvalRunConfig } from '@/api/eval-runs'
import type { EvalRunConfig, EvalMode } from '@/types/eval-run'
import { usePromptConfig } from '@/hooks/usePromptConfig'
import { PromptConfigEditor } from '@/components/shared/PromptConfigEditor'

export default function NewEvalRunPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { currentProject } = useProject()
  const projectId = currentProject?.id ?? null

  const cloneRunId = searchParams.get('clone')
  const experimentId = searchParams.get('experiment')

  const { goldenSets } = useGoldenSets(projectId)
  const { indexes } = useIndexes(projectId)
  const { createRun } = useEvalRuns(projectId)

  const [goldenSetId, setGoldenSetId] = useState('')
  const [indexId, setIndexId] = useState('')
  const [name, setName] = useState('')
  const [variantLabel, setVariantLabel] = useState('')
  const [searchType, setSearchType] = useState<EvalRunConfig['searchType']>('semantic')
  const [topK, setTopK] = useState(5)
  const [similarityThreshold, setSimilarityThreshold] = useState(0)
  const [mode, setMode] = useState<EvalMode | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [cloneSourceName, setCloneSourceName] = useState<string | null>(null)

  const {
    promptConfig: generationConfig,
    setPromptConfig: setGenerationConfig,
    setProvider: setGenerationProvider,
  } = usePromptConfig()
  const {
    promptConfig: judgeConfig,
    setPromptConfig: setJudgeConfig,
    setProvider: setJudgeProvider,
  } = usePromptConfig()

  // Clone: fetch source run config and pre-fill
  useEffect(() => {
    if (!cloneRunId || !projectId) return
    let cancelled = false

    const loadConfig = async () => {
      try {
        const config = await getEvalRunConfig(projectId, cloneRunId)
        if (cancelled) return

        if (config.goldenSetId) setGoldenSetId(config.goldenSetId as string)
        if (config.indexId) setIndexId(config.indexId as string)
        if (config.name) setCloneSourceName(config.name as string)
        if (config.mode) setMode(config.mode as EvalMode)

        const runConfig = config.config as Record<string, unknown> | undefined
        if (runConfig) {
          if (runConfig.searchType) setSearchType(runConfig.searchType as EvalRunConfig['searchType'])
          if (runConfig.topK) setTopK(runConfig.topK as number)
          if (runConfig.similarityThreshold != null) setSimilarityThreshold(runConfig.similarityThreshold as number)
        }

        const gc = config.generationConfig as Record<string, unknown> | null
        if (gc) {
          setGenerationConfig({
            provider: gc.provider as string | undefined,
            model: gc.model as string | undefined,
            temperature: gc.temperature as number | undefined,
            maxTokens: gc.max_tokens as number | undefined,
            systemPrompt: gc.system_prompt as string | undefined,
            topP: gc.top_p as number | undefined,
          })
        }
        const jc = config.judgeConfig as Record<string, unknown> | null
        if (jc) {
          setJudgeConfig({
            provider: jc.provider as string | undefined,
            model: jc.model as string | undefined,
            temperature: jc.temperature as number | undefined,
          })
        }
      } catch {
        // ignore clone errors — user can fill manually
      }
    }

    loadConfig()
    return () => { cancelled = true }
  }, [cloneRunId, projectId, setGenerationConfig, setJudgeConfig])

  const readyIndexes = indexes.filter((i) => i.status === 'ready')

  const selectedGoldenSet = goldenSets.find((gs) => gs.id === goldenSetId)
  const queryCount = selectedGoldenSet?.queryCount ?? 0

  const sameModelWarning =
    mode === 'retrieval_and_answer' &&
    generationConfig.provider &&
    generationConfig.provider === judgeConfig.provider &&
    generationConfig.model === judgeConfig.model

  const canSubmit =
    goldenSetId &&
    indexId &&
    mode !== null &&
    (mode === 'retrieval_only' || (
      generationConfig.provider && generationConfig.model &&
      judgeConfig.provider && judgeConfig.model
    ))

  const handleSubmit = async () => {
    if (!canSubmit || !mode) return
    setIsSubmitting(true)
    try {
      const run = await createRun({
        goldenSetId,
        indexId,
        name: name.trim() || undefined,
        config: { searchType, topK, similarityThreshold },
        mode,
        generationConfig: mode === 'retrieval_and_answer' ? generationConfig : undefined,
        judgeConfig: mode === 'retrieval_and_answer' ? judgeConfig : undefined,
        experimentId: experimentId || undefined,
        variantLabel: variantLabel.trim() || undefined,
      })
      navigate(`/evaluation/runs/${run.id}`)
    } catch {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="space-y-6 max-w-3xl">
      <div className="flex items-center gap-4">
        <Button
          variant="ghost"
          size="icon"
          onClick={() =>
            experimentId
              ? navigate(`/evaluation/experiments/${experimentId}`)
              : navigate('/evaluation')
          }
        >
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <h1 className="text-2xl font-bold">
          {cloneRunId ? 'New Variant' : 'New Evaluation Run'}
        </h1>
      </div>

      {/* Clone banner */}
      {cloneSourceName && (
        <div className="flex items-center gap-2 p-3 rounded-lg border border-blue-200 bg-blue-50 text-blue-800 text-sm dark:border-blue-800 dark:bg-blue-950/30 dark:text-blue-400">
          <Copy className="h-4 w-4 shrink-0" />
          <span>
            Creating variant based on <strong>{cloneSourceName}</strong>.
            Change the variable you want to test.
          </span>
        </div>
      )}

      {/* Mode Selector */}
      <div className="space-y-2">
        <Label className="text-sm font-medium">Evaluation Mode</Label>
        <div className="grid grid-cols-2 gap-4">
          <button
            type="button"
            onClick={() => setMode('retrieval_only')}
            className={`flex flex-col items-center gap-2 p-5 rounded-lg border-2 text-center transition-colors ${
              mode === 'retrieval_only'
                ? 'border-primary bg-primary/5'
                : 'border-muted hover:border-muted-foreground/30'
            }`}
          >
            <Search className="h-6 w-6 text-muted-foreground" />
            <span className="text-sm font-medium">Retrieval Only</span>
            <span className="text-xs text-muted-foreground">
              Fast &middot; No LLM cost
            </span>
          </button>
          <button
            type="button"
            onClick={() => setMode('retrieval_and_answer')}
            className={`flex flex-col items-center gap-2 p-5 rounded-lg border-2 text-center transition-colors ${
              mode === 'retrieval_and_answer'
                ? 'border-primary bg-primary/5'
                : 'border-muted hover:border-muted-foreground/30'
            }`}
          >
            <MessageSquare className="h-6 w-6 text-muted-foreground" />
            <span className="text-sm font-medium">Retrieval + Answer</span>
            <span className="text-xs text-muted-foreground">
              Slower &middot; LLM cost
            </span>
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* Golden Set */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Golden Set</CardTitle>
          </CardHeader>
          <CardContent>
            <Select value={goldenSetId} onValueChange={setGoldenSetId}>
              <SelectTrigger>
                <SelectValue placeholder="Select golden set" />
              </SelectTrigger>
              <SelectContent>
                {goldenSets.map((gs) => (
                  <SelectItem key={gs.id} value={gs.id}>
                    {gs.name} ({gs.queryCount} queries)
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </CardContent>
        </Card>

        {/* Index */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Index</CardTitle>
          </CardHeader>
          <CardContent>
            <Select value={indexId} onValueChange={setIndexId}>
              <SelectTrigger>
                <SelectValue placeholder="Select index" />
              </SelectTrigger>
              <SelectContent>
                {readyIndexes.map((idx) => (
                  <SelectItem key={idx.id} value={idx.id}>
                    {idx.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </CardContent>
        </Card>

        {/* Config */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Retrieval Config</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label className="text-xs">Search Mode</Label>
              <ToggleGroup
                type="single"
                value={searchType}
                onValueChange={(v) => {
                  if (v) setSearchType(v as EvalRunConfig['searchType'])
                }}
                className="justify-start"
              >
                <ToggleGroupItem value="semantic" size="sm">Semantic</ToggleGroupItem>
                <ToggleGroupItem value="keyword" size="sm">Keyword</ToggleGroupItem>
                <ToggleGroupItem value="hybrid" size="sm">Hybrid</ToggleGroupItem>
              </ToggleGroup>
            </div>
            <div className="space-y-2">
              <Label className="text-xs">Top K: {topK}</Label>
              <Slider
                value={[topK]}
                onValueChange={([v]) => setTopK(v)}
                min={1}
                max={20}
                step={1}
              />
            </div>
            <div className="space-y-2">
              <Label className="text-xs">
                Similarity Threshold: {similarityThreshold.toFixed(2)}
              </Label>
              <Slider
                value={[similarityThreshold]}
                onValueChange={([v]) => setSimilarityThreshold(v)}
                min={0}
                max={1}
                step={0.05}
              />
            </div>
          </CardContent>
        </Card>

        {/* Run Name + Variant Label */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Run Name</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Optional — auto-generated if empty"
            />
            {experimentId && (
              <div className="space-y-1">
                <Label className="text-xs">Variant Label</Label>
                <Input
                  value={variantLabel}
                  onChange={(e) => setVariantLabel(e.target.value)}
                  placeholder="e.g. topK=10, hybrid search"
                />
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Answer Config — only for retrieval_and_answer mode */}
      {mode === 'retrieval_and_answer' && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Answer Evaluation Config</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            {sameModelWarning && (
              <div className="flex items-center gap-2 text-xs text-amber-600">
                <AlertTriangle className="h-3 w-3" />
                Using the same model for generation and judging may reduce evaluation quality
              </div>
            )}

            <div className="space-y-2">
              <h3 className="text-sm font-medium">Generation Config</h3>
              <div className="rounded-md border p-3">
                <PromptConfigEditor
                  value={generationConfig}
                  onChange={setGenerationConfig}
                  onProviderChange={setGenerationProvider}
                  capabilities={{ thinking: true }}
                />
              </div>
            </div>

            <div className="space-y-2">
              <h3 className="text-sm font-medium">Judge Config</h3>
              <div className="rounded-md border p-3">
                <PromptConfigEditor
                  value={judgeConfig}
                  onChange={setJudgeConfig}
                  onProviderChange={setJudgeProvider}
                />
              </div>
            </div>

            {queryCount > 0 && (
              <p className="text-xs text-muted-foreground">
                Estimated: {queryCount} &times; 2 = {queryCount * 2} LLM calls
              </p>
            )}
          </CardContent>
        </Card>
      )}

      <div className="flex gap-3">
        <Button
          onClick={handleSubmit}
          disabled={!canSubmit || isSubmitting}
        >
          <Play className="mr-2 h-4 w-4" />
          {isSubmitting ? 'Starting...' : 'Run Evaluation'}
        </Button>
        <Button
          variant="outline"
          onClick={() =>
            experimentId
              ? navigate(`/evaluation/experiments/${experimentId}`)
              : navigate('/evaluation')
          }
        >
          Cancel
        </Button>
      </div>
    </div>
  )
}
