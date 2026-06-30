import { useState } from 'react'
import { X, ChevronDown } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import { PromptConfigEditor } from '@/components/shared/PromptConfigEditor'
import type { PromptConfig } from '@/types/prompt-config'

const CLASSIFIER_TYPES = [
  { value: 'llm', label: 'LLM classifier' },
  { value: 'llamaindex_split', label: 'LlamaIndex split (not yet implemented)' },
]

const DEFAULT_PROMPT_CONFIG: PromptConfig = {
  provider: 'ollama_local',
  model: 'qwen2.5:7b',
  temperature: 0.0,
  maxTokens: 4096,
}

export interface ClassificationConfigValue {
  labels: string[]
  classifierType: string
  classifierConfig: Record<string, unknown>
}

interface Props {
  defaultValues?: Partial<ClassificationConfigValue>
  onChange: (value: ClassificationConfigValue) => void
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

function buildClassifierConfig(
  classifierType: string,
  promptConfig: PromptConfig,
  batchSize: number,
  batchOverlap: number,
): Record<string, unknown> {
  if (classifierType !== 'llm') return {}
  return {
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
}

export function ClassificationConfig({ defaultValues, onChange }: Props) {
  const dv = defaultValues ?? {}
  const [labels, setLabels] = useState<string[]>(dv.labels ?? [])
  const [labelInput, setLabelInput] = useState('')
  const [classifierType, setClassifierType] = useState(dv.classifierType ?? 'llm')
  const [promptConfig, setPromptConfig] = useState<PromptConfig>(
    dv.classifierConfig && Object.keys(dv.classifierConfig).length > 0
      ? configToPromptConfig(dv.classifierConfig)
      : DEFAULT_PROMPT_CONFIG,
  )
  const [batchSize, setBatchSize] = useState(
    (dv.classifierConfig?.batch_size as number | undefined) ?? 10,
  )
  const [batchOverlap, setBatchOverlap] = useState(
    (dv.classifierConfig?.batch_overlap as number | undefined) ?? 3,
  )

  function emit(
    nextLabels: string[],
    nextType: string,
    nextPrompt: PromptConfig,
    nextBatch: number,
    nextOverlap: number,
  ) {
    onChange({
      labels: nextLabels,
      classifierType: nextType,
      classifierConfig: buildClassifierConfig(nextType, nextPrompt, nextBatch, nextOverlap),
    })
  }

  const addLabel = () => {
    const trimmed = labelInput.trim()
    if (!trimmed || labels.includes(trimmed)) return
    const next = [...labels, trimmed]
    setLabels(next)
    setLabelInput('')
    emit(next, classifierType, promptConfig, batchSize, batchOverlap)
  }

  const removeLabel = (l: string) => {
    const next = labels.filter((x) => x !== l)
    setLabels(next)
    emit(next, classifierType, promptConfig, batchSize, batchOverlap)
  }

  const handleClassifierTypeChange = (v: string) => {
    setClassifierType(v)
    emit(labels, v, promptConfig, batchSize, batchOverlap)
  }

  const handlePromptConfigChange = (v: PromptConfig) => {
    setPromptConfig(v)
    emit(labels, classifierType, v, batchSize, batchOverlap)
  }

  const handleBatchSizeChange = (v: number) => {
    setBatchSize(v)
    emit(labels, classifierType, promptConfig, v, batchOverlap)
  }

  const handleBatchOverlapChange = (v: number) => {
    setBatchOverlap(v)
    emit(labels, classifierType, promptConfig, batchSize, v)
  }

  return (
    <div className="space-y-6">
      {/* Labels */}
      <div className="space-y-2">
        <Label>Labels to classify</Label>
        <div className="flex gap-2">
          <Input
            placeholder="e.g. balance_sheet"
            value={labelInput}
            onChange={(e) => setLabelInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault()
                addLabel()
              }
            }}
          />
          <Button type="button" variant="outline" onClick={addLabel}>
            Add
          </Button>
        </div>
        {labels.length > 0 && (
          <div className="flex flex-wrap gap-2 mt-2">
            {labels.map((l) => (
              <Badge key={l} variant="secondary" className="flex items-center gap-1">
                {l}
                <button
                  aria-label={`Remove ${l}`}
                  onClick={() => removeLabel(l)}
                  className="ml-1 hover:text-destructive"
                >
                  <X className="h-3 w-3" />
                </button>
              </Badge>
            ))}
          </div>
        )}
      </div>

      {/* Classifier type */}
      <div className="space-y-2">
        <Label>Classifier</Label>
        <Select value={classifierType} onValueChange={handleClassifierTypeChange}>
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {CLASSIFIER_TYPES.map((t) => (
              <SelectItem key={t.value} value={t.value}>
                {t.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* LLM config */}
      {classifierType === 'llm' && (
        <>
          <PromptConfigEditor value={promptConfig} onChange={handlePromptConfigChange} />
          <Collapsible>
            <CollapsibleTrigger className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground">
              <ChevronDown className="h-4 w-4" />
              Batch settings
            </CollapsibleTrigger>
            <CollapsibleContent className="mt-3 grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Batch size (pages)</Label>
                <Input
                  type="number"
                  min={1}
                  value={batchSize}
                  onChange={(e) => handleBatchSizeChange(Number(e.target.value))}
                />
              </div>
              <div className="space-y-2">
                <Label>Batch overlap (pages)</Label>
                <Input
                  type="number"
                  min={0}
                  value={batchOverlap}
                  onChange={(e) => handleBatchOverlapChange(Number(e.target.value))}
                />
              </div>
            </CollapsibleContent>
          </Collapsible>
        </>
      )}

      {/* LlamaIndex placeholder */}
      {classifierType === 'llamaindex_split' && (
        <p className="text-sm text-muted-foreground">
          LlamaIndex split classifier is not yet implemented. Select LLM classifier to proceed.
        </p>
      )}
    </div>
  )
}
