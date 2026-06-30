import { Link } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import type { ParseConfigOption } from '@/lib/parsed-documents'

interface SelectedFamily {
  parser: string
  parseConfigHash: string
}

interface ParseConfigFamilySelectorProps {
  options: ParseConfigOption[]
  selected: SelectedFamily | null
  onChange: (selected: SelectedFamily) => void
}

const PARSER_NAMES: Record<string, string> = {
  llamaparse: 'LlamaParse',
  landing_ai: 'Landing AI',
  docling: 'Docling',
}

function parserDisplayName(parser: string): string {
  return PARSER_NAMES[parser] ?? parser
}

function summarizeConfig(config: Record<string, unknown>): string {
  const parts: string[] = []
  if (config.result_type) parts.push(`type: ${config.result_type}`)
  if (config.num_workers) parts.push(`workers: ${config.num_workers}`)
  if (parts.length === 0) return 'Default config'
  return parts.join(' · ')
}

export function ParseConfigFamilySelector({
  options,
  selected,
  onChange,
}: ParseConfigFamilySelectorProps) {
  if (options.length === 0) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        <p className="mb-2">No parse runs found for this project.</p>
        <p>
          <Link to="/parse" className="underline text-primary">
            Parse some documents first.
          </Link>
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {options.map((option) => {
        const isSelected =
          selected?.parser === option.parser &&
          selected?.parseConfigHash === option.parseConfigHash

        return (
          <button
            key={`${option.parser}|${option.parseConfigHash}`}
            type="button"
            aria-pressed={isSelected}
            onClick={() =>
              onChange({
                parser: option.parser,
                parseConfigHash: option.parseConfigHash,
              })
            }
            className={`w-full text-left rounded-lg border p-4 transition-colors
              ${
                isSelected
                  ? 'border-primary ring-2 ring-primary/20 bg-primary/5'
                  : 'border-border hover:border-primary/40 hover:bg-muted/30'
              }`}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-semibold">
                    {parserDisplayName(option.parser)}
                  </span>
                  {option.hasFullMarkdown && (
                    <Badge variant="secondary" className="text-xs">
                      markdown
                    </Badge>
                  )}
                </div>
                <p className="text-sm text-muted-foreground truncate">
                  {summarizeConfig(option.config)}
                </p>
              </div>
              <span className="text-sm text-muted-foreground whitespace-nowrap">
                {option.parsedDocumentCount}{' '}
                {option.parsedDocumentCount === 1
                  ? 'parsed document'
                  : 'parsed documents'}
              </span>
            </div>
          </button>
        )
      })}
    </div>
  )
}
