import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type { ParseConfig } from '@/types/parsing'
import { LandingAIConfig } from './parser-configs/LandingAIConfig'
import { LlamaParseConfig } from './parser-configs/LlamaParseConfig'
import { CustomPipelineConfig } from './parser-configs/CustomPipelineConfig'
import { DOCLING_DEFAULT_CONFIG, DoclingConfig } from './parser-configs/DoclingConfig'

interface ParserMeta {
  label: string
  description: string
  defaultConfig: ParseConfig
}

export const PARSER_REGISTRY: Record<string, ParserMeta> = {
  simple: {
    label: 'Simple (local)',
    description: 'Basic text extraction. Works on clean text-based PDFs.',
    defaultConfig: {},
  },
  llamaparse: {
    label: 'LlamaParse',
    description: 'Intelligent parsing. Handles complex layouts, tables, scanned documents.',
    defaultConfig: { tier: 'agentic', expand: ['markdown', 'text', 'items'] },
  },
  landing_ai: {
    label: 'Landing AI',
    description: 'Vision-based parsing. Best for images, shelf photos, and complex visual layouts.',
    defaultConfig: { model: 'dpt-2-latest' },
  },
  docling: {
    label: 'Docling',
    description:
      "Local ML pipeline — layout, reading order, and table structure in one pass. Configured on docling's own terms.",
    defaultConfig: DOCLING_DEFAULT_CONFIG,
  },
  custom_pipeline: {
    label: 'Custom pipeline',
    description: 'Composable tools',
    defaultConfig: {
      tools: {
        fitz: {
          tool: 'fitz',
          config: { min_chars_threshold: 10, include_images: true, span_detail: false },
        },
      },
      capabilities: { layout_analysis: 'fitz' },
      eviction_overlap_threshold: 0.5,
    },
  },
}

interface ParseMethodSelectorProps {
  parserType: string
  config: ParseConfig
  onParserTypeChange: (type: string) => void
  onConfigChange: (config: ParseConfig) => void
  disabled?: boolean
  compact?: boolean
}

export function ParseMethodSelector({
  parserType,
  config,
  onParserTypeChange,
  onConfigChange,
  disabled = false,
  compact = false,
}: ParseMethodSelectorProps) {
  const handleParserChange = (newType: string) => {
    onParserTypeChange(newType)
    onConfigChange(PARSER_REGISTRY[newType]?.defaultConfig ?? {})
  }

  return (
    <div className="space-y-3">
      <div className={compact ? 'flex items-center gap-2' : 'space-y-2'}>
        <Label className={compact ? 'text-xs text-muted-foreground shrink-0' : undefined}>
          Parse method
        </Label>
        <Select value={parserType} onValueChange={handleParserChange} disabled={disabled}>
          <SelectTrigger className={compact ? 'h-8 text-xs' : undefined}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {Object.entries(PARSER_REGISTRY).map(([value, meta]) => (
              <SelectItem key={value} value={value}>
                {meta.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {!compact && (
          <p className="text-xs text-muted-foreground">
            {PARSER_REGISTRY[parserType]?.description}
          </p>
        )}
      </div>

      {parserType === 'llamaparse' && (
        <LlamaParseConfig config={config} onChange={onConfigChange} disabled={disabled} />
      )}
      {parserType === 'landing_ai' && (
        <LandingAIConfig config={config} onChange={onConfigChange} disabled={disabled} />
      )}
      {parserType === 'docling' && (
        <DoclingConfig
          config={config}
          onChange={onConfigChange}
          disabled={disabled}
          compact={compact}
        />
      )}
      {parserType === 'custom_pipeline' && (
        <CustomPipelineConfig config={config} onChange={onConfigChange} disabled={disabled} />
      )}
    </div>
  )
}
