import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type { ParseConfig } from '@/types/parsing'

interface LlamaParseConfigProps {
  config: ParseConfig
  onChange: (config: ParseConfig) => void
  disabled?: boolean
}

const TIERS = [
  { value: 'fast', label: 'Fast (1 credit/page)', supportsMarkdown: false },
  { value: 'cost_effective', label: 'Cost Effective (3 credits/page)', supportsMarkdown: true },
  { value: 'agentic', label: 'Agentic (10 credits/page)', supportsMarkdown: true },
  { value: 'agentic_plus', label: 'Agentic Plus (45 credits/page)', supportsMarkdown: true },
]

export function LlamaParseConfig({ config, onChange, disabled = false }: LlamaParseConfigProps) {
  const tier = config.tier || 'agentic'
  const expand = config.expand || ['markdown', 'text', 'items']
  const currentTier = TIERS.find((t) => t.value === tier)
  const supportsMarkdown = currentTier?.supportsMarkdown ?? true

  const handleTierChange = (newTier: string) => {
    const tierInfo = TIERS.find((t) => t.value === newTier)
    let newExpand = [...expand]
    if (!tierInfo?.supportsMarkdown) {
      newExpand = newExpand.filter((e) => e === 'text')
      if (!newExpand.includes('text')) newExpand.push('text')
    }
    onChange({ ...config, tier: newTier, expand: newExpand })
  }

  const handleExpandToggle = (option: string, checked: boolean) => {
    let newExpand = [...expand]
    if (checked) {
      newExpand.push(option)
    } else {
      newExpand = newExpand.filter((e) => e !== option)
    }
    if (!newExpand.includes('text')) newExpand.push('text') // text is always included
    onChange({ ...config, expand: newExpand })
  }

  return (
    <>
      <div className="space-y-2">
        <Label>Tier</Label>
        <Select value={tier} onValueChange={handleTierChange} disabled={disabled}>
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {TIERS.map((t) => (
              <SelectItem key={t.value} value={t.value}>
                {t.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <Label>Output Options</Label>
        <div className="space-y-2">
          <div className="flex items-center space-x-2">
            <Checkbox id="expand-text" checked disabled />
            <Label htmlFor="expand-text" className="text-sm font-normal">
              Text (always included)
            </Label>
          </div>
          <div className="flex items-center space-x-2">
            <Checkbox
              id="expand-markdown"
              checked={expand.includes('markdown')}
              onCheckedChange={(checked) => handleExpandToggle('markdown', !!checked)}
              disabled={disabled || !supportsMarkdown}
            />
            <Label htmlFor="expand-markdown" className="text-sm font-normal">
              Markdown{!supportsMarkdown && ' (not available on fast tier)'}
            </Label>
          </div>
          <div className="flex items-center space-x-2">
            <Checkbox
              id="expand-items"
              checked={expand.includes('items')}
              onCheckedChange={(checked) => handleExpandToggle('items', !!checked)}
              disabled={disabled || !supportsMarkdown}
            />
            <Label htmlFor="expand-items" className="text-sm font-normal">
              Structured Items{!supportsMarkdown && ' (not available on fast tier)'}
            </Label>
          </div>
        </div>
      </div>
    </>
  )
}
