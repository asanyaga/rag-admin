import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Input } from '@/components/ui/input'
import { Slider } from '@/components/ui/slider'
import { Switch } from '@/components/ui/switch'
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
import { ChevronDown } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { PromptConfig, PromptConfigCapabilities } from '@/types/prompt-config'
import { PROVIDERS, PROVIDER_MODEL_OPTIONS, THINKING_PROVIDERS } from '@/types/prompt-config'

interface PromptConfigEditorProps {
  value: PromptConfig
  onChange: (config: PromptConfig) => void
  onProviderChange?: (provider: string) => void
  capabilities?: PromptConfigCapabilities
  className?: string
}

export function PromptConfigEditor({
  value,
  onChange,
  onProviderChange,
  capabilities = {},
  className,
}: PromptConfigEditorProps) {
  const modelOptions = value.provider ? (PROVIDER_MODEL_OPTIONS[value.provider] ?? []) : []
  const supportsThinking = capabilities.thinking && THINKING_PROVIDERS.has(value.provider ?? '')

  const update = (patch: Partial<PromptConfig>) => onChange({ ...value, ...patch })

  return (
    <div className={cn('space-y-4', className)}>
      {/* System Prompt */}
      <div className="space-y-1.5">
        <Label>System Prompt</Label>
        <Textarea
          className="font-mono text-sm min-h-[120px]"
          placeholder="Leave empty to use the default system prompt…"
          value={value.systemPrompt ?? ''}
          onChange={(e) => update({ systemPrompt: e.target.value || undefined })}
        />
      </div>

      {/* Provider + Model */}
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <Label>Provider</Label>
          <Select
            value={value.provider ?? ''}
            onValueChange={(p) => {
              onProviderChange?.(p)
              const models = PROVIDER_MODEL_OPTIONS[p]
              update({ provider: p, model: models?.[0]?.value ?? value.model, thinking: undefined })
            }}
          >
            <SelectTrigger>
              <SelectValue placeholder="Select provider" />
            </SelectTrigger>
            <SelectContent>
              {PROVIDERS.map((p) => (
                <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label>Model</Label>
          {(value.provider === 'ollama_cloud' || value.provider === 'ollama_local') ? (
            <Input
              placeholder="e.g. llama3.2"
              value={value.model ?? ''}
              onChange={(e) => update({ model: e.target.value || undefined })}
            />
          ) : (
            <Select
              value={value.model ?? ''}
              onValueChange={(m) => update({ model: m })}
              disabled={!modelOptions.length}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select model" />
              </SelectTrigger>
              <SelectContent>
                {modelOptions.map((m) => (
                  <SelectItem key={m.value} value={m.value}>{m.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        </div>
      </div>

      {/* Temperature */}
      <div className="space-y-1.5">
        <div className="flex justify-between">
          <Label>Temperature</Label>
          <span className="text-sm text-muted-foreground">{value.temperature ?? 0}</span>
        </div>
        <Slider
          min={0}
          max={2}
          step={0.05}
          value={[value.temperature ?? 0]}
          onValueChange={([v]) => update({ temperature: v })}
        />
      </div>

      {/* Max Tokens */}
      <div className="space-y-1.5">
        <Label>Max Tokens</Label>
        <Input
          type="number"
          min={64}
          max={32000}
          value={value.maxTokens ?? ''}
          onChange={(e) => update({ maxTokens: e.target.value ? Number(e.target.value) : undefined })}
          placeholder="1024"
        />
      </div>

      {/* Thinking */}
      {supportsThinking && (
        <div className="space-y-3 border rounded-md p-3">
          <div className="flex items-center justify-between">
            <Label>Thinking / Reasoning</Label>
            <Switch
              checked={value.thinking?.enabled ?? false}
              onCheckedChange={(checked) =>
                update({ thinking: checked ? { enabled: true } : undefined })
              }
            />
          </div>
          {value.thinking?.enabled && (
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label className="text-xs">Effort</Label>
                <Select
                  value={value.thinking.effort ?? ''}
                  onValueChange={(v) =>
                    update({ thinking: { ...value.thinking!, effort: v as 'low' | 'medium' | 'high' } })
                  }
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Default" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="low">Low</SelectItem>
                    <SelectItem value="medium">Medium</SelectItem>
                    <SelectItem value="high">High</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs">Budget Tokens</Label>
                <Input
                  type="number"
                  min={1024}
                  placeholder="e.g. 4000"
                  value={value.thinking.budgetTokens ?? ''}
                  onChange={(e) =>
                    update({
                      thinking: {
                        ...value.thinking!,
                        budgetTokens: e.target.value ? Number(e.target.value) : undefined,
                      },
                    })
                  }
                />
              </div>
            </div>
          )}
        </div>
      )}

      {/* Advanced */}
      <Collapsible>
        <CollapsibleTrigger className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ChevronDown className="h-3 w-3" />
          Advanced
        </CollapsibleTrigger>
        <CollapsibleContent className="pt-3 space-y-3">
          <div className="space-y-1.5">
            <Label>Top P</Label>
            <Input
              type="number"
              min={0}
              max={1}
              step={0.01}
              placeholder="1.0"
              value={value.topP ?? ''}
              onChange={(e) => update({ topP: e.target.value ? Number(e.target.value) : undefined })}
            />
          </div>
          {capabilities.structuredOutput && (
            <div className="space-y-1.5">
              <Label>Structured Output Schema (JSON)</Label>
              <Textarea
                className="font-mono text-sm min-h-[80px]"
                placeholder='{"type": "object", "properties": {...}}'
                value={value.structuredOutput ? JSON.stringify(value.structuredOutput, null, 2) : ''}
                onChange={(e) => {
                  try {
                    const parsed = e.target.value ? JSON.parse(e.target.value) : undefined
                    update({ structuredOutput: parsed })
                  } catch {
                    // Invalid JSON — don't update until valid
                  }
                }}
              />
            </div>
          )}
        </CollapsibleContent>
      </Collapsible>
    </div>
  )
}
