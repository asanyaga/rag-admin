import { useState } from 'react'
import type { DocumentListItem } from '@/types/document'
import type { Folder } from '@/types/folder'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { DocumentStatusBadge } from '@/components/documents/DocumentStatusBadge'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'
import { Search, Upload, FileText } from 'lucide-react'

interface DocumentPickerPanelProps {
  documents: DocumentListItem[]
  folders: Folder[]
  isLoading: boolean
  selectedDocumentId: string | null
  onSelect: (documentId: string) => void
  onUploadClick: () => void
}

export function DocumentPickerPanel({
  documents,
  folders,
  isLoading,
  selectedDocumentId,
  onSelect,
  onUploadClick,
}: DocumentPickerPanelProps) {
  const [search, setSearch] = useState('')
  const [folderId, setFolderId] = useState<string | null>(null)

  const filtered = documents.filter((doc) => {
    const matchesFolder = folderId === null || doc.folderId === folderId
    const matchesSearch = doc.title.toLowerCase().includes(search.toLowerCase())
    return matchesFolder && matchesSearch
  })

  return (
    <div className="flex flex-col h-full">
      {folders.length > 0 && (
        <div className="p-3 border-b">
          <Select
            value={folderId ?? '__all__'}
            onValueChange={(v) => setFolderId(v === '__all__' ? null : v)}
          >
            <SelectTrigger className="h-8 text-sm">
              <SelectValue placeholder="All folders" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__all__">All folders</SelectItem>
              {folders.map((f) => (
                <SelectItem key={f.id} value={f.id}>
                  {f.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}
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
      <ScrollArea className="flex-1">
        <div className="p-2">
          {isLoading ? (
            <div className="space-y-2 p-2">
              {[0, 1, 2].map((i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : filtered.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-8">
              {search ? 'No documents match your search' : 'No documents yet'}
            </p>
          ) : (
            filtered.map((doc) => {
              const isProcessing = doc.status === 'processing'
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
                    selectedDocumentId === doc.id && 'bg-muted',
                    isProcessing && 'opacity-50 cursor-not-allowed',
                  )}
                >
                  <div className="flex items-center gap-2">
                    <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
                    <span className="text-sm truncate flex-1">{doc.title}</span>
                    <DocumentStatusBadge status={doc.status} />
                  </div>
                </button>
              )
            })
          )}
        </div>
      </ScrollArea>
      <div className="p-3 border-t">
        <Button variant="outline" className="w-full" size="sm" onClick={onUploadClick}>
          <Upload className="h-4 w-4 mr-2" />
          Upload Document
        </Button>
      </div>
    </div>
  )
}
