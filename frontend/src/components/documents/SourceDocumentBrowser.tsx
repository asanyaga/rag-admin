import { useState } from 'react'
import { useSourceDocuments } from '@/hooks/useSourceDocuments'
import { ParseMethodSelector } from '@/components/documents/ParseMethodSelector'
import type { ParseConfig } from '@/types/parsing'
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Badge } from '@/components/ui/badge'
import { Search, FileText, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'

function formatBytes(bytes: number | null): string {
  if (bytes === null) return '—'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

interface SourceDocumentBrowserProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  existingSourceDocumentIds: Set<string>
  onAdd: (sourceDocumentId: string, parserType: string, parseConfig?: ParseConfig) => Promise<void>
}

export function SourceDocumentBrowser({
  open,
  onOpenChange,
  existingSourceDocumentIds,
  onAdd,
}: SourceDocumentBrowserProps) {
  const { sourceDocuments, isLoading } = useSourceDocuments()
  const [search, setSearch] = useState('')
  const [selectedSourceId, setSelectedSourceId] = useState<string | null>(null)
  const [parserType, setParserType] = useState('simple')
  const [parseConfig, setParseConfig] = useState<ParseConfig>({})
  const [isSubmitting, setIsSubmitting] = useState(false)

  const available = sourceDocuments.filter(
    (sd) =>
      !existingSourceDocumentIds.has(sd.id) &&
      (sd.filename?.toLowerCase().includes(search.toLowerCase()) ?? true),
  )

  const handleAdd = async () => {
    if (!selectedSourceId) return
    setIsSubmitting(true)
    try {
      await onAdd(
        selectedSourceId,
        parserType,
        Object.keys(parseConfig).length ? parseConfig : undefined,
      )
      onOpenChange(false)
      setSelectedSourceId(null)
      setSearch('')
    } catch (err) {
      console.error('Failed to add from source', err)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full sm:max-w-lg flex flex-col p-0">
        <SheetHeader className="px-6 py-4 border-b">
          <SheetTitle>Add from Source</SheetTitle>
        </SheetHeader>

        <div className="px-4 py-3 border-b">
          <div className="relative">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search source documents..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9 h-9"
            />
          </div>
        </div>

        <ScrollArea className="flex-1">
          <div className="p-3 space-y-1">
            {isLoading ? (
              <div className="flex items-center justify-center py-8 text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin mr-2" />
                <span className="text-sm">Loading...</span>
              </div>
            ) : available.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-8">
                {search
                  ? 'No source documents match your search'
                  : 'All source documents are already in this project'}
              </p>
            ) : (
              available.map((sd) => (
                <button
                  key={sd.id}
                  onClick={() => setSelectedSourceId(sd.id)}
                  className={cn(
                    'w-full text-left rounded-md px-3 py-2.5 transition-colors',
                    'hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                    selectedSourceId === sd.id && 'bg-muted ring-2 ring-ring',
                  )}
                >
                  <div className="flex items-center gap-2.5">
                    <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
                    <span className="text-sm truncate flex-1">{sd.filename ?? 'Untitled'}</span>
                    <Badge variant="outline" className="text-[10px] px-1.5 shrink-0">
                      {formatBytes(sd.byteSize)}
                    </Badge>
                  </div>
                </button>
              ))
            )}
          </div>
        </ScrollArea>

        <div className="px-4 py-4 border-t space-y-3">
          <ParseMethodSelector
            parserType={parserType}
            config={parseConfig}
            onParserTypeChange={setParserType}
            onConfigChange={setParseConfig}
          />
        </div>

        <div className="px-4 py-4 border-t flex justify-end gap-2">
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isSubmitting}>
            Cancel
          </Button>
          <Button onClick={handleAdd} disabled={!selectedSourceId || isSubmitting}>
            {isSubmitting ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Adding...
              </>
            ) : (
              'Add & Parse'
            )}
          </Button>
        </div>
      </SheetContent>
    </Sheet>
  )
}
