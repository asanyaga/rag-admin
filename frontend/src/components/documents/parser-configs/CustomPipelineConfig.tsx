import { Checkbox } from '@/components/ui/checkbox'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
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
import { ChevronDown } from 'lucide-react'
import { useState } from 'react'

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

type TableTool = 'none' | 'fitz_tables' | 'camelot'

const TABLE_TOOL_IDS: TableTool[] = ['fitz_tables', 'camelot']

const CAMELOT_DEFAULTS = { flavor: 'lattice', edge_tol: 50, row_tol: 2 }

const FITZ_TABLES_DEFAULTS = {
  vertical_strategy: 'lines_strict',
  horizontal_strategy: 'lines_strict',
  snap_tolerance: 3.0,
  snap_x_tolerance: null,
  snap_y_tolerance: null,
  join_tolerance: 3.0,
  join_x_tolerance: null,
  join_y_tolerance: null,
  edge_min_length: 3.0,
  min_words_vertical: 3,
  min_words_horizontal: 1,
  intersection_tolerance: 3.0,
  intersection_x_tolerance: null,
  intersection_y_tolerance: null,
  text_tolerance: 3.0,
  text_x_tolerance: null,
  text_y_tolerance: null,
}

function NumField({
  id,
  label,
  value,
  onChange,
  disabled,
  description,
}: {
  id: string
  label: string
  value: number
  onChange: (v: number) => void
  disabled?: boolean
  description?: string
}) {
  return (
    <div className="space-y-1">
      <Label htmlFor={id}>{label}</Label>
      {description && <p className="text-xs text-muted-foreground">{description}</p>}
      <Input
        id={id}
        type="number"
        step="0.5"
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        disabled={disabled}
      />
    </div>
  )
}

function NullableNumField({
  id,
  label,
  value,
  baseValue,
  onChange,
  disabled,
  description,
}: {
  id: string
  label: string
  value: number | null
  baseValue: number
  onChange: (v: number | null) => void
  disabled?: boolean
  description?: string
}) {
  const isOverridden = value !== null
  return (
    <div className="space-y-1">
      <div className="flex items-center gap-2">
        <Checkbox
          id={`${id}-enabled`}
          checked={isOverridden}
          onCheckedChange={(c) => onChange(c ? baseValue : null)}
          disabled={disabled}
        />
        <Label htmlFor={`${id}-enabled`}>{label}</Label>
      </div>
      {description && <p className="text-xs text-muted-foreground pl-6">{description}</p>}
      {isOverridden && (
        <Input
          id={id}
          type="number"
          step="0.5"
          value={value ?? baseValue}
          onChange={(e) => onChange(Number(e.target.value))}
          disabled={disabled}
          className="ml-6 w-28"
        />
      )}
    </div>
  )
}

function FitzTablesConfigPanel({
  config,
  onChange,
  disabled,
}: {
  config: Record<string, unknown>
  onChange: (patch: Record<string, unknown>) => void
  disabled?: boolean
}) {
  const [advOpen, setAdvOpen] = useState(false)
  const c = { ...FITZ_TABLES_DEFAULTS, ...config }

  const strategies = ['lines_strict', 'lines', 'text', 'explicit']

  return (
    <div className="space-y-4 pl-6">
      {/* Core strategy params */}
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1">
          <Label htmlFor="fitz-tables-v-strategy">Vertical strategy</Label>
          <p className="text-xs text-muted-foreground">
            How vertical column boundaries are detected
          </p>
          <Select
            value={c.vertical_strategy as string}
            onValueChange={(v) => onChange({ vertical_strategy: v })}
            disabled={disabled}
          >
            <SelectTrigger id="fitz-tables-v-strategy">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {strategies.map((s) => (
                <SelectItem key={s} value={s}>
                  {s}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1">
          <Label htmlFor="fitz-tables-h-strategy">Horizontal strategy</Label>
          <p className="text-xs text-muted-foreground">
            How horizontal row boundaries are detected
          </p>
          <Select
            value={c.horizontal_strategy as string}
            onValueChange={(v) => onChange({ horizontal_strategy: v })}
            disabled={disabled}
          >
            <SelectTrigger id="fitz-tables-h-strategy">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {strategies.map((s) => (
                <SelectItem key={s} value={s}>
                  {s}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <NumField
          id="fitz-tables-snap-tol"
          label="Snap tolerance"
          description="Max gap to snap nearby lines together"
          value={c.snap_tolerance as number}
          onChange={(v) => onChange({ snap_tolerance: v })}
          disabled={disabled}
        />
        <NumField
          id="fitz-tables-join-tol"
          label="Join tolerance"
          description="Max gap to join collinear line segments"
          value={c.join_tolerance as number}
          onChange={(v) => onChange({ join_tolerance: v })}
          disabled={disabled}
        />
        <NumField
          id="fitz-tables-edge-min"
          label="Edge min length"
          description="Minimum line length to count as a table edge"
          value={c.edge_min_length as number}
          onChange={(v) => onChange({ edge_min_length: v })}
          disabled={disabled}
        />
        <NumField
          id="fitz-tables-inter-tol"
          label="Intersection tolerance"
          description="Max distance for lines to be considered intersecting"
          value={c.intersection_tolerance as number}
          onChange={(v) => onChange({ intersection_tolerance: v })}
          disabled={disabled}
        />
        <NumField
          id="fitz-tables-min-words-v"
          label="Min words vertical"
          description="Min words to form a vertical boundary in text strategy"
          value={c.min_words_vertical as number}
          onChange={(v) => onChange({ min_words_vertical: Math.round(v) })}
          disabled={disabled}
        />
        <NumField
          id="fitz-tables-min-words-h"
          label="Min words horizontal"
          description="Min words to form a horizontal boundary in text strategy"
          value={c.min_words_horizontal as number}
          onChange={(v) => onChange({ min_words_horizontal: Math.round(v) })}
          disabled={disabled}
        />
        <NumField
          id="fitz-tables-text-tol"
          label="Text tolerance"
          description="Snap tolerance used when extracting cell text"
          value={c.text_tolerance as number}
          onChange={(v) => onChange({ text_tolerance: v })}
          disabled={disabled}
        />
      </div>

      {/* Per-axis overrides — collapsible */}
      <Collapsible open={advOpen} onOpenChange={setAdvOpen}>
        <CollapsibleTrigger className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ChevronDown
            className={`h-4 w-4 transition-transform ${advOpen ? 'rotate-180' : ''}`}
          />
          Per-axis overrides (advanced)
        </CollapsibleTrigger>
        <CollapsibleContent className="mt-3 space-y-3">
          <p className="text-xs text-muted-foreground">
            Override tolerances for X or Y axis independently. When enabled, these take
            precedence over the shared tolerance.
          </p>
          <div className="grid grid-cols-2 gap-3">
            <NullableNumField
              id="fitz-tables-snap-x"
              label="snap_x_tolerance"
              description="Horizontal snap override"
              value={c.snap_x_tolerance as number | null}
              baseValue={c.snap_tolerance as number}
              onChange={(v) => onChange({ snap_x_tolerance: v })}
              disabled={disabled}
            />
            <NullableNumField
              id="fitz-tables-snap-y"
              label="snap_y_tolerance"
              description="Vertical snap override"
              value={c.snap_y_tolerance as number | null}
              baseValue={c.snap_tolerance as number}
              onChange={(v) => onChange({ snap_y_tolerance: v })}
              disabled={disabled}
            />
            <NullableNumField
              id="fitz-tables-join-x"
              label="join_x_tolerance"
              description="Horizontal join override"
              value={c.join_x_tolerance as number | null}
              baseValue={c.join_tolerance as number}
              onChange={(v) => onChange({ join_x_tolerance: v })}
              disabled={disabled}
            />
            <NullableNumField
              id="fitz-tables-join-y"
              label="join_y_tolerance"
              description="Vertical join override"
              value={c.join_y_tolerance as number | null}
              baseValue={c.join_tolerance as number}
              onChange={(v) => onChange({ join_y_tolerance: v })}
              disabled={disabled}
            />
            <NullableNumField
              id="fitz-tables-inter-x"
              label="intersection_x_tolerance"
              description="Horizontal intersection override"
              value={c.intersection_x_tolerance as number | null}
              baseValue={c.intersection_tolerance as number}
              onChange={(v) => onChange({ intersection_x_tolerance: v })}
              disabled={disabled}
            />
            <NullableNumField
              id="fitz-tables-inter-y"
              label="intersection_y_tolerance"
              description="Vertical intersection override"
              value={c.intersection_y_tolerance as number | null}
              baseValue={c.intersection_tolerance as number}
              onChange={(v) => onChange({ intersection_y_tolerance: v })}
              disabled={disabled}
            />
            <NullableNumField
              id="fitz-tables-text-x"
              label="text_x_tolerance"
              description="Horizontal text snap override"
              value={c.text_x_tolerance as number | null}
              baseValue={c.text_tolerance as number}
              onChange={(v) => onChange({ text_x_tolerance: v })}
              disabled={disabled}
            />
            <NullableNumField
              id="fitz-tables-text-y"
              label="text_y_tolerance"
              description="Vertical text snap override"
              value={c.text_y_tolerance as number | null}
              baseValue={c.text_tolerance as number}
              onChange={(v) => onChange({ text_y_tolerance: v })}
              disabled={disabled}
            />
          </div>
        </CollapsibleContent>
      </Collapsible>
    </div>
  )
}

export function LocalPipelineConfig({
  config,
  onChange,
  disabled = false,
  profile,
}: LocalPipelineConfigProps) {
  const tools = (config.tools as ToolEntry[] | undefined) ?? []
  const threshold = (config.eviction_overlap_threshold as number | undefined) ?? 0.5

  const fitz = tools.find((t) => t.tool_id === 'fitz')
  const currentTableTool = tools.find((t) =>
    TABLE_TOOL_IDS.includes(t.tool_id as TableTool)
  )
  const selectedTableTool: TableTool = (currentTableTool?.tool_id as TableTool) ?? 'none'

  const setTools = (next: ToolEntry[]) => onChange({ ...config, tools: next })

  const updateTool = (toolId: string, patch: Record<string, unknown>) => {
    setTools(
      tools.map((t) =>
        t.tool_id === toolId ? { ...t, config: { ...t.config, ...patch } } : t
      )
    )
  }

  const handleTableToolChange = (value: TableTool) => {
    const withoutAnyTableTool = tools.filter(
      (t) => !TABLE_TOOL_IDS.includes(t.tool_id as TableTool)
    )
    if (value === 'none') {
      setTools(withoutAnyTableTool)
    } else if (value === 'fitz_tables') {
      setTools([
        ...withoutAnyTableTool,
        { tool_id: 'fitz_tables', config: { ...FITZ_TABLES_DEFAULTS } },
      ])
    } else if (value === 'camelot') {
      setTools([
        ...withoutAnyTableTool,
        { tool_id: 'camelot', config: { ...CAMELOT_DEFAULTS } },
      ])
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

      {/* Table extraction — mutually exclusive tool selector */}
      <div className="space-y-2 rounded-md border p-3">
        <div className="space-y-1">
          <Label htmlFor="table-tool-select">Table extraction</Label>
          <p className="text-xs text-muted-foreground">
            Optional table extraction tool. Only one can be active at a time.
          </p>
          <Select
            value={selectedTableTool}
            onValueChange={(v) => handleTableToolChange(v as TableTool)}
            disabled={disabled}
          >
            <SelectTrigger id="table-tool-select" aria-label="Table extraction">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="none">none</SelectItem>
              <SelectItem value="fitz_tables">
                fitz_tables — built-in PyMuPDF table detection
              </SelectItem>
              <SelectItem value="camelot">camelot — ruled / borderless table parser</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {selectedTableTool === 'fitz_tables' && currentTableTool && (
          <FitzTablesConfigPanel
            config={currentTableTool.config}
            onChange={(patch) => updateTool('fitz_tables', patch)}
            disabled={disabled}
          />
        )}

        {selectedTableTool === 'camelot' && currentTableTool && (
          <div className="space-y-3 pl-6">
            <div className="space-y-1">
              <Label htmlFor="camelot-flavor">Flavor</Label>
              <Select
                value={(currentTableTool.config.flavor as string) ?? 'lattice'}
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
            {/* edge_tol / row_tol only apply to stream flavor */}
            {(currentTableTool.config.flavor as string) === 'stream' && (
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label htmlFor="camelot-edge-tol">edge_tol</Label>
                  <Input
                    id="camelot-edge-tol"
                    type="number"
                    value={(currentTableTool.config.edge_tol as number) ?? 50}
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
                    value={(currentTableTool.config.row_tol as number) ?? 2}
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
