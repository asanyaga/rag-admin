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

interface ParserMeta {
  label: string
  description: string
  defaultConfig: ParseConfig
}

const PARSER_REGISTRY: Record<string, ParserMeta> = {
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
    description: 'Local PDF parsing. Rich layout extraction with tables, headings, and figures.',
    defaultConfig: {},
  },
}

interface ParseMethodSelectorProps {
  parserType: string
  config: ParseConfig
  onParserTypeChange: (type: string) => void
  onConfigChange: (config: ParseConfig) => void
  disabled?: boolean
}

export function ParseMethodSelector({
  parserType,
  config,
  onParserTypeChange,
  onConfigChange,
  disabled = false,
}: ParseMethodSelectorProps) {
  const handleParserChange = (newType: string) => {
    onParserTypeChange(newType)
    onConfigChange(PARSER_REGISTRY[newType]?.defaultConfig ?? {})
  }

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label>Parse Method</Label>
        <Select value={parserType} onValueChange={handleParserChange} disabled={disabled}>
          <SelectTrigger>
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
        <p className="text-xs text-muted-foreground">
          {PARSER_REGISTRY[parserType]?.description}
        </p>
      </div>

      {parserType === 'llamaparse' && (
        <LlamaParseConfig config={config} onChange={onConfigChange} disabled={disabled} />
      )}
      {parserType === 'landing_ai' && (
        <LandingAIConfig config={config} onChange={onConfigChange} disabled={disabled} />
      )}
    </div>
  )
}
