import { useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'

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

interface DoclingConfigProps {
  config: ParseConfig
  onChange: (config: ParseConfig) => void
  disabled?: boolean
}

/**
 * Empty on purpose. Docling's own defaults are good, and sending nothing means
 * an untouched config behaves exactly like a bare DocumentConverter(). The
 * backend model tracks docling's defaults rather than restating them here.
 */
export const DOCLING_DEFAULT_CONFIG: ParseConfig = {}

/** Engines needing platform support we don't run are excluded server-side too. */
const OCR_ENGINES = [
  { value: 'auto', label: 'auto — docling picks (default)' },
  { value: 'easyocr', label: 'easyocr' },
  { value: 'tesseract', label: 'tesseract (CLI)' },
  { value: 'tesserocr', label: 'tesserocr' },
  { value: 'rapidocr', label: 'rapidocr' },
]

const LAYOUT_MODELS = [
  { value: 'docling_layout_heron', label: 'heron — default' },
  { value: 'docling_layout_heron_101', label: 'heron 101' },
  { value: 'docling_layout_egret_medium', label: 'egret medium' },
  { value: 'docling_layout_egret_large', label: 'egret large — higher accuracy' },
  { value: 'docling_layout_egret_xlarge', label: 'egret xlarge — slowest' },
  { value: 'docling_layout_v2', label: 'v2 — legacy' },
]

const BACKENDS = [
  { value: 'docling_parse_v4', label: 'docling-parse v4 — default' },
  { value: 'docling_parse_v2', label: 'docling-parse v2' },
  { value: 'pypdfium2', label: 'pypdfium2' },
]

/** Keys the backend rejects when pipeline is `vlm`. */
const STANDARD_ONLY = [
  'do_ocr',
  'do_table_structure',
  'do_code_enrichment',
  'do_formula_enrichment',
  'force_backend_text',
  'images_scale',
  'generate_page_images',
  'generate_picture_images',
  'layout_options',
  'ocr_options',
  'table_structure_options',
]

function omit(config: ParseConfig, keys: string[]): ParseConfig {
  const next = { ...config }
  for (const key of keys) delete (next as Record<string, unknown>)[key]
  return next
}

export function DoclingConfig({ config, onChange, disabled = false }: DoclingConfigProps) {
  const [advancedOpen, setAdvancedOpen] = useState(false)

  const pipeline = (config.pipeline as string) ?? 'standard'
  const isVlm = pipeline === 'vlm'
  const doOcr = (config.do_ocr as boolean) ?? true
  const doTables = (config.do_table_structure as boolean) ?? true

  const ocrOptions = (config.ocr_options as Record<string, unknown>) ?? {}
  const tableOptions = (config.table_structure_options as Record<string, unknown>) ?? {}
  const layoutOptions = (config.layout_options as Record<string, unknown>) ?? {}

  const setPipeline = (value: string) => {
    // Standard-only keys are a validation error on the vlm pipeline, so they go
    // rather than lingering invisibly until the request 422s.
    onChange(
      value === 'vlm'
        ? { ...omit(config, STANDARD_ONLY), pipeline: 'vlm' }
        : omit({ ...config, pipeline: 'standard' }, ['vlm_model']),
    )
  }

  const setStage = (stage: 'do_ocr' | 'do_table_structure', enabled: boolean) => {
    // Same reasoning: the backend rejects a stage's options when its stage is
    // off, so disabling a stage clears them.
    const optionsKey = stage === 'do_ocr' ? 'ocr_options' : 'table_structure_options'
    const next = enabled ? { ...config } : omit(config, [optionsKey])
    onChange({ ...next, [stage]: enabled })
  }

  const setNested = (key: string, patch: Record<string, unknown>) =>
    onChange({
      ...config,
      [key]: { ...((config[key] as Record<string, unknown>) ?? {}), ...patch },
    })

  return (
    <div className="space-y-3 rounded-md border p-3">
      <p className="text-xs text-muted-foreground">
        Docling is an end-to-end pipeline — layout, OCR, and tables come out of one pass. Stages
        can be switched off or their models swapped, but not replaced with other tools; for that,
        use the custom pipeline.
      </p>

      <div className="space-y-1">
        <Label htmlFor="docling-pipeline">Pipeline</Label>
        <Select value={pipeline} onValueChange={setPipeline} disabled={disabled}>
          <SelectTrigger id="docling-pipeline" aria-label="Pipeline">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="standard">standard — layout + OCR + tables</SelectItem>
            <SelectItem value="vlm">vlm — one vision model over rendered pages</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {!isVlm && (
        <>
          <div className="flex items-center gap-2">
            <Checkbox
              id="docling-do-ocr"
              checked={doOcr}
              onCheckedChange={(c) => setStage('do_ocr', !!c)}
              disabled={disabled}
            />
            <Label htmlFor="docling-do-ocr">OCR</Label>
          </div>
          <div className="flex items-center gap-2">
            <Checkbox
              id="docling-do-tables"
              checked={doTables}
              onCheckedChange={(c) => setStage('do_table_structure', !!c)}
              disabled={disabled}
            />
            <Label htmlFor="docling-do-tables">Table structure</Label>
          </div>

          <button
            type="button"
            className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
            onClick={() => setAdvancedOpen((open) => !open)}
            aria-expanded={advancedOpen}
          >
            {advancedOpen ? (
              <ChevronDown className="h-3 w-3" />
            ) : (
              <ChevronRight className="h-3 w-3" />
            )}
            Advanced
          </button>

          {advancedOpen && (
            <div className="space-y-3 border-l pl-3">
              <div className="space-y-1">
                <Label htmlFor="docling-backend">PDF backend</Label>
                <Select
                  value={(config.backend as string) ?? 'docling_parse_v4'}
                  onValueChange={(v) => onChange({ ...config, backend: v })}
                  disabled={disabled}
                >
                  <SelectTrigger id="docling-backend" aria-label="PDF backend">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {BACKENDS.map((b) => (
                      <SelectItem key={b.value} value={b.value}>
                        {b.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-1">
                <Label htmlFor="docling-layout-model">Layout model</Label>
                <Select
                  value={(layoutOptions.model as string) ?? 'docling_layout_heron'}
                  onValueChange={(v) => setNested('layout_options', { model: v })}
                  disabled={disabled}
                >
                  <SelectTrigger id="docling-layout-model" aria-label="Layout model">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {LAYOUT_MODELS.map((m) => (
                      <SelectItem key={m.value} value={m.value}>
                        {m.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {doOcr && (
                <>
                  <div className="space-y-1">
                    <Label htmlFor="docling-ocr-engine">OCR engine</Label>
                    <Select
                      value={(ocrOptions.kind as string) ?? 'auto'}
                      onValueChange={(v) => onChange({ ...config, ocr_options: { kind: v } })}
                      disabled={disabled}
                    >
                      <SelectTrigger id="docling-ocr-engine" aria-label="OCR engine">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {OCR_ENGINES.map((e) => (
                          <SelectItem key={e.value} value={e.value}>
                            {e.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="flex items-center gap-2">
                    <Checkbox
                      id="docling-force-ocr"
                      checked={(ocrOptions.force_full_page_ocr as boolean) ?? false}
                      onCheckedChange={(c) =>
                        setNested('ocr_options', {
                          kind: (ocrOptions.kind as string) ?? 'auto',
                          force_full_page_ocr: !!c,
                        })
                      }
                      disabled={disabled}
                    />
                    <Label htmlFor="docling-force-ocr">
                      Force full-page OCR (ignore the embedded text layer)
                    </Label>
                  </div>
                </>
              )}

              {doTables && (
                <>
                  <div className="space-y-1">
                    <Label htmlFor="docling-table-mode">Table mode</Label>
                    <Select
                      value={(tableOptions.mode as string) ?? 'accurate'}
                      onValueChange={(v) => setNested('table_structure_options', { mode: v })}
                      disabled={disabled}
                    >
                      <SelectTrigger id="docling-table-mode" aria-label="Table mode">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="accurate">accurate — default, slower</SelectItem>
                        <SelectItem value="fast">fast</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="flex items-center gap-2">
                    <Checkbox
                      id="docling-cell-matching"
                      checked={(tableOptions.do_cell_matching as boolean) ?? true}
                      onCheckedChange={(c) =>
                        setNested('table_structure_options', { do_cell_matching: !!c })
                      }
                      disabled={disabled}
                    />
                    <Label htmlFor="docling-cell-matching">
                      Match PDF text into cells (rather than OCR-ing them)
                    </Label>
                  </div>
                </>
              )}

              <div className="flex items-center gap-2">
                <Checkbox
                  id="docling-formula"
                  checked={(config.do_formula_enrichment as boolean) ?? false}
                  onCheckedChange={(c) => onChange({ ...config, do_formula_enrichment: !!c })}
                  disabled={disabled}
                />
                <Label htmlFor="docling-formula">Formula enrichment</Label>
              </div>
              <div className="flex items-center gap-2">
                <Checkbox
                  id="docling-code"
                  checked={(config.do_code_enrichment as boolean) ?? false}
                  onCheckedChange={(c) => onChange({ ...config, do_code_enrichment: !!c })}
                  disabled={disabled}
                />
                <Label htmlFor="docling-code">Code enrichment</Label>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
