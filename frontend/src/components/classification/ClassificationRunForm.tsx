// frontend/src/components/classification/ClassificationRunForm.tsx
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

const PROVIDER_OPTIONS = [
  { value: 'ollama_local', label: 'Ollama — local' },
  { value: 'ollama_cloud', label: 'Ollama — cloud' },
  { value: 'groq', label: 'Groq (hosted)' },
  { value: 'anthropic', label: 'Anthropic' },
]

const DEFAULT_MODELS: Record<string, string> = {
  ollama_local: 'qwen2.5:7b',
  ollama_cloud: 'qwen3:32b',
  groq: 'llama-3.3-70b-versatile',
  anthropic: 'claude-haiku-4-5-20251001',
}

export interface ClassificationRunFormValues {
  labels: string[]
  llmProvider: string
  llmModel: string
  batchSize: number
  batchOverlap: number
}

interface Props {
  defaultValues?: Partial<ClassificationRunFormValues>
  onSubmit: (values: ClassificationRunFormValues) => void
  isSubmitting?: boolean
  submitLabel?: string
}

export function ClassificationRunForm({
  defaultValues,
  onSubmit,
  isSubmitting,
  submitLabel = 'Start classification',
}: Props) {
  const [labels, setLabels] = useState<string[]>(defaultValues?.labels ?? [])
  const [labelInput, setLabelInput] = useState('')
  const [provider, setProvider] = useState(defaultValues?.llmProvider ?? 'ollama_local')
  const [model, setModel] = useState(defaultValues?.llmModel ?? DEFAULT_MODELS['ollama_local'])
  const [batchSize, setBatchSize] = useState(defaultValues?.batchSize ?? 10)
  const [batchOverlap, setBatchOverlap] = useState(defaultValues?.batchOverlap ?? 3)

  const addLabel = () => {
    const trimmed = labelInput.trim()
    if (trimmed && !labels.includes(trimmed)) {
      setLabels((prev) => [...prev, trimmed])
    }
    setLabelInput('')
  }

  const removeLabel = (l: string) => setLabels((prev) => prev.filter((x) => x !== l))

  const handleProviderChange = (p: string) => {
    setProvider(p)
    setModel(DEFAULT_MODELS[p] ?? '')
  }

  const handleSubmit = () => {
    if (labels.length === 0) return
    onSubmit({ labels, llmProvider: provider, llmModel: model, batchSize, batchOverlap })
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

      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label>LLM provider</Label>
          <Select value={provider} onValueChange={handleProviderChange}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {PROVIDER_OPTIONS.map((o) => (
                <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-2">
          <Label>Model</Label>
          <Input value={model} onChange={(e) => setModel(e.target.value)} />
        </div>
      </div>

      <Collapsible>
        <CollapsibleTrigger className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground">
          <ChevronDown className="h-4 w-4" />
          Advanced
        </CollapsibleTrigger>
        <CollapsibleContent className="mt-3 grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label>Batch size (pages)</Label>
            <Input
              type="number"
              min={1}
              value={batchSize}
              onChange={(e) => setBatchSize(Number(e.target.value))}
            />
          </div>
          <div className="space-y-2">
            <Label>Batch overlap (pages)</Label>
            <Input
              type="number"
              min={0}
              value={batchOverlap}
              onChange={(e) => setBatchOverlap(Number(e.target.value))}
            />
          </div>
        </CollapsibleContent>
      </Collapsible>

      <Button onClick={handleSubmit} disabled={labels.length === 0 || isSubmitting}>
        {isSubmitting ? 'Starting…' : submitLabel}
      </Button>
    </div>
  )
}
