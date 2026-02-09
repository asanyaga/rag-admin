/**
 * Dual-pane document selector for index creation
 */
import { useState, useMemo } from 'react'
import { DocumentListItem } from '@/types/document'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  ChevronRight,
  ChevronLeft,
  ChevronsRight,
  Search,
  FileText,
  X,
} from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'

interface DocumentSelectorProps {
  documents: DocumentListItem[]
  selectedIds: string[]
  onChange: (selectedIds: string[]) => void
}

export function DocumentSelector({
  documents,
  selectedIds,
  onChange,
}: DocumentSelectorProps) {
  const [searchQuery, setSearchQuery] = useState('')

  // Filter available documents (not selected and matching search)
  const availableDocuments = useMemo(() => {
    return documents.filter((doc) => {
      const matchesSearch =
        !searchQuery ||
        doc.title.toLowerCase().includes(searchQuery.toLowerCase())
      const notSelected = !selectedIds.includes(doc.id)
      const isReady = doc.status === 'ready'
      return matchesSearch && notSelected && isReady
    })
  }, [documents, selectedIds, searchQuery])

  // Get selected documents in order
  const selectedDocuments = useMemo(() => {
    return selectedIds
      .map((id) => documents.find((d) => d.id === id))
      .filter((d): d is DocumentListItem => d !== undefined)
  }, [documents, selectedIds])

  const handleSelectDocument = (docId: string) => {
    onChange([...selectedIds, docId])
  }

  const handleDeselectDocument = (docId: string) => {
    onChange(selectedIds.filter((id) => id !== docId))
  }

  const handleSelectAll = () => {
    const availableIds = availableDocuments.map((d) => d.id)
    onChange([...selectedIds, ...availableIds])
  }

  const handleDeselectAll = () => {
    onChange([])
  }

  return (
    <div className="grid grid-cols-[1fr_auto_1fr] gap-2 min-h-[300px]">
      {/* Available Documents (Left Pane) */}
      <div className="border rounded-lg flex flex-col">
        <div className="p-2 border-b bg-muted/50">
          <div className="relative">
            <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search documents..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-8 h-9"
            />
          </div>
        </div>
        <div className="px-2 py-1.5 text-xs text-muted-foreground border-b">
          {availableDocuments.length} available
        </div>
        <ScrollArea className="flex-1">
          <div className="p-2 space-y-1">
            {availableDocuments.length === 0 ? (
              <div className="text-center py-8 text-sm text-muted-foreground">
                {searchQuery
                  ? 'No matching documents'
                  : 'All documents selected'}
              </div>
            ) : (
              availableDocuments.map((doc) => (
                <button
                  key={doc.id}
                  onClick={() => handleSelectDocument(doc.id)}
                  className="w-full text-left p-2 rounded hover:bg-accent transition-colors flex items-start gap-2 group"
                >
                  <FileText className="h-4 w-4 mt-0.5 text-muted-foreground" />
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-sm truncate">
                      {doc.title}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {formatDistanceToNow(new Date(doc.createdAt), {
                        addSuffix: true,
                      })}
                    </div>
                  </div>
                  <ChevronRight className="h-4 w-4 opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground" />
                </button>
              ))
            )}
          </div>
        </ScrollArea>
      </div>

      {/* Controls (Center) */}
      <div className="flex flex-col items-center justify-center gap-2 px-1">
        <Button
          variant="outline"
          size="icon"
          onClick={handleSelectAll}
          disabled={availableDocuments.length === 0}
          title="Select all"
        >
          <ChevronsRight className="h-4 w-4" />
        </Button>
        <Button
          variant="outline"
          size="icon"
          onClick={handleDeselectAll}
          disabled={selectedIds.length === 0}
          title="Deselect all"
        >
          <ChevronLeft className="h-4 w-4" />
        </Button>
      </div>

      {/* Selected Documents (Right Pane) */}
      <div className="border rounded-lg flex flex-col">
        <div className="p-2 border-b bg-muted/50">
          <div className="text-sm font-medium">Selected for Index</div>
        </div>
        <div className="px-2 py-1.5 text-xs text-muted-foreground border-b">
          {selectedIds.length} selected
        </div>
        <ScrollArea className="flex-1">
          <div className="p-2 space-y-1">
            {selectedDocuments.length === 0 ? (
              <div className="text-center py-8 text-sm text-muted-foreground">
                No documents selected
              </div>
            ) : (
              selectedDocuments.map((doc) => (
                <div
                  key={doc.id}
                  className="w-full p-2 rounded bg-accent/50 flex items-start gap-2 group"
                >
                  <FileText className="h-4 w-4 mt-0.5 text-muted-foreground" />
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-sm truncate">
                      {doc.title}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {formatDistanceToNow(new Date(doc.createdAt), {
                        addSuffix: true,
                      })}
                    </div>
                  </div>
                  <button
                    onClick={() => handleDeselectDocument(doc.id)}
                    className="p-1 hover:bg-background rounded opacity-0 group-hover:opacity-100 transition-opacity"
                    title="Remove"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </div>
              ))
            )}
          </div>
        </ScrollArea>
      </div>
    </div>
  )
}
