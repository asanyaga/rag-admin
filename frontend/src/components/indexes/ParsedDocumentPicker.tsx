import { useState, useEffect, useCallback } from 'react'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Label } from '@/components/ui/label'
import { listParsedDocuments } from '@/lib/parsed-documents'
import type { ParsedDocumentListItem } from '@/lib/parsed-documents'
import type { SourceRepresentation } from '@/types/index'

interface ParsedDocumentPickerProps {
  projectId: string
  parser: string
  parseConfigHash: string
  representation: SourceRepresentation
  selectedIds: string[]
  onChange: (ids: string[]) => void
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function ParsedDocumentPicker({
  projectId,
  parser,
  parseConfigHash,
  representation,
  selectedIds,
  onChange,
}: ParsedDocumentPickerProps) {
  const [docs, setDocs] = useState<ParsedDocumentListItem[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [latestPerSource, setLatestPerSource] = useState(true)
  const [search, setSearch] = useState('')

  const fetchDocs = useCallback(async () => {
    setIsLoading(true)
    try {
      const result = await listParsedDocuments(projectId, {
        parser,
        parseConfigHash,
        representation,
        latestPerSource,
      })
      setDocs(result)
    } finally {
      setIsLoading(false)
    }
  }, [projectId, parser, parseConfigHash, representation, latestPerSource])

  useEffect(() => {
    fetchDocs()
  }, [fetchDocs])

  const filtered = docs.filter(
    (d) =>
      !search.trim() ||
      (d.sourceFilename ?? '').toLowerCase().includes(search.trim().toLowerCase()),
  )

  function toggleId(id: string) {
    if (selectedIds.includes(id)) {
      onChange(selectedIds.filter((x) => x !== id))
    } else {
      onChange([...selectedIds, id])
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <Checkbox
            id="latest-per-source"
            checked={latestPerSource}
            onCheckedChange={(v) => setLatestPerSource(!!v)}
            aria-label="Latest per source"
          />
          <Label htmlFor="latest-per-source" className="cursor-pointer">
            Latest per source document
          </Label>
        </div>
        <Input
          className="w-56"
          placeholder="Search by filename..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {isLoading ? (
        <div className="space-y-2">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-14 w-full rounded-lg" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <p className="text-center py-8 text-muted-foreground">
          No parsed documents found.
        </p>
      ) : (
        <div className="space-y-2">
          {filtered.map((doc) => (
            <label
              key={doc.id}
              className="flex items-center gap-3 rounded-lg border p-3 cursor-pointer hover:bg-muted/30 has-[:checked]:border-primary has-[:checked]:bg-primary/5"
            >
              <Checkbox
                checked={selectedIds.includes(doc.id)}
                onCheckedChange={() => toggleId(doc.id)}
                aria-label={doc.sourceFilename ?? 'Unknown file'}
              />
              <span className="flex-1 min-w-0">
                <span className="font-medium truncate block">
                  {doc.sourceFilename ?? 'Unknown file'}
                </span>
                <span className="text-xs text-muted-foreground">
                  run {doc.parseRunId.slice(0, 5)}… · {formatDate(doc.parsedAt)}
                </span>
              </span>
              {doc.hasFullMarkdown && (
                <Badge variant="secondary" className="text-xs shrink-0">
                  markdown ✓
                </Badge>
              )}
              <Badge variant="outline" className="text-xs shrink-0 font-mono">
                {doc.blockCount} blocks
              </Badge>
            </label>
          ))}
        </div>
      )}
    </div>
  )
}
