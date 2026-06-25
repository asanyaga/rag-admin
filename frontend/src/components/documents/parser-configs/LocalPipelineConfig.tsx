import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Slider } from '@/components/ui/slider'
import type { ParseConfig } from '@/types/parsing'
import type { DocumentProfile } from '@/types/probe'

interface ToolEntry {
  tool_id: string
  config: Record<string, unknown>
}

interface LocalPipelineConfigProps {
  config: ParseConfig
  onChange: (config: ParseConfig) => void
  disabled?: boolean
  profile?: DocumentProfile | null
}

const CAMELOT_DEFAULTS = { flavor: 'lattice', edge_tol: 50, row_tol: 2 }

export function LocalPipelineConfig({
  config,
  onChange,
  disabled = false,
  profile,
}: LocalPipelineConfigProps) {
  const tools = (config.tools as ToolEntry[] | undefined) ?? []
  const threshold = (config.eviction_overlap_threshold as number | undefined) ?? 0.5

  const fitz = tools.find((t) => t.tool_id === 'fitz')
  const camelot = tools.find((t) => t.tool_id === 'camelot')

  const setTools = (next: ToolEntry[]) => onChange({ ...config, tools: next })

  const updateTool = (toolId: string, patch: Record<string, unknown>) => {
    setTools(
      tools.map((t) =>
        t.tool_id === toolId ? { ...t, config: { ...t.config, ...patch } } : t
      )
    )
  }

  const toggleCamelot = (on: boolean) => {
    if (on) {
      setTools([...tools, { tool_id: 'camelot', config: { ...CAMELOT_DEFAULTS } }])
    } else {
      setTools(tools.filter((t) => t.tool_id !== 'camelot'))
    }
  }

  return (
    <div className="space-y-4">
      {profile && (
        <p className="text-sm text-muted-foreground">
          Suggested tools:{' '}
          <span className="font-medium">{profile.recommended_tools.join(', ')}</span>
        </p>
      )}

      {/* Fitz — always on */}
      <div className="space-y-2 rounded-md border p-3">
        <div className="flex items-center justify-between">
          <Label>fitz (text + images)</Label>
          <span className="text-xs text-muted-foreground">always on</span>
        </div>
        <div className="flex items-center gap-2">
          <Checkbox
            id="fitz-include-images"
            checked={(fitz?.config.include_images as boolean) ?? true}
            onCheckedChange={(c) => updateTool('fitz', { include_images: !!c })}
            disabled={disabled}
          />
          <Label htmlFor="fitz-include-images">Include images (FIGURE blocks)</Label>
        </div>
        <div className="flex items-center gap-2">
          <Checkbox
            id="fitz-span-detail"
            checked={(fitz?.config.span_detail as boolean) ?? false}
            onCheckedChange={(c) => updateTool('fitz', { span_detail: !!c })}
            disabled={disabled}
          />
          <Label htmlFor="fitz-span-detail">Record span detail</Label>
        </div>
      </div>

      {/* Camelot — optional */}
      <div className="space-y-2 rounded-md border p-3">
        <div className="flex items-center gap-2">
          <Checkbox
            id="enable-camelot"
            checked={!!camelot}
            onCheckedChange={(c) => toggleCamelot(!!c)}
            disabled={disabled}
          />
          <Label htmlFor="enable-camelot">camelot (tables)</Label>
        </div>

        {camelot && (
          <div className="space-y-3 pl-6">
            <div className="space-y-1">
              <Label htmlFor="camelot-flavor">Flavor</Label>
              <Select
                value={(camelot.config.flavor as string) ?? 'lattice'}
                onValueChange={(v) => updateTool('camelot', { flavor: v })}
                disabled={disabled}
              >
                <SelectTrigger id="camelot-flavor">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="lattice">lattice (ruled tables)</SelectItem>
                  <SelectItem value="stream">stream (borderless tables)</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {/* edge_tol / row_tol only apply to stream flavor — camelot
                rejects them for lattice. */}
            {(camelot.config.flavor as string) === 'stream' && (
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label htmlFor="camelot-edge-tol">edge_tol</Label>
                  <Input
                    id="camelot-edge-tol"
                    type="number"
                    value={(camelot.config.edge_tol as number) ?? 50}
                    onChange={(e) =>
                      updateTool('camelot', { edge_tol: Number(e.target.value) })
                    }
                    disabled={disabled}
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="camelot-row-tol">row_tol</Label>
                  <Input
                    id="camelot-row-tol"
                    type="number"
                    value={(camelot.config.row_tol as number) ?? 2}
                    onChange={(e) =>
                      updateTool('camelot', { row_tol: Number(e.target.value) })
                    }
                    disabled={disabled}
                  />
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Eviction threshold */}
      <div className="space-y-2">
        <Label htmlFor="eviction-threshold">
          Eviction overlap threshold: {threshold.toFixed(2)}
        </Label>
        <Slider
          id="eviction-threshold"
          min={0}
          max={1}
          step={0.05}
          value={[threshold]}
          onValueChange={([v]) => onChange({ ...config, eviction_overlap_threshold: v })}
          disabled={disabled}
        />
      </div>
    </div>
  )
}
