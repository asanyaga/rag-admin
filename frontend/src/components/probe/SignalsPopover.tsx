import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import type { ProbeConfig } from '@/types/probeReport'
import { SlidersHorizontal } from 'lucide-react'

const ALL_SIGNALS = [
  'text_layer', 'font_health', 'copy_restricted',
  'coverage', 'dpi', 'text_overlap', 'table_grid', 'edge_density',
]

export const DEFAULT_PROBE_CONFIG: ProbeConfig = {
  enabled_signals: [...ALL_SIGNALS],
  thresholds: {
    min_text_chars: 10, cid_ratio: 0.3, edge_density_min: 0.15,
    coverage_min: 0.10, table_line_min: 3, overlap_covered: 0.6,
  },
  backend: 'fitz',
}

interface Props {
  config: ProbeConfig
  onChange: (c: ProbeConfig) => void
  onRerun: () => void
}

export function SignalsPopover({ config, onChange, onRerun }: Props) {
  const toggle = (name: string) => {
    const on = config.enabled_signals.includes(name)
    onChange({
      ...config,
      enabled_signals: on
        ? config.enabled_signals.filter((s) => s !== name)
        : [...config.enabled_signals, name],
    })
  }
  const setThreshold = (key: keyof ProbeConfig['thresholds'], value: number) =>
    onChange({ ...config, thresholds: { ...config.thresholds, [key]: value } })

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="outline" size="sm">
          <SlidersHorizontal className="h-4 w-4 mr-1.5" />
          Signals
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-72 space-y-3">
        <div className="space-y-1.5">
          {ALL_SIGNALS.map((name) => (
            <div key={name} className="flex items-center justify-between">
              <Label htmlFor={name} className="text-xs">{name}</Label>
              <Switch
                id={name}
                aria-label={name}
                checked={config.enabled_signals.includes(name)}
                onCheckedChange={() => toggle(name)}
              />
            </div>
          ))}
        </div>
        <div className="space-y-2 border-t pt-2">
          <label className="text-xs flex items-center justify-between">
            edge_density_min
            <Input type="number" step="0.01" className="h-7 w-20"
              value={config.thresholds.edge_density_min}
              onChange={(e) => setThreshold('edge_density_min', parseFloat(e.target.value))} />
          </label>
          <label className="text-xs flex items-center justify-between">
            coverage_min
            <Input type="number" step="0.05" className="h-7 w-20"
              value={config.thresholds.coverage_min}
              onChange={(e) => setThreshold('coverage_min', parseFloat(e.target.value))} />
          </label>
          <label className="text-xs flex items-center justify-between">
            min_text_chars
            <Input type="number" className="h-7 w-20"
              value={config.thresholds.min_text_chars}
              onChange={(e) => setThreshold('min_text_chars', parseInt(e.target.value, 10))} />
          </label>
        </div>
        <Button size="sm" className="w-full" onClick={onRerun}>Re-probe</Button>
      </PopoverContent>
    </Popover>
  )
}
