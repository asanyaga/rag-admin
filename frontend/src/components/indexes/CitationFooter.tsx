import { ChunkCitation } from '@/types/index'

interface CitationFooterProps {
  citation: ChunkCitation
}

function pageLabel(citation: ChunkCitation): string | null {
  if (citation.sourceType === 'block' && citation.pageIndices && citation.pageIndices.length > 0) {
    // page_index is 0-indexed in CDM; display as 1-indexed page number.
    const pages = citation.pageIndices.map((p) => p + 1)
    return pages.length === 1 ? `Page ${pages[0]}` : `Pages ${pages.join(', ')}`
  }
  if (citation.pageNumbers.length > 0) {
    return citation.pageNumbers.length === 1
      ? `Page ${citation.pageNumbers[0]}`
      : `Pages ${citation.pageNumbers.join(', ')}`
  }
  if (citation.startChar != null && citation.endChar != null) {
    return `Chars ${citation.startChar}–${citation.endChar}`
  }
  return null
}

function roleLabel(citation: ChunkCitation): string | null {
  if (!citation.blockRoles || citation.blockRoles.length === 0) return null
  // Show first non-heading role for compact display; fall back to first.
  const primary = citation.blockRoles.find((r) => r !== 'heading' && r !== 'title')
    ?? citation.blockRoles[0]
  return primary.charAt(0).toUpperCase() + primary.slice(1)
}

export function CitationFooter({ citation }: CitationFooterProps) {
  const page = pageLabel(citation)
  const role = roleLabel(citation)
  const lowConfidence = citation.confidence != null && citation.confidence < 0.7

  return (
    <div className="flex flex-wrap items-center gap-2 text-xs text-zinc-500 mt-2">
      {citation.sourceType === 'full_markdown' && citation.headingPath && citation.headingPath.length > 0 && (
        <span className="flex items-center gap-1">
          {citation.headingPath.map((h, i) => (
            <span key={i} className="flex items-center gap-1">
              {i > 0 && <span className="text-zinc-300">›</span>}
              <span>{h}</span>
            </span>
          ))}
        </span>
      )}
      {page && <span>{page}</span>}
      {role && <span>· {role}</span>}
      {lowConfidence && (
        <span className="rounded-sm bg-amber-50 text-amber-700 px-1.5 py-0.5">
          Low confidence
        </span>
      )}
      <span className="ml-auto text-zinc-400">Index v{citation.indexVersion}</span>
    </div>
  )
}
