import { useState } from 'react'
import type { DocumentListItem } from '@/types/document'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'
import { Search, Upload, FileText, Loader2, AlertCircle } from 'lucide-react'

interface DocumentSelectorProps {
  documents: DocumentListItem[]
  isLoading: boolean
  selectedDocumentId: string | null
  onSelect: (documentId: string) => void
  onUploadClick?: () => void
}

export function DocumentSelector({
  documents,
  isLoading,
  selectedDocumentId,
  onSelect,
  onUploadClick,
}: DocumentSelectorProps) {
  const [search, setSearch] = useState('')

  const filtered = documents.filter((doc) =>
    doc.title.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="flex flex-col h-full">
      {/* Search */}
      <div className="p-3 border-b">
        <div className="relative">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search documents..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9 h-9"
          />
        </div>
      </div>

      {/* Document list */}
      <ScrollArea className="flex-1">
        <div className="p-2">
          {isLoading ? (
            <div className="flex items-center justify-center py-8 text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin mr-2" />
              <span className="text-sm">Loading...</span>
            </div>
          ) : filtered.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-8">
              {search ? 'No documents match your search' : 'No documents yet'}
            </p>
          ) : (
            filtered.map((doc) => {
              const isProcessing = doc.status === 'processing'
              const isFailed = doc.status === 'failed'
              const isSelected = doc.id === selectedDocumentId

              return (
                <button
                  key={doc.id}
                  onClick={() => {
                    if (!isProcessing) onSelect(doc.id)
                  }}
                  disabled={isProcessing}
                  className={cn(
                    'w-full text-left rounded-md px-3 py-2.5 mb-1 transition-colors',
                    'hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                    isSelected && 'bg-muted',
                    isProcessing && 'opacity-50 cursor-not-allowed'
                  )}
                >
                  <div className="flex items-start gap-2.5">
                    <FileText className={cn(
                      'h-4 w-4 mt-0.5 shrink-0',
                      isSelected ? 'text-primary' : 'text-muted-foreground'
                    )} />
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium truncate">{doc.title}</p>
                      <div className="flex items-center gap-1.5 mt-0.5">
                        {isProcessing ? (
                          <Badge variant="secondary" className="text-[10px] px-1.5 py-0 h-4 gap-1">
                            <Loader2 className="h-2.5 w-2.5 animate-spin" />
                            processing
                          </Badge>
                        ) : isFailed ? (
                          <Badge variant="destructive" className="text-[10px] px-1.5 py-0 h-4 gap-1">
                            <AlertCircle className="h-2.5 w-2.5" />
                            failed
                          </Badge>
                        ) : (
                          <Badge variant="outline" className="text-[10px] px-1.5 py-0 h-4">
                            ready
                          </Badge>
                        )}
                      </div>
                    </div>
                  </div>
                </button>
              )
            })
          )}
        </div>
      </ScrollArea>

      {/* Upload button */}
      {onUploadClick && (
        <div className="p-3 border-t">
          <Button
            variant="outline"
            className="w-full"
            size="sm"
            onClick={onUploadClick}
          >
            <Upload className="h-4 w-4 mr-2" />
            Upload Document
          </Button>
        </div>
      )}
    </div>
  )
}
