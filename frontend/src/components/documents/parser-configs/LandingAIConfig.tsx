import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type { ParseConfig } from '@/types/parsing'

interface LandingAIConfigProps {
  config: ParseConfig
  onChange: (config: ParseConfig) => void
  disabled?: boolean
}

const MODELS = [{ value: 'dpt-2-latest', label: 'dpt-2-latest' }]

export function LandingAIConfig({ config, onChange, disabled = false }: LandingAIConfigProps) {
  const model = config.model || 'dpt-2-latest'

  return (
    <div className="space-y-2">
      <Label>Model</Label>
      <Select
        value={model}
        onValueChange={(value) => onChange({ ...config, model: value })}
        disabled={disabled}
      >
        <SelectTrigger>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {MODELS.map((m) => (
            <SelectItem key={m.value} value={m.value}>
              {m.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <p className="text-xs text-muted-foreground">Vision-based document parsing model.</p>
    </div>
  )
}
