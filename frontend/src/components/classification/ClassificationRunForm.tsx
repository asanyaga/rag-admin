// frontend/src/components/classification/ClassificationRunForm.tsx
import { useState } from 'react'
import { X, ChevronDown } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import {
  Collapsible, CollapsibleContent, CollapsibleTrigger,
} from '@/components/ui/collapsible'
import { PromptConfigEditor } from '@/components/shared/PromptConfigEditor'
import type { PromptConfig } from '@/types/prompt-config'

const CLASSIFIER_TYPES = [
  { value: 'llm', label: 'LLM classifier' },
  { value: 'llamaindex_split', label: 'LlamaIndex split (not yet implemented)' },
]

const DEFAULT_LLM_PROMPT_CONFIG: PromptConfig = {
  provider: 'ollama_local',
  model: 'qwen2.5:7b',
  temperature: 0.0,
  maxTokens: 4096,
}

export interface ClassificationRunFormValues {
  labels: string[]
  classifierType: string
  classifierConfig: Record<string, unknown>
}

interface Props {
  defaultValues?: Partial<ClassificationRunFormValues>
  onSubmit: (values: ClassificationRunFormValues) => void
  isSubmitting?: boolean
  submitLabel?: string
}

function _configToPromptConfig(config: Record<string, unknown>): PromptConfig {
  const llmConfig = (config.llm_config as Record<string, unknown> | undefined) ?? {}
  return {
    provider: (config.provider as string | undefined) ?? DEFAULT_LLM_PROMPT_CONFIG.provider,
    model: (config.model as string | undefined) ?? DEFAULT_LLM_PROMPT_CONFIG.model,
    temperature: (llmConfig.temperature as number | undefined) ?? DEFAULT_LLM_PROMPT_CONFIG.temperature,
    maxTokens: (llmConfig.max_tokens as number | undefined) ?? DEFAULT_LLM_PROMPT_CONFIG.maxTokens,
    systemPrompt: (llmConfig.system_prompt as string | undefined),
  }
}

export function ClassificationRunForm({
  defaultValues,
  onSubmit,
  isSubmitting,
  submitLabel = 'Start classification',
}: Props) {
  const [labels, setLabels] = useState<string[]>(defaultValues?.labels ?? [])
  const [labelInput, setLabelInput] = useState('')
  const [classifierType, setClassifierType] = useState(defaultValues?.classifierType ?? 'llm')
  const [promptConfig, setPromptConfig] = useState<PromptConfig>(
    defaultValues?.classifierConfig
      ? _configToPromptConfig(defaultValues.classifierConfig)
      : DEFAULT_LLM_PROMPT_CONFIG,
  )
  const [batchSize, setBatchSize] = useState(
    (defaultValues?.classifierConfig?.batch_size as number | undefined) ?? 10,
  )
  const [batchOverlap, setBatchOverlap] = useState(
    (defaultValues?.classifierConfig?.batch_overlap as number | undefined) ?? 3,
  )

  const addLabel = () => {
    const trimmed = labelInput.trim()
    if (trimmed && !labels.includes(trimmed)) setLabels((prev) => [...prev, trimmed])
    setLabelInput('')
  }

  const removeLabel = (l: string) => setLabels((prev) => prev.filter((x) => x !== l))

  const handleSubmit = () => {
    if (labels.length === 0) return
    const classifierConfig: Record<string, unknown> =
      classifierType === 'llm'
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
    onSubmit({ labels, classifierType, classifierConfig })
  }

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <Label>Labels to classify</Label>
        <div className="flex gap-2">
          <Input
            placeholder="e.g. balance_sheet"
            value={labelInput}
            onChange={(e) => setLabelInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addLabel() } }}
          />
          <Button type="button" variant="outline" onClick={addLabel}>Add</Button>
        </div>
        {labels.length > 0 && (
          <div className="flex flex-wrap gap-2 mt-2">
            {labels.map((l) => (
              <Badge key={l} variant="secondary" className="flex items-center gap-1">
                {l}
                <button onClick={() => removeLabel(l)} className="ml-1 hover:text-destructive">
                  <X className="h-3 w-3" />
                </button>
              </Badge>
            ))}
          </div>
        )}
      </div>

      <div className="space-y-2">
        <Label>Classifier</Label>
        <Select value={classifierType} onValueChange={setClassifierType}>
          <SelectTrigger><SelectValue /></SelectTrigger>
          <SelectContent>
            {CLASSIFIER_TYPES.map((t) => (
              <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {classifierType === 'llm' && (
        <>
          <PromptConfigEditor value={promptConfig} onChange={setPromptConfig} />
          <Collapsible>
            <CollapsibleTrigger className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground">
              <ChevronDown className="h-4 w-4" />
              Batch settings
            </CollapsibleTrigger>
            <CollapsibleContent className="mt-3 grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Batch size (pages)</Label>
                <Input type="number" min={1} value={batchSize}
                  onChange={(e) => setBatchSize(Number(e.target.value))} />
              </div>
              <div className="space-y-2">
                <Label>Batch overlap (pages)</Label>
                <Input type="number" min={0} value={batchOverlap}
                  onChange={(e) => setBatchOverlap(Number(e.target.value))} />
              </div>
            </CollapsibleContent>
          </Collapsible>
        </>
      )}

      {classifierType === 'llamaindex_split' && (
        <p className="text-sm text-muted-foreground">
          LlamaIndex split classifier is not yet implemented. Select LLM classifier to proceed.
        </p>
      )}

      <Button
        onClick={handleSubmit}
        disabled={labels.length === 0 || isSubmitting || classifierType === 'llamaindex_split'}
      >
        {isSubmitting ? 'Starting…' : submitLabel}
      </Button>
    </div>
  )
}
