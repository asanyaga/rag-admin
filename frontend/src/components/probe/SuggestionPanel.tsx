import type { ParserSuggestion } from '@/types/probeReport'

export function SuggestionPanel({ suggestion }: { suggestion: ParserSuggestion }) {
  return (
    <div className="rounded-md border bg-indigo-50/60 dark:bg-indigo-950/20 p-3 mb-4">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">Suggested parse configuration</span>
        <span className="text-[10px] uppercase text-muted-foreground">Suggested — not authoritative</span>
      </div>
      <div className="flex flex-wrap gap-1 my-2">
        {suggestion.tools.map((t) => (
          <span key={t} className="text-[11px] px-2 py-0.5 rounded-full bg-indigo-600 text-white">{t}</span>
        ))}
        {suggestion.ocr_pages.length > 0 && (
          <span className="text-[11px] px-2 py-0.5 rounded-full bg-blue-600 text-white">
            OCR · pages [{suggestion.ocr_pages.join(', ')}]
          </span>
        )}
      </div>
      <ul className="text-xs text-muted-foreground space-y-0.5">
        {suggestion.rationale.map((r, i) => (
          <li key={i}>• {r}</li>
        ))}
      </ul>
    </div>
  )
}
