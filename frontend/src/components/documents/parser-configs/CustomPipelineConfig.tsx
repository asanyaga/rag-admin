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
import { ChevronDown } from 'lucide-react'
import { useEffect, useState } from 'react'

interface ToolInstance {
  tool: string
  config: Record<string, unknown>
}

/** Capability slots: each capability is filled by at most one named tool instance. */
interface PipelineConfig {
  tools: Record<string, ToolInstance>
  capabilities: Record<string, string>
  precedence?: Record<string, string>
  eviction_overlap_threshold?: number
  ocr_eviction_threshold?: number
  page_flags?: Record<string, number>
}

interface CustomPipelineConfigProps {
  config: ParseConfig
  onChange: (config: ParseConfig) => void
  disabled?: boolean
}

type TableTool = 'none' | 'fitz_tables' | 'camelot'

const CAMELOT_DEFAULTS = { flavor: 'lattice', edge_tol: 50, row_tol: 2 }

const TESSERACT_DEFAULTS = {
  pages: 'auto', lang: 'eng', psm: 3, dpi: 300, min_confidence: 0,
}

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

const CAPABILITY_BY_TOOL: Record<string, string> = {
  fitz: 'text_extraction',
  pdfplumber: 'text_extraction',
  fitz_tables: 'table_detection',
  camelot: 'table_detection',
}

/** Coerce any accepted config shape into the capability-slot shape, and
 * guarantee the required `text_extraction` slot.
 *
 * Handles the pre-refactor array shape (`tools: [{tool_id, config}]`, no
 * `capabilities`) so re-parsing an old run — or any stale seed — cannot emit a
 * config the backend will reject with "text_extraction is required".
 * Idempotent: normalizing an already-normal config returns an equal object.
 */
export function normalizeCustomPipelineConfig(raw: unknown): PipelineConfig {
  const src = (raw ?? {}) as Record<string, unknown>
  const tools: Record<string, ToolInstance> = {}
  const capabilities: Record<string, string> = {
    ...((src.capabilities as Record<string, string>) ?? {}),
  }

  const rawTools = src.tools
  if (Array.isArray(rawTools)) {
    // Old shape: [{ tool_id, config }] keyed by tool id, inferring slots.
    for (const entry of rawTools as Array<Record<string, unknown>>) {
      const toolId = (entry.tool ?? entry.tool_id) as string | undefined
      if (!toolId) continue
      tools[toolId] = { tool: toolId, config: (entry.config as Record<string, unknown>) ?? {} }
      const cap = CAPABILITY_BY_TOOL[toolId]
      if (cap && !capabilities[cap]) capabilities[cap] = toolId
    }
  } else if (rawTools && typeof rawTools === 'object') {
    for (const [key, entry] of Object.entries(rawTools as Record<string, Record<string, unknown>>)) {
      const toolId = (entry.tool ?? entry.tool_id) as string | undefined
      if (!toolId) continue
      tools[key] = { tool: toolId, config: (entry.config as Record<string, unknown>) ?? {} }
    }
  }

  // Guarantee the required text_extraction slot.
  if (!capabilities.text_extraction) {
    if (!tools.fitz) tools.fitz = { tool: 'fitz', config: {} }
    capabilities.text_extraction = 'fitz'
  }

  const out: PipelineConfig = { tools, capabilities }
  if (typeof src.eviction_overlap_threshold === 'number') {
    out.eviction_overlap_threshold = src.eviction_overlap_threshold
  }
  if (typeof src.ocr_eviction_threshold === 'number') {
    out.ocr_eviction_threshold = src.ocr_eviction_threshold
  }
  return out
}

/** Assign (or clear) the tool filling a capability slot.
 *
 * Instance keys are the tool id — a 1:1 simplification of the named-instance
 * model. A tool referenced from two slots therefore resolves to one instance.
 */
function setSlot(
  cfg: PipelineConfig,
  capability: string,
  toolId: string | null,
  defaults: Record<string, unknown> = {},
): PipelineConfig {
  const capabilities = { ...cfg.capabilities }
  const tools = { ...cfg.tools }
  const previous = capabilities[capability]
  if (previous) {
    delete capabilities[capability]
    // Drop the instance only if no other slot still references it.
    if (!Object.values(capabilities).includes(previous)) delete tools[previous]
  }
  if (toolId) {
    capabilities[capability] = toolId
    tools[toolId] = tools[toolId] ?? { tool: toolId, config: defaults }
  }
  return { ...cfg, tools, capabilities }
}

function setToolConfig(
  cfg: PipelineConfig,
  instanceKey: string,
  patch: Record<string, unknown>,
): PipelineConfig {
  const existing = cfg.tools[instanceKey]
  if (!existing) return cfg
  return {
    ...cfg,
    tools: {
      ...cfg.tools,
      [instanceKey]: { ...existing, config: { ...existing.config, ...patch } },
    },
  }
}

export function CustomPipelineConfig({
  config,
  onChange,
  disabled = false,
}: CustomPipelineConfigProps) {
  const cfg = normalizeCustomPipelineConfig(config)

  // If the incoming config was a stale/legacy shape, push the normalized shape
  // up so the parent (and any parse it triggers) uses the corrected config even
  // if the user never edits anything.
  const normalizedKey = JSON.stringify(cfg)
  useEffect(() => {
    if (JSON.stringify(config) !== normalizedKey) {
      onChange(cfg as unknown as ParseConfig)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [normalizedKey])

  const tools = cfg.tools
  const capabilities = cfg.capabilities
  const threshold = cfg.eviction_overlap_threshold ?? 0.5

  const textKey = capabilities.text_extraction ?? 'fitz'
  const fitz = tools[textKey]

  const tableKey = capabilities.table_detection
  const currentTableTool = tableKey ? tools[tableKey] : undefined
  const selectedTableTool: TableTool = (currentTableTool?.tool as TableTool) ?? 'none'

  const updateTool = (instanceKey: string, patch: Record<string, unknown>) => {
    onChange(setToolConfig(cfg, instanceKey, patch) as unknown as ParseConfig)
  }

  const handleTableToolChange = (value: TableTool) => {
    const defaults =
      value === 'camelot' ? { ...CAMELOT_DEFAULTS } : { ...FITZ_TABLES_DEFAULTS }
    const next = setSlot(
      cfg,
      'table_detection',
      value === 'none' ? null : value,
      defaults,
    )
    onChange(next as unknown as ParseConfig)
  }

  const ocrKey = capabilities.text_ocr
  const ocrTool = ocrKey ? tools[ocrKey] : undefined
  const ocrOn = !!ocrTool
  const precedencePrefer = cfg.precedence?.text_ocr === 'prefer'

  const handleOcrToolChange = (value: 'none' | 'tesseract') => {
    onChange(setSlot(cfg, 'text_ocr', value === 'none' ? null : value,
      { ...TESSERACT_DEFAULTS }) as unknown as ParseConfig)
  }

  const setPrecedence = (prefer: boolean) => {
    onChange({
      ...cfg,
      precedence: { ...cfg.precedence, text_ocr: prefer ? 'prefer' : 'fallback' },
    } as unknown as ParseConfig)
  }

  return (
    <div className="space-y-4">
      {/* Text extraction — a capability slot (required) */}
      <div className="space-y-2 rounded-md border p-3">
        <div className="space-y-1">
          <Label htmlFor="text-tool-select">Text extraction</Label>
          <p className="text-xs text-muted-foreground">
            The base text extractor. Required — every pipeline fills this slot.
          </p>
          <Select value={textKey} onValueChange={() => {}} disabled={disabled}>
            <SelectTrigger id="text-tool-select" aria-label="Text extraction">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="fitz">fitz (text + images)</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="flex items-center gap-2">
          <Checkbox
            id="fitz-include-images"
            checked={(fitz?.config.include_images as boolean) ?? true}
            onCheckedChange={(c) => updateTool(textKey, { include_images: !!c })}
            disabled={disabled}
          />
          <Label htmlFor="fitz-include-images">Include images (FIGURE blocks)</Label>
        </div>
        <div className="flex items-center gap-2">
          <Checkbox
            id="fitz-span-detail"
            checked={(fitz?.config.span_detail as boolean) ?? false}
            onCheckedChange={(c) => updateTool(textKey, { span_detail: !!c })}
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
            onChange={(patch) => updateTool(tableKey as string, patch)}
            disabled={disabled}
          />
        )}

        {selectedTableTool === 'camelot' && currentTableTool && (
          <div className="space-y-3 pl-6">
            <div className="space-y-1">
              <Label htmlFor="camelot-flavor">Flavor</Label>
              <Select
                value={(currentTableTool.config.flavor as string) ?? 'lattice'}
                onValueChange={(v) => updateTool(tableKey as string, { flavor: v })}
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
                      updateTool(tableKey as string, { edge_tol: Number(e.target.value) })
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
                      updateTool(tableKey as string, { row_tol: Number(e.target.value) })
                    }
                    disabled={disabled}
                  />
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Text OCR — a capability slot */}
      <div className="space-y-2 rounded-md border p-3">
        <div className="space-y-1">
          <Label htmlFor="ocr-tool-select">Text OCR</Label>
          <p className="text-xs text-muted-foreground">
            Optional. Recovers text from scanned pages and text-in-images.
          </p>
          <Select
            value={ocrOn ? 'tesseract' : 'none'}
            onValueChange={(v) => handleOcrToolChange(v as 'none' | 'tesseract')}
            disabled={disabled}
          >
            <SelectTrigger id="ocr-tool-select" aria-label="Text OCR">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="none">none</SelectItem>
              <SelectItem value="tesseract">tesseract — local OCR</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {ocrOn && ocrKey && ocrTool && (
          <div className="space-y-3 pl-6">
            <div className="space-y-1">
              <Label htmlFor="ocr-pages">Pages</Label>
              <Select
                value={String(ocrTool.config.pages ?? 'auto')}
                onValueChange={(v) => updateTool(ocrKey, { pages: v })}
                disabled={disabled}
              >
                <SelectTrigger id="ocr-pages">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="auto">auto (scanned / CID / text-in-image)</SelectItem>
                  <SelectItem value="all">all pages</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <NumField
              id="ocr-dpi"
              label="dpi"
              value={(ocrTool.config.dpi as number) ?? 300}
              onChange={(v) => updateTool(ocrKey, { dpi: Math.round(v) })}
              disabled={disabled}
            />
            <NumField
              id="ocr-min-conf"
              label="min_confidence"
              description="0..1; 0 keeps every result"
              value={(ocrTool.config.min_confidence as number) ?? 0}
              onChange={(v) => updateTool(ocrKey, { min_confidence: v })}
              disabled={disabled}
            />
            <div className="space-y-1">
              <Label htmlFor="ocr-precedence">When OCR overlaps native text</Label>
              <Select
                value={precedencePrefer ? 'prefer' : 'fallback'}
                onValueChange={(v) => setPrecedence(v === 'prefer')}
                disabled={disabled}
              >
                <SelectTrigger id="ocr-precedence" aria-label="Precedence">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="fallback">Native text wins (default)</SelectItem>
                  <SelectItem value="prefer">
                    OCR wins — for scans with a poor text layer
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>
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
