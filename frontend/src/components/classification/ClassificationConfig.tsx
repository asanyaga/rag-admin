import { useState } from 'react'
import { X } from 'lucide-react'
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

const CLASSIFIER_TYPES = [
  { value: 'llm', label: 'LLM classifier' },
  { value: 'llamaindex_split', label: 'LlamaIndex split (not yet implemented)' },
]

export interface ClassificationConfigValue {
  labels: string[]
  classifierType: string
}

interface Props {
  defaultValues?: Partial<ClassificationConfigValue>
  onChange: (value: ClassificationConfigValue) => void
}

export function ClassificationConfig({ defaultValues, onChange }: Props) {
  const dv = defaultValues ?? {}
  const [labels, setLabels] = useState<string[]>(dv.labels ?? [])
  const [labelInput, setLabelInput] = useState('')
  const [classifierType, setClassifierType] = useState(dv.classifierType ?? 'llm')

  function emit(nextLabels: string[], nextType: string) {
    onChange({ labels: nextLabels, classifierType: nextType })
  }

  const addLabel = () => {
    const trimmed = labelInput.trim()
    if (!trimmed || labels.includes(trimmed)) return
    const next = [...labels, trimmed]
    setLabels(next)
    setLabelInput('')
    emit(next, classifierType)
  }

  const removeLabel = (l: string) => {
    const next = labels.filter((x) => x !== l)
    setLabels(next)
    emit(next, classifierType)
  }

  const handleClassifierTypeChange = (v: string) => {
    setClassifierType(v)
    emit(labels, v)
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
    </div>
  )
}
